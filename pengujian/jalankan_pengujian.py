"""
Menjalankan seluruh pengujian EcoDrop dan menyimpan hasilnya untuk laporan.

  1. Black-box  : 26 skenario endpoint API (termasuk unggah foto).
  2. Akurasi    : jarak Haversine dibandingkan jarak geodesik elipsoid WGS84 (pyproj, metode Karney)
                  sebagai acuan, ditambah kecocokan urutan 5 lokasi terdekat.
  3. Kecepatan  : waktu proses per permintaan rekomendasi.

Jalankan dari folder utama:  python pengujian/jalankan_pengujian.py
Hasil tersimpan di folder pengujian/hasil.
"""

import statistics
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from pyproj import Geod

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))
sys.path.insert(0, str(AKAR / "pengujian"))

from ecodrop.api import app  # noqa: E402
from ecodrop.haversine import haversine_km, haversine_km_vektor  # noqa: E402
from ecodrop.rekomendasi import JENIS_LOKASI, MesinRekomendasi  # noqa: E402
from skenario_blackbox import SKENARIO, kirim, periksa  # noqa: E402

OUT = AKAR / "pengujian" / "hasil"
OUT.mkdir(parents=True, exist_ok=True)
GEOD = Geod(ellps="WGS84")
SEED = 42
N_TITIK = 1000


def uji_blackbox():
    klien = TestClient(app)
    baris = []
    for s in SKENARIO:
        r = kirim(klien, s)
        lulus, aktual = periksa(s, r)
        baris.append({"kode": s["kode"], "fitur": s["fitur"], "skenario": s["uraian"],
                      "hasil_diharapkan": s["harapan"], "hasil_aktual": aktual,
                      "kesimpulan": "Berhasil" if lulus else "Gagal"})
    df = pd.DataFrame(baris)
    df.to_csv(OUT / "hasil_blackbox.csv", index=False, encoding="utf-8-sig")
    return df


def titik_uji(mesin, rng):
    """Titik pengguna acak di daratan Jakarta: acak di kotak batas, disimpan bila ada lokasi dalam 1 km."""
    lat_d, lon_d = mesin.lat[mesin.lat < -6.05], mesin.lon[mesin.lat < -6.05]
    titik = []
    while len(titik) < N_TITIK:
        la = rng.uniform(lat_d.min(), lat_d.max())
        lo = rng.uniform(lon_d.min(), lon_d.max())
        if haversine_km_vektor(la, lo, lat_d, lon_d).min() <= 1.0:
            titik.append((la, lo))
    return titik


def uji_akurasi(mesin, titik):
    pasangan, ranking = [], []
    for la, lo in titik:
        for j in JENIS_LOKASI:
            idx = mesin.indeks_jenis[j]
            lat2, lon2 = mesin.lat[idx], mesin.lon[idx]
            d_h = haversine_km_vektor(la, lo, lat2, lon2)
            az, _, d_g = GEOD.inv(np.full(len(idx), lo), np.full(len(idx), la), lon2, lat2)
            d_g = d_g / 1000
            top_h = np.argsort(d_h, kind="stable")[:5]
            top_g = np.argsort(d_g, kind="stable")[:5]
            ranking.append({"jenis_lokasi": j, "top1_sama": top_h[0] == top_g[0],
                            # bila pilihan pertama berbeda: berapa meter lebih jauh lokasi pilihan Haversine
                            "kerugian_jarak_m": (d_g[top_h[0]] - d_g[top_g[0]]) * 1000,
                            "top5_urutan_sama": bool(np.array_equal(top_h, top_g)),
                            "top5_anggota_sama": set(top_h) == set(top_g)})
            for i in top_g:
                pasangan.append({"jenis_lokasi": j, "jarak_geodesik_km": d_g[i], "jarak_haversine_km": d_h[i],
                                 "azimut": az[i] % 360})
    p = pd.DataFrame(pasangan)
    p["selisih_m"] = (p["jarak_haversine_km"] - p["jarak_geodesik_km"]) * 1000
    p["selisih_relatif_persen"] = p["selisih_m"] / (p["jarak_geodesik_km"] * 1000) * 100
    p = p[p["jarak_geodesik_km"] > 0]
    r = pd.DataFrame(ranking)
    p.to_csv(OUT / "akurasi_pasangan_jarak.csv", index=False, encoding="utf-8-sig")
    return p, r


def uji_kecepatan(mesin, titik, rng):
    label = list(mesin.aturan)
    waktu = []
    for la, lo in titik:
        lb = label[rng.integers(len(label))]
        t0 = time.perf_counter()
        mesin.rekomendasi(lb, 0.95, la, lo, top_k=5)
        waktu.append((time.perf_counter() - t0) * 1000)

    klien = TestClient(app)
    waktu_api = []
    for la, lo in titik[:300]:
        t0 = time.perf_counter()
        klien.post("/ecodrop/rekomendasi", json={"label": "plastic", "confidence": 0.9,
                                                 "latitude": la, "longitude": lo})
        waktu_api.append((time.perf_counter() - t0) * 1000)

    # pembanding: perulangan Python biasa tanpa numpy, ke seluruh lokasi
    waktu_loop = []
    semua = list(zip(mesin.lat.tolist(), mesin.lon.tolist()))
    for la, lo in titik[:100]:
        t0 = time.perf_counter()
        sorted((haversine_km(la, lo, a, b), i) for i, (a, b) in enumerate(semua))[:5]
        waktu_loop.append((time.perf_counter() - t0) * 1000)

    def ringkas(w):
        w = sorted(w)
        return {"rata_rata_ms": statistics.mean(w), "median_ms": statistics.median(w),
                "p95_ms": w[int(0.95 * (len(w) - 1))], "maks_ms": w[-1], "n": len(w)}

    return {"Modul rekomendasi (numpy)": ringkas(waktu),
            "Endpoint API lengkap (FastAPI, in-process)": ringkas(waktu_api),
            f"Pembanding: perulangan Python ke {len(semua):,} lokasi".replace(",", "."): ringkas(waktu_loop)}


