"""
ARGO Data Processor.
Orchestrates raw NetCDF reading, QC validation, and Parquet data generation.
Preserves raw NetCDF files completely unaltered under data/raw/.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from app.argo.qc import ArgoQualityControl
from app.argo.reader import ArgoNetCDFReader


class ArgoProcessor:
    """
    Ingests authentic ARGO NetCDF files from data/raw/ and generates
    optimized Parquet index and observation datasets in data/processed/.
    """

    def __init__(
        self,
        raw_dir: Union[str, Path] = "data/raw",
        processed_dir: Union[str, Path] = "data/processed",
    ):
        self.raw_dir = Path(raw_dir).resolve()
        self.processed_dir = Path(processed_dir).resolve()

    def is_configured(self) -> bool:
        """Verify if raw data directory exists."""
        return self.raw_dir.exists()

    def process_all(self, save_parquet: bool = True) -> Dict[str, Any]:
        """
        Scans all NetCDF files in data/raw/, applies QC, and exports processed data.
        Original files in data/raw/ are opened strictly read-only and never modified.
        """
        if not self.raw_dir.exists():
            return {
                "success": False,
                "error": f"Raw data directory does not exist: {self.raw_dir}",
                "num_files": 0,
                "num_profiles": 0,
                "num_observations": 0,
            }

        nc_files = sorted(list(self.raw_dir.glob("*.nc")))
        if not nc_files:
            return {
                "success": False,
                "error": f"No .nc NetCDF files found in {self.raw_dir}",
                "num_files": 0,
                "num_profiles": 0,
                "num_observations": 0,
            }

        index_records: List[Dict[str, Any]] = []
        observation_records: List[Dict[str, Any]] = []

        for nc_path in nc_files:
            try:
                reader = ArgoNetCDFReader(nc_path)
                n_prof = reader.get_num_profiles()

                for p_idx in range(n_prof):
                    profile_raw = reader.read_profile(p_idx)

                    # Validate coordinates and time
                    lat = profile_raw["latitude"]
                    lon = profile_raw["longitude"]
                    dt = profile_raw["datetime"]
                    pos_qc = profile_raw["position_qc"]
                    juld_qc = profile_raw["juld_qc"]

                    if not ArgoQualityControl.is_valid_profile_metadata(pos_qc, juld_qc, lat, lon, dt):
                        continue

                    data_mode = profile_raw["data_mode"]
                    params = profile_raw["parameters"]

                    # Resolve parameters (adjusted vs raw based on DATA_MODE & availability)
                    pres_vals, pres_qc, pres_src = ArgoQualityControl.resolve_parameter_values("PRES", params, data_mode)
                    temp_vals, temp_qc, temp_src = ArgoQualityControl.resolve_parameter_values("TEMP", params, data_mode)
                    psal_vals, psal_qc, psal_src = ArgoQualityControl.resolve_parameter_values("PSAL", params, data_mode)

                    # Apply QC masking (masks bad values with NaN, preserves original QC flags array)
                    pres_clean, pres_qc_pres = ArgoQualityControl.apply_qc_filter(pres_vals, pres_qc)
                    temp_clean, temp_qc_pres = ArgoQualityControl.apply_qc_filter(temp_vals, temp_qc)
                    psal_clean, psal_qc_pres = ArgoQualityControl.apply_qc_filter(psal_vals, psal_qc)

                    # Depth calculation
                    valid_pres = pres_clean[~np.isnan(pres_clean)]
                    min_pres = float(np.min(valid_pres)) if len(valid_pres) > 0 else np.nan
                    max_pres = float(np.max(valid_pres)) if len(valid_pres) > 0 else np.nan

                    # Profile Index record
                    index_record = {
                        "platform_id": profile_raw["platform_id"],
                        "cycle_number": profile_raw["cycle_number"],
                        "datetime": dt.isoformat() if dt else None,
                        "latitude": lat,
                        "longitude": lon,
                        "position_qc": pos_qc,
                        "juld_qc": juld_qc,
                        "data_mode": data_mode,
                        "pres_source": pres_src,
                        "temp_source": temp_src,
                        "psal_source": psal_src,
                        "min_pressure_dbar": min_pres,
                        "max_pressure_dbar": max_pres,
                        "num_levels": len(pres_vals),
                        "source_file": profile_raw["source_file"],
                    }
                    index_records.append(index_record)

                    # Level-by-level observation records
                    num_levels = len(pres_vals)
                    for lvl in range(num_levels):
                        p_val = float(pres_clean[lvl]) if lvl < len(pres_clean) else np.nan
                        t_val = float(temp_clean[lvl]) if lvl < len(temp_clean) else np.nan
                        s_val = float(psal_clean[lvl]) if lvl < len(psal_clean) else np.nan

                        # Keep levels that have at least one valid measurement
                        if np.isnan(p_val) and np.isnan(t_val) and np.isnan(s_val):
                            continue

                        obs_record = {
                            "platform_id": profile_raw["platform_id"],
                            "cycle_number": profile_raw["cycle_number"],
                            "datetime": dt.isoformat() if dt else None,
                            "latitude": lat,
                            "longitude": lon,
                            "level_index": lvl,
                            "pressure_dbar": p_val,
                            "temperature_c": t_val,
                            "salinity_psu": s_val,
                            # Original QC flags preserved
                            "pres_qc": str(pres_qc_pres[lvl]) if lvl < len(pres_qc_pres) else "",
                            "temp_qc": str(temp_qc_pres[lvl]) if lvl < len(temp_qc_pres) else "",
                            "psal_qc": str(psal_qc_pres[lvl]) if lvl < len(psal_qc_pres) else "",
                            "position_qc": pos_qc,
                            "juld_qc": juld_qc,
                            # Lineage tracking
                            "pres_source": pres_src,
                            "temp_source": temp_src,
                            "psal_source": psal_src,
                        }
                        observation_records.append(obs_record)

            except Exception as e:
                print(f"Error processing {nc_path.name}: {e}")

        # Convert to DataFrames
        df_index = pd.DataFrame(index_records)
        df_obs = pd.DataFrame(observation_records)

        # Save to Parquet in data/processed/
        if save_parquet:
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            index_path = self.processed_dir / "profiles_index.parquet"
            obs_path = self.processed_dir / "argo_observations.parquet"

            df_index.to_parquet(index_path, index=False, engine="pyarrow")
            df_obs.to_parquet(obs_path, index=False, engine="pyarrow")

        return {
            "success": True,
            "num_files": len(nc_files),
            "num_profiles": len(df_index),
            "num_observations": len(df_obs),
            "df_index": df_index,
            "df_obs": df_obs,
        }
