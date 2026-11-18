"""
Logika rekomendasi lokasi penyetoran sampah EcoDrop.

Alur:
  1. Label jenis sampah mengikuti 12 kelas dataset publik Garbage Classification (Mohamed, 2021),
     sehingga dapat berasal dari model klasifikasi citra mana pun yang dilatih dengan kelas tersebut
     atau dipilih langsung oleh pengguna. Label dipetakan ke jenis lokasi memakai data/aturan_label.csv.
  2. Bila confidence di bawah ambang dan pengguna belum mengonfirmasi, sistem meminta konfirmasi.
  3. Jarak dari lokasi pengguna ke semua lokasi yang sesuai dihitung dengan Haversine,
     lalu diurutkan dari yang terdekat.
"""

import csv
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
# kotak batas lima kota administrasi DKI Jakarta (tanpa Kepulauan Seribu), untuk memberi peringatan
BATAS_DKI = {"lat_min": -6.40, "lat_max": -6.05, "lon_min": 106.65, "lon_max": 107.00}


def normalisasi_label(label):
    return str(label or "").strip().lower().replace("_", "-").replace(" ", "-")


class MesinRekomendasi:
    def __init__(self, path_lokasi=None, path_aturan=None):
        path_lokasi = Path(path_lokasi or FOLDER_DATA / "lokasi_ecodrop.csv")
        path_aturan = Path(path_aturan or FOLDER_DATA / "aturan_label.csv")

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

    # ------------------------------------------------------------------
    def daftar_label(self):
        return [
            {"label": k, "nama_indonesia": v["nama_indonesia"], "kelompok": v["kelompok"],
             "jenis_lokasi": v["jenis_lokasi"]}
            for k, v in self.aturan.items()
        ]

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
        """Rekomendasi lokasi berdasarkan label jenis sampah (hasil klasifikasi atau pilihan pengguna)."""
        kunci = normalisasi_label(label)
        if kunci not in self.aturan:
            raise KeyError(f"Label '{label}' tidak dikenal. Label yang tersedia: {', '.join(self.aturan)}")
        if not 0 <= confidence <= 1:
            raise ValueError("Confidence harus di antara 0 dan 1.")
        self._cek_koordinat(lat, lon)

        aturan = self.aturan[kunci]
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
