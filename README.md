# EcoDrop

Aplikasi web untuk mencari lokasi penyetoran sampah terdekat di DKI Jakarta: bank sampah, dropbox e-waste,
collection point B3, dan TPS. Jenis sampah mengikuti 12 kelas dataset Garbage Classification, dan jarak
dihitung dengan rumus Haversine.

Dibuat sebagai Capstone Project Program Studi Informatika, Universitas Mercu Buana.

## Menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

REST API (opsional): `uvicorn ecodrop.api:app --reload`. Pengujian: `pytest -q`.

## Data

3.127 lokasi dari e-Bank Sampah Jakarta, portal e-waste, dan layer TPS di Jakarta Satu milik Dinas
Lingkungan Hidup Provinsi DKI Jakarta (diakses 17 November 2026), tanpa Kepulauan Seribu.
