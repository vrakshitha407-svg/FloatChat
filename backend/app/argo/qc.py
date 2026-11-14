"""
Quality Control (QC) handling and parameter resolution for ARGO observations.
Enforces ARGO scientific standards, preserves original QC flags, and resolves adjusted vs raw variables.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.argo.constants import (
    DATA_MODE_ADJUSTED,
    DATA_MODE_DELAYED,
    DATA_MODE_REALTIME,
    SCIENTIFIC_VALID_QC,
)


class ArgoQualityControl:
    """Manages ARGO scientific quality control filtering and variable resolution."""

    @staticmethod
    def is_valid_profile_metadata(
        position_qc: str,
        juld_qc: str,
        lat: float,
        lon: float,
        dt: Any,
    ) -> bool:
        """
        Validates profile-level location and time.
        Only profiles with valid coordinates and timestamp flags are indexed.
        """
        if dt is None:
            return False
        if np.isnan(lat) or np.isnan(lon):
            return False
        # Valid latitude/longitude bounds
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return False
        # Check standard ARGO position and Julian day QC flags
        if position_qc not in SCIENTIFIC_VALID_QC:
            return False
        if juld_qc not in SCIENTIFIC_VALID_QC:
            return False
        return True

    @staticmethod
    def resolve_parameter_values(
        param_name: str,
        param_dict: Dict[str, Any],
        data_mode: str,
    ) -> Tuple[np.ndarray, np.ndarray, str]:
        """
        Selects between adjusted and raw variables based on DATA_MODE and availability.
        Returns:
            (values_array, qc_flags_array, value_source)
            where value_source is 'adjusted' or 'raw'.
        """
        mode = data_mode.upper() if data_mode else DATA_MODE_REALTIME
        adj_var = f"{param_name}_ADJUSTED"
        adj_qc_var = f"{param_name}_ADJUSTED_QC"

        # Check if file mode qualifies for adjusted variables ('D' or 'A')
        if mode in (DATA_MODE_DELAYED, DATA_MODE_ADJUSTED):
            adj_vals = param_dict.get(adj_var)
            adj_qc = param_dict.get(adj_qc_var)

            # Check if adjusted variable actually exists and has non-NaN entries
            if adj_vals is not None and len(adj_vals) > 0 and np.any(~np.isnan(adj_vals)):
                qc_array = adj_qc if adj_qc is not None and len(adj_qc) == len(adj_vals) else np.array([""] * len(adj_vals))
                return adj_vals, qc_array, "adjusted"

        # Fallback to unadjusted raw variables
        raw_vals = param_dict.get(param_name, np.array([]))
        raw_qc = param_dict.get(f"{param_name}_QC")
        qc_array = raw_qc if raw_qc is not None and len(raw_qc) == len(raw_vals) else np.array([""] * len(raw_vals))
        return raw_vals, qc_array, "raw"

    @staticmethod
    def apply_qc_filter(
        values: np.ndarray,
        qc_flags: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Masks values that fail scientific QC ('1' or '2') with NaN,
        while strictly preserving the original QC flags array unaltered.
        """
        if len(values) == 0:
            return values, qc_flags

        cleaned = values.copy().astype(float)
        # Identify bad or missing flags: anything NOT in {'1', '2'}
        for i, flag in enumerate(qc_flags):
            flag_str = str(flag).strip()
            if flag_str not in SCIENTIFIC_VALID_QC:
                cleaned[i] = np.nan

        # Return the scientifically filtered values alongside the untouched original QC flags
        return cleaned, qc_flags
