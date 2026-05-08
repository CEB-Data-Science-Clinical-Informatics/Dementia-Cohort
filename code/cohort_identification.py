import os
import re
from datetime import datetime
from glob import glob
from pathlib import Path

import polars as pl
import pandas as pd
from tqdm import tqdm

import shutup

from tabulate import tabulate

# Environment used for this script:
# - conda env: cohort
# - python: 3.10.16
# - polars: 1.32.3
# - pandas: 2.2.2
# - tqdm: 4.66.5
# - shutup: 0.2.0
# - tabulate: 0.9.0

shutup.please()


# =============================================================================
# Project paths and data sources
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAP_DIR = PROJECT_ROOT / "map_list" / "cohort"
DATA_DIR = PROJECT_ROOT / "data" / "251231"

# Set this in your shell before running, e.g. COHORT_DATALAKE_ROOT=/path/to/20251231_fu_vte_nc
datalake = os.environ.get("COHORT_DATALAKE_ROOT", "")
diagnosis_path = str(Path(datalake) / "diagnosis")
order_path = str(Path(datalake) / "order")
medication_path = str(Path(datalake) / "medication")
operation_path = str(Path(datalake) / "operation")
surgery_path = str(Path(datalake) / "surgery")


# =============================================================================
# Internal Column Glossary (Clinical Meaning)
# =============================================================================
# ENC_HN: patient identifier (hospital number)
# D001KEY: event date (used across diagnosis/operation/surgery tables)
# D035KEY: ICD-10 diagnosis code (diagnosis table)
# D036KEY: ICD-9 procedure code (operation table)
# OPR_*: ICD-9 procedure code columns in surgery table (e.g., OPR_1, OPR_2)
# D020AT3: date of birth in demographic table
#
# Pipeline-standard working columns created by this script:
# REC_DATE: normalized medication/order date
# CODE: normalized medication code in working medication tables
# PROC_DATE: normalized procedure date
# PROC_CODE: normalized ICD-9 procedure code in working procedure tables


# =============================================================================
# Shared utilities
# =============================================================================
def _normalize_code_expr(expr: pl.Expr) -> pl.Expr:
    """Normalize a code expression to uppercase alphanumeric text."""
    return expr.cast(pl.Utf8).str.to_uppercase().str.replace_all(r"[^A-Z0-9]", "")


def _normalize_code_value(code: str) -> str:
    """Normalize a single code value to uppercase alphanumeric text."""
    return re.sub(r"[^A-Z0-9]", "", str(code).upper())


def _scan_file(file_path: str) -> pl.LazyFrame:
    """Return a Polars lazy scanner for CSV or Parquet input files."""
    lower = file_path.lower()
    if lower.endswith(".csv") or lower.endswith(".csv.gz"):
        return pl.scan_csv(file_path)
    return pl.scan_parquet(file_path)


def _build_prefix_regex(prefixes: list[str]) -> str:
    """Build a regex pattern that matches any code prefix in the input list."""
    escaped = [re.escape(p) for p in prefixes if p]
    if not escaped:
        raise ValueError("No diagnosis prefixes were found in mapping CSV files.")
    return r"^(?:" + "|".join(sorted(set(escaped), key=len, reverse=True)) + r")"


# =============================================================================
# Diagnosis processing
# =============================================================================
def load_diagnosis_prefixes(map_dir: Path = MAP_DIR) -> list[str]:
    """Load and normalize diagnosis prefixes from mapping CSV files."""
    map_files = [
        map_dir / "dementia_icd10_map.csv",
        map_dir / "mci_icd10_map.csv",
        map_dir / "review_code_map.csv",
        map_dir / "schizophrenia_icd10_map.csv",
    ]

    prefixes: set[str] = set()
    for file_path in map_files:
        if not file_path.exists():
            continue
        df = pl.read_csv(str(file_path))
        if "code" not in df.columns:
            continue
        prefixes.update(
            _normalize_code_value(code)
            for code in df["code"].to_list()
            if code is not None and str(code).strip()
        )

    return sorted(prefixes)


def read_diagnosis_working_df(
    diagnosis_dir: str,
    prefixes: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pl.DataFrame:
    """Read and filter diagnosis records to a compact patient-date-code working table.

    Output schema:
    - ENC_HN: patient identifier
    - D001KEY: diagnosis/event date (datetime)
    - D035KEY: ICD-10 diagnosis code(s), normalized and comma-joined per date
    """
    files = sorted(glob(os.path.join(diagnosis_dir, "*")))
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        return pl.DataFrame({"ENC_HN": [], "D001KEY": [], "D035KEY": []})

    prefix_pattern = _build_prefix_regex(prefixes)
    working_chunks: list[pl.DataFrame] = []

    for file_path in tqdm(files, desc="Reading diagnosis files"):
        lf = _scan_file(file_path)

        date_expr = pl.coalesce(
            [
                pl.col("D001KEY").cast(pl.Datetime, strict=False),
                pl.col("D001KEY").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y%m%d", strict=False),
                pl.col("D001KEY").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y-%m-%d", strict=False),
                pl.col("D001KEY").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=False),
            ]
        )

        filtered = (
            lf.select(["ENC_HN", "D001KEY", "D035KEY"])
            .with_columns(
                [
                    date_expr.alias("D001KEY"),
                    _normalize_code_expr(pl.col("D035KEY")).alias("D035KEY"),
                ]
            )
            .filter(pl.col("D001KEY").is_not_null())
            .filter(pl.col("D035KEY").is_not_null())
            .filter(pl.col("D035KEY").str.contains(prefix_pattern))
            .filter((pl.col("D001KEY") >= start_date) & (pl.col("D001KEY") <= end_date))
            .select(["ENC_HN", "D001KEY", "D035KEY"])
            .collect()
        )

        if filtered.height > 0:
            working_chunks.append(filtered)

    if not working_chunks:
        return pl.DataFrame({"ENC_HN": [], "D001KEY": [], "D035KEY": []})

    return (
        pl.concat(working_chunks, how="vertical_relaxed")
        .group_by(["ENC_HN", "D001KEY"])
        .agg(pl.col("D035KEY").unique().sort().alias("D035KEY_LIST"))
        .with_columns(pl.col("D035KEY_LIST").list.join(", ").alias("D035KEY"))
        .drop("D035KEY_LIST")
        .sort(["ENC_HN", "D001KEY"])
    )


def _load_prefixes_from_map(file_path: Path, code_col: str = "code") -> list[str]:
    """Load normalized unique prefixes from a mapping file code column."""
    if not file_path.exists():
        return []
    df = pl.read_csv(str(file_path))
    if code_col not in df.columns:
        return []
    codes = [
        _normalize_code_value(code)
        for code in df[code_col].to_list()
        if code is not None and str(code).strip()
    ]
    return sorted(set(codes), key=len, reverse=True)


