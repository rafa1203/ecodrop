# EcoDrop — konteks proyek

Capstone Project individu Rafah Wildan (Informatika, Universitas Mercu Buana).
Judul: "EcoDrop: Sistem Rekomendasi Lokasi Penyetoran Sampah Terdekat di DKI Jakarta Berdasarkan Hasil
Klasifikasi Sampah Menggunakan Metode Haversine". Laporan bersifat individu; jangan menyebut kelompok,
anggota kelompok lain, atau aplikasi Flutter.

Gunakan bahasa Indonesia untuk antarmuka, komentar kode, dan penjelasan.

## Cara kerja sistem

1. Masukan jenis sampah: kode salah satu dari 58 jenis EcoDrop (`data/jenis_sampah.csv`, mis. AN05) atau
   salah satu dari 12 label umum Garbage Classification (`data/aturan_label.csv`, untuk model 12 kelas),
   beserta confidence 0–1. Pilihan manual memakai confidence 1,0.
2. Pengenalan foto (`ecodrop/foto.py`): zero-shot OpenCLIP ViT-B/32 (LAION-400M). Encoder gambar berupa
   ONNX int8 (`model/visual.onnx`, diunduh dari rilis GitHub `model-v1` lalu dicek SHA-256-nya); vektor
   184 deskripsi teks ada di `model/teks.npy` (urutan per jenis, baris awal tiap jenis di
   `konfigurasi.json` › `awal_deskripsi`). Skor jenis = kemiripan kosinus tertinggi di antara
   deskripsinya × skala logit, lalu softmax. Aplikasi menampilkan tiga saran; bila peluang teratas ≥ 0,6,
   saran pertama langsung dipilih.
3. Jika confidence < 0,6 dan belum dikonfirmasi, status `perlu_konfirmasi` (lokasi belum ditampilkan).
4. Jenis dipetakan ke jenis lokasi: anorganik -> bank_sampah; e-waste kecil -> dropbox_ewaste dan
   collection_point_b3; e-waste besar dan B3 -> collection_point_b3; residu dan obat -> tps;
   organik, tekstil, jelantah, puing, furnitur -> tanpa lokasi (hanya pesan arahan).
5. Lokasi disaring sesuai jenis, jarak Haversine (R = 6371 km) dihitung tervektorisasi dengan NumPy,
   lalu diambil k terdekat (bawaan 5, maksimal 20, opsional radius_km).
6. Keluaran tiap lokasi: urutan, id, nama, jenis_lokasi, jenis_lokasi_nama, jarak_km, jarak_m, latitude,
   longitude, alamat, kelurahan, kecamatan, kota, keterangan, jam_buka, akurasi ("tepat"/"perkiraan"),
   url_rute. Antarmuka memakai tautan pin koordinat Google Maps. Ada peringatan bila pengguna di luar DKI.
7. Status: `ok`, `perlu_konfirmasi`, `tanpa_lokasi`, `tidak_ditemukan`.

## Struktur

- `ecodrop/haversine.py` — `haversine_km`, `haversine_km_vektor`.
- `ecodrop/rekomendasi.py` — `MesinRekomendasi(path_lokasi=None, path_aturan=None, path_jenis=None)` dengan
  `daftar_label()`, `daftar_jenis()`, `aturan_untuk(label)`,
  `cari_terdekat(lat, lon, jenis_lokasi, top_k=5, radius_km=None)`,
  `rekomendasi(label, confidence, lat, lon, top_k=5, radius_km=None, dikonfirmasi=False)`.
  Konstanta: `AMBANG_CONFIDENCE = 0.6`, `TOP_K_MAKS = 20`, `BATAS_DKI`.
- `ecodrop/foto.py` — `PengenalFoto().kenali(gambar_PIL, k=3)` -> `[{"kode", "peluang"}]`. Tanpa PyTorch.
- `ecodrop/api.py` — FastAPI, router prefix `/ecodrop`: `GET /kesehatan`, `GET /label`, `GET /jenis`,
  `POST /rekomendasi`, `POST /kenali-foto` (multipart, field `foto`), `GET /lokasi-terdekat`.
- `app.py` — antarmuka Streamlit (iterasi 3): unggah/potret foto -> tiga saran, kotak pencarian 58 jenis,
  GPS/peta/koordinat, hasil berupa peta dan kartu lokasi. Paket Streamlit dikunci versinya.
- `model/` — `prompt_jenis.csv` (deskripsi bahasa Inggris per jenis), `teks.npy`, `konfigurasi.json`.
  Berkas `.onnx` dan `.pt` tidak masuk git.
- `tools/siapkan_model.py` — membuat isi `model/` dari bobot OpenCLIP (butuh torch, open_clip_torch, onnx).
  Dijalankan oleh `.github/workflows/siapkan-model.yml` (manual), yang mengunggah `visual.onnx` ke rilis
  `model-v1` dan meng-commit `teks.npy` serta `konfigurasi.json`. Bila `prompt_jenis.csv` atau
  `jenis_sampah.csv` diubah, jalankan ulang workflow itu.
- `data/lokasi_ecodrop.csv` — 3.127 lokasi (bank sampah 1.923, dropbox e-waste 34, collection point B3 51,
  TPS 1.119) dari tiga platform DLH DKI Jakarta; tanpa Kepulauan Seribu.
- `data/jenis_sampah.csv` — 58 jenis: kode, nama, contoh, kelompok, jenis_lokasi, pesan, dasar, perlu_dicek.
- `tests/` — pytest (32 tes). Jalankan: `pytest -q`.
- `pengujian/` — black-box 26 skenario, akurasi Haversine vs geodesik WGS84 (pyproj), waktu respons
  (`jalankan_pengujian.py`); akurasi foto (`uji_foto.py data_uji`, daftar foto di `data_uji_foto/`,
  bagian pengembangan 30% untuk menyusun deskripsi, angka laporan dari bagian uji 70%).

Jangan mengubah isi `data/` dan logika `ecodrop/` tanpa alasan; hasil pengujian di laporan bergantung
padanya. Jika logika diubah, jalankan ulang `pytest` dan skrip pengujian.

## Hasil pengujian foto (bagian uji, 2.497 foto, ONNX int8)

TrashNet (tingkat bahan): top-1 64,6%, top-3 87,8%, tujuan 75,9%. TrashIVL (tingkat jenis): top-1 70,0%,
top-3 87,7%, tujuan 85,1%. E-Waste Vision: top-1 85,6%, top-3 94,8%, tujuan 96,3%. Gabungan: top-1 68,3%,
top-3 88,7%, tujuan 80,2%. Sekitar 16 ms per foto di CPU; RAM proses sekitar 260 MB dengan model.
Perbandingan arsitektur (bagian pengembangan, fp32): ViT-L/14 lebih akurat (TrashNet top-1 72,5% vs 66,4%)
tetapi 3,5 kali lebih besar dan sekitar 12 kali lebih lambat, jadi aplikasi memakai ViT-B/32.

## Rencana berikutnya

Uji SUS (rencana 20 responden, target rata-rata ≥ 68) dan uji foto lapangan untuk jenis yang belum
tercakup dataset publik. Bab IV dan V laporan ditulis setelah aplikasi selesai diuji, menunggu arahan Rafa.
