"""
Antarmuka Streamlit EcoDrop (iterasi 2).

Aplikasi memakai MesinRekomendasi secara langsung (tanpa lewat HTTP):
  1. Pengguna memilih jenis sampah (12 label Garbage Classification). Bila jenis sampah berasal dari
     model klasifikasi, nilai confidence-nya bisa diatur; pilihan manual memakai confidence 1,0.
  2. Posisi pengguna diambil dari GPS peramban (Geolocation API, butuh HTTPS atau localhost),
     klik titik di peta, atau isian lintang/bujur.
  3. MesinRekomendasi menghitung jarak Haversine ke lokasi yang sesuai dan mengembalikan k terdekat.

Jalankan:
    streamlit run app.py
"""

import html

import folium
import streamlit as st
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

from ecodrop.rekomendasi import AMBANG_CONFIDENCE, JENIS_LOKASI, NAMA_JENIS, TOP_K_MAKS, MesinRekomendasi

# Titik tengah peta awal. Juga dipakai sebagai koordinat pengganti untuk label tanpa lokasi
# (organik, pakaian, sepatu): status dan pesannya tidak bergantung pada posisi pengguna.
PUSAT_JAKARTA = (-6.2088, 106.8456)

IKON_LABEL = {
    "cardboard": "📦", "paper": "📄", "metal": "🥫", "plastic": "🧴",
    "brown-glass": "🍺", "green-glass": "🍾", "white-glass": "🫙",
    "battery": "🔋", "trash": "🗑️", "biological": "🍌", "clothes": "👕", "shoes": "👟",
}
WARNA_PETA = {"bank_sampah": "#2e7d32", "dropbox_ewaste": "#6a1b9a",
              "collection_point_b3": "#c62828", "tps": "#5d4037"}
WARNA_BADGE = {"bank_sampah": "green", "dropbox_ewaste": "violet",
               "collection_point_b3": "red", "tps": "gray"}
WARNA_PENGGUNA = "#1a73e8"

PESAN_GALAT_GPS = {
    1: ("Izin lokasi ditolak. Izinkan akses lokasi untuk situs ini (di iPhone: Pengaturan › Privasi & "
        "Keamanan › Layanan Lokasi › Situs Web Safari), lalu coba lagi. Fitur ini hanya berjalan lewat HTTPS."),
    2: "Posisi tidak dapat ditentukan. Pastikan Layanan Lokasi/GPS aktif, lalu coba lagi.",
    3: "Waktu habis saat mencari posisi. Coba lagi.",
}
PESAN_GALAT_GPS_LAIN = "Peramban ini tidak dapat memberikan lokasi."


@st.cache_resource
def muat_mesin():
    return MesinRekomendasi()


# ----------------------------------------------------------------------------- utilitas tampilan
def md(teks):
    """Escape karakter Markdown (termasuk $ untuk rumus) agar teks dari data tampil apa adanya."""
    teks = str(teks or "")
    for c in "\\`*_{}[]<>()#+-!|$~":
        teks = teks.replace(c, "\\" + c)
    return teks


def angka_id(nilai, desimal=1):
    """Format angka gaya Indonesia: 1.234,5"""
    s = f"{nilai:,.{desimal}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def format_jarak(lok):
    if lok["jarak_m"] < 1000:
        return f"{lok['jarak_m']} m"
    return f"{angka_id(lok['jarak_km'])} km"


def alamat_lengkap(lok):
    bagian = [
        lok["alamat"],
        lok["kelurahan"] and f"Kel. {lok['kelurahan']}",
        lok["kecamatan"] and f"Kec. {lok['kecamatan']}",
        lok["kota"],
    ]
    return ", ".join(b for b in bagian if b)


def nama_jenis_lokasi(daftar_jenis):
    return " / ".join(NAMA_JENIS[j] for j in daftar_jenis)


# ----------------------------------------------------------------------------- state & callback
def siapkan_state():
    ss = st.session_state
    ss.setdefault("posisi", None)            # {"lat", "lon", "sumber", "akurasi_m"}
    ss.setdefault("gps_aktif", False)        # sedang menunggu jawaban Geolocation API
    ss.setdefault("gps_ke", 0)               # penghitung agar tiap permintaan GPS memakai komponen baru
    ss.setdefault("gps_galat", None)
    ss.setdefault("klik_terakhir", None)     # klik peta terakhir yang sudah diproses
    ss.setdefault("konfirmasi_untuk", None)  # (label, confidence) yang sudah dikonfirmasi pengguna


def set_posisi(lat, lon, sumber, akurasi_m=None):
    st.session_state.posisi = {"lat": float(lat), "lon": float(lon), "sumber": sumber, "akurasi_m": akurasi_m}


def minta_gps():
    st.session_state.gps_aktif = True
    st.session_state.gps_ke += 1
    st.session_state.gps_galat = None