def _prefix_match_expr(code_expr: pl.Expr, prefixes: list[str]) -> pl.Expr:
    """Create a Polars expression that matches values by any prefix."""
    if not prefixes:
        return pl.lit(False)
    return pl.any_horizontal([code_expr.str.starts_with(prefix) for prefix in prefixes])


def _get_diagnosis_prefix_groups(map_dir: Path = MAP_DIR) -> dict[str, list[str]]:
    """Build grouped diagnosis prefix lists used for dementia subtype labeling."""
    dementia_map = pl.read_csv(str(map_dir / "dementia_icd10_map.csv"))
    dementia_map = dementia_map.with_columns(
        _normalize_code_expr(pl.col("code")).alias("code"),
        pl.col("subtype").cast(pl.Utf8),
    )

    return {
        "dementia": dementia_map["code"].to_list(),
        "ad": dementia_map.filter(pl.col("subtype") == "AD")["code"].to_list(),
        "vad": dementia_map.filter(pl.col("subtype") == "VaD")["code"].to_list(),
        "other": dementia_map.filter(pl.col("subtype") == "Other")["code"].to_list(),
        "unspecified": dementia_map.filter(pl.col("subtype") == "Unspecified")["code"].to_list(),
        "mci": _load_prefixes_from_map(map_dir / "mci_icd10_map.csv"),
        "schizophrenia": _load_prefixes_from_map(map_dir / "schizophrenia_icd10_map.csv"),
    }


def add_diagnosis_labels_to_working(dx_working_df: pl.DataFrame, map_dir: Path = MAP_DIR) -> pl.DataFrame:
    """Attach boolean label flags to each diagnosis working row using mapping prefixes."""
    if dx_working_df.is_empty():
        return dx_working_df

    groups = _get_diagnosis_prefix_groups(map_dir)
    dx_long = (
        dx_working_df
        .with_columns(pl.col("D035KEY").cast(pl.Utf8).str.split(", ").alias("D035KEY_LIST"))
        .explode("D035KEY_LIST")
        .with_columns(_normalize_code_expr(pl.col("D035KEY_LIST")).alias("code"))
        .filter(pl.col("code").is_not_null() & (pl.col("code") != ""))
    )

    flagged = dx_long.with_columns(
        _prefix_match_expr(pl.col("code"), groups["dementia"]).alias("is_dementia"),
        _prefix_match_expr(pl.col("code"), groups["ad"]).alias("is_ad"),
        _prefix_match_expr(pl.col("code"), groups["vad"]).alias("is_vad"),
        _prefix_match_expr(pl.col("code"), groups["other"]).alias("is_other"),
        _prefix_match_expr(pl.col("code"), groups["unspecified"]).alias("is_unspecified"),
        _prefix_match_expr(pl.col("code"), groups["mci"]).alias("is_mci"),
        _prefix_match_expr(pl.col("code"), groups["schizophrenia"]).alias("is_schizophrenia"),
    )

    labels = flagged.group_by(["ENC_HN", "D001KEY"]).agg(
        pl.col("is_dementia").any().alias("is_dementia"),
        pl.col("is_ad").any().alias("is_ad"),
        pl.col("is_vad").any().alias("is_vad"),
        pl.col("is_other").any().alias("is_other"),
        pl.col("is_unspecified").any().alias("is_unspecified"),
        pl.col("is_mci").any().alias("is_mci"),
        pl.col("is_schizophrenia").any().alias("is_schizophrenia"),
    )

    return dx_working_df.join(labels, on=["ENC_HN", "D001KEY"], how="left").with_columns(
        pl.col("is_dementia").fill_null(False),
        pl.col("is_ad").fill_null(False),
        pl.col("is_vad").fill_null(False),
        pl.col("is_other").fill_null(False),
        pl.col("is_unspecified").fill_null(False),
        pl.col("is_mci").fill_null(False),
        pl.col("is_schizophrenia").fill_null(False),
    )


