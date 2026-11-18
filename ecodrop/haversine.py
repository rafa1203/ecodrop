"""
Perhitungan jarak great-circle dengan rumus Haversine.

    a = sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2)
    d = 2R · arcsin(√a)

φ = latitude, λ = longitude (radian), R = jari-jari rata-rata Bumi.
"""

import math

import numpy as np

R_BUMI_KM = 6371.0  # jari-jari rata-rata Bumi (km)


def haversine_km(lat1, lon1, lat2, lon2):
    """Jarak dua titik (derajat desimal) dalam kilometer."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R_BUMI_KM * math.asin(math.sqrt(a))


def haversine_km_vektor(lat1, lon1, lat2, lon2):
    """
    Versi vektor (numpy): jarak dari satu titik (lat1, lon1) ke banyak titik
    (lat2, lon2 berupa array). Dipakai untuk menghitung jarak ke ribuan lokasi sekaligus.
    """
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = phi2 - phi1
    dlam = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return 2 * R_BUMI_KM * np.arcsin(np.sqrt(a))
