# EcoDrop — konteks proyek

Capstone Project individu Rafah Wildan (Informatika, Universitas Mercu Buana).
Judul: "EcoDrop: Sistem Rekomendasi Lokasi Penyetoran Sampah Terdekat di DKI Jakarta Berdasarkan Hasil
Klasifikasi Sampah Menggunakan Metode Haversine". Laporan bersifat individu; jangan menyebut kelompok,
anggota kelompok lain, atau aplikasi Flutter.

Gunakan bahasa Indonesia untuk antarmuka, komentar kode, dan penjelasan.

## Cara kerja sistem

1. Masukan jenis sampah: salah satu dari 12 label dataset Garbage Classification (Mohamed, 2021) beserta
   confidence 0–1 dari model klasifikasi citra, atau dipilih manual oleh pengguna.
2. Jika confidence < 0,6 dan belum dikonfirmasi, status `perlu_konfirmasi` (lokasi belum ditampilkan).
3. Label dipetakan ke jenis lokasi lewat `data/aturan_label.csv`:
   cardboard, paper, plastic, metal, brown-glass, green-glass, white-glass -> bank_sampah;
   battery -> dropbox_ewaste;collection_point_b3; trash -> tps;
   biological, clothes, shoes -> tanpa lokasi (hanya pesan arahan).
4. Lokasi disaring sesuai jenis, jarak Haversine (R = 6371 km) dihitung tervektorisasi dengan NumPy,
   lalu diambil k terdekat (bawaan 5, maksimal 20, opsional radius_km).
5. Keluaran tiap lokasi: urutan, id, nama, jenis_lokasi, jenis_lokasi_nama, jarak_km, jarak_m, latitude,
   longitude, alamat, kelurahan, kecamatan, kota, keterangan, jam_buka, akurasi ("tepat"/"perkiraan"),
   url_rute (Google Maps directions). Ada peringatan bila pengguna di luar DKI Jakarta.
6. Status: `ok`, `perlu_konfirmasi`, `tanpa_lokasi`, `tidak_ditemukan`.

## Struktur

- `ecodrop/haversine.py` — `haversine_km`, `haversine_km_vektor`.
- `ecodrop/rekomendasi.py` — `MesinRekomendasi(path_lokasi=None, path_aturan=None)` dengan
  `daftar_label()`, `cari_terdekat(lat, lon, jenis_lokasi, top_k=5, radius_km=None)`,
  `rekomendasi(label, confidence, lat, lon, top_k=5, radius_km=None, dikonfirmasi=False)`.
  Konstanta: `AMBANG_CONFIDENCE = 0.6`, `TOP_K_MAKS = 20`, `BATAS_DKI`.
- `ecodrop/api.py` — FastAPI, router prefix `/ecodrop`: `GET /kesehatan`, `GET /label`,
  `POST /rekomendasi`, `GET /lokasi-terdekat`. Jalankan: `uvicorn ecodrop.api:app --reload`.
- `app.py` — antarmuka Streamlit (iterasi 2), memakai `MesinRekomendasi` langsung. Jalankan:
  `streamlit run app.py`. Tema di `.streamlit/config.toml`. Paket Streamlit di `requirements.txt`
  dikunci versinya agar tampilan tetap sama selama uji SUS.
- `data/lokasi_ecodrop.csv` — 3.127 lokasi (bank sampah 1.923, dropbox e-waste 34, collection point B3 51,
  TPS 1.119) dari tiga platform DLH DKI Jakarta, sudah dibersihkan; tanpa Kepulauan Seribu.
- `data/aturan_label.csv` — kolom label, nama_indonesia, kelompok, jenis_lokasi, pesan.
- `tests/` — pytest (24 tes). Jalankan: `pytest -q`.
- `pengujian/` — black-box 18 skenario, akurasi Haversine vs geodesik WGS84 (pyproj), waktu respons.
  Jalankan: `python pengujian/jalankan_pengujian.py`.
- `dokumen/` — laporan Bab I–III dan daftar jurnal (hanya acuan, jangan diubah dari sini).

Jangan mengubah isi `data/` dan logika `ecodrop/` tanpa alasan; hasil pengujian di laporan bergantung
padanya. Jika logika diubah, jalankan ulang `pytest` dan skrip pengujian.

## Tugas berikutnya: antarmuka Streamlit (iterasi 2)

Status: `app.py` sudah dibuat dan diuji di peramban desktop dengan viewport iPhone 15 (GPS tiruan).
Belum: uji langsung di iPhone 15 (Safari) dan publikasi ke Streamlit Community Cloud.

Buat `app.py` (Streamlit) yang memakai `MesinRekomendasi` langsung (tanpa lewat HTTP):

- Pilihan jenis sampah: daftar 12 label dengan nama Indonesia dari `aturan_label.csv`; slider confidence
  opsional (bawaan 1,0 untuk pilihan manual). Bila status `perlu_konfirmasi`, tampilkan tombol konfirmasi.
- Lokasi pengguna: tombol "Gunakan lokasi saya" (Geolocation API peramban, misalnya paket
  `streamlit-geolocation` atau `streamlit_js_eval`; butuh HTTPS) dan cadangan berupa klik titik di peta
  (`folium` + `streamlit-folium`) atau isian lintang/bujur.
- Pengaturan jumlah hasil (1–20) dan radius opsional.
- Hasil: daftar kartu lokasi (nama, jenis, jarak, alamat, jam buka, keterangan akurasi) dengan tombol
  rute ke Google Maps, ditambah peta yang menampilkan posisi pengguna dan lokasi rekomendasi.
- Untuk label tanpa lokasi (organik, pakaian, sepatu) tampilkan pesan arahan dari `aturan_label.csv`.
- Tampilan sederhana, rapi, ramah ponsel (diuji di iPhone 15 lewat Safari).
- Perbarui `requirements.txt` dan siapkan untuk dipublikasikan ke Streamlit Community Cloud
  (berkas utama `app.py`).

Pengembangan opsional sesudahnya: unggah foto yang diklasifikasikan oleh model pralatih 12 kelas
(misalnya ResNet50 Garbage Classification di Hugging Face, lisensi MIT) lalu label dan confidence-nya
dikirim ke `MesinRekomendasi`.

## Rencana berikutnya

Iterasi 3: uji SUS (rencana 20 responden, target rata-rata ≥ 68) dan penyempurnaan. Bab IV dan V laporan
ditulis setelah aplikasi selesai dan diuji, menunggu arahan Rafa.
