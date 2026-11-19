"""
Pengenalan jenis sampah dari foto secara zero-shot dengan CLIP.

Cara kerja:
  1. Setiap jenis dari 58 jenis sampah EcoDrop diberi beberapa deskripsi teks berbahasa Inggris
     sesuai contoh bendanya (model/prompt_jenis.csv). Tiap deskripsi diubah menjadi vektor oleh
     encoder teks CLIP (model/teks.npy). Langkah ini dikerjakan sekali saat model disiapkan
     (tools/siapkan_model.py), jadi aplikasi tidak memerlukan encoder teks.
  2. Foto pengguna diubah menjadi vektor oleh encoder gambar CLIP (berkas ONNX).
  3. Skor tiap jenis adalah kemiripan kosinus tertinggi antara foto dan deskripsi-deskripsi jenis
     itu. Skor dikalikan skala logit model lalu diubah menjadi peluang dengan softmax. Tiga jenis
     dengan peluang tertinggi ditampilkan sebagai saran, dan pengguna memilih atau mengonfirmasi
     jenis yang benar.

Model: OpenCLIP (Ilharco dkk., 2021) yang dilatih pada LAION-400M (Schuhmann dkk., 2021).
Encoder gambar dijalankan dengan ONNX Runtime sehingga aplikasi tidak memerlukan PyTorch.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

FOLDER_MODEL = Path(__file__).resolve().parent.parent / "model"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def pastikan_berkas_onnx(folder_model=FOLDER_MODEL):
    """Unduh encoder gambar ONNX dari rilis GitHub bila belum ada, lalu cek SHA-256-nya."""
    folder_model = Path(folder_model)
    cfg = json.loads((folder_model / "konfigurasi.json").read_text(encoding="utf-8"))
    tujuan = folder_model / cfg["berkas_onnx"]
    if tujuan.exists() and _sha256(tujuan) == cfg["sha256_onnx"]:
        return tujuan
    fd, sementara = tempfile.mkstemp(dir=folder_model, suffix=".unduh")
    os.close(fd)
    try:
        urllib.request.urlretrieve(cfg["url_onnx"], sementara)
        if _sha256(sementara) != cfg["sha256_onnx"]:
            raise RuntimeError("Berkas model yang diunduh tidak cocok (SHA-256 berbeda).")
        os.replace(sementara, tujuan)
    finally:
        if os.path.exists(sementara):
            os.remove(sementara)
    return tujuan


class PengenalFoto:
    def __init__(self, folder_model=FOLDER_MODEL, threads=2):
        import onnxruntime as ort

        folder_model = Path(folder_model)
        self.cfg = json.loads((folder_model / "konfigurasi.json").read_text(encoding="utf-8"))
        self.kode = list(self.cfg["kode"])
        self.teks = np.load(folder_model / "teks.npy").astype(np.float32)
        self.awal = np.array(self.cfg["awal_deskripsi"], dtype=np.int64)  # baris pertama tiap jenis
        if len(self.awal) != len(self.kode) or self.awal[-1] >= len(self.teks):
            raise ValueError("Konfigurasi deskripsi tidak cocok dengan model/teks.npy.")
        self.mean = np.array(self.cfg["mean"], dtype=np.float32)[:, None, None]
        self.std = np.array(self.cfg["std"], dtype=np.float32)[:, None, None]

        opsi = ort.SessionOptions()
        opsi.intra_op_num_threads = threads
        self.sesi = ort.InferenceSession(str(pastikan_berkas_onnx(folder_model)), opsi,
                                         providers=["CPUExecutionProvider"])

    def praproses(self, gambar):
        """Sama dengan praproses CLIP: sisi terpendek diubah ke ukuran input (bikubik), potong tengah,
        lalu normalisasi per kanal."""
        n = self.cfg["ukuran"]
        g = ImageOps.exif_transpose(gambar).convert("RGB")  # foto ponsel sering diputar lewat EXIF
        w, h = g.size
        s = n / min(w, h)
        g = g.resize((max(n, round(w * s)), max(n, round(h * s))), Image.BICUBIC)
        w, h = g.size
        kiri, atas = int(round((w - n) / 2.0)), int(round((h - n) / 2.0))
        g = g.crop((kiri, atas, kiri + n, atas + n))
        x = np.asarray(g, dtype=np.float32).transpose(2, 0, 1) / 255.0
        return ((x - self.mean) / self.std)[None]

    def peluang(self, gambar):
        """Peluang tiap jenis (array sepanjang jumlah kode, berjumlah 1)."""
        emb = self.sesi.run(None, {"pixel": self.praproses(gambar)})[0][0]
        skor = np.maximum.reduceat(self.teks @ emb, self.awal)  # kemiripan tertinggi per jenis
        logit = self.cfg["skala_logit"] * skor
        p = np.exp(logit - logit.max())
        return p / p.sum()

    def kenali(self, gambar, k=3):
        """k jenis dengan peluang tertinggi: [{"kode": "AN05", "peluang": 0.83}, ...]"""
        p = self.peluang(gambar)
        urut = np.argsort(-p)[:k]
        return [{"kode": self.kode[i], "peluang": round(float(p[i]), 4)} for i in urut]