def konfirmasi(label, confidence):
    st.session_state.konfirmasi_untuk = (label, confidence)


# ----------------------------------------------------------------------------- peta
def tambah_penanda_pengguna(peta, pos):
    if pos["akurasi_m"] and pos["akurasi_m"] <= 2000:
        folium.Circle((pos["lat"], pos["lon"]), radius=pos["akurasi_m"], color=WARNA_PENGGUNA,
                      weight=1, fill=True, fill_opacity=0.1).add_to(peta)
    folium.CircleMarker((pos["lat"], pos["lon"]), radius=8, color="#ffffff", weight=3, fill=True,
                        fill_color=WARNA_PENGGUNA, fill_opacity=1, tooltip="Posisi Anda").add_to(peta)


def ikon_nomor(nomor, warna):
    return folium.DivIcon(
        icon_size=(28, 28), icon_anchor=(14, 14),
        html=(f'<div style="width:28px;height:28px;border-radius:50%;background:{warna};color:#fff;'
              'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);box-sizing:border-box;'
              'display:flex;align-items:center;justify-content:center;'
              f'font:600 13px/1 system-ui,-apple-system,sans-serif">{nomor}</div>'),
    )


def peta_pilih_posisi(pos):
    """Peta untuk memilih posisi dengan klik. Penanda dikirim lewat feature group agar
    tampilan peta (zoom dan geseran pengguna) tidak ter-reset setiap kali posisi berubah."""
    peta = folium.Map(location=PUSAT_JAKARTA, zoom_start=11, scrollWheelZoom=False, control_scale=True)
    penanda = folium.FeatureGroup(name="Posisi Anda")
    if pos:
        tambah_penanda_pengguna(penanda, pos)
    keluaran = st_folium(peta, key="peta_pilih", height=320, use_container_width=True,
                         returned_objects=["last_clicked"], feature_group_to_add=penanda,
                         wrap_longitude=True)
    klik = (keluaran or {}).get("last_clicked")
    if klik:
        titik = (round(klik["lat"], 6), round(klik["lng"], 6))
        if titik != st.session_state.klik_terakhir:
            st.session_state.klik_terakhir = titik
            set_posisi(*titik, "titik di peta")
            st.rerun()


def peta_hasil(pos, lokasi, radius_km):
    peta = folium.Map(location=(pos["lat"], pos["lon"]), zoom_start=14, scrollWheelZoom=False,
                      control_scale=True)
    if radius_km:
        folium.Circle((pos["lat"], pos["lon"]), radius=radius_km * 1000, color=WARNA_PENGGUNA, weight=1,
                      dash_array="6", fill=False, tooltip=f"Radius {angka_id(radius_km)} km").add_to(peta)
    for lok in reversed(lokasi):  # urutan 1 digambar paling akhir agar berada di atas
        nama = html.escape(lok["nama"])
        popup = (f"<b>{lok['urutan']}. {nama}</b><br>{html.escape(lok['jenis_lokasi_nama'])} · "
                 f"{format_jarak(lok)}<br><a href=\"{html.escape(lok['url_rute'])}\" target=\"_blank\" "
                 "rel=\"noopener\">Rute di Google Maps</a>")
        folium.Marker((lok["latitude"], lok["longitude"]),
                      icon=ikon_nomor(lok["urutan"], WARNA_PETA[lok["jenis_lokasi"]]),
                      tooltip=f"{lok['urutan']}. {nama}",
                      popup=folium.Popup(popup, max_width=260)).add_to(peta)
    tambah_penanda_pengguna(peta, pos)

    lat = [pos["lat"]] + [l["latitude"] for l in lokasi]
    lon = [pos["lon"]] + [l["longitude"] for l in lokasi]
    peta.fit_bounds([[min(lat), min(lon)], [max(lat), max(lon)]], padding=(30, 30), max_zoom=17)
    st_folium(peta, key="peta_hasil", height=360, use_container_width=True, returned_objects=[])


# ----------------------------------------------------------------------------- bagian halaman
def bagian_jenis_sampah(mesin):
    st.subheader("1. Jenis sampah")
    label = st.pills(
        "Pilih jenis sampah", options=list(mesin.aturan),
        format_func=lambda k: f"{IKON_LABEL.get(k, '')} {mesin.aturan[k]['nama_indonesia']}".strip(),
        key="label",
    )
    with st.expander("Dari model klasifikasi? Atur confidence", icon=":material/tune:"):
        confidence = st.slider("Confidence model", 0.0, 1.0, 1.0, 0.01, format="%.2f", key="confidence")
        st.caption(f"Biarkan 1,00 bila jenis sampah dipilih sendiri. Di bawah "
                   f"{angka_id(AMBANG_CONFIDENCE, 2)} sistem meminta konfirmasi lebih dulu.")
    if label:
        jenis = mesin.aturan[label]["jenis_lokasi"]
        st.caption(f"Disetor ke: **{nama_jenis_lokasi(jenis)}**" if jenis
                   else "Tidak disetor ke lokasi tertentu — lihat saran di bawah.")
    return label, confidence