def save_pl_dataset(df: pl.DataFrame, output_path: Path) -> None:
    """Write a Polars DataFrame to parquet, creating parent folders if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(str(output_path))


def build_diagnosis_summary(dx_working_df: pl.DataFrame, map_dir: Path = MAP_DIR) -> pl.DataFrame:
    """Build patient-level diagnosis summary with earliest date per subtype/history signal."""
    if dx_working_df.is_empty():
        return pl.DataFrame(
            {
                "ENC_HN": [],
                "diagnosis_date": [],
                "ad_date": [],
                "vad_date": [],
                "other_date": [],
                "unspecified_date": [],
                "mci_date": [],
                "schizophrenia_date": [],
                "has_mci_history": [],
                "has_schizophrenia_history": [],
            }
        )

    groups = _get_diagnosis_prefix_groups(map_dir)

    dx_long = (
        dx_working_df
        .with_columns(pl.col("D035KEY").cast(pl.Utf8).str.split(", ").alias("D035KEY_LIST"))
        .explode("D035KEY_LIST")
        .with_columns(_normalize_code_expr(pl.col("D035KEY_LIST")).alias("code"))
        .filter(pl.col("code").is_not_null() & (pl.col("code") != ""))
    )

    code_expr = pl.col("code")
    flagged = dx_long.with_columns(
        _prefix_match_expr(code_expr, groups["dementia"]).alias("is_dementia"),
        _prefix_match_expr(code_expr, groups["ad"]).alias("is_ad"),
        _prefix_match_expr(code_expr, groups["vad"]).alias("is_vad"),
        _prefix_match_expr(code_expr, groups["other"]).alias("is_other"),
        _prefix_match_expr(code_expr, groups["unspecified"]).alias("is_unspecified"),
        code_expr.str.starts_with("F03").alias("is_f03"),
        _prefix_match_expr(code_expr, groups["mci"]).alias("is_mci"),
        _prefix_match_expr(code_expr, groups["schizophrenia"]).alias("is_schizophrenia"),
    )

    return flagged.group_by("ENC_HN").agg(
        pl.when(pl.col("is_dementia")).then(pl.col("D001KEY")).otherwise(None).min().alias("diagnosis_date"),
        pl.when(pl.col("is_ad")).then(pl.col("D001KEY")).otherwise(None).min().alias("ad_date"),
        pl.when(pl.col("is_vad")).then(pl.col("D001KEY")).otherwise(None).min().alias("vad_date"),
        pl.when(pl.col("is_other")).then(pl.col("D001KEY")).otherwise(None).min().alias("other_date"),
        pl.when(pl.col("is_f03")).then(pl.col("D001KEY")).otherwise(None).min().alias("unspecified_date"),
        pl.when(pl.col("is_mci")).then(pl.col("D001KEY")).otherwise(None).min().alias("mci_date"),
        pl.when(pl.col("is_schizophrenia")).then(pl.col("D001KEY")).otherwise(None).min().alias("schizophrenia_date"),
        pl.col("is_mci").any().alias("has_mci_history"),
        pl.col("is_schizophrenia").any().alias("has_schizophrenia_history"),
    )


# Step 1: Set working directory and analysis window.
os.chdir(PROJECT_ROOT)

start = datetime.strptime("20100101", "%Y%m%d")
end = datetime.strptime("20251231", "%Y%m%d")

# Step 2: Load diagnosis code prefixes from mapping files.
icd10_prefixes = load_diagnosis_prefixes(MAP_DIR)

# Step 3: Build diagnosis working table and patient-level diagnosis summary.
dx_working_pl = read_diagnosis_working_df(
    diagnosis_dir=diagnosis_path,
    prefixes=icd10_prefixes,
    start_date=start,
    end_date=end,
)
dx_working_pl = add_diagnosis_labels_to_working(dx_working_pl, MAP_DIR)

print(f"number of diagnosis records: {dx_working_pl.height}")

dx_summary_pl = build_diagnosis_summary(dx_working_pl, MAP_DIR)
print(f"number of patients in diagnosis summary: {dx_summary_pl.height}")
print(f"number of unique patients: {dx_working_pl.select(pl.col('ENC_HN').n_unique()).item()}")

# Step 4: Convert diagnosis outputs to pandas and save intermediate datasets.
# Keep pandas as the default objects for downstream line-by-line work.
dx_working = dx_working_pl.to_pandas()
dx_summary = dx_summary_pl.to_pandas()

save_pl_dataset(dx_working_pl, DATA_DIR / "dx_working.parquet")
save_pl_dataset(dx_summary_pl, DATA_DIR / "dx_summary.parquet")

# Step 5: Keep ICD10-confirmed dementia branch for flow counts.
# ICD10-confirmed dementia branch from the flowdiagram.
dx_dementia_patients = dx_summary.loc[
    dx_summary["diagnosis_date"].notna(),
].copy()

print(f"number of ICD10 dementia patients: {dx_dementia_patients.shape[0]}")


# =============================================================================
# Medication processing
# =============================================================================

def _list_medication_files(order_dir: str, med_dir: str) -> list[str]:
    """List medication/order parquet files included in medication processing."""
    order_files = sorted(glob(os.path.join(order_dir, "*.parquet.gzip")))
    order_files = [
        f for f in order_files
        if not any(year in os.path.basename(f) for year in ["2023", "2024", "2025"])
    ]
    med_files = sorted(glob(os.path.join(med_dir, "*.parquet.gzip")))
    return order_files + med_files


def _load_medication_maps(map_dir: Path = MAP_DIR) -> tuple[dict[str, str], set[str]]:
    """Load medication class mapping and optional clozapine code set."""
    med_map = pl.read_csv(str(map_dir / "medication_map.csv"))
    med_map = med_map.with_columns(
        _normalize_code_expr(pl.col("drug_code")).alias("drug_code"),
        pl.col("drug_class").cast(pl.Utf8),
        pl.col("include_in_cohort").cast(pl.Int64, strict=False).fill_null(0).alias("include_in_cohort"),
    )
    med_map = med_map.filter(pl.col("include_in_cohort") == 1)

    med_class_map = {
        code: cls for code, cls in med_map.select(["drug_code", "drug_class"]).iter_rows()
    }

    cloz_map_path = map_dir / "clozapine_map.csv"
    cloz_codes: set[str] = set()
    if cloz_map_path.exists():
        cloz_map = pl.read_csv(str(cloz_map_path)).with_columns(
            _normalize_code_expr(pl.col("drug_code")).alias("drug_code")
        )
        cloz_codes = set(cloz_map["drug_code"].to_list())

    return med_class_map, cloz_codes


def _standardize_med_file(file_path: str) -> pl.DataFrame:
    """Standardize one medication/order file to ENC_HN, REC_DATE, CODE format.

    Notes:
    - REC_DATE is the normalized medication/order date.
    - CODE is a intrainstitutional medication code.
    """
    lf = _scan_file(file_path)
    schema_names = set(lf.collect_schema().names())

    if "ENC_HN" not in schema_names:
        return pl.DataFrame({"ENC_HN": [], "REC_DATE": [], "CODE": []})

    date_candidates = ["REC_DATE", "D001KEY", "PerformDate", "BillDate"]
    date_col = next((c for c in date_candidates if c in schema_names), None)
    if date_col is None:
        return pl.DataFrame({"ENC_HN": [], "REC_DATE": [], "CODE": []})

    if "Comment" in schema_names and "DSPCode" in schema_names:
        code_col = "DSPCode"
    elif "PROP_HELP" in schema_names and "CODE" in schema_names:
        code_col = "CODE"
    elif "freetext" in schema_names and "Drugcode" in schema_names:
        code_col = "Drugcode"
    elif "CODE" in schema_names:
        code_col = "CODE"
    elif "Drugcode" in schema_names:
        code_col = "Drugcode"
    elif "D403KEY" in schema_names:
        code_col = "D403KEY"
    else:
        return pl.DataFrame({"ENC_HN": [], "REC_DATE": [], "CODE": []})

    date_expr = pl.coalesce(
        [
            pl.col(date_col).cast(pl.Datetime, strict=False),
            pl.col(date_col).cast(pl.Utf8).str.strptime(pl.Datetime, "%Y%m%d", strict=False),
            pl.col(date_col).cast(pl.Utf8).str.strptime(pl.Datetime, "%Y-%m-%d", strict=False),
            pl.col(date_col).cast(pl.Utf8).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=False),
        ]
    )

    return (
        lf.select(["ENC_HN", date_col, code_col])
        .with_columns(
            [
                date_expr.alias("REC_DATE"),
                _normalize_code_expr(pl.col(code_col)).alias("CODE"),
            ]
        )
        .select(["ENC_HN", "REC_DATE", "CODE"])
        .filter(pl.col("REC_DATE").is_not_null())
        .filter(pl.col("CODE").is_not_null())
        .collect()
    )


def read_medication_working_df(
    order_dir: str,
    med_dir: str,
    start_date: datetime,
    end_date: datetime,
    map_dir: Path = MAP_DIR,
) -> pl.DataFrame:
    """Read order/medication sources and keep dementia-related drug events only."""
    med_class_map, cloz_codes = _load_medication_maps(map_dir)
    med_codes = set(med_class_map.keys())
    relevant_codes = med_codes | cloz_codes
    if not relevant_codes:
        return pl.DataFrame({
            "ENC_HN": [],
            "REC_DATE": [],
            "CODE": [],
            "drug_class": [],
            "is_dementia_med": [],
            "is_clozapine": [],
        })

    files = _list_medication_files(order_dir, med_dir)
    chunks: list[pl.DataFrame] = []

    for file_path in tqdm(files, desc="Reading medication/order files"):
        temp = _standardize_med_file(file_path)
        if temp.is_empty():
            continue

        temp = (
            temp
            .filter((pl.col("REC_DATE") >= start_date) & (pl.col("REC_DATE") <= end_date))
            .filter(pl.col("CODE").is_in(list(relevant_codes)))
            .with_columns(
                pl.col("CODE").replace_strict(med_class_map, default=None).alias("drug_class"),
                pl.col("CODE").is_in(list(cloz_codes)).alias("is_clozapine"),
            )
            .with_columns(pl.col("drug_class").is_not_null().alias("is_dementia_med"))
        )

        if temp.height > 0:
            chunks.append(temp)

    if not chunks:
        return pl.DataFrame({
            "ENC_HN": [],
            "REC_DATE": [],
            "CODE": [],
            "drug_class": [],
            "is_dementia_med": [],
            "is_clozapine": [],
        })

    return pl.concat(chunks, how="vertical_relaxed").sort(["ENC_HN", "REC_DATE"])


def build_medication_summary(med_working_df: pl.DataFrame) -> pl.DataFrame:
    """Build patient-level medication summary with earliest key medication dates."""
    if med_working_df.is_empty():
        return pl.DataFrame(
            {
                "ENC_HN": [],
                "medication_date": [],
                "achei_date": [],
                "memantine_date": [],
                "clozapine_date": [],
                "has_clozapine_history": [],
            }
        )

    return med_working_df.group_by("ENC_HN").agg(
        pl.when(pl.col("is_dementia_med")).then(pl.col("REC_DATE")).otherwise(None).min().alias("medication_date"),
        pl.when(pl.col("drug_class") == "AChEI").then(pl.col("REC_DATE")).otherwise(None).min().alias("achei_date"),
        pl.when(pl.col("drug_class") == "Memantine").then(pl.col("REC_DATE")).otherwise(None).min().alias("memantine_date"),
        pl.when(pl.col("is_clozapine")).then(pl.col("REC_DATE")).otherwise(None).min().alias("clozapine_date"),
        pl.col("is_clozapine").any().alias("has_clozapine_history"),
    )


def _list_procedure_files(*dirs: str) -> list[str]:
    """List unique procedure parquet files from one or more source directories."""
    files: list[str] = []
    for directory in dirs:
        files.extend(sorted(glob(os.path.join(directory, "*.parquet.gzip"))))
    return sorted(set(files))


def profile_procedure_sources(procedure_dirs: list[str], max_files_per_dir: int = 3) -> dict[str, dict[str, object]]:
    """Profile procedure sources by file counts and sample schemas for QA."""
    profile: dict[str, dict[str, object]] = {}
    for directory in procedure_dirs:
        files = sorted(glob(os.path.join(directory, "*.parquet.gzip")))
        sample_files = files[:max_files_per_dir]
        schemas: dict[str, list[str]] = {}

        for file_path in sample_files:
            try:
                schema_cols = _scan_file(file_path).collect_schema().names()
                schemas[os.path.basename(file_path)] = schema_cols
            except Exception as exc:
                schemas[os.path.basename(file_path)] = [f"SCHEMA_ERROR: {exc}"]

        profile[directory] = {
            "file_count": len(files),
            "sample_files": [os.path.basename(f) for f in sample_files],
            "sample_schemas": schemas,
        }

    return profile


def _load_radiotherapy_codes(map_dir: Path = MAP_DIR) -> set[str]:
    """Load normalized radiotherapy ICD9 codes from mapping CSV."""
    file_path = map_dir / "radiotherapy_icd9_map.csv"
    if not file_path.exists():
        return set()
    df = pl.read_csv(str(file_path))
    if "code" not in df.columns:
        return set()
    return {
        _normalize_code_value(code)
        for code in df["code"].to_list()
        if code is not None and str(code).strip()
    }


def _build_prefix_match_expr(code_expr: pl.Expr, prefixes: list[str]) -> pl.Expr:
    """Create a Polars expression that matches values by any prefix."""
    if not prefixes:
        return pl.lit(False)
    return pl.any_horizontal([code_expr.str.starts_with(prefix) for prefix in prefixes])


def _standardize_procedure_file(file_path: str) -> pl.DataFrame:
    """Standardize one operation/surgery file to ENC_HN, PROC_DATE, PROC_CODE."""
    lf = _scan_file(file_path)
    schema_names = set(lf.collect_schema().names())

    if "ENC_HN" not in schema_names:
        return pl.DataFrame({"ENC_HN": [], "PROC_DATE": [], "PROC_CODE": []})

    if "D001KEY" not in schema_names:
        return pl.DataFrame({"ENC_HN": [], "PROC_DATE": [], "PROC_CODE": []})

    date_expr = pl.coalesce(
        [
            pl.col("D001KEY").cast(pl.Datetime, strict=False),
            pl.col("D001KEY").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y%m%d", strict=False),
            pl.col("D001KEY").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y-%m-%d", strict=False),
            pl.col("D001KEY").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S", strict=False),
        ]
    )

    # Operation table: ICD-9 procedure codes are in D036KEY.
    if "D036KEY" in schema_names:
        return (
            lf.select(["ENC_HN", "D001KEY", "D036KEY"])
            .with_columns(
                [
                    date_expr.alias("PROC_DATE"),
                    _normalize_code_expr(pl.col("D036KEY")).alias("PROC_CODE"),
                ]
            )
            .select(["ENC_HN", "PROC_DATE", "PROC_CODE"])
            .filter(pl.col("PROC_DATE").is_not_null())
            .filter(pl.col("PROC_CODE").is_not_null())
            .collect()
        )

    # Surgery table: ICD-9 procedure codes are spread across OPR_* columns.
    opr_cols = sorted([c for c in schema_names if c.startswith("OPR_")])
    if opr_cols:
        return (
            lf.select(["ENC_HN", "D001KEY", *opr_cols])
            .with_columns(date_expr.alias("PROC_DATE"))
            .unpivot(index=["ENC_HN", "PROC_DATE"], on=opr_cols, variable_name="OPR_COL", value_name="RAW_CODE")
            .with_columns(_normalize_code_expr(pl.col("RAW_CODE")).alias("PROC_CODE"))
            .select(["ENC_HN", "PROC_DATE", "PROC_CODE"])
            .filter(pl.col("PROC_DATE").is_not_null())
            .filter(pl.col("PROC_CODE").is_not_null() & (pl.col("PROC_CODE") != ""))
            .collect()
        )

    return pl.DataFrame({"ENC_HN": [], "PROC_DATE": [], "PROC_CODE": []})


# =============================================================================
# Radiotherapy processing
# =============================================================================
def read_radiotherapy_working_df(
    procedure_dirs: list[str],
    start_date: datetime,
    end_date: datetime,
    map_dir: Path = MAP_DIR,
) -> pl.DataFrame:
    """Read procedure sources and keep radiotherapy-coded events only."""
    rt_codes = _load_radiotherapy_codes(map_dir)
    if not rt_codes:
        return pl.DataFrame({"ENC_HN": [], "PROC_DATE": [], "PROC_CODE": []})
    rt_code_prefixes = sorted(rt_codes, key=len, reverse=True)

    files = _list_procedure_files(*procedure_dirs)
    chunks: list[pl.DataFrame] = []

    for file_path in tqdm(files, desc="Reading procedure files"):
        temp = _standardize_procedure_file(file_path)
        if temp.is_empty():
            continue
        temp = (
            temp
            .filter((pl.col("PROC_DATE") >= start_date) & (pl.col("PROC_DATE") <= end_date))
            .filter(_build_prefix_match_expr(pl.col("PROC_CODE"), rt_code_prefixes))
        )
        if temp.height > 0:
            chunks.append(temp)

    if not chunks:
        return pl.DataFrame({"ENC_HN": [], "PROC_DATE": [], "PROC_CODE": []})

    return pl.concat(chunks, how="vertical_relaxed").sort(["ENC_HN", "PROC_DATE"])


def build_radiotherapy_summary(rt_working_df: pl.DataFrame) -> pl.DataFrame:
    """Build patient-level radiotherapy window (first and last RT dates)."""
    if rt_working_df.is_empty():
        return pl.DataFrame({"ENC_HN": [], "rt_first_date": [], "rt_last_date": []})

    return rt_working_df.group_by("ENC_HN").agg(
        pl.col("PROC_DATE").min().alias("rt_first_date"),
        pl.col("PROC_DATE").max().alias("rt_last_date"),
    )


def apply_exact_criteria(
    dx_summary_df,
    med_summary_df,
    rt_summary_df,
):
    """Apply exact medication exclusion logic and derive final cohort objects.

    Returns:
    - merged base table with flags
    - exact medication evaluated subset
    - inferred unspecified subset
    - final cohort
    - exact-count metrics dictionary
    """
    dx_cols = [
        "ENC_HN",
        "diagnosis_date",
        "ad_date",
        "vad_date",
        "other_date",
        "unspecified_date",
        "mci_date",
        "schizophrenia_date",
        "has_mci_history",
        "has_schizophrenia_history",
    ]
    med_cols = [
        "ENC_HN",
        "medication_date",
        "achei_date",
        "memantine_date",
        "clozapine_date",
        "has_clozapine_history",
    ]

    dx_base = dx_summary_df[dx_cols].copy() if len(dx_summary_df) > 0 else dx_summary_df.copy()
    med_base = med_summary_df[med_cols].copy() if len(med_summary_df) > 0 else med_summary_df.copy()
    rt_base = rt_summary_df[["ENC_HN", "rt_first_date", "rt_last_date"]].copy() if len(rt_summary_df) > 0 else rt_summary_df.copy()

    merged = dx_base.merge(med_base, on="ENC_HN", how="outer")
    merged = merged.merge(rt_base, on="ENC_HN", how="left")

    bool_cols = ["has_mci_history", "has_schizophrenia_history", "has_clozapine_history"]
    for col in bool_cols:
        if col not in merged.columns:
            merged[col] = False
        merged[col] = merged[col].fillna(False)

    merged["is_dx_confirmed"] = merged["diagnosis_date"].notna()
    merged["is_med_candidate"] = merged["medication_date"].notna()

    # AChEI branch: evaluate all medication patients, then mark exclusions.
    merged["is_achei_candidate"] = merged["is_med_candidate"] & merged["achei_date"].notna()
    merged["exclude_mci_achei"] = merged["is_achei_candidate"] & merged["has_mci_history"]
    merged["achei_left"] = merged["is_achei_candidate"] & (~merged["exclude_mci_achei"])

    # Memantine branch: sequential exclusion = schizophrenia first, then radiotherapy among remaining.
    merged["is_memantine_candidate"] = merged["is_med_candidate"] & merged["memantine_date"].notna()
    merged["exclude_schizophrenia_memantine"] = (
        merged["is_memantine_candidate"]
        & (merged["has_schizophrenia_history"] | merged["has_clozapine_history"])
    )
    merged["memantine_after_schizo"] = merged["is_memantine_candidate"] & (~merged["exclude_schizophrenia_memantine"])

    merged["exclude_radiotherapy_memantine"] = (
        merged["memantine_after_schizo"]
        & merged["rt_first_date"].notna()
        & merged["rt_last_date"].notna()
        & (merged["memantine_date"] >= merged["rt_first_date"])
        & (merged["memantine_date"] <= merged["rt_last_date"])
    )
    merged["memantine_left"] = merged["memantine_after_schizo"] & (~merged["exclude_radiotherapy_memantine"])

    merged["excluded_med"] = (
        merged["exclude_mci_achei"]
        | merged["exclude_schizophrenia_memantine"]
        | merged["exclude_radiotherapy_memantine"]
    )

    # Medication qualification after exact criteria.
    merged["is_med_qualifying"] = merged["achei_left"] | merged["memantine_left"]
    merged["qualified_achei_date"] = merged["achei_date"].where(merged["achei_left"])
    merged["qualified_memantine_date"] = merged["memantine_date"].where(merged["memantine_left"])
    merged["qualified_medication_date"] = merged[["qualified_achei_date", "qualified_memantine_date"]].min(axis=1)
    # Final medication date in exact-criteria outputs should be the qualified medication date.
    merged["medication_date"] = merged["qualified_medication_date"]

    # Inferred unspecified = qualifying medication patients without ICD10 dementia diagnosis.
    merged["is_inferred_unspecified"] = merged["is_med_qualifying"] & (~merged["is_dx_confirmed"])
    merged["is_final_cohort"] = merged["is_dx_confirmed"] | merged["is_med_qualifying"]

    exact_med_evaluated = merged.loc[merged["is_med_candidate"]].copy()
    inferred_unspecified = merged.loc[merged["is_inferred_unspecified"]].copy()
    final_cohort = merged.loc[merged["is_final_cohort"]].copy()

    exact_counts = {
        "medication_patients_evaluated": int(merged["is_med_candidate"].sum()),
        "achei_patients": int(merged["is_achei_candidate"].sum()),
        "memantine_patients": int(merged["is_memantine_candidate"].sum()),
        "achei_excluded_mci": int(merged["exclude_mci_achei"].sum()),
        "achei_left": int(merged["achei_left"].sum()),
        "memantine_excluded_schizo": int(merged["exclude_schizophrenia_memantine"].sum()),
        "memantine_after_schizo": int(merged["memantine_after_schizo"].sum()),
        "memantine_excluded_radio": int(merged["exclude_radiotherapy_memantine"].sum()),
        "memantine_left": int(merged["memantine_left"].sum()),
        "medication_qualifying_patients": int(merged["is_med_qualifying"].sum()),
        "medication_excluded_patients": int((merged["is_med_candidate"] & (~merged["is_med_qualifying"])).sum()),
        "inferred_unspecified_patients": int(merged["is_inferred_unspecified"].sum()),
    }

    return merged, exact_med_evaluated, inferred_unspecified, final_cohort, exact_counts


# Step 6: Build medication working table and medication summary.
med_working_pl = read_medication_working_df(
    order_dir=order_path,
    med_dir=medication_path,
    start_date=start,
    end_date=end,
    map_dir=MAP_DIR,
)
print(f"number of medication records: {med_working_pl.height}")

med_summary_pl = build_medication_summary(med_working_pl)
print(f"number of patients in medication summary: {med_summary_pl.height}")

# Step 7: Convert medication outputs to pandas and save intermediate datasets.
# Keep pandas as the default objects for downstream line-by-line work.
med_working = med_working_pl.to_pandas()
med_summary = med_summary_pl.to_pandas()

save_pl_dataset(med_working_pl, DATA_DIR / "med_working.parquet")
save_pl_dataset(med_summary_pl, DATA_DIR / "med_summary.parquet")

med_dementia_patients = med_summary.loc[
    med_summary["medication_date"].notna(),
].copy()

print(f"number of medication dementia patients: {med_dementia_patients.shape[0]}")


# =============================================================================
# Exact criteria application and cohort outputs
# =============================================================================

# Step 8: Profile operation/surgery schemas, then build radiotherapy datasets.
operation_source_profile = profile_procedure_sources(
    procedure_dirs=[operation_path],
    max_files_per_dir=3,
)
surgery_source_profile = profile_procedure_sources(
    procedure_dirs=[surgery_path],
    max_files_per_dir=3,
)
procedure_source_profile = {**operation_source_profile, **surgery_source_profile}

rt_working_pl = read_radiotherapy_working_df(
    procedure_dirs=[operation_path, surgery_path],
    start_date=start,
    end_date=end,
    map_dir=MAP_DIR,
)
print(f"number of radiotherapy records: {rt_working_pl.height}")

rt_summary_pl = build_radiotherapy_summary(rt_working_pl)
print(f"number of patients in radiotherapy summary: {rt_summary_pl.height}")

rt_working = rt_working_pl.to_pandas()
rt_summary = rt_summary_pl.to_pandas()

save_pl_dataset(rt_working_pl, DATA_DIR / "rt_working.parquet")
save_pl_dataset(rt_summary_pl, DATA_DIR / "rt_summary.parquet")

# Step 9: Apply exact exclusion criteria and generate final cohort tables.
exact_base, exact_med_evaluated, inferred_unspecified, final_cohort, exact_counts = apply_exact_criteria(
    dx_summary_df=dx_summary,
    med_summary_df=med_summary,
    rt_summary_df=rt_summary,
)

exact_base.to_parquet(DATA_DIR / "exact_criteria_base.parquet", index=False)
exact_med_evaluated.to_parquet(DATA_DIR / "exact_med_evaluated.parquet", index=False)
inferred_unspecified.to_parquet(DATA_DIR / "inferred_unspecified.parquet", index=False)
final_cohort.to_parquet(DATA_DIR / "final_cohort_exact_step.parquet", index=False)

# =============================================================================
# Flow Charts
# =============================================================================

# Step 10: Persist exact-criteria metrics and print flow summaries for QA.
# Persist exact-criteria count metrics for auditing and reproducibility.
exact_counts_df = pl.DataFrame(
    {
        "metric": list(exact_counts.keys()),
        "value": list(exact_counts.values()),
    }
)
save_pl_dataset(exact_counts_df, DATA_DIR / "exact_criteria_counts.parquet")

icd_only_tentative = int((exact_base["is_dx_confirmed"] & ~exact_base["is_med_candidate"]).sum())
med_only_tentative = int((~exact_base["is_dx_confirmed"] & exact_base["is_med_candidate"]).sum())
both_tentative = int((exact_base["is_dx_confirmed"] & exact_base["is_med_candidate"]).sum())
total_tentative = int(exact_base["is_dx_confirmed"].sum() + exact_base["is_med_candidate"].sum() - both_tentative)

dx_date = final_cohort["diagnosis_date"]
med_date = final_cohort["qualified_medication_date"]

# Final-group assignment is based on index timing.
# If one criterion occurs earlier, patient is counted in that branch.
# If both occur on the same earliest date, patient is counted in both.
dx_at_index = dx_date.notna() & (med_date.isna() | (dx_date <= med_date))
med_at_index = med_date.notna() & (dx_date.isna() | (med_date <= dx_date))

icd_only_final_any = int((dx_date.notna() & med_date.isna()).sum())
med_only_final_any = int((dx_date.isna() & med_date.notna()).sum())
both_final_any = int((dx_date.notna() & med_date.notna()).sum())
icd_final_total_any = int(dx_date.notna().sum())
med_final_total_any = int(med_date.notna().sum())

icd_only_final_index = int((dx_at_index & ~med_at_index).sum())
med_only_final_index = int((~dx_at_index & med_at_index).sum())
both_final_index = int((dx_at_index & med_at_index).sum())
icd_final_total_index = int(dx_at_index.sum())
med_final_total_index = int(med_at_index.sum())

flow_rows_availability = [
    ["ICD10 patients", int(dx_dementia_patients.shape[0])],
    ["Medication patients", int(med_dementia_patients.shape[0])],
    ["ICD10 only (tentative)", icd_only_tentative],
    ["Medication only (tentative)", med_only_tentative],
    ["Both (tentative)", both_tentative],
    ["Total tentative dementia", total_tentative],
    ["", ""],
    ["ICD10 patients", icd_final_total_any],
    ["Medication patients", med_final_total_any],
    ["ICD10 only (final)", icd_only_final_any],
    ["Medication only (final)", med_only_final_any],
    ["Both (final)", both_final_any],
    ["Total dementia", int(final_cohort.shape[0])],
]

flow_rows_index = [
    ["ICD10 patients", int(dx_dementia_patients.shape[0])],
    ["Medication patients", int(med_dementia_patients.shape[0])],
    ["ICD10 only (tentative)", icd_only_tentative],
    ["Medication only (tentative)", med_only_tentative],
    ["Both (tentative)", both_tentative],
    ["Total tentative dementia", total_tentative],
    ["", ""],
    ["ICD10 patients", icd_final_total_index],
    ["Medication patients", med_final_total_index],
    ["ICD10 only (final)", icd_only_final_index],
    ["Medication only (final)", med_only_final_index],
    ["Both (final)", both_final_index],
    ["Total dementia", int(final_cohort.shape[0])],
]

exclusion_rows = [
    ["Medication patients evaluated", exact_counts["medication_patients_evaluated"]],
    ["", ""],
    ["AChEI patients", exact_counts["achei_patients"]],
    ["AChEI excluded by MCI", exact_counts["achei_excluded_mci"]],
    ["AChEI left", exact_counts["achei_left"]],
    ["", ""],
    ["Memantine patients", exact_counts["memantine_patients"]],
    ["Memantine excluded by schizophrenia/clozapine", exact_counts["memantine_excluded_schizo"]],
    ["Memantine remaining after schizo", exact_counts["memantine_after_schizo"]],
    ["Memantine excluded by radiotherapy", exact_counts["memantine_excluded_radio"]],
    ["Memantine left", exact_counts["memantine_left"]],
    ["", ""],
    ["Medication excluded patients (total)", exact_counts["medication_excluded_patients"]],
    ["Medication qualifying patients", exact_counts["medication_qualifying_patients"]],
    ["Inferred diagnosis patients", exact_counts["inferred_unspecified_patients"]],
]

# Human-readable flow and exclusion summaries for quick QA checks.

print("\n=== Dementia Flow Summary (Final by Index Timing) ===")
print(tabulate(flow_rows_index, headers=["Step", "Patients"], tablefmt="github"))
# | Step                        | Patients   |
# |-----------------------------|------------|
# | ICD10 patients              | 12796      |
# | Medication patients         | 10340      |
# | ICD10 only (tentative)      | 6041       |
# | Medication only (tentative) | 3585       |
# | Both (tentative)            | 6755       |
# | Total tentative dementia    | 16381      |
# |                             |            |
# | ICD10 patients              | 9885       |
# | Medication patients         | 6849       |
# | ICD10 only (final)          | 9116       |
# | Medication only (final)     | 6080       |
# | Both (final)                | 769        |
# | Total dementia              | 15965      |

print("\n=== Dementia Flow Summary (Final by Availability) ===")
print(tabulate(flow_rows_availability, headers=["Step", "Patients"], tablefmt="github"))
# | Step                        | Patients   |
# |-----------------------------|------------|
# | ICD10 patients              | 12796      |
# | Medication patients         | 10340      |
# | ICD10 only (tentative)      | 6041       |
# | Medication only (tentative) | 3585       |
# | Both (tentative)            | 6755       |
# | Total tentative dementia    | 16381      |
# |                             |            |
# | ICD10 patients              | 12796      |
# | Medication patients         | 8957       |
# | ICD10 only (final)          | 7008       |
# | Medication only (final)     | 3169       |
# | Both (final)                | 5788       |
# | Total dementia              | 15965      |



print("\n=== Medication Exclusion Step-by-Step ===")
print(tabulate(exclusion_rows, headers=["Step", "Patients"], tablefmt="github"))
# | Step                                          | Patients   |
# |-----------------------------------------------|------------|
# | Medication patients evaluated                 | 10340      |
# |                                               |            |
# | AChEI patients                                | 9443       |
# | AChEI excluded by MCI                         | 1741       |
# | AChEI left                                    | 7702       |
# |                                               |            |
# | Memantine patients                            | 3532       |
# | Memantine excluded by schizophrenia/clozapine | 38         |
# | Memantine remaining after schizo              | 3494       |
# | Memantine excluded by radiotherapy            | 45         |
# | Memantine left                                | 3449       |
# |                                               |            |
# | Medication excluded patients (total)          | 1383       |
# | Medication qualifying patients                | 8957       |

# =============================================================================
# Index Dataframe construction and subtype classification
# =============================================================================

# Step 11: Build index table and enforce age filter at index date.
# Index date = earlier of diagnosis date and qualified medication date.
final_cohort["index_date"] = final_cohort[["diagnosis_date", "medication_date"]].min(axis=1)

# Example data table format from cohort_identification.md
dementia_index = final_cohort.loc[
    :,
    [
        "ENC_HN",
        "index_date",
        "diagnosis_date",
        "medication_date",
        "ad_date",
        "vad_date",
        "other_date",
        "unspecified_date",
    ],
].copy()

dementia_index = dementia_index.rename(
    columns={
        "index_date": "Index Date",
        "diagnosis_date": "Diagnosis Date",
        "medication_date": "Medication Date",
        "ad_date": "AD Date",
        "vad_date": "VaD Date",
        "other_date": "Other Date",
        "unspecified_date": "Unspecified Date",
    }
)


demo = pd.read_parquet(datalake + "demographic/demographic_1_cleaned.parquet.gzip")
demo = demo.loc[demo['ENC_HN'].isin(dementia_index['ENC_HN']), ['ENC_HN','D020AT3']]
demo["D020AT3"] = demo["D020AT3"].astype(str).str.replace(".0", "", regex=False)
demo["D020AT3"] = pd.to_datetime(demo["D020AT3"], format="%Y%m%d", errors="coerce")
demo = demo.sort_values("D020AT3").drop_duplicates("ENC_HN", keep="last").reset_index(drop=True)


temp = dementia_index.merge(demo, on="ENC_HN", how="left")
temp["age_at_index"] = (temp["Index Date"] - temp["D020AT3"]).dt.days / 365
temp.loc[temp["age_at_index"] < 18, "age_at_index"].describe() 
# count    25.000000
# mean      7.890740
# std       5.616569
# min       0.361644
# 25%       3.032877
# 50%       7.079452
# 75%      13.186301
# max      17.928767
temp.loc[temp["age_at_index"] < 18, :].to_excel(DATA_DIR / "potential_age_issues.xlsx", index=False)

dementia_index = dementia_index.merge(demo[["ENC_HN", "D020AT3"]], on="ENC_HN", how="left")
dementia_index["age_at_index"] = (dementia_index["Index Date"] - dementia_index["D020AT3"]).dt.days / 365
flag = dementia_index["age_at_index"] >= 18
print(f"Number of patients flagged for age at index < 18: {(~flag).sum()}")

dementia_index = dementia_index.loc[flag, :].copy()
dementia_index.to_parquet(DATA_DIR / "dementia_index.parquet", index=False)


# Step 12: Assign subtype labels at index and across full follow-up.
# =============================================================================
# Label assignment on dementia_index (subtype classification rules)
# =============================================================================
dementia_index_labelled = dementia_index.copy()

ad_at_index = dementia_index_labelled["AD Date"].notna() & (dementia_index_labelled["AD Date"] <= dementia_index_labelled["Index Date"])
vad_at_index = dementia_index_labelled["VaD Date"].notna() & (dementia_index_labelled["VaD Date"] <= dementia_index_labelled["Index Date"])
other_at_index = dementia_index_labelled["Other Date"].notna() & (dementia_index_labelled["Other Date"] <= dementia_index_labelled["Index Date"])

specific_count_at_index = ad_at_index.astype(int) + vad_at_index.astype(int) + other_at_index.astype(int)

dementia_index_labelled["Initial Label"] = "Unspecified"
dementia_index_labelled.loc[specific_count_at_index >= 2, "Initial Label"] = "Mixed"
dementia_index_labelled.loc[(specific_count_at_index == 1) & ad_at_index, "Initial Label"] = "AD"
dementia_index_labelled.loc[(specific_count_at_index == 1) & vad_at_index, "Initial Label"] = "VaD"
dementia_index_labelled.loc[(specific_count_at_index == 1) & other_at_index, "Initial Label"] = "Other"

ad_any = dementia_index_labelled["AD Date"].notna()
vad_any = dementia_index_labelled["VaD Date"].notna()
other_any = dementia_index_labelled["Other Date"].notna()
specific_count_any = ad_any.astype(int) + vad_any.astype(int) + other_any.astype(int)

dementia_index_labelled["Final Label"] = "Unspecified"
dementia_index_labelled.loc[specific_count_any >= 2, "Final Label"] = "Mixed"
dementia_index_labelled.loc[(specific_count_any == 1) & ad_any, "Final Label"] = "AD"
dementia_index_labelled.loc[(specific_count_any == 1) & vad_any, "Final Label"] = "VaD"
dementia_index_labelled.loc[(specific_count_any == 1) & other_any, "Final Label"] = "Other"

dementia_index_labelled.to_parquet(DATA_DIR / "dementia_index_labelled.parquet", index=False)




# Step 13: Generate subtype distribution and transition summaries.
# =============================================================================
# Subtype distribution and transition summaries
# =============================================================================
dist_order = ["AD", "VaD", "Unspecified", "Other", "Mixed"]
trans_order = ["AD", "VaD", "Unspecified", "Mixed", "Other"]

n_total = int(len(dementia_index_labelled))
init_counts = dementia_index_labelled["Initial Label"].value_counts().reindex(dist_order, fill_value=0)
final_counts = dementia_index_labelled["Final Label"].value_counts().reindex(dist_order, fill_value=0)

subtype_name_map = {
    "AD": "Alzheimer's Disease",
    "VaD": "Vascular Dementia",
    "Unspecified": "Unspecified",
    "Other": "Other Dementia",
    "Mixed": "Mixed Dementia",
}

distribution_rows = []
for label in dist_order:
    init_n = int(init_counts[label])
    final_n = int(final_counts[label])
    init_pct = (init_n / n_total * 100.0) if n_total > 0 else 0.0
    final_pct = (final_n / n_total * 100.0) if n_total > 0 else 0.0
    distribution_rows.append(
        {
            "Subtype": subtype_name_map[label],
            "Index n": init_n,
            "Index %": round(init_pct, 2),
            "Index n (%)": f"{init_n} ({init_pct:.2f}%)",
            "Final n": final_n,
            "Final %": round(final_pct, 2),
            "Final n (%)": f"{final_n} ({final_pct:.2f}%)",
        }
    )

distribution_rows.append(
    {
        "Subtype": "Total",
        "Index n": n_total,
        "Index %": 100.0,
        "Index n (%)": f"{n_total} (100.00%)",
        "Final n": n_total,
        "Final %": 100.0,
        "Final n (%)": f"{n_total} (100.00%)",
    }
)

subtype_distribution = pd.DataFrame(distribution_rows)
subtype_distribution.to_parquet(DATA_DIR / "subtype_distribution.parquet", index=False)

transition_counts = pd.crosstab(
    dementia_index_labelled["Initial Label"],
    dementia_index_labelled["Final Label"],
).reindex(index=trans_order, columns=trans_order, fill_value=0)

row_totals = transition_counts.sum(axis=1)
transition_pct = transition_counts.div(row_totals.replace(0, pd.NA), axis=0).fillna(0.0) * 100.0

transition_rows = []
for initial_label in trans_order:
    row_dict = {"Index \\ Final": initial_label}
    for final_label in trans_order:
        n_val = int(transition_counts.loc[initial_label, final_label])
        pct_val = float(transition_pct.loc[initial_label, final_label])
        row_dict[final_label] = f"{n_val} ({pct_val:.2f}%)"
    row_dict["Row Total"] = int(row_totals.loc[initial_label])
    transition_rows.append(row_dict)

column_total_row = {"Index \\ Final": "Column Total"}
for final_label in trans_order:
    column_total_row[final_label] = int(transition_counts[final_label].sum())
column_total_row["Row Total"] = int(transition_counts.values.sum())
transition_rows.append(column_total_row)

subtype_transition = pd.DataFrame(transition_rows)
subtype_transition.to_parquet(DATA_DIR / "subtype_transition.parquet", index=False)

print("\n=== Subtype Distribution ===")
print(tabulate(subtype_distribution[["Subtype", "Index n (%)", "Final n (%)"]], headers="keys", tablefmt="github", showindex=False))
# | Subtype             | Index n (%)     | Final n (%)     |
# |---------------------|-----------------|-----------------|
# | Alzheimer's Disease | 3459 (21.70%)   | 5051 (31.69%)   |
# | Vascular Dementia   | 1038 (6.51%)    | 1335 (8.38%)    |
# | Unspecified         | 9565 (60.01%)   | 5688 (35.68%)   |
# | Other Dementia      | 1757 (11.02%)   | 1807 (11.34%)   |
# | Mixed Dementia      | 121 (0.76%)     | 2059 (12.92%)   |
# | Total               | 15940 (100.00%) | 15940 (100.00%) |

print("\n=== Subtype Transition (Row %) ===")
columns_for_display = ["Index \ Final", "Row Total", "AD", "VaD", "Unspecified", "Mixed", "Other"]
print(tabulate(subtype_transition[columns_for_display], headers="keys", tablefmt="github", showindex=False))
# | Index \ Final   |   Row Total | AD            | VaD          | Unspecified   | Mixed         | Other         |
# |-----------------|-------------|---------------|--------------|---------------|---------------|---------------|
# | AD              |        3459 | 2921 (84.45%) | 0 (0.00%)    | 0 (0.00%)     | 538 (15.55%)  | 0 (0.00%)     |
# | VaD             |        1038 | 0 (0.00%)     | 774 (74.57%) | 0 (0.00%)     | 264 (25.43%)  | 0 (0.00%)     |
# | Unspecified     |        9565 | 2130 (22.27%) | 561 (5.87%)  | 5688 (59.47%) | 1014 (10.60%) | 172 (1.80%)   |
# | Mixed           |         121 | 0 (0.00%)     | 0 (0.00%)    | 0 (0.00%)     | 121 (100.00%) | 0 (0.00%)     |
# | Other           |        1757 | 0 (0.00%)     | 0 (0.00%)    | 0 (0.00%)     | 122 (6.94%)   | 1635 (93.06%) |
# | Column Total    |       15940 | 5051          | 1335         | 5688          | 2059          | 1807          |