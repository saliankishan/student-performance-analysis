from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW_FILE = BASE_DIR / "student_performance_messy.csv"
NUMERIC_COLUMNS = ["study_hrs", "attend", "prev", "sleep", "exam"]


def extract_data(file_path: Path = RAW_FILE) -> pd.DataFrame:
    """Load the CSV without depending on the terminal's working directory."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Put {file_path.name} beside this script: {BASE_DIR}")
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    missing = set(NUMERIC_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize units; reject invalid attendance/exam; retain optional gaps."""
    df = df.copy()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string").str.strip()

    for col in NUMERIC_COLUMNS:
        values = df[col].astype("string").str.strip()
        # Remove only a trailing unit, so malformed embedded text stays invalid.
        if col in ["study_hrs", "sleep"]:
            values = values.str.replace(r"(?i)\s*(?:hours?|hrs?)\s*$", "", regex=True)
        else:
            values = values.str.replace(r"\s*(?:%|/\s*100)\s*$", "", regex=True)
        df[col] = pd.to_numeric(values, errors="coerce")

    before = len(df)
    df = df.drop_duplicates().copy()
    print(f"Duplicate rows removed after normalization: {before - len(df)}")

    # Missing or invalid optional measurements are excluded from their averages.
    for col, upper in [("study_hrs", 24), ("sleep", 24), ("prev", 100)]:
        invalid = df[col].notna() & ~df[col].between(0, upper)
        df.loc[invalid, col] = float("nan")

    valid = (df["attend"].between(0, 100) & df["exam"].between(0, 100)).fillna(False)
    print(f"Rows removed for missing/invalid attendance or exam: {(~valid).sum()}")
    return df.loc[valid].reset_index(drop=True)


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    """Assign exact grade boundaries and attendance groups."""
    df = df.copy()
    df["grade"] = pd.cut(
        df["exam"], bins=[-float("inf"), 50, 80, float("inf")],
        labels=["Needs Improvement", "Good", "Excellent"], right=False,
    )
    # Low: 0-75; Mid: >75-90; High: >90-100.
    df["att_group"] = pd.cut(
        df["attend"], bins=[0, 75, 90, 100],
        labels=["Low", "Mid", "High"], include_lowest=True,
    )
    return df


def analyze_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize attendance groups and correlate measurements (not IDs)."""
    summary = df.groupby("att_group", observed=False).agg(
        avg_study_hrs=("study_hrs", "mean"),
        avg_exam_score=("exam", "mean"),
        student_count=("exam", "count"),
        study_hrs_count=("study_hrs", "count"),
    ).round(2).reset_index()
    # Correlations use available pairs; blanks mean insufficient data/variation.
    corr = df[NUMERIC_COLUMNS].corr(min_periods=2).round(2)
    return summary, corr


def load_results(df: pd.DataFrame, summary: pd.DataFrame, corr: pd.DataFrame) -> None:
    """Write outputs beside this script; subsequent runs overwrite them."""
    df.to_csv(BASE_DIR / "clean_students.csv", index=False)
    summary.to_csv(BASE_DIR / "analysis_results.csv", index=False)
    corr.to_csv(BASE_DIR / "correlations.csv", index_label="metric")


def run_pipeline() -> None:
    raw = extract_data()
    print(f"Raw records loaded: {len(raw)}")
    cleaned = clean_data(raw)
    if cleaned.empty:
        raise ValueError("No valid records remain. Check attendance and exam values; outputs were not updated.")
    transformed = transform_data(cleaned)
    summary, corr = analyze_data(transformed)
    load_results(transformed, summary, corr)
    print(f"Clean records saved: {len(transformed)}")
    print("\nAttendance summary:")
    print(summary.to_string(index=False))
    print(f"\nPipeline completed successfully. Output folder: {BASE_DIR}")


if __name__ == "__main__":
    run_pipeline()
