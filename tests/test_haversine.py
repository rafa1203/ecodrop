"""Pengujian unit fungsi Haversine. Jalankan: pytest -q"""

import sys
from pathlib import Path

import numpy as np
import pytest
from pyproj import Geod

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ecodrop.haversine import haversine_km, haversine_km_vektor  # noqa: E402

GEOD = Geod(ellps="WGS84")
MONAS = (-6.175392, 106.827153)
BUNDARAN_HI = (-6.194990, 106.823060)
BLOK_M = (-6.244310, 106.801750)
TANJUNG_PRIOK = (-6.110000, 106.880000)


def geodesik_km(a, b):
    _, _, m = GEOD.inv(a[1], a[0], b[1], b[0])
    return m / 1000


def test_titik_sama_nol():
    assert haversine_km(*MONAS, *MONAS) == 0


def test_simetris():
    assert haversine_km(*MONAS, *BLOK_M) == pytest.approx(haversine_km(*BLOK_M, *MONAS))


@pytest.mark.parametrize("a,b", [(MONAS, BUNDARAN_HI), (MONAS, BLOK_M), (BLOK_M, TANJUNG_PRIOK)])
def test_selisih_dengan_geodesik_di_bawah_0_6_persen(a, b):
    # Haversine menganggap Bumi bulat sempurna (R = 6371 km). Di lintang Jakarta (sekitar 6° LS),
    # selisihnya dengan jarak geodesik elipsoid WGS84 berkisar -0,12% (arah timur-barat)
    # sampai +0,56% (arah utara-selatan).
    h, g = haversine_km(*a, *b), geodesik_km(a, b)
    assert abs(h - g) / g < 0.006


def test_versi_vektor_sama_dengan_skalar():
    lat2 = np.array([BUNDARAN_HI[0], BLOK_M[0], TANJUNG_PRIOK[0]])
    lon2 = np.array([BUNDARAN_HI[1], BLOK_M[1], TANJUNG_PRIOK[1]])
    v = haversine_km_vektor(MONAS[0], MONAS[1], lat2, lon2)
    s = [haversine_km(*MONAS, la, lo) for la, lo in zip(lat2, lon2)]
    assert np.allclose(v, s)
