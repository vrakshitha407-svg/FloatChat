"""
Data-Dependent Integration Tests for ARGO Ingestion Pipeline.
Requires real sample NetCDF files in data/raw/.
Cleanly skips if sample files are not present.
"""

import hashlib
from pathlib import Path
import pytest
import numpy as np

from app.argo.processor import ArgoProcessor
from app.argo.query import ArgoQueryEngine
from app.argo.reader import ArgoNetCDFReader

# Path resolution relative to repository root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
SAMPLE_NC_FILES = sorted(list(RAW_DIR.glob("*.nc")))

# Pytest skip condition when sample data has not yet been fetched
skip_if_no_sample_data = pytest.mark.skipif(
    len(SAMPLE_NC_FILES) == 0,
    reason="Sample ARGO NetCDF files not found in data/raw/. Run backend/scripts/download_sample_argo.py first."
)


def get_file_md5(file_path: Path) -> str:
    """Calculates MD5 checksum of a file to verify immutability."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


@skip_if_no_sample_data
class TestArgoIntegration:
    """Integration test suite against genuine ARGO NetCDF files."""

    def test_raw_netcdf_immutability(self):
        """Verifies that reading the NetCDF file leaves the raw file completely unaltered."""
        first_file = SAMPLE_NC_FILES[0]
        initial_hash = get_file_md5(first_file)
        initial_size = first_file.stat().st_size

        # Perform read operations
        reader = ArgoNetCDFReader(first_file)
        profile_data = reader.read_profile(0)
        assert profile_data["platform_id"] != ""

        # Post-read immutability check
        post_hash = get_file_md5(first_file)
        post_size = first_file.stat().st_size

        assert initial_size == post_size, "Raw NetCDF file size changed during reading!"
        assert initial_hash == post_hash, "Raw NetCDF file content was modified during reading!"

    def test_reader_extracts_real_profile(self):
        """Verifies parsing of real coordinates, timestamps, and parameters from sample profile."""
        first_file = SAMPLE_NC_FILES[0]
        reader = ArgoNetCDFReader(first_file)
        profile = reader.read_profile(0)

        # Verified metadata from INCOIS Float 1900121
        assert profile["platform_id"] == "1900121"
        assert profile["cycle_number"] == 1
        assert profile["data_mode"] == "D"
        assert profile["position_qc"] == "1"
        assert profile["juld_qc"] == "1"
        assert profile["datetime"] is not None

        # Coordinates within Indian Ocean
        assert -15.0 <= profile["latitude"] <= 0.0
        assert 50.0 <= profile["longitude"] <= 65.0

        # Parameters exist with 45 depth levels
        params = profile["parameters"]
        assert "PRES" in params and len(params["PRES"]) == 45
        assert "TEMP" in params and len(params["TEMP"]) == 45
        assert "PSAL" in params and len(params["PSAL"]) == 45

    def test_processor_ingestion_and_parquet_generation(self):
        """Verifies end-to-end processing and generation of Parquet datasets with preserved QC flags."""
        processor = ArgoProcessor(raw_dir=RAW_DIR, processed_dir=PROCESSED_DIR)
        result = processor.process_all(save_parquet=True)

        assert result["success"] is True
        assert result["num_files"] >= 1
        assert result["num_profiles"] >= 1
        assert result["num_observations"] > 0

        # Verify output Parquet files exist
        index_file = PROCESSED_DIR / "profiles_index.parquet"
        obs_file = PROCESSED_DIR / "argo_observations.parquet"
        assert index_file.exists() and index_file.stat().st_size > 0
        assert obs_file.exists() and obs_file.stat().st_size > 0

        df_obs = result["df_obs"]

        # Verify that original QC flag columns are preserved
        assert "pres_qc" in df_obs.columns
        assert "temp_qc" in df_obs.columns
        assert "psal_qc" in df_obs.columns
        assert "position_qc" in df_obs.columns
        assert "juld_qc" in df_obs.columns

        # Verify that lineage columns are present
        assert "temp_source" in df_obs.columns
        assert "psal_source" in df_obs.columns

        # Scientific bounds verification (sanity check on real observations)
        valid_temps = df_obs["temperature_c"].dropna()
        valid_psal = df_obs["salinity_psu"].dropna()
        valid_pres = df_obs["pressure_dbar"].dropna()

        assert len(valid_temps) > 0
        assert 0.0 <= valid_temps.min() and valid_temps.max() <= 35.0  # Real ocean temperatures in Celsius
        assert 30.0 <= valid_psal.min() and valid_psal.max() <= 40.0  # Real ocean salinity in PSU
        assert valid_pres.min() >= 0.0  # Pressure in dbar (positive)

    def test_query_engine_on_real_data(self):
        """Verifies query engine on the generated Parquet datasets."""
        query_engine = ArgoQueryEngine(processed_dir=PROCESSED_DIR)
        summary = query_engine.get_summary()

        assert summary["status"] == "ready"
        assert summary["total_profiles"] >= 1
        assert "1900121" in summary["platforms"]

        # Query by bounding box enclosing the Indian Ocean coordinates
        bbox_profiles = query_engine.filter_profiles(
            min_lat=-15.0,
            max_lat=0.0,
            min_lon=50.0,
            max_lon=65.0,
        )
        assert len(bbox_profiles) >= 1

        # Query shallow ocean observations (0 to 200 dbar)
        shallow_obs = query_engine.filter_observations(
            platform_id="1900121",
            min_depth=0.0,
            max_depth=200.0,
        )
        assert len(shallow_obs) > 0
        assert shallow_obs["pressure_dbar"].max() <= 200.0
