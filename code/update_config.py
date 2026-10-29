"""Settings for cohort_identification.py. Edit the lines marked EDIT.

Every setting can be overridden with an environment variable of the same name.
COHORT_DATALAKE_ROOT also overrides STRICT_ROOT.
"""

import os
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# EDIT: governed data delivery (folders diagnosis/, order/, medication/ if present,
# operation/, surgery/, demographic/).
STRICT_ROOT = Path(os.environ.get("STRICT_ROOT", "/path/to/20260630_fu_nc"))

# EDIT: evidence window (inclusive). The exclusion criteria and the final label
# use the full history, so the window starts at the start of the data warehouse.
COHORT_START_DATE = datetime.strptime(os.environ.get("COHORT_START_DATE", "20100101"), "%Y%m%d")
END_DATE = datetime.strptime(os.environ.get("END_DATE", "20260630"), "%Y%m%d")

# EDIT: name of the output folder, e.g. 2010-202606.
RUN_TAG = os.environ.get("RUN_TAG", "2010-202606")

MAP_DIR = Path(os.environ.get("COHORT_MAP_DIR", REPO_ROOT / "maplist" / "cohort"))
STRICT_DIR = Path(os.environ.get("COHORT_OUT_DIR", REPO_ROOT / "data" / RUN_TAG))
