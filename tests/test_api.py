"""Pengujian black-box endpoint EcoDrop. Jalankan: pytest -q"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))
sys.path.insert(0, str(AKAR / "pengujian"))

from ecodrop.api import app  # noqa: E402
from skenario_blackbox import SKENARIO, periksa  # noqa: E402

klien = TestClient(app)


@pytest.mark.parametrize("s", SKENARIO, ids=[s["kode"] for s in SKENARIO])
def test_skenario(s):
    if s["metode"] == "POST":
        r = klien.post(s["url"], json=s["data"])
    else:
        r = klien.get(s["url"], params=s["data"])
    lulus, aktual = periksa(s, r)
    assert lulus, f"{s['kode']}: {aktual}"