def bagian_lokasi_pengguna():
    st.subheader("2. Lokasi Anda")
    st.button("Gunakan lokasi saya", icon=":material/my_location:", type="primary", width="stretch",
              on_click=minta_gps)

    ss = st.session_state
    if ss.gps_aktif:
        jawaban = get_geolocation(component_key=f"gps_{ss.gps_ke}")
        if jawaban is None:
            st.caption("Menunggu posisi dari peramban… Pilih **Izinkan** bila diminta.")
        else:
            if isinstance(jawaban, dict) and "coords" in jawaban:
                c = jawaban["coords"]
                set_posisi(c["latitude"], c["longitude"], "GPS", c.get("accuracy"))
            else:
                kode = (jawaban.get("error") or {}).get("code") if isinstance(jawaban, dict) else None
                ss.gps_galat = PESAN_GALAT_GPS.get(kode, PESAN_GALAT_GPS_LAIN)
            ss.gps_aktif = False
            st.rerun()  # jalankan ulang tanpa komponen GPS agar tidak tersisa ruang kosong

    if ss.gps_galat:
        st.warning(f"{ss.gps_galat} Anda juga bisa memilih titik di peta di bawah.", icon=":material/location_off:")

    pos = ss.posisi
    if pos:
        sumber = pos["sumber"]
        if pos["akurasi_m"]:
            sumber += f", akurasi ±{angka_id(pos['akurasi_m'], 0)} m"
        st.markdown(f":material/location_on: **Posisi dipakai:** {pos['lat']:.5f}, {pos['lon']:.5f} "
                    f"<span style='opacity:.7'>({sumber})</span>", unsafe_allow_html=True)

    with st.expander("Pilih titik di peta atau isi koordinat", icon=":material/map:"):
        st.caption("Ketuk peta untuk menandai posisi Anda.")
        peta_pilih_posisi(pos)

        with st.form("form_koordinat", border=False):
            k1, k2 = st.columns(2)
            lat = k1.number_input("Lintang (latitude)", min_value=-90.0, max_value=90.0, value=None,
                                  step=0.0001, format="%.6f", placeholder="-6.208800")
            lon = k2.number_input("Bujur (longitude)", min_value=-180.0, max_value=180.0, value=None,
                                  step=0.0001, format="%.6f", placeholder="106.845600")
            if st.form_submit_button("Pakai koordinat ini", icon=":material/check:", width="stretch"):
                if lat is None or lon is None:
                    st.error("Isi lintang dan bujur terlebih dahulu.")
                else:
                    set_posisi(lat, lon, "koordinat manual")
                    st.rerun()
        st.caption("Tips: di Google Maps, tekan lama sebuah titik untuk melihat dan menyalin koordinatnya.")
    return ss.posisi


def pengaturan_hasil():
    with st.expander("Atur jumlah hasil dan radius", icon=":material/filter_list:"):
        top_k = st.slider("Jumlah lokasi", 1, TOP_K_MAKS, 5, key="top_k")
        radius_km = None
        if st.toggle("Batasi radius pencarian", key="pakai_radius"):
            radius_km = st.slider("Radius (km)", 0.5, 20.0, 3.0, 0.5, format="%.1f km", key="radius_km")
    return top_k, radius_km


def kartu_lokasi(lok):
    with st.container(border=True):
        st.markdown(f"**{lok['urutan']}. {md(lok['nama'])}**")
        badge = [f":{WARNA_BADGE[lok['jenis_lokasi']]}-badge[{lok['jenis_lokasi_nama']}]",
                 f":blue-badge[:material/straighten: {format_jarak(lok)}]"]
        if lok["akurasi"] == "perkiraan":
            badge.append(":orange-badge[:material/warning: Titik perkiraan]")
        else:
            badge.append(":gray-badge[:material/check: Titik tepat]")
        jam = md(lok["jam_buka"]) if lok["jam_buka"] else "Jam buka tidak tercatat"
        baris = [
            " ".join(badge),
            f":material/location_on: {md(alamat_lengkap(lok))}",
            f":material/schedule: {jam}",
            f":material/info: {md(lok['keterangan'])}",
        ]
        st.markdown("  \n".join(baris))
        st.link_button("Rute di Google Maps", lok["url_rute"], icon=":material/directions:", width="stretch")