def gambar_akurasi(p):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    ax[0].hist(p["selisih_relatif_persen"], bins=60, color="#2e7d32")
    ax[0].set_xlabel("Selisih relatif Haversine terhadap geodesik (%)")
    ax[0].set_ylabel("Jumlah pasangan titik")
    ax[0].set_title("Sebaran selisih jarak")
    ax[1].scatter(p["azimut"], p["selisih_relatif_persen"], s=3, alpha=0.4, color="#1565c0")
    ax[1].set_xlabel("Arah dari pengguna ke lokasi (azimut, derajat)")
    ax[1].set_ylabel("Selisih relatif (%)")
    ax[1].set_xticks([0, 90, 180, 270, 360])
    ax[1].set_title("Selisih menurut arah (0/180 = utara/selatan, 90/270 = timur/barat)")
    fig.tight_layout()
    fig.savefig(OUT / "grafik_akurasi_haversine.png", dpi=200)


def main():
    rng = np.random.default_rng(SEED)
    mesin = MesinRekomendasi()

    bb = uji_blackbox()
    titik = titik_uji(mesin, rng)
    p, r = uji_akurasi(mesin, titik)
    gambar_akurasi(p)
    kec = uji_kecepatan(mesin, titik, rng)

    per_jenis = r.groupby("jenis_lokasi")[["top1_sama", "top5_anggota_sama", "top5_urutan_sama"]].mean() * 100
    baris = [
        "RINGKASAN PENGUJIAN ECODROP",
        "",
        "1. PENGUJIAN BLACK-BOX",
        f"   Skenario: {len(bb)}, berhasil: {(bb['kesimpulan'] == 'Berhasil').sum()}, "
        f"gagal: {(bb['kesimpulan'] == 'Gagal').sum()}  (rincian: hasil_blackbox.csv)",
        "",
        "2. PENGUJIAN AKURASI JARAK",
        f"   Acuan: jarak geodesik elipsoid WGS84 (pyproj Geod, metode Karney)",
        f"   Titik pengguna acak di daratan Jakarta: {len(titik)} titik (seed {SEED})",
        f"   Pasangan yang dibandingkan (5 lokasi terdekat x 4 jenis lokasi x {len(titik)} titik): {len(p):,}",
        f"   Rata-rata jarak acuan           : {p['jarak_geodesik_km'].mean():.3f} km",
        f"   Rata-rata selisih absolut (MAE) : {p['selisih_m'].abs().mean():.2f} m",
        f"   Selisih absolut maksimum        : {p['selisih_m'].abs().max():.2f} m",
        f"   Rata-rata selisih relatif (MAPE): {p['selisih_relatif_persen'].abs().mean():.3f} %",
        f"   Rentang selisih relatif         : {p['selisih_relatif_persen'].min():.3f} % s.d. "
        f"{p['selisih_relatif_persen'].max():.3f} %",
        f"   Akurasi jarak (100% - MAPE)     : {100 - p['selisih_relatif_persen'].abs().mean():.3f} %",
        "",
        "   Kecocokan urutan rekomendasi Haversine vs geodesik:",
        f"   - lokasi terdekat pertama sama : {r['top1_sama'].mean() * 100:.2f} %",
        f"   - 5 lokasi terdekat sama       : {r['top5_anggota_sama'].mean() * 100:.2f} %",
        f"   - 5 lokasi dengan urutan sama  : {r['top5_urutan_sama'].mean() * 100:.2f} %",
        f"   Bila lokasi pertama berbeda ({(~r['top1_sama']).sum()} dari {len(r):,} kasus), lokasi pilihan Haversine "
        f"hanya lebih jauh maksimum {r['kerugian_jarak_m'].max():.2f} m dari lokasi terdekat sebenarnya.",
        "",
        "   Per jenis lokasi (%):",
        per_jenis.round(2).to_string(),
        "",
        "3. PENGUJIAN KECEPATAN",
    ]
    for nama, k in kec.items():
        baris.append(f"   {nama} (n={k['n']}): rata-rata {k['rata_rata_ms']:.3f} ms, median {k['median_ms']:.3f} ms, "
                     f"p95 {k['p95_ms']:.3f} ms, maks {k['maks_ms']:.3f} ms")
    teks = "\n".join(baris)
    (OUT / "ringkasan_pengujian.txt").write_text(teks, encoding="utf-8")
    print(teks)


if __name__ == "__main__":
    main()
