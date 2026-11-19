"""
Skenario pengujian black-box endpoint EcoDrop.
Dipakai oleh tests/test_api.py (pytest) dan pengujian/uji_blackbox.py (tabel hasil untuk laporan).

Lokasi uji: sekitar Jl. Menteng Raya, Jakarta Pusat (-6.2088, 106.8456).
Skenario BB-25 dan BB-26 mengunggah berkas; isinya dibuat oleh berkas_unggahan().
"""

import io

LAT, LON = -6.2088, 106.8456


def berkas_unggahan(jenis):
    """Berkas untuk skenario unggah foto: 'gambar' = foto JPEG sintetis, 'teks' = berkas bukan gambar."""
    if jenis == "teks":
        return {"foto": ("catatan.txt", b"bukan gambar", "text/plain")}
    from PIL import Image, ImageDraw
    g = Image.new("RGB", (640, 480), (235, 235, 230))
    ImageDraw.Draw(g).rectangle((260, 80, 380, 420), fill=(60, 150, 210))  # bentuk sederhana mirip botol
    buf = io.BytesIO()
    g.save(buf, format="JPEG")
    return {"foto": ("botol.jpg", buf.getvalue(), "image/jpeg")}

SKENARIO = [
    {
        "kode": "BB-01", "fitur": "Rekomendasi anorganik",
        "uraian": "Label plastic, confidence 0,92, lokasi Jakarta Pusat",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "plastic", "confidence": 0.92, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, 5 lokasi bank sampah urut dari yang terdekat",
        "cek": {"http": 200, "status": "ok", "jumlah": 5, "jenis": ["bank_sampah"], "urut": True},
    },
    {
        "kode": "BB-02", "fitur": "Rekomendasi anorganik",
        "uraian": "Label white-glass (kaca bening)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "white-glass", "confidence": 0.85, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, semua lokasi bank sampah",
        "cek": {"http": 200, "status": "ok", "jenis": ["bank_sampah"], "urut": True},
    },
    {
        "kode": "BB-03", "fitur": "Rekomendasi B3",
        "uraian": "Label battery, confidence 0,88",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "battery", "confidence": 0.88, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, lokasi berupa dropbox e-waste atau collection point B3",
        "cek": {"http": 200, "status": "ok", "jenis": ["dropbox_ewaste", "collection_point_b3"], "urut": True},
    },
    {
        "kode": "BB-04", "fitur": "Rekomendasi residu",
        "uraian": "Label trash, confidence 0,81",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "trash", "confidence": 0.81, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, semua lokasi TPS",
        "cek": {"http": 200, "status": "ok", "jenis": ["tps"], "urut": True},
    },
    {
        "kode": "BB-05", "fitur": "Sampah tanpa lokasi",
        "uraian": "Label biological (organik)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "biological", "confidence": 0.90, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status tanpa_lokasi, daftar lokasi kosong, ada pesan arahan",
        "cek": {"http": 200, "status": "tanpa_lokasi", "jumlah": 0},
    },
    {
        "kode": "BB-06", "fitur": "Sampah tanpa lokasi",
        "uraian": "Label clothes (pakaian)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "clothes", "confidence": 0.77, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status tanpa_lokasi",
        "cek": {"http": 200, "status": "tanpa_lokasi", "jumlah": 0},
    },
    {
        "kode": "BB-07", "fitur": "Ambang confidence",
        "uraian": "Label paper, confidence 0,45 (di bawah ambang 0,6)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "paper", "confidence": 0.45, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status perlu_konfirmasi, belum ada lokasi",
        "cek": {"http": 200, "status": "perlu_konfirmasi", "jumlah": 0},
    },
    {
        "kode": "BB-08", "fitur": "Ambang confidence",
        "uraian": "Label paper, confidence 0,45, pengguna sudah mengonfirmasi",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "paper", "confidence": 0.45, "latitude": LAT, "longitude": LON, "dikonfirmasi": True},
        "harapan": "HTTP 200, status ok, lokasi bank sampah tampil",
        "cek": {"http": 200, "status": "ok", "jenis": ["bank_sampah"], "urut": True},
    },
    {
        "kode": "BB-09", "fitur": "Jumlah hasil",
        "uraian": "Label metal dengan top_k = 3",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "metal", "confidence": 0.9, "latitude": LAT, "longitude": LON, "top_k": 3},
        "harapan": "HTTP 200, tepat 3 lokasi",
        "cek": {"http": 200, "status": "ok", "jumlah": 3, "urut": True},
    },
    {
        "kode": "BB-10", "fitur": "Radius pencarian",
        "uraian": "Label battery dengan radius 0,5 km",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "battery", "confidence": 0.9, "latitude": LAT, "longitude": LON, "radius_km": 0.5},
        "harapan": "HTTP 200, semua lokasi (bila ada) berjarak <= 0,5 km; bila tidak ada, status tidak_ditemukan",
        "cek": {"http": 200, "radius": 0.5},
    },
    {
        "kode": "BB-11", "fitur": "Validasi masukan",
        "uraian": "Label tidak dikenal ('kayu')",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "kayu", "confidence": 0.9, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 422 dengan pesan label tidak dikenal",
        "cek": {"http": 422},
    },
    {
        "kode": "BB-12", "fitur": "Validasi masukan",
        "uraian": "Latitude di luar rentang (-95)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "plastic", "confidence": 0.9, "latitude": -95, "longitude": LON},
        "harapan": "HTTP 422",
        "cek": {"http": 422},
    },
    {
        "kode": "BB-13", "fitur": "Validasi masukan",
        "uraian": "Confidence lebih dari 1 (1,5)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "plastic", "confidence": 1.5, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 422",
        "cek": {"http": 422},
    },
    {
        "kode": "BB-14", "fitur": "Validasi masukan",
        "uraian": "Field latitude tidak dikirim",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "plastic", "confidence": 0.9, "longitude": LON},
        "harapan": "HTTP 422",
        "cek": {"http": 422},
    },
    {
        "kode": "BB-15", "fitur": "Lokasi di luar Jakarta",
        "uraian": "Pengguna di Kota Bogor (-6.5950, 106.8167), label plastic",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "plastic", "confidence": 0.9, "latitude": -6.5950, "longitude": 106.8167},
        "harapan": "HTTP 200, status ok, ada peringatan di luar cakupan EcoDrop",
        "cek": {"http": 200, "status": "ok", "peringatan": True},
    },
    {
        "kode": "BB-16", "fitur": "Pencarian manual",
        "uraian": "GET lokasi-terdekat jenis tps, top_k 5",
        "metode": "GET", "url": "/ecodrop/lokasi-terdekat",
        "data": {"latitude": LAT, "longitude": LON, "jenis_lokasi": "tps", "top_k": 5},
        "harapan": "HTTP 200, 5 TPS urut dari yang terdekat",
        "cek": {"http": 200, "jumlah": 5, "jenis": ["tps"], "urut": True, "daftar": True},
    },
    {
        "kode": "BB-17", "fitur": "Pencarian manual",
        "uraian": "GET lokasi-terdekat dengan jenis tidak valid ('pasar')",
        "metode": "GET", "url": "/ecodrop/lokasi-terdekat",
        "data": {"latitude": LAT, "longitude": LON, "jenis_lokasi": "pasar"},
        "harapan": "HTTP 422",
        "cek": {"http": 422},
    },
    {
        "kode": "BB-18", "fitur": "Daftar label",
        "uraian": "GET /ecodrop/label",
        "metode": "GET", "url": "/ecodrop/label",
        "data": {},
        "harapan": "HTTP 200, 12 label sesuai kelas dataset Garbage Classification",
        "cek": {"http": 200, "jumlah_label": 12},
    },
    {
        "kode": "BB-19", "fitur": "Daftar jenis sampah",
        "uraian": "GET /ecodrop/jenis",
        "metode": "GET", "url": "/ecodrop/jenis",
        "data": {},
        "harapan": "HTTP 200, 58 jenis sampah EcoDrop",
        "cek": {"http": 200, "jumlah_label": 58},
    },
    {
        "kode": "BB-20", "fitur": "Rekomendasi dengan kode jenis",
        "uraian": "Kode AN05 (botol plastik minuman), confidence 0,72",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "AN05", "confidence": 0.72, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, 5 lokasi bank sampah urut dari yang terdekat",
        "cek": {"http": 200, "status": "ok", "jumlah": 5, "jenis": ["bank_sampah"], "urut": True},
    },
    {
        "kode": "BB-21", "fitur": "Rekomendasi dengan kode jenis",
        "uraian": "Kode ek05 (baterai kecil) ditulis huruf kecil",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "ek05", "confidence": 0.9, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, lokasi berupa dropbox e-waste atau collection point B3",
        "cek": {"http": 200, "status": "ok", "jenis": ["dropbox_ewaste", "collection_point_b3"], "urut": True},
    },
    {
        "kode": "BB-22", "fitur": "Rekomendasi dengan kode jenis",
        "uraian": "Kode EB03 (kulkas, mesin cuci, AC)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "EB03", "confidence": 0.9, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, semua lokasi collection point B3 (dropbox hanya untuk barang kecil)",
        "cek": {"http": 200, "status": "ok", "jenis": ["collection_point_b3"], "urut": True},
    },
    {
        "kode": "BB-23", "fitur": "Rekomendasi dengan kode jenis",
        "uraian": "Kode LN02 (obat kedaluwarsa)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "LN02", "confidence": 0.9, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status ok, lokasi TPS, pesan menyebut apotek",
        "cek": {"http": 200, "status": "ok", "jenis": ["tps"], "urut": True, "pesan_memuat": "apotek"},
    },
    {
        "kode": "BB-24", "fitur": "Sampah tanpa lokasi",
        "uraian": "Kode OR01 (sisa makanan)",
        "metode": "POST", "url": "/ecodrop/rekomendasi",
        "data": {"label": "OR01", "confidence": 0.9, "latitude": LAT, "longitude": LON},
        "harapan": "HTTP 200, status tanpa_lokasi, ada saran pengolahan",
        "cek": {"http": 200, "status": "tanpa_lokasi", "jumlah": 0, "pesan_memuat": "kompos"},
    },
    {
        "kode": "BB-25", "fitur": "Pengenalan foto",
        "uraian": "POST /ecodrop/kenali-foto dengan foto JPEG",
        "metode": "UNGGAH", "url": "/ecodrop/kenali-foto", "berkas": "gambar",
        "data": {},
        "harapan": "HTTP 200, tiga saran jenis berurutan dari peluang terbesar, kode termasuk 58 jenis",
        "cek": {"http": 200, "saran": 3},
    },
    {
        "kode": "BB-26", "fitur": "Pengenalan foto",
        "uraian": "POST /ecodrop/kenali-foto dengan berkas teks",
        "metode": "UNGGAH", "url": "/ecodrop/kenali-foto", "berkas": "teks",
        "data": {},
        "harapan": "HTTP 422, berkas bukan gambar",
        "cek": {"http": 422},
    },
]


