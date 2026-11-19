"""
Pengujian akurasi pengenalan jenis sampah dari foto (ecodrop/foto.py).

Data uji (tidak disertakan di repositori karena ukurannya; susun di satu folder, mis. data_uji/):
  trashnet/<kelas>/*.jpg        TrashNet (Thung & Yang, 2016), github.com/garythung/trashnet,
                                berkas data/dataset-resized.zip: 2.527 foto, 6 kelas bahan.
  trashivl/<kategori>/<sub>/*   TrashIVL, github.com/0815LHL/TrashIVL: 50 foto per subkelas.
  ewaste/<kelas>/*              E-Waste Vision Dataset (Islam dkk., 2023),
                                github.com/NifulIslam/EWasteNet-A-Two-Stream-DeiT-Approach-for-E-Waste-Classification:
                                60 foto per kelas.
Daftar foto yang dipakai ada di pengujian/data_uji_foto/daftar_semua.txt. Bagian pengembangan (30%,
daftar_dev.txt) dipakai untuk menyusun deskripsi teks (model/prompt_jenis.csv); angka di laporan
diambil dari bagian uji (70% sisanya) yang tidak dilihat selama penyusunan.

Jalankan dari folder utama:  python pengujian/uji_foto.py data_uji
Hasil tersimpan di pengujian/hasil (hasil_uji_foto.csv, ringkasan_uji_foto.csv, ringkasan_uji_foto.txt).
"""

import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd
from PIL import Image

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))
from ecodrop.foto import PengenalFoto  # noqa: E402
from ecodrop.rekomendasi import AMBANG_CONFIDENCE, MesinRekomendasi  # noqa: E402

OUT = AKAR / "pengujian" / "hasil"
DAFTAR = AKAR / "pengujian" / "data_uji_foto"

R = lambda awal, a, b: [f"{awal}{i:02d}" for i in range(a, b + 1)]  # noqa: E731
KERTAS, PLASTIK, LOGAM, KACA, RESIDU = R("AN", 1, 4) + ["AN18"], R("AN", 5, 11), R("AN", 12, 15), \
    ["AN16", "AN17"], R("RS", 1, 9)

# label dataset -> (kode jenis EcoDrop yang dianggap benar, tingkat penilaian)
# TrashNet hanya berlabel bahan, jadi dinilai pada tingkat bahan; dua dataset lain berlabel benda.
KUNCI = {
    "trashnet/cardboard": (KERTAS, "bahan"), "trashnet/paper": (KERTAS, "bahan"),
    "trashnet/glass": (KACA, "bahan"), "trashnet/metal": (LOGAM, "bahan"),
    "trashnet/plastic": (PLASTIK, "bahan"), "trashnet/trash": (RESIDU, "bahan"),
    "trashivl/Clothes/pants": (["TK01"], "jenis"), "trashivl/Clothes/skirt": (["TK01"], "jenis"),
    "trashivl/Clothes/upper garment": (["TK01"], "jenis"), "trashivl/Glass/glass bottle": (["AN16"], "jenis"),
    "trashivl/Metal/can": (["AN12", "AN13"], "jenis"), "trashivl/Paper/cardboard": (["AN01", "AN04"], "jenis"),
    "trashivl/Paper/carton": (["AN18", "AN04", "AN01"], "jenis"),
    "trashivl/Paper/newspaper": (["AN03"], "jenis"), "trashivl/Plastic/plastic bag": (["AN10"], "jenis"),
    "trashivl/Plastic/plastic basin": (["AN09"], "jenis"),
    "trashivl/Plastic/plastic bottle": (["AN05", "AN08"], "jenis"),
    "ewaste/Mobile": (["EK01"], "jenis"), "ewaste/TV": (["EB01"], "jenis"), "ewaste/laptop": (["EB02"], "jenis"),
    "ewaste/Keyboards": (["EK07"], "jenis"), "ewaste/Mouses": (["EK07"], "jenis"),
    "ewaste/camera": (["EK07"], "jenis"), "ewaste/smartwatch": (["EK07", "EK01"], "jenis"),
    "ewaste/microwave": (["EB04"], "jenis"),
}
NAMA_DATASET = {"trashnet": "TrashNet", "trashivl": "TrashIVL", "ewaste": "E-Waste Vision"}


def tujuan(mesin, kode):
    jl = mesin.jenis[kode]["jenis_lokasi"]
    if not jl:
        return "tanpa lokasi"
    return "e-waste/B3" if "collection_point_b3" in jl else ("bank sampah" if jl == ["bank_sampah"] else "TPS")


