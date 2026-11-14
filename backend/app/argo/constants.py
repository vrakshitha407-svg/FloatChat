"""
Official ARGO constants, Quality Control (QC) standards, and reference epoch definitions.
Reference: ARGO User's Manual v3.1 / v3.2 (http://www.argodatamgt.org/Documentation)
"""

from datetime import datetime, timezone

# ARGO Julian Day Reference Epoch: 1950-01-01 00:00:00 UTC
ARGO_EPOCH = datetime(1950, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# Standard ARGO Quality Control (QC) Flags
QC_NO_QC = "0"              # No QC performed
QC_GOOD = "1"               # Good data
QC_PROBABLY_GOOD = "2"      # Probably good data
QC_BAD_CORRECTABLE = "3"    # Bad data that are potentially correctable
QC_BAD = "4"                # Bad data
QC_VALUE_CHANGED = "5"      # Value changed
QC_NOT_USED = "6"           # Not used
QC_NOMINAL = "7"            # Nominal value
QC_INTERPOLATED = "8"       # Interpolated value
QC_MISSING = "9"            # Missing value

# Scientifically acceptable QC flags for analysis
SCIENTIFIC_VALID_QC = {"1", "2"}

# Invalid QC flags that must be masked out in observations
INVALID_QC_FLAGS = {"3", "4", "9"}

# ARGO Data Modes
DATA_MODE_REALTIME = "R"    # Real-time data (uncalibrated)
DATA_MODE_ADJUSTED = "A"    # Real-time with adjustments applied
DATA_MODE_DELAYED = "D"     # Delayed-mode scientific quality data

# Oceanographic Parameters of Interest
CORE_PARAMETERS = ["PRES", "TEMP", "PSAL"]
