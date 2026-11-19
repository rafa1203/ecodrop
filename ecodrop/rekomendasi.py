"""
Logika rekomendasi lokasi penyetoran sampah EcoDrop.

Alur:
  1. Jenis sampah dinyatakan dengan salah satu dari dua cara:
     - kode jenis dari daftar 58 jenis sampah EcoDrop (data/jenis_sampah.csv), mis. "AN05" untuk botol
       plastik minuman. Kode ini dipakai fitur pengenalan foto (ecodrop/foto.py) dan pilihan manual;
     - label umum 12 kelas dataset Garbage Classification (Mohamed, 2021) di data/aturan_label.csv,
       agar modul tetap bisa dipakai model klasifikasi citra yang dilatih dengan kelas tersebut.
     Keduanya dipetakan ke jenis lokasi tujuan (bank sampah, dropbox e-waste, collection point B3, TPS).
  2. Bila confidence di bawah ambang dan pengguna belum mengonfirmasi, sistem meminta konfirmasi.
  3. Jarak dari lokasi pengguna ke semua lokasi yang sesuai dihitung dengan Haversine,
     lalu diurutkan dari yang terdekat.
"""

import csv
import re
from pathlib import Path

import numpy as np

from .haversine import haversine_km_vektor

FOLDER_DATA = Path(__file__).resolve().parent.parent / "data"
AMBANG_CONFIDENCE = 0.6
TOP_K_MAKS = 20
JENIS_LOKASI = ("bank_sampah", "dropbox_ewaste", "collection_point_b3", "tps")
NAMA_JENIS = {
    "bank_sampah": "Bank sampah",
    "dropbox_ewaste": "Dropbox e-waste",
    "collection_point_b3": "Collection point B3",
    "tps": "TPS",
}
TUJUAN_KALIMAT = {"bank_sampah": "bank sampah", "dropbox_ewaste": "dropbox e-waste",
                  "collection_point_b3": "collection point B3", "tps": "TPS"}
# kotak batas lima kota administrasi DKI Jakarta (tanpa Kepulauan Seribu), untuk memberi peringatan
BATAS_DKI = {"lat_min": -6.40, "lat_max": -6.05, "lon_min": 106.65, "lon_max": 107.00}


POLA_KODE = re.compile(r"^[A-Z]{2}\d{2}$|^B3\d{2}$")


def normalisasi_label(label):
    teks = str(label or "").strip()
    if POLA_KODE.match(teks.upper()):
        return teks.upper()  # kode jenis, mis. "an05" -> "AN05"
    return teks.lower().replace("_", "-").replace(" ", "-")


def _pesan_jenis(r, jenis_lokasi):
    saran = "" if str(r["pesan"]).strip() in ("", "-") else str(r["pesan"]).strip()
    if not jenis_lokasi:
        return saran
    tujuan = " atau ".join(TUJUAN_KALIMAT[j] for j in jenis_lokasi)
    kerja = "dibuang ke" if jenis_lokasi == ["tps"] else "disetor ke"
    return f"{r['nama']} {kerja} {tujuan} terdekat. {saran}".strip()