def tampilkan_hasil(hasil, pos, radius_km):
    if hasil["peringatan"]:
        st.warning(hasil["peringatan"], icon=":material/warning:")

    status = hasil["status"]
    if status == "perlu_konfirmasi":
        st.warning(hasil["pesan"], icon=":material/help:")
        st.button(f"Ya, ini {hasil['nama_indonesia'].lower()}", type="primary", width="stretch",
                  icon=":material/check:", on_click=konfirmasi, args=(hasil["label"], hasil["confidence"]))
        st.caption("Bukan? Pilih jenis sampah yang benar di bagian 1.")
        return
    if status == "tanpa_lokasi":
        st.info(hasil["pesan"], icon=":material/recycling:")
        return
    if status == "tidak_ditemukan":
        st.warning(f"{hasil['pesan']} Perbesar radius atau matikan batas radius.", icon=":material/search_off:")
        return

    lokasi = hasil["lokasi"]
    st.success(hasil["pesan"], icon=":material/recycling:")
    st.markdown(f"**{len(lokasi)} lokasi terdekat** · {nama_jenis_lokasi(hasil['jenis_lokasi'])}")
    peta_hasil(pos, lokasi, radius_km)
    legenda = [f"<span style='color:{WARNA_PENGGUNA}'>●</span> Posisi Anda"]
    if len(hasil["jenis_lokasi"]) > 1:
        legenda += [f"<span style='color:{WARNA_PETA[j]}'>●</span> {NAMA_JENIS[j]}" for j in hasil["jenis_lokasi"]]
    st.caption(" &nbsp; ".join(legenda), unsafe_allow_html=True)
    for lok in lokasi:
        kartu_lokasi(lok)
    catatan = ["Jarak dihitung dengan rumus Haversine (garis lurus); jarak tempuh di jalan biasanya lebih jauh."]
    if any(l["akurasi"] == "perkiraan" for l in lokasi):
        catatan.append("**Titik perkiraan**: koordinat lokasi belum persis, jadi cocokkan juga dengan alamatnya.")
    st.caption("  \n".join(catatan))


def bagian_tentang(mesin):
    per_jenis = {j: len(mesin.indeks_jenis[j]) for j in JENIS_LOKASI}
    with st.expander("Tentang EcoDrop", icon=":material/info:"):
        st.markdown(
            f"- **{angka_id(len(mesin.lokasi), 0)} lokasi** di lima kota administrasi DKI Jakarta "
            "(tanpa Kepulauan Seribu): "
            + ", ".join(f"{NAMA_JENIS[j].lower() if j != 'tps' else 'TPS'} {angka_id(n, 0)}"
                        for j, n in per_jenis.items()) + ".\n"
            "- Sumber data: e-Bank Sampah Jakarta, Portal E-Waste DLH DKI, dan layer TPS di Jakarta Satu "
            "(Dinas Lingkungan Hidup DKI Jakarta).\n"
            "- Jarak dihitung dengan rumus Haversine (R = 6.371 km).\n"
            "- Jenis sampah mengikuti 12 kelas dataset Garbage Classification (Mohamed, 2021)."
        )


# ----------------------------------------------------------------------------- halaman utama
def main(mesin):
    label, confidence = bagian_jenis_sampah(mesin)
    if not label:
        st.info("Pilih jenis sampah untuk mulai.", icon=":material/touch_app:")
        return

    dikonfirmasi = st.session_state.konfirmasi_untuk == (label, round(confidence, 4))
    butuh_lokasi = bool(mesin.aturan[label]["jenis_lokasi"])

    if not butuh_lokasi:
        st.subheader("2. Saran penanganan")
        hasil = mesin.rekomendasi(label, confidence, *PUSAT_JAKARTA, dikonfirmasi=dikonfirmasi)
        tampilkan_hasil(hasil, None, None)
        return

    pos = bagian_lokasi_pengguna()
    st.subheader("3. Lokasi terdekat")
    top_k, radius_km = pengaturan_hasil()
    if not pos:
        st.info("Tentukan lokasi Anda di bagian 2 untuk melihat lokasi terdekat.", icon=":material/location_on:")
        return
    try:
        hasil = mesin.rekomendasi(label, confidence, pos["lat"], pos["lon"], top_k=top_k,
                                  radius_km=radius_km, dikonfirmasi=dikonfirmasi)
    except (KeyError, ValueError) as e:
        st.error(str(e).strip("'\""))
        return
    tampilkan_hasil(hasil, pos, radius_km)


st.set_page_config(page_title="EcoDrop — Lokasi Setor Sampah", page_icon="♻️", layout="centered")
siapkan_state()
mesin = muat_mesin()

st.title("♻️ EcoDrop")
st.caption("Cari lokasi penyetoran sampah terdekat di DKI Jakarta: bank sampah, dropbox e-waste, "
           "collection point B3, dan TPS.")
main(mesin)
st.divider()
bagian_tentang(mesin)
