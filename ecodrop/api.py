"""
Endpoint FastAPI EcoDrop.

Berdiri sendiri:
    uvicorn ecodrop.api:app --reload
    lalu buka http://127.0.0.1:8000/docs

Dipasang di aplikasi lain berbasis FastAPI:
    from ecodrop.api import router as ecodrop_router
    app.include_router(ecodrop_router)
"""

from typing import List, Literal, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .rekomendasi import JENIS_LOKASI, MesinRekomendasi

mesin = MesinRekomendasi()
router = APIRouter(prefix="/ecodrop", tags=["EcoDrop"])

JenisLokasi = Literal["bank_sampah", "dropbox_ewaste", "collection_point_b3", "tps"]


class PermintaanRekomendasi(BaseModel):
    label: str = Field(..., description="Label jenis sampah (12 kelas Garbage Classification), mis. 'plastic'", examples=["plastic"])
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


@router.get("/label")
def daftar_label():
    """Daftar 12 label jenis sampah dan jenis lokasi tujuannya."""
    return mesin.daftar_label()


@router.post("/rekomendasi", response_model=HasilRekomendasi)
def rekomendasi(req: PermintaanRekomendasi):
    """Rekomendasi lokasi penyetoran terdekat berdasarkan label jenis sampah."""
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


app = FastAPI(title="EcoDrop API", version="1.0.0",
              description="Rekomendasi lokasi penyetoran sampah terdekat di DKI Jakarta dengan metode Haversine.")
app.include_router(router)
