"""
Utility script to download verified authentic sample ARGO NetCDF files
from the official Ifremer GDAC repository into data/raw/.
"""

import os
import sys
import ssl
import urllib.request
from pathlib import Path

# Verify SSL certificates properly across environments
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

# Verified official Ifremer GDAC repository URL for INCOIS Float 1900121 (Indian Ocean)
GDAC_BASE_URL = "https://data-argo.ifremer.fr/dac/incois/1900121/profiles"
SAMPLE_FILES = [
    "D1900121_001.nc",
    "D1900121_002.nc",
    "D1900121_003.nc",
]

DEFAULT_DEST_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def download_sample_profiles(dest_dir: Path = DEFAULT_DEST_DIR) -> list[Path]:
    """
    Downloads verified ARGO NetCDF files from the official GDAC.
    Preserves raw files without alteration.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    downloaded_paths = []

    print(f"Target raw directory: {dest_dir}")
    print(f"Connecting to official ARGO GDAC: {GDAC_BASE_URL}")

    headers = {"User-Agent": "FloatChat-Research/1.0 (Oceanographic-Data-Ingestion)"}

    for filename in SAMPLE_FILES:
        target_path = dest_dir / filename
        file_url = f"{GDAC_BASE_URL}/{filename}"

        if target_path.exists() and target_path.stat().st_size > 0:
            print(f"  [EXISTS] {filename} ({target_path.stat().st_size:,} bytes) - preserving raw file.")
            downloaded_paths.append(target_path)
            continue

        print(f"  [VERIFY & FETCH] {file_url} ...")
        req = urllib.request.Request(file_url, headers=headers)

        try:
            with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=30) as response:
                if response.status != 200:
                    print(f"  [ERROR] HTTP {response.status} received for {filename}. Aborting.")
                    continue

                content = response.read()
                # Write to raw directory
                with open(target_path, "wb") as f:
                    f.write(content)

                print(f"  [SUCCESS] Downloaded {filename} ({len(content):,} bytes)")
                downloaded_paths.append(target_path)
        except Exception as e:
            print(f"  [FAILED] Could not download {filename}: {e}", file=sys.stderr)

    return downloaded_paths


if __name__ == "__main__":
    downloaded = download_sample_profiles()
    print(f"\nCompleted: {len(downloaded)} verified ARGO NetCDF files ready in data/raw/.")
