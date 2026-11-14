"""
NetCDF Reader for ARGO oceanographic float profiles using Xarray.
Opens files strictly in read-only mode, preserving the raw dataset unaltered.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import xarray as xr

from app.argo.constants import ARGO_EPOCH, CORE_PARAMETERS


def decode_byte_string(val: Any) -> str:
    """Decodes byte array, numpy character array, or string into a clean stripped string."""
    if val is None:
        return ""
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="ignore").strip()
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, np.ndarray):
        if val.dtype.kind in ("S", "U", "O", "a"):
            flattened = val.flatten()
            chars = []
            for item in flattened:
                if isinstance(item, (bytes, bytearray)):
                    chars.append(item.decode("utf-8", errors="ignore"))
                elif isinstance(item, str):
                    chars.append(item)
            return "".join(chars).strip()
    return str(val).strip()


def decode_juld(val: Any) -> Optional[datetime]:
    """
    Converts ARGO Julian Days or Xarray-decoded datetime64 to Python UTC datetime.
    Supports numpy.datetime64, pandas.Timestamp, datetime, and raw float days since 1950-01-01.
    """
    if val is None:
        return None
    if isinstance(val, np.datetime64):
        if np.isnat(val):
            return None
        import pandas as pd
        ts = pd.to_datetime(val)
        return ts.to_pydatetime().replace(tzinfo=timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        import pandas as pd
        if isinstance(val, pd.Timestamp):
            if pd.isna(val):
                return None
            return val.to_pydatetime().replace(tzinfo=timezone.utc)
        f_val = float(val)
        if np.isnan(f_val):
            return None
        return ARGO_EPOCH + timedelta(days=f_val)
    except (OverflowError, ValueError, TypeError):
        return None



class ArgoNetCDFReader:
    """Reads authentic ARGO NetCDF profile files in read-only mode."""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path).resolve()
        if not self.file_path.exists():
            raise FileNotFoundError(f"ARGO NetCDF file not found: {self.file_path}")

    def read_profile(self, profile_index: int = 0) -> Dict[str, Any]:
        """
        Reads a single profile from the NetCDF file.
        Returns a dictionary containing metadata, coordinates, raw variables, and QC arrays.
        """
        # Strictly open in read-only mode with xarray
        with xr.open_dataset(self.file_path, engine="netcdf4", mask_and_scale=True) as ds:
            # Determine dimensions
            n_prof = ds.sizes.get("N_PROF", 1)
            if profile_index >= n_prof:
                raise IndexError(f"Profile index {profile_index} out of range (N_PROF={n_prof})")

            # Extract platform metadata
            platform_num = decode_byte_string(ds["PLATFORM_NUMBER"].values[profile_index]) if "PLATFORM_NUMBER" in ds else ""
            cycle_raw = ds["CYCLE_NUMBER"].values[profile_index] if "CYCLE_NUMBER" in ds else 0
            cycle_number = int(cycle_raw) if not np.isnan(cycle_raw) else 0

            data_mode = decode_byte_string(ds["DATA_MODE"].values[profile_index]) if "DATA_MODE" in ds else "R"
            direction = decode_byte_string(ds["DIRECTION"].values[profile_index]) if "DIRECTION" in ds else "A"

            # Coordinates & timestamps
            lat_val = float(ds["LATITUDE"].values[profile_index]) if "LATITUDE" in ds else np.nan
            lon_val = float(ds["LONGITUDE"].values[profile_index]) if "LONGITUDE" in ds else np.nan
            pos_qc = decode_byte_string(ds["POSITION_QC"].values[profile_index]) if "POSITION_QC" in ds else ""

            juld_raw = ds["JULD"].values[profile_index] if "JULD" in ds else None
            juld_qc = decode_byte_string(ds["JULD_QC"].values[profile_index]) if "JULD_QC" in ds else ""
            utc_datetime = decode_juld(juld_raw)


            # Measurement parameters
            param_data: Dict[str, Any] = {}

            for param in CORE_PARAMETERS:
                # Raw variable and QC
                if param in ds:
                    param_data[param] = ds[param].values[profile_index].astype(float)
                else:
                    param_data[param] = np.array([], dtype=float)

                qc_var = f"{param}_QC"
                if qc_var in ds:
                    qc_raw = ds[qc_var].values[profile_index]
                    param_data[qc_var] = np.array([decode_byte_string(q) for q in qc_raw])
                else:
                    param_data[qc_var] = np.array([])

                # Adjusted variable and QC (if present)
                adj_var = f"{param}_ADJUSTED"
                if adj_var in ds:
                    param_data[adj_var] = ds[adj_var].values[profile_index].astype(float)
                else:
                    param_data[adj_var] = None

                adj_qc_var = f"{param}_ADJUSTED_QC"
                if adj_qc_var in ds:
                    adj_qc_raw = ds[adj_qc_var].values[profile_index]
                    param_data[adj_qc_var] = np.array([decode_byte_string(q) for q in adj_qc_raw])
                else:
                    param_data[adj_qc_var] = None

            return {
                "source_file": self.file_path.name,
                "platform_id": platform_num,
                "cycle_number": cycle_number,
                "data_mode": data_mode,
                "direction": direction,
                "latitude": lat_val,
                "longitude": lon_val,
                "position_qc": pos_qc,
                "juld": juld_raw,
                "juld_qc": juld_qc,
                "datetime": utc_datetime,
                "parameters": param_data,
            }

    def get_num_profiles(self) -> int:
        """Returns the number of profiles (N_PROF) in the NetCDF file."""
        with xr.open_dataset(self.file_path, engine="netcdf4") as ds:
            return ds.sizes.get("N_PROF", 1)
