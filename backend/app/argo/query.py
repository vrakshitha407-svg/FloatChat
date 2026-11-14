"""
ARGO Query Engine.
Provides spatial, temporal, depth, and parameter query filters against processed ARGO data.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd



class ArgoQueryEngine:
    """Fast querying interface for processed ARGO profiles and observations."""

    def __init__(self, processed_dir: Union[str, Path] = "data/processed"):
        self.processed_dir = Path(processed_dir).resolve()
        self._index_df: Optional[pd.DataFrame] = None
        self._obs_df: Optional[pd.DataFrame] = None

    def _load_data(self) -> bool:
        """Loads processed Parquet files into memory if available."""
        index_path = self.processed_dir / "profiles_index.parquet"
        obs_path = self.processed_dir / "argo_observations.parquet"

        if not index_path.exists() or not obs_path.exists():
            return False

        if self._index_df is None:
            self._index_df = pd.read_parquet(index_path, engine="pyarrow")
            # Parse datetime column to Pandas datetime for fast temporal filtering
            if "datetime" in self._index_df.columns:
                self._index_df["datetime"] = pd.to_datetime(self._index_df["datetime"], utc=True)

        if self._obs_df is None:
            self._obs_df = pd.read_parquet(obs_path, engine="pyarrow")
            if "datetime" in self._obs_df.columns:
                self._obs_df["datetime"] = pd.to_datetime(self._obs_df["datetime"], utc=True)


        return True

    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level statistics of the processed dataset."""
        if not self._load_data():
            return {"status": "empty", "message": "No processed ARGO datasets found."}

        df_idx = self._index_df
        df_obs = self._obs_df

        return {
            "status": "ready",
            "total_profiles": len(df_idx),
            "total_observations": len(df_obs),
            "platforms": df_idx["platform_id"].unique().tolist() if "platform_id" in df_idx else [],
            "date_min": df_idx["datetime"].min().isoformat() if not df_idx.empty and "datetime" in df_idx else None,
            "date_max": df_idx["datetime"].max().isoformat() if not df_idx.empty and "datetime" in df_idx else None,
            "lat_min": float(df_idx["latitude"].min()) if not df_idx.empty and "latitude" in df_idx else None,
            "lat_max": float(df_idx["latitude"].max()) if not df_idx.empty and "latitude" in df_idx else None,
            "lon_min": float(df_idx["longitude"].min()) if not df_idx.empty and "longitude" in df_idx else None,
            "lon_max": float(df_idx["longitude"].max()) if not df_idx.empty and "longitude" in df_idx else None,
        }

    @staticmethod
    def _normalize_filter_datetime(val: Any, target_tz: Any) -> Optional[pd.Timestamp]:
        """Normalizes a filter timestamp to match the target column's timezone."""
        if val is None:
            return None
        ts = pd.to_datetime(val)
        if target_tz is not None:
            if ts.tzinfo is None:
                return ts.tz_localize(target_tz)
            return ts.tz_convert(target_tz)
        else:
            if ts.tzinfo is not None:
                return ts.tz_localize(None)
            return ts

    def filter_profiles(
        self,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        start_date: Optional[Union[str, pd.Timestamp]] = None,
        end_date: Optional[Union[str, pd.Timestamp]] = None,
        platform_id: Optional[str] = None,
    ) -> pd.DataFrame:
        """Filters profile metadata index by bounding box, date range, and platform."""
        if not self._load_data() or self._index_df.empty:
            return pd.DataFrame()

        df = self._index_df.copy()

        if min_lat is not None:
            df = df[df["latitude"] >= min_lat]
        if max_lat is not None:
            df = df[df["latitude"] <= max_lat]
        if min_lon is not None:
            df = df[df["longitude"] >= min_lon]
        if max_lon is not None:
            df = df[df["longitude"] <= max_lon]

        if "datetime" in df:
            target_tz = df["datetime"].dt.tz
            if start_date is not None:
                start_ts = self._normalize_filter_datetime(start_date, target_tz)
                if start_ts is not None:
                    df = df[df["datetime"] >= start_ts]

            if end_date is not None:
                end_ts = self._normalize_filter_datetime(end_date, target_tz)
                if end_ts is not None:
                    df = df[df["datetime"] <= end_ts]

        if platform_id is not None:
            df = df[df["platform_id"] == str(platform_id)]

        return df


    def filter_observations(
        self,
        platform_id: Optional[str] = None,
        cycle_number: Optional[int] = None,
        min_depth: Optional[float] = None,
        max_depth: Optional[float] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
    ) -> pd.DataFrame:
        """Filters vertical observation levels by depth/pressure, platform, cycle, and coordinates."""
        if not self._load_data() or self._obs_df.empty:
            return pd.DataFrame()

        df = self._obs_df.copy()

        if platform_id is not None:
            df = df[df["platform_id"] == str(platform_id)]
        if cycle_number is not None:
            df = df[df["cycle_number"] == cycle_number]

        if min_depth is not None and "pressure_dbar" in df:
            df = df[df["pressure_dbar"] >= min_depth]
        if max_depth is not None and "pressure_dbar" in df:
            df = df[df["pressure_dbar"] <= max_depth]

        if min_lat is not None:
            df = df[df["latitude"] >= min_lat]
        if max_lat is not None:
            df = df[df["latitude"] <= max_lat]
        if min_lon is not None:
            df = df[df["longitude"] >= min_lon]
        if max_lon is not None:
            df = df[df["longitude"] <= max_lon]

        return df

    def get_profile_detail(
        self,
        platform_id: str,
        cycle_number: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single profile metadata record along with its vertical observation levels.
        Returns None if the profile does not exist.
        """
        if not self._load_data() or self._index_df.empty:
            return None

        p_matches = self._index_df[
            (self._index_df["platform_id"] == str(platform_id)) &
            (self._index_df["cycle_number"] == int(cycle_number))
        ]

        if p_matches.empty:
            return None

        profile_row = p_matches.iloc[0].to_dict()
        if isinstance(profile_row.get("datetime"), pd.Timestamp):
            profile_row["datetime"] = profile_row["datetime"].isoformat()

        # Clean NaNs in profile dict
        cleaned_profile = {k: (None if pd.isna(v) else v) for k, v in profile_row.items()}

        # Match observations
        o_matches = self._obs_df[
            (self._obs_df["platform_id"] == str(platform_id)) &
            (self._obs_df["cycle_number"] == int(cycle_number))
        ].copy()

        if "level_index" in o_matches.columns:
            o_matches = o_matches.sort_values(by="level_index")
        elif "pressure_dbar" in o_matches.columns:
            o_matches = o_matches.sort_values(by="pressure_dbar")

        if "datetime" in o_matches.columns:
            o_matches["datetime"] = o_matches["datetime"].apply(
                lambda x: x.isoformat() if isinstance(x, pd.Timestamp) and not pd.isna(x) else None
            )

        # Replace NaNs with None for clean JSON serialization
        obs_records = o_matches.replace({np.nan: None}).to_dict(orient="records")

        return {
            "profile": cleaned_profile,
            "observations": obs_records,
        }