class MesinRekomendasi:
    def __init__(self, path_lokasi=None, path_aturan=None, path_jenis=None):
        path_lokasi = Path(path_lokasi or FOLDER_DATA / "lokasi_ecodrop.csv")
        path_aturan = Path(path_aturan or FOLDER_DATA / "aturan_label.csv")
        path_jenis = Path(path_jenis or FOLDER_DATA / "jenis_sampah.csv")

        with open(path_lokasi, encoding="utf-8-sig", newline="") as f:
            self.lokasi = list(csv.DictReader(f))
        self.lat = np.array([float(r["latitude"]) for r in self.lokasi])
        self.lon = np.array([float(r["longitude"]) for r in self.lokasi])
        jenis = np.array([r["jenis_lokasi"] for r in self.lokasi])
        self.indeks_jenis = {j: np.where(jenis == j)[0] for j in JENIS_LOKASI}

        with open(path_aturan, encoding="utf-8-sig", newline="") as f:
            self.aturan = {}
            for r in csv.DictReader(f):
                r["jenis_lokasi"] = [j for j in r["jenis_lokasi"].split(";") if j]
                self.aturan[normalisasi_label(r["label"])] = r

        # 58 jenis sampah EcoDrop, dikunci dengan kodenya
        with open(path_jenis, encoding="utf-8-sig", newline="") as f:
            self.jenis = {}
            for r in csv.DictReader(f):
                jl = [j for j in r["jenis_lokasi"].split(";") if j]
                tidak_dikenal = [j for j in jl if j not in JENIS_LOKASI]
                if tidak_dikenal:
                    raise ValueError(f"Jenis lokasi tidak dikenal di {r['kode']}: {tidak_dikenal}")
                self.jenis[r["kode"]] = {
                    "kode": r["kode"], "nama_indonesia": r["nama"], "contoh": r["contoh"],
                    "kelompok": r["kelompok"], "jenis_lokasi": jl, "pesan": _pesan_jenis(r, jl),
                    "perlu_dicek": r["perlu_dicek"] == "Ya",
                }

    # ------------------------------------------------------------------
    def daftar_label(self):
        """12 label umum (kelas Garbage Classification)."""
        return [
            {"label": k, "nama_indonesia": v["nama_indonesia"], "kelompok": v["kelompok"],
             "jenis_lokasi": v["jenis_lokasi"]}
            for k, v in self.aturan.items()
        ]

    def daftar_jenis(self):
        """58 jenis sampah EcoDrop beserta contoh dan jenis lokasi tujuannya."""
        return [{"kode": v["kode"], "nama_indonesia": v["nama_indonesia"], "contoh": v["contoh"],
                 "kelompok": v["kelompok"], "jenis_lokasi": v["jenis_lokasi"]} for v in self.jenis.values()]

    def aturan_untuk(self, label):
        """Aturan untuk kode jenis (mis. "AN05") atau label umum (mis. "plastic"). KeyError bila tidak dikenal."""
        kunci = normalisasi_label(label)
        if kunci in self.jenis:
            return kunci, self.jenis[kunci]
        if kunci in self.aturan:
            return kunci, self.aturan[kunci]
        raise KeyError(f"Label '{label}' tidak dikenal. Gunakan kode jenis sampah (lihat /ecodrop/jenis, "
                       f"mis. AN05) atau salah satu label umum: {', '.join(self.aturan)}")

    @staticmethod
    def _cek_koordinat(lat, lon):
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Koordinat tidak valid: latitude harus -90..90 dan longitude -180..180.")

    @staticmethod
    def _di_dki(lat, lon):
        b = BATAS_DKI
        return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]

    # ------------------------------------------------------------------
    def cari_terdekat(self, lat, lon, jenis_lokasi, top_k=5, radius_km=None):
        """Lokasi terdekat dari (lat, lon) untuk jenis lokasi tertentu, urut dari yang terdekat."""
        self._cek_koordinat(lat, lon)
        tidak_dikenal = [j for j in jenis_lokasi if j not in self.indeks_jenis]
        if tidak_dikenal:
            raise ValueError(f"Jenis lokasi tidak dikenal: {', '.join(tidak_dikenal)}")
        top_k = max(1, min(int(top_k), TOP_K_MAKS))

        idx = np.concatenate([self.indeks_jenis[j] for j in jenis_lokasi])
        jarak = haversine_km_vektor(lat, lon, self.lat[idx], self.lon[idx])
        if radius_km is not None:
            dalam = jarak <= radius_km
            idx, jarak = idx[dalam], jarak[dalam]
        if len(jarak) == 0:
            return []

        k = min(top_k, len(jarak))
        calon = np.argpartition(jarak, k - 1)[:k]
        urut = calon[np.argsort(jarak[calon], kind="stable")]

        hasil = []
        for n, i in enumerate(urut, start=1):
            r = self.lokasi[idx[i]]
            hasil.append({
                "urutan": n,
                "id": r["id"],
                "nama": r["nama"],
                "jenis_lokasi": r["jenis_lokasi"],
                "jenis_lokasi_nama": NAMA_JENIS[r["jenis_lokasi"]],
                "jarak_km": round(float(jarak[i]), 2),
                "jarak_m": int(round(float(jarak[i]) * 1000)),
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "alamat": r["alamat"],
                "kelurahan": r["kelurahan"],
                "kecamatan": r["kecamatan"],
                "kota": r["kota"],
                "keterangan": r["keterangan"],
                "jam_buka": r["jam_buka"],
                "akurasi": r["akurasi"],
                "url_rute": ("https://www.google.com/maps/dir/?api=1"
                             f"&origin={lat},{lon}&destination={r['latitude']},{r['longitude']}"),
            })
        return hasil

    # ------------------------------------------------------------------
    def rekomendasi(self, label, confidence, lat, lon, top_k=5, radius_km=None, dikonfirmasi=False):
        """Rekomendasi lokasi berdasarkan jenis sampah (kode jenis atau label umum), dari hasil
        pengenalan foto atau pilihan pengguna."""
        kunci, aturan = self.aturan_untuk(label)
        if not 0 <= confidence <= 1:
            raise ValueError("Confidence harus di antara 0 dan 1.")
        self._cek_koordinat(lat, lon)
        hasil = {
            "label": kunci,
            "nama_indonesia": aturan["nama_indonesia"],
            "kelompok": aturan["kelompok"],
            "confidence": round(float(confidence), 4),
            "jenis_lokasi": aturan["jenis_lokasi"],
            "status": "ok",
            "pesan": aturan["pesan"],
            "peringatan": None,
            "lokasi": [],
        }
        if not self._di_dki(lat, lon):
            hasil["peringatan"] = ("Lokasi Anda di luar cakupan EcoDrop. Data EcoDrop hanya mencakup lima kota "
                                   "administrasi DKI Jakarta (tanpa Kepulauan Seribu).")

        if confidence < AMBANG_CONFIDENCE and not dikonfirmasi:
            hasil["status"] = "perlu_konfirmasi"
            hasil["pesan"] = (f"Model kurang yakin ({confidence:.0%}). Pastikan jenis sampahnya adalah "
                              f"{aturan['nama_indonesia'].lower()} atau pilih jenis yang benar, lalu kirim ulang.")
            return hasil

        if not aturan["jenis_lokasi"]:
            hasil["status"] = "tanpa_lokasi"
            return hasil

        hasil["lokasi"] = self.cari_terdekat(lat, lon, aturan["jenis_lokasi"], top_k, radius_km)
        if not hasil["lokasi"]:
            hasil["status"] = "tidak_ditemukan"
            hasil["pesan"] = "Tidak ada lokasi yang sesuai dalam radius yang diminta."
        return hasil
