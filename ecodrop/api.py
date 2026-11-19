"""
Endpoint FastAPI EcoDrop.

Berdiri sendiri:
    uvicorn ecodrop.api:app --reload
    lalu buka http://127.0.0.1:8000/docs

Dipasang di aplikasi lain berbasis FastAPI:
    from ecodrop.api import router as ecodrop_router
    app.include_router(ecodrop_router)
"""

from functools import lru_cache
from io import BytesIO
from typing import List, Literal, Optional

from fastapi import APIRouter, FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from .rekomendasi import AMBANG_CONFIDENCE, JENIS_LOKASI, MesinRekomendasi

mesin = MesinRekomendasi()
UKURAN_FOTO_MAKS = 10 * 1024 * 1024  # 10 MB


@lru_cache(maxsize=1)
def pengenal_foto():
    from .foto import PengenalFoto  # dimuat saat pertama dibutuhkan (mengunduh model bila belum ada)
    return PengenalFoto()
router = APIRouter(prefix="/ecodrop", tags=["EcoDrop"])

JenisLokasi = Literal["bank_sampah", "dropbox_ewaste", "collection_point_b3", "tps"]


class PermintaanRekomendasi(BaseModel):
    label: str = Field(..., description="Kode jenis sampah (lihat /ecodrop/jenis), mis. 'AN05', "
                       "atau label umum 12 kelas Garbage Classification, mis. 'plastic'", examples=["AN05"])
    confidence: float = Field(..., ge=0, le=1, description="Nilai confidence model (0 sampai 1)", examples=[0.92])
    latitude: float = Field(..., ge=-90, le=90, examples=[-6.2088])
    longitude: float = Field(..., ge=-180, le=180, examples=[106.8456])
    top_k: int = Field(5, ge=1, le=20, description="Jumlah lokasi terdekat yang dikembalikan")
    radius_km: Optional[float] = Field(None, gt=0, description="Batas jarak maksimum (opsional)")
    dikonfirmasi: bool = Field(False, description="True bila pengguna sudah mengonfirmasi jenis sampah")


class Lokasi(BaseModel):
    urutan: int
    id: str
    nama: str
    jenis_lokasi: str
    jenis_lokasi_nama: str
    jarak_km: float
    jarak_m: int
    latitude: float
    longitude: float
    alamat: str
    kelurahan: str
    kecamatan: str
    kota: str
    keterangan: str
    jam_buka: str
    akurasi: str
    url_rute: str


class HasilRekomendasi(BaseModel):
    label: str
    nama_indonesia: str
    kelompok: str
    confidence: float
    jenis_lokasi: List[str]
    status: Literal["ok", "perlu_konfirmasi", "tanpa_lokasi", "tidak_ditemukan"]
    pesan: str
    peringatan: Optional[str]
    lokasi: List[Lokasi]


@router.get("/kesehatan")
def kesehatan():
    """Cek layanan dan jumlah data lokasi yang dimuat."""
    return {"status": "ok", "jumlah_lokasi": len(mesin.lokasi),
            "per_jenis": {j: int(len(mesin.indeks_jenis[j])) for j in JENIS_LOKASI}}


class SaranJenis(BaseModel):
    kode: str
    nama_indonesia: str
    peluang: float
    jenis_lokasi: List[str]


class HasilFoto(BaseModel):
    saran: List[SaranJenis]
    ambang_confidence: float
    yakin: bool


@router.get("/label")
def daftar_label():
    """Daftar 12 label umum (kelas Garbage Classification) dan jenis lokasi tujuannya."""
    return mesin.daftar_label()


@router.get("/jenis")
def daftar_jenis():
    """Daftar 58 jenis sampah EcoDrop beserta contoh dan jenis lokasi tujuannya."""
    return mesin.daftar_jenis()


@router.post("/kenali-foto", response_model=HasilFoto)
async def kenali_foto(foto: UploadFile = File(..., description="Foto sampah (JPG, PNG, atau WEBP)"),
                      top_k: int = Query(3, ge=1, le=10)):
    """Kenali jenis sampah dari foto (zero-shot CLIP). Hasilnya saran; pengguna tetap memilih jenis yang benar,
    lalu memanggil /rekomendasi dengan kode jenis tersebut."""
    from PIL import Image, UnidentifiedImageError

    isi = await foto.read(UKURAN_FOTO_MAKS + 1)
    if len(isi) > UKURAN_FOTO_MAKS:
        raise HTTPException(status_code=413, detail="Ukuran foto maksimal 10 MB.")
    try:
        gambar = Image.open(BytesIO(isi))
        gambar.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=422, detail="Berkas tidak dapat dibaca sebagai gambar.")
    try:
        pengenal = pengenal_foto()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model foto belum tersedia: {e}")
    saran = [{**s, "nama_indonesia": mesin.jenis[s["kode"]]["nama_indonesia"],
              "jenis_lokasi": mesin.jenis[s["kode"]]["jenis_lokasi"]} for s in pengenal.kenali(gambar, top_k)]
    return {"saran": saran, "ambang_confidence": AMBANG_CONFIDENCE,
            "yakin": saran[0]["peluang"] >= AMBANG_CONFIDENCE}


@router.post("/rekomendasi", response_model=HasilRekomendasi)
def rekomendasi(req: PermintaanRekomendasi):
    """Rekomendasi lokasi penyetoran terdekat berdasarkan jenis sampah (kode jenis atau label umum)."""
    try:
        return mesin.rekomendasi(req.label, req.confidence, req.latitude, req.longitude,
                                 req.top_k, req.radius_km, req.dikonfirmasi)
    except KeyError as e:
        raise HTTPException(status_code=422, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/lokasi-terdekat", response_model=List[Lokasi])
def lokasi_terdekat(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    jenis_lokasi: List[JenisLokasi] = Query(..., description="Boleh lebih dari satu"),
    top_k: int = Query(5, ge=1, le=20),
    radius_km: Optional[float] = Query(None, gt=0),
):
    """Cari lokasi terdekat langsung berdasarkan jenis lokasi (tanpa klasifikasi gambar)."""
    try:
        return mesin.cari_terdekat(latitude, longitude, jenis_lokasi, top_k, radius_km)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


app = FastAPI(title="EcoDrop API", version="1.1.0",
              description="Rekomendasi lokasi penyetoran sampah terdekat di DKI Jakarta dengan metode Haversine.")
app.include_router(router)
