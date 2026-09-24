from pathlib import Path
import pandas as pd
import numpy as np

RAW_FOLDER = Path("raw")
PROCESSED_FOLDER = Path("processed v1")
TOTALS_FOLDER = PROCESSED_FOLDER / "step_type_totals"

STEP_TYPES = {
    "obs steps": "obs_steps",
    "ambulatory": "ambulatory",
    "mini": "mini"
}

results = []

for processed_file in sorted(PROCESSED_FOLDER.glob("*_seconds.csv")):

    # Find matching raw file
    raw_name = processed_file.name.replace("_seconds.csv", ".csv")
    raw_file = RAW_FOLDER / raw_name

    if not raw_file.exists():
        print(f"MISSING RAW: {raw_name}")
        continue

    # Read raw and processed data
    raw = pd.read_csv(raw_file)
    processed = pd.read_csv(processed_file)

    raw.columns = raw.columns.str.strip()

    # Clean raw behavior information
    raw["_behavior"] = (
        raw["Behavior"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    raw["_event"] = (
        raw["Behavior type"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    raw["_time"] = pd.to_numeric(
        raw["Time"],
        errors="coerce"
    )

    # Keep only valid step POINT events
    steps = raw[
        (raw["_event"] == "POINT")
        & (raw["_behavior"].isin(STEP_TYPES))
        & (raw["_time"].notna())
    ].copy()

    # Assign each event to its second:
    # 56.6 -> second 56
    steps["_second"] = np.floor(
        steps["_time"]
    ).astype(int)

    # -----------------------------------
    # Expected counts from raw data

    expected = pd.DataFrame({
        "relative_time": processed["relative_time"]
    })

    for behavior, column in STEP_TYPES.items():

        counts = (
            steps[steps["_behavior"] == behavior]
            .groupby("_second")
            .size()
        )

        expected[column] = (
            expected["relative_time"]
            .map(counts)
            .fillna(0)
            .astype(int)
        )

    expected["steps_do"] = (
        expected["obs_steps"]
        + expected["ambulatory"]
        + expected["mini"]
    )

    # -----------------------------------
    # Check every second and step type

    obs_pass = (
        processed["obs_steps"].reset_index(drop=True)
        == expected["obs_steps"]
    ).all()

    ambulatory_pass = (
        processed["ambulatory"].reset_index(drop=True)
        == expected["ambulatory"]
    ).all()

    mini_pass = (
        processed["mini"].reset_index(drop=True)
        == expected["mini"]
    ).all()

    steps_do_pass = (
        processed["steps_do"].reset_index(drop=True)
        == expected["steps_do"]
    ).all()

    # Check that steps_do always equals
    # OBS Steps + Ambulatory + Mini
    sum_pass = (
        processed["steps_do"]
        == (
            processed["obs_steps"]
            + processed["ambulatory"]
            + processed["mini"]
        )
    ).all()

    # -----------------------------------
    # Check saved step-type totals

    totals_file = TOTALS_FOLDER / processed_file.name
    totals_pass = False

    if totals_file.exists():

        totals = pd.read_csv(totals_file)

        totals_pass = (
            int(totals["total_steps_do"].iloc[0])
            == int(processed["steps_do"].sum())
            and
            int(totals["total_obs_steps"].iloc[0])
            == int(processed["obs_steps"].sum())
            and
            int(totals["total_ambulatory"].iloc[0])
            == int(processed["ambulatory"].sum())
            and
            int(totals["total_mini"].iloc[0])
            == int(processed["mini"].sum())
        )

    # -----------------------------------
    # Overall result

    overall = all([
        obs_pass,
        ambulatory_pass,
        mini_pass,
        steps_do_pass,
        sum_pass,
        totals_pass
    ])

    results.append({
        "file": processed_file.name,
        "obs_steps": obs_pass,
        "ambulatory": ambulatory_pass,
        "mini": mini_pass,
        "steps_do": steps_do_pass,
        "type_sum": sum_pass,
        "totals": totals_pass,
        "overall": overall
    })

    print(
        f"{processed_file.name}: "
        f"{'PASS' if overall else 'FAIL'}"
    )

# -----------------------------------
# Save validation report

report = pd.DataFrame(results)

report.to_csv(
    "processed_validation_results.csv",
    index=False
)

print("\nDONE")

if len(report) > 0:
    print(
        f"{report['overall'].sum()} / "
        f"{len(report)} files passed"
    )
else:
    print("No processed files were found.")