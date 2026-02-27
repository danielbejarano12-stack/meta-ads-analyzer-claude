#!/usr/bin/env python3
"""
Sync ventas data from Google Sheets.
Downloads the 'Ventas x mes 2026' sheet as CSV for dashboard integration.

Usage:
    python3 sync_ventas.py           # Download fresh data
    python3 sync_ventas.py --force   # Force re-download even if recent

The CSV is saved to ventas_2026.csv in the same directory.
"""

import os
import sys
import time
import urllib.request
import urllib.error

# ── Configuration ───────────────────────────────────────────────────────────
SHEET_ID = "19uNOkJ39tTLP6jYQADAN8CFrr2g8ViIaylMOat51Ghk"
GID = "992221371"  # "Ventas x mes 2026" tab
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "ventas_2026.csv")
CACHE_MAX_AGE = 3600  # Skip download if file is less than 1 hour old


def download_sheet():
    """Download the Google Sheet as CSV."""
    print(f"📥 Descargando datos de ventas desde Google Sheets...")
    print(f"   Sheet: {SHEET_ID}")
    print(f"   Tab GID: {GID}")

    try:
        req = urllib.request.Request(EXPORT_URL, headers={
            "User-Agent": "Mozilla/5.0 (Meta Ads Dashboard Sync)"
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()

        with open(OUTPUT_FILE, "wb") as f:
            f.write(data)

        # Validate
        lines = data.decode("utf-8").strip().split("\n")
        print(f"✅ Descarga exitosa: {len(lines)} filas ({len(data)/1024:.1f} KB)")
        print(f"   Guardado en: {OUTPUT_FILE}")
        return True

    except urllib.error.HTTPError as e:
        print(f"❌ Error HTTP {e.code}: {e.reason}")
        if e.code == 403:
            print("   → El Sheet no es público. Verifica permisos de acceso.")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Error de conexión: {e.reason}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False


def is_cache_fresh():
    """Check if the cached CSV is recent enough."""
    if not os.path.exists(OUTPUT_FILE):
        return False
    age = time.time() - os.path.getmtime(OUTPUT_FILE)
    return age < CACHE_MAX_AGE


def main():
    force = "--force" in sys.argv

    if not force and is_cache_fresh():
        age_min = (time.time() - os.path.getmtime(OUTPUT_FILE)) / 60
        print(f"⏭️  Cache fresco ({age_min:.0f} min). Usa --force para re-descargar.")
        return True

    return download_sheet()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