def kirim(klien, s):
    """Kirim permintaan sesuai skenario memakai TestClient FastAPI."""
    if s["metode"] == "POST":
        return klien.post(s["url"], json=s["data"])
    if s["metode"] == "UNGGAH":
        return klien.post(s["url"], files=berkas_unggahan(s["berkas"]))
    return klien.get(s["url"], params=s["data"])


def periksa(skenario, respons):
    """Mengembalikan (lulus: bool, hasil_aktual: str)."""
    cek = skenario["cek"]
    catatan = [f"HTTP {respons.status_code}"]
    lulus = respons.status_code == cek["http"]
    if respons.status_code != 200:
        return lulus, "; ".join(catatan)

    body = respons.json()
    lokasi = body if cek.get("daftar") else (body.get("lokasi", []) if isinstance(body, dict) else [])

    if "status" in cek:
        catatan.append(f"status {body['status']}")
        lulus &= body["status"] == cek["status"]
    if "jumlah" in cek:
        catatan.append(f"{len(lokasi)} lokasi")
        lulus &= len(lokasi) == cek["jumlah"]
    if "jenis" in cek and lokasi:
        jenis = sorted({x["jenis_lokasi"] for x in lokasi})
        catatan.append("jenis " + ", ".join(jenis))
        lulus &= set(jenis) <= set(cek["jenis"])
    if cek.get("urut") and lokasi:
        jarak = [x["jarak_km"] for x in lokasi]
        urut = jarak == sorted(jarak)
        catatan.append(f"jarak {jarak[0]}-{jarak[-1]} km, {'urut' if urut else 'TIDAK urut'}")
        lulus &= urut
    if "radius" in cek:
        if lokasi:
            maks = max(x["jarak_km"] for x in lokasi)
            catatan.append(f"{len(lokasi)} lokasi, terjauh {maks} km")
            lulus &= maks <= cek["radius"]
        else:
            catatan.append(f"status {body['status']}")
            lulus &= body["status"] == "tidak_ditemukan"
    if cek.get("peringatan"):
        catatan.append("ada peringatan" if body.get("peringatan") else "tanpa peringatan")
        lulus &= bool(body.get("peringatan"))
    if "jumlah_label" in cek:
        catatan.append(f"{len(body)} label")
        lulus &= len(body) == cek["jumlah_label"]
    if "pesan_memuat" in cek:
        ada = cek["pesan_memuat"] in body.get("pesan", "")
        catatan.append(f"pesan {'memuat' if ada else 'tidak memuat'} '{cek['pesan_memuat']}'")
        lulus &= ada
    if "saran" in cek:
        saran = body.get("saran", [])
        peluang = [x["peluang"] for x in saran]
        catatan.append(f"{len(saran)} saran: " + ", ".join(f"{x['kode']} {x['peluang']:.2f}" for x in saran))
        lulus &= len(saran) == cek["saran"] and peluang == sorted(peluang, reverse=True)
        lulus &= all(len(x["kode"]) == 4 and x["jenis_lokasi"] is not None for x in saran)
    return lulus, "; ".join(catatan)