def main(folder_data):
    folder_data = Path(folder_data)
    mesin = MesinRekomendasi()
    pengenal = PengenalFoto()
    semua = (DAFTAR / "daftar_semua.txt").read_text(encoding="utf-8").split("\n")
    dev = set((DAFTAR / "daftar_dev.txt").read_text(encoding="utf-8").split("\n"))

    baris, waktu = [], []
    for rel in filter(None, semua):
        label = rel.rsplit("/", 1)[0]
        benar, tingkat = KUNCI[label]
        t0 = time.perf_counter()
        saran = pengenal.kenali(Image.open(folder_data / rel), k=3)
        waktu.append((time.perf_counter() - t0) * 1000)
        kode = [s["kode"] for s in saran]
        tujuan_benar = tujuan(mesin, benar[0])
        baris.append({
            "berkas": rel, "bagian": "pengembangan" if rel in dev else "uji",
            "dataset": NAMA_DATASET[rel.split("/")[0]], "label_dataset": label.split("/", 1)[1],
            "tingkat": tingkat, "kode_benar": ";".join(benar),
            "saran_1": kode[0], "saran_2": kode[1], "saran_3": kode[2],
            "peluang_1": saran[0]["peluang"],
            "top1_benar": kode[0] in benar, "top3_benar": any(k in benar for k in kode),
            "tujuan_benar": tujuan_benar, "tujuan_saran_1": tujuan(mesin, kode[0]),
            "tujuan_top1_benar": tujuan(mesin, kode[0]) == tujuan_benar,
            "di_atas_ambang": saran[0]["peluang"] >= AMBANG_CONFIDENCE,
        })
    df = pd.DataFrame(baris)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "hasil_uji_foto.csv", index=False, encoding="utf-8-sig")

    ringkas = []
    for bagian in ["uji", "pengembangan"]:
        for ds, d in df[df.bagian == bagian].groupby("dataset", sort=False):
            atas = d[d.di_atas_ambang]
            ringkas.append({
                "bagian": bagian, "dataset": ds, "tingkat": d.tingkat.iloc[0], "jumlah_foto": len(d),
                "akurasi_top1": d.top1_benar.mean(), "akurasi_top3": d.top3_benar.mean(),
                "akurasi_tujuan": d.tujuan_top1_benar.mean(),
                "porsi_di_atas_ambang": len(atas) / len(d),
                "akurasi_top1_di_atas_ambang": atas.top1_benar.mean() if len(atas) else float("nan"),
            })
    r = pd.DataFrame(ringkas)
    r.to_csv(OUT / "ringkasan_uji_foto.csv", index=False, encoding="utf-8-sig")

    uji = df[df.bagian == "uji"]
    teks = [f"Pengujian pengenalan foto EcoDrop ({pengenal.cfg['model']})",
            f"Ambang confidence {AMBANG_CONFIDENCE}. Angka utama dari bagian uji ({len(uji)} foto).", ""]
    for _, x in r[r.bagian == "uji"].iterrows():
        teks.append(f"{x.dataset} (tingkat {x.tingkat}, n={x.jumlah_foto}): top-1 {x.akurasi_top1:.1%}, "
                    f"top-3 {x.akurasi_top3:.1%}, tujuan benar {x.akurasi_tujuan:.1%}, "
                    f"di atas ambang {x.porsi_di_atas_ambang:.1%} (top-1 {x.akurasi_top1_di_atas_ambang:.1%})")
    teks.append(f"Gabungan uji: top-1 {uji.top1_benar.mean():.1%}, top-3 {uji.top3_benar.mean():.1%}, "
                f"tujuan benar {uji.tujuan_top1_benar.mean():.1%}")
    teks += ["", "Akurasi per label (bagian uji):"]
    for lab, d in uji.groupby(["dataset", "label_dataset"], sort=False):
        salah = Counter(d[~d.top1_benar].saran_1).most_common(3)
        teks.append(f"  {lab[0]} / {lab[1]}: n={len(d)}, top-1 {d.top1_benar.mean():.0%}, "
                    f"top-3 {d.top3_benar.mean():.0%}; salah terbanyak: "
                    + (", ".join(f"{k} {mesin.jenis[k]['nama_indonesia']} ({n})" for k, n in salah) or "-"))
    teks += ["", "Matriks tujuan (bagian uji, baris = tujuan benar, kolom = tujuan saran pertama):",
             pd.crosstab(uji.tujuan_benar, uji.tujuan_saran_1).to_string(), "",
             f"Waktu per foto (praproses + inferensi, CPU, n={len(waktu)}): rata-rata {statistics.mean(waktu):.1f} ms, "
             f"median {statistics.median(waktu):.1f} ms, p95 {sorted(waktu)[int(0.95 * len(waktu))]:.1f} ms"]
    (OUT / "ringkasan_uji_foto.txt").write_text("\n".join(teks), encoding="utf-8")
    print("\n".join(teks))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data_uji")
