# EcoDrop

Aplikasi web untuk mencari lokasi penyetoran sampah terdekat di DKI Jakarta: bank sampah, dropbox e-waste,
collection point B3, dan TPS. Pengguna memotret sampahnya atau mencari jenisnya dari 58 jenis sampah,
lalu jarak ke lokasi yang sesuai dihitung dengan rumus Haversine.

Dibuat sebagai Capstone Project Program Studi Informatika, Universitas Mercu Buana.

## Menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

REST API (opsional): `uvicorn ecodrop.api:app --reload`. Pengujian: `pytest -q`.

Saat foto pertama dikenali, aplikasi mengunduh encoder gambar CLIP (sekitar 96 MB) dari rilis
[`model-v1`](https://github.com/rafa1203/ecodrop/releases/tag/model-v1). Berkas itu dibuat oleh
`tools/siapkan_model.py` lewat GitHub Actions (tab Actions › Siapkan model foto).

## Data

3.127 lokasi dari e-Bank Sampah Jakarta, portal e-waste, dan layer TPS di Jakarta Satu milik Dinas
Lingkungan Hidup Provinsi DKI Jakarta (diakses 17 November 2026), tanpa Kepulauan Seribu.
Daftar 58 jenis sampah (`data/jenis_sampah.csv`) disusun dari Instruksi Gubernur DKI Jakarta Nomor 5
Tahun 2026 dan Portal E-Waste DLH DKI.

## Pengenalan foto

Foto dikenali secara *zero-shot* dengan OpenCLIP ViT-B/32 (LAION-400M): tiap jenis sampah diwakili
beberapa deskripsi teks (`model/prompt_jenis.csv`), dan aplikasi menampilkan tiga jenis yang paling mirip
untuk dipilih pengguna. Hasil uji pada 2.497 foto (TrashNet, TrashIVL, E-Waste Vision): jenis benar ada
di tiga saran pada 87,8% foto, dan tujuan penyetoran dari saran pertama benar pada 80,1% foto
(`pengujian/hasil/ringkasan_uji_foto.txt`).
