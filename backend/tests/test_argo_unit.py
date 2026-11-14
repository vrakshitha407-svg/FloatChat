"""
Independent Unit Tests for ARGO Processing & QC Logic.
Runs without network access or downloaded ARGO NetCDF files.
"""

from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest

from app.argo.constants import ARGO_EPOCH, SCIENTIFIC_VALID_QC
from app.argo.qc import ArgoQualityControl
from app.argo.query import ArgoQueryEngine
from app.argo.reader import decode_byte_string, decode_juld


class TestArgoDecodingUnit:
    """Tests for string decoding and Julian date calculation."""

    def test_decode_byte_string_variations(self):
        """Verifies byte string decoding across types."""
        assert decode_byte_string(b"1900121") == "1900121"
        assert decode_byte_string("1900121") == "1900121"
        assert decode_byte_string(np.array([b"1", b"9", b"0"])) == "190"
        assert decode_byte_string(None) == ""

    def test_decode_juld_epoch(self):
        """Verifies JULD conversion from 1950-01-01 epoch."""
        # 0 days after 1950-01-01 00:00:00 UTC
        dt_zero = decode_juld(0.0)
        assert dt_zero == datetime(1950, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 1 day after epoch
        dt_one = decode_juld(1.0)
        assert dt_one == datetime(1950, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        # NaN handling
        assert decode_juld(np.nan) is None
        assert decode_juld(None) is None


class TestArgoQualityControlUnit:
    """Tests for QC validation, adjusted parameter resolution, and flag preservation."""

    def test_profile_metadata_validation(self):
        """Verifies metadata validation rejects invalid coordinates or bad QC."""
        dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
        # Valid profile
        assert ArgoQualityControl.is_valid_profile_metadata("1", "1", 10.0, 60.0, dt) is True
        assert ArgoQualityControl.is_valid_profile_metadata("2", "1", -15.0, 75.0, dt) is True

        # Invalid position QC or JULD QC
        assert ArgoQualityControl.is_valid_profile_metadata("4", "1", 10.0, 60.0, dt) is False
        assert ArgoQualityControl.is_valid_profile_metadata("1", "3", 10.0, 60.0, dt) is False

        # Invalid coordinates
        assert ArgoQualityControl.is_valid_profile_metadata("1", "1", 95.0, 60.0, dt) is False
        assert ArgoQualityControl.is_valid_profile_metadata("1", "1", np.nan, 60.0, dt) is False

    def test_resolve_parameter_delayed_mode(self):
        """Verifies that DATA_MODE 'D' selects adjusted variables when present."""
        param_dict = {
            "TEMP": np.array([25.0, 24.0]),
            "TEMP_QC": np.array(["1", "1"]),
            "TEMP_ADJUSTED": np.array([25.1, 24.05]),
            "TEMP_ADJUSTED_QC": np.array(["1", "1"]),
        }
        vals, qc, src = ArgoQualityControl.resolve_parameter_values("TEMP", param_dict, "D")
        assert src == "adjusted"
        np.testing.assert_array_equal(vals, [25.1, 24.05])

    def test_resolve_parameter_realtime_mode(self):
        """Verifies that DATA_MODE 'R' selects raw variables even if adjusted key exists."""
        param_dict = {
            "TEMP": np.array([25.0, 24.0]),
            "TEMP_QC": np.array(["1", "1"]),
            "TEMP_ADJUSTED": np.array([25.1, 24.05]),
            "TEMP_ADJUSTED_QC": np.array(["1", "1"]),
        }
        vals, qc, src = ArgoQualityControl.resolve_parameter_values("TEMP", param_dict, "R")
        assert src == "raw"
        np.testing.assert_array_equal(vals, [25.0, 24.0])

    def test_resolve_parameter_fallback_when_adjusted_all_nan(self):
        """Verifies fallback to raw when adjusted variable is entirely NaN."""
        param_dict = {
            "PSAL": np.array([35.2, 35.4]),
            "PSAL_QC": np.array(["1", "1"]),
            "PSAL_ADJUSTED": np.array([np.nan, np.nan]),
            "PSAL_ADJUSTED_QC": np.array(["4", "4"]),
        }
        vals, qc, src = ArgoQualityControl.resolve_parameter_values("PSAL", param_dict, "D")
        assert src == "raw"
        np.testing.assert_array_equal(vals, [35.2, 35.4])

    def test_qc_filter_masks_bad_data_and_preserves_flags(self):
        """
        Verifies that observations with flags '3', '4', '9' are masked to NaN,
        while original QC flags are completely preserved in the returned array.
        """
        values = np.array([28.5, 27.0, 15.0, 999.0])
        qc_flags = np.array(["1", "2", "4", "9"])

        cleaned, preserved_qc = ArgoQualityControl.apply_qc_filter(values, qc_flags)

        # Flag '1' (Good) and '2' (Probably Good) are preserved
        assert cleaned[0] == 28.5
        assert cleaned[1] == 27.0
        # Flag '4' (Bad) and '9' (Missing) are masked with NaN
        assert np.isnan(cleaned[2])
        assert np.isnan(cleaned[3])

        # Original QC flags remain completely intact
        np.testing.assert_array_equal(preserved_qc, ["1", "2", "4", "9"])


class TestArgoQueryEngineUnit:
    """Tests for spatial, temporal, and depth query filters using in-memory DataFrame fixtures."""

    @pytest.fixture
    def query_engine_with_mock_data(self, tmp_path):
        """Sets up a temporary directory with mock processed Parquet data for unit testing."""
        idx_data = pd.DataFrame([
            {
                "platform_id": "1900121",
                "cycle_number": 1,
                "datetime": "2023-01-10T12:00:00",
                "latitude": 10.0,
                "longitude": 65.0,
                "min_pressure_dbar": 5.0,
                "max_pressure_dbar": 2000.0,
            },
            {
                "platform_id": "1900121",
                "cycle_number": 2,
                "datetime": "2023-01-20T12:00:00",
                "latitude": 12.0,
                "longitude": 66.0,
                "min_pressure_dbar": 5.0,
                "max_pressure_dbar": 2000.0,
            },
            {
                "platform_id": "1900999",
                "cycle_number": 1,
                "datetime": "2023-02-15T12:00:00",
                "latitude": -5.0,
                "longitude": 80.0,
                "min_pressure_dbar": 5.0,
                "max_pressure_dbar": 1500.0,
            },
        ])

        obs_data = pd.DataFrame([
            {"platform_id": "1900121", "cycle_number": 1, "pressure_dbar": 10.0, "temperature_c": 28.0, "salinity_psu": 35.5, "pres_qc": "1", "temp_qc": "1", "psal_qc": "1"},
            {"platform_id": "1900121", "cycle_number": 1, "pressure_dbar": 500.0, "temperature_c": 12.0, "salinity_psu": 34.8, "pres_qc": "1", "temp_qc": "1", "psal_qc": "1"},
            {"platform_id": "1900121", "cycle_number": 1, "pressure_dbar": 1200.0, "temperature_c": 4.5, "salinity_psu": 34.7, "pres_qc": "1", "temp_qc": "1", "psal_qc": "1"},
        ])

        idx_data.to_parquet(tmp_path / "profiles_index.parquet", index=False)
        obs_data.to_parquet(tmp_path / "argo_observations.parquet", index=False)

        return ArgoQueryEngine(processed_dir=tmp_path)

    def test_query_filter_bounding_box(self, query_engine_with_mock_data):
        """Verifies spatial bounding box filtering."""
        # Query box enclosing only the two Northern Hemisphere profiles
        results = query_engine_with_mock_data.filter_profiles(min_lat=0.0, max_lat=20.0, min_lon=60.0, max_lon=70.0)
        assert len(results) == 2
        assert set(results["cycle_number"]) == {1, 2}

    def test_query_filter_date_range(self, query_engine_with_mock_data):
        """Verifies temporal filtering."""
        results = query_engine_with_mock_data.filter_profiles(
            start_date="2023-01-01",
            end_date="2023-01-15",
        )
        assert len(results) == 1
        assert results.iloc[0]["cycle_number"] == 1

    def test_query_filter_depth_range(self, query_engine_with_mock_data):
        """Verifies depth/pressure range filtering on vertical observations."""
        obs = query_engine_with_mock_data.filter_observations(min_depth=0.0, max_depth=600.0)
        assert len(obs) == 2
        assert max(obs["pressure_dbar"]) == 500.0
