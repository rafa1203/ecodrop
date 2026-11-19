"""
Menyiapkan model pengenalan foto EcoDrop (dijalankan sekali, bukan oleh aplikasi).

  1. Mengunduh bobot OpenCLIP dari rilis GitHub mlfoundations/open_clip.
  2. Menghitung vektor teks: tiap deskripsi di model/prompt_jenis.csv dipasangkan dengan empat
     templat kalimat, diubah oleh encoder teks CLIP, lalu dirata-ratakan per deskripsi
     (model/teks.npy, satu baris per deskripsi, berurutan per jenis). Skor sebuah jenis adalah
     kemiripan tertinggi di antara deskripsinya.
  3. Mengekspor encoder gambar ke ONNX, lalu mengkuantisasi bobot MatMul ke int8 per kanal agar
     berkasnya sekitar empat kali lebih kecil dan inferensi di CPU lebih cepat. Rentang bobot
     dipersempit (reduce_range) agar hasilnya sama di CPU dengan atau tanpa instruksi VNNI.
  4. Menulis model/konfigurasi.json (ukuran input, normalisasi, urutan kode, skala logit, URL dan
     SHA-256 berkas ONNX).

Butuh: torch, open_clip_torch, onnx, onnxruntime, pandas.
Jalankan dari folder utama:  python tools/siapkan_model.py
"""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import open_clip
from onnxruntime.quantization import QuantType, quantize_dynamic

AKAR = Path(__file__).resolve().parent.parent
TEMPLAT = ["a photo of {}.", "a close-up photo of {}.", "a photo of {} thrown away as trash.",
           "a low quality photo of {}."]
URL_BOBOT = "https://github.com/mlfoundations/open_clip/releases/download/v0.2-weights/"

ap = argparse.ArgumentParser()
ap.add_argument("--arch", default="ViT-B-32-quickgelu")
ap.add_argument("--bobot", default="vit_b_32-quickgelu-laion400m_e32-46683a32.pt")
ap.add_argument("--keluar", default=str(AKAR / "model"))
ap.add_argument("--repo", default="rafa1203/ecodrop")
ap.add_argument("--rilis", default="model-v1")
a = ap.parse_args()
keluar = Path(a.keluar)
keluar.mkdir(parents=True, exist_ok=True)

path_bobot = keluar / a.bobot
if not path_bobot.exists():
    print("Mengunduh bobot", a.bobot)
    urllib.request.urlretrieve(URL_BOBOT + a.bobot, path_bobot)

torch.manual_seed(0)
model, _, pre = open_clip.create_model_and_transforms(a.arch, pretrained=str(path_bobot))
model.eval()
ukuran = model.visual.image_size
ukuran = ukuran[0] if isinstance(ukuran, (tuple, list)) else ukuran

# 1) vektor teks per jenis
tok = open_clip.get_tokenizer(a.arch)
jenis = pd.read_csv(AKAR / "data" / "jenis_sampah.csv")
prompt = pd.read_csv(keluar / "prompt_jenis.csv").set_index("kode")
assert set(jenis.kode) == set(prompt.index), "Kode di prompt_jenis.csv harus sama dengan jenis_sampah.csv"
vektor, awal = [], []
with torch.no_grad():
    for k in jenis.kode:
        awal.append(len(vektor))
        for d in prompt.loc[k, "prompt_en"].split("|"):
            f = model.encode_text(tok([t.format(d) for t in TEMPLAT]))
            f = (f / f.norm(dim=-1, keepdim=True)).mean(0)
            vektor.append((f / f.norm()).numpy())
np.save(keluar / "teks.npy", np.array(vektor, dtype=np.float32))


# 2) encoder gambar -> ONNX (keluaran sudah dinormalisasi panjangnya)
class EncoderGambar(torch.nn.Module):
    def __init__(self, visual):
        super().__init__()
        self.visual = visual

    def forward(self, x):
        f = self.visual(x)
        return f / f.norm(dim=-1, keepdim=True)


fp32 = keluar / "visual_fp32.onnx"
torch.onnx.export(EncoderGambar(model.visual), torch.randn(1, 3, ukuran, ukuran), str(fp32),
                  input_names=["pixel"], output_names=["emb"],
                  dynamic_axes={"pixel": {0: "n"}, "emb": {0: "n"}}, opset_version=17, dynamo=False)
onnx_akhir = keluar / "visual.onnx"
quantize_dynamic(str(fp32), str(onnx_akhir), weight_type=QuantType.QInt8, per_channel=True,
                 reduce_range=True, op_types_to_quantize=["MatMul"])
fp32.unlink()

sha = hashlib.sha256(onnx_akhir.read_bytes()).hexdigest()
normalisasi = pre.transforms[-1]
konfigurasi = {
    "model": f"OpenCLIP {a.arch}, bobot {a.bobot} (LAION-400M)",
    "ukuran": int(ukuran),
    "mean": [float(x) for x in normalisasi.mean],
    "std": [float(x) for x in normalisasi.std],
    "skala_logit": round(float(model.logit_scale.exp().item()), 4),
    "templat": TEMPLAT,
    "kode": list(jenis.kode),
    "awal_deskripsi": awal,
    "berkas_onnx": onnx_akhir.name,
    "url_onnx": f"https://github.com/{a.repo}/releases/download/{a.rilis}/{onnx_akhir.name}",
    "sha256_onnx": sha,
}
(keluar / "konfigurasi.json").write_text(json.dumps(konfigurasi, indent=1, ensure_ascii=False), encoding="utf-8")
print("Selesai:", onnx_akhir, f"{onnx_akhir.stat().st_size / 1e6:.1f} MB", sha)
