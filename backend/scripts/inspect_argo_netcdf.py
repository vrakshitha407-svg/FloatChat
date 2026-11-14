"""
Inspection script to examine the schema, dimensions, variables,
attributes, and QC flags of actual downloaded ARGO NetCDF files.
"""

import sys
from pathlib import Path

def inspect_netcdf(nc_path: Path):
    """Inspects an ARGO NetCDF profile file and prints a comprehensive schema report."""
    import xarray as xr
    import numpy as np

    print("=" * 70)
    print(f"INSPECTING ARGO NETCDF FILE: {nc_path.name}")
    print(f"File Size: {nc_path.stat().st_size:,} bytes")
    print("=" * 70)

    # Open with xarray in read-only mode, mask_and_scale=False to inspect raw values too
    with xr.open_dataset(nc_path, decode_times=False) as ds:
        print("\n--- 1. GLOBAL ATTRIBUTES ---")
        for k, v in ds.attrs.items():
            print(f"  {k}: {v}")

        print("\n--- 2. DIMENSIONS ---")
        for dim_name, size in ds.dims.items():
            print(f"  {dim_name}: {size}")

        print("\n--- 3. KEY METADATA & COORDINATES ---")
        for key in ["PLATFORM_NUMBER", "CYCLE_NUMBER", "DATA_MODE", "DIRECTION", "LATITUDE", "LONGITUDE", "POSITION_QC", "JULD", "JULD_QC"]:
            if key in ds:
                val = ds[key].values
                # Decode bytes to string if needed
                if isinstance(val, bytes) or (isinstance(val, np.ndarray) and val.dtype.kind in ('S', 'U', 'O')):
                    try:
                        str_val = "".join([x.decode('utf-8') if isinstance(x, bytes) else str(x) for x in val.flatten()]).strip()
                        print(f"  {key}: {str_val!r} (shape={val.shape}, dtype={val.dtype})")
                    except Exception:
                        print(f"  {key}: {val} (shape={val.shape}, dtype={val.dtype})")
                else:
                    print(f"  {key}: {val} (shape={val.shape}, dtype={val.dtype})")
            else:
                print(f"  {key}: [NOT FOUND]")

        print("\n--- 4. SCIENTIFIC VARIABLES & ADJUSTED PAIRS ---")
        param_groups = [
            ("PRES", ["PRES", "PRES_QC", "PRES_ADJUSTED", "PRES_ADJUSTED_QC", "PRES_ADJUSTED_ERROR"]),
            ("TEMP", ["TEMP", "TEMP_QC", "TEMP_ADJUSTED", "TEMP_ADJUSTED_QC", "TEMP_ADJUSTED_ERROR"]),
            ("PSAL", ["PSAL", "PSAL_QC", "PSAL_ADJUSTED", "PSAL_ADJUSTED_QC", "PSAL_ADJUSTED_ERROR"]),
        ]

        for group_name, vars_in_group in param_groups:
            print(f"\n  [{group_name} Group]")
            for var_name in vars_in_group:
                if var_name in ds:
                    v = ds[var_name]
                    arr = v.values
                    # Check fill values and valid data counts
                    non_nan_count = np.count_nonzero(~np.isnan(arr)) if np.issubdtype(arr.dtype, np.floating) else "N/A"
                    print(f"    {var_name:20} shape={str(arr.shape):12} dtype={str(arr.dtype):10} non_nan={non_nan_count}")
                    if var_name.endswith("_QC"):
                        sample_flags = np.unique(arr.flatten())
                        print(f"      QC Flags observed: {[f.decode('utf-8') if isinstance(f, bytes) else str(f) for f in sample_flags]}")
                else:
                    print(f"    {var_name:20} [NOT PRESENT IN THIS FILE]")

    print("\n" + "=" * 70)
    print("INSPECTION COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    raw_dir = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
    nc_files = sorted(list(raw_dir.glob("*.nc")))

    if not nc_files:
        print(f"No NetCDF files found in {raw_dir}. Run download_sample_argo.py first.")
        sys.exit(1)

    print(f"Found {len(nc_files)} NetCDF file(s). Inspecting the first profile...")
    inspect_netcdf(nc_files[0])
