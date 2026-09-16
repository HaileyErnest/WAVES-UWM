from pathlib import Path
import pandas as pd

# Folders
PROCESSED_FOLDER = Path("processed")
TOTALS_FOLDER = PROCESSED_FOLDER / "step_type_totals"

# Create the new folder automatically
TOTALS_FOLDER.mkdir(parents=True, exist_ok=True)

# Find all individual second-by-second processed files
csv_files = sorted(PROCESSED_FOLDER.glob("*_seconds.csv"))

for file_path in csv_files:
    df = pd.read_csv(file_path)

    # Create one-row session summary
    summary = pd.DataFrame({
        "pid": [df["pid"].iloc[0]],
        "observation": [df["observation"].iloc[0]],
        "total_steps_do": [df["steps_do"].sum()],
        "total_obs_steps": [df["obs_steps"].sum()],
        "total_ambulatory": [df["ambulatory"].sum()],
        "total_mini": [df["mini"].sum()]
    })

    # Keep exactly the same filename
    output_path = TOTALS_FOLDER / file_path.name
    summary.to_csv(output_path, index=False)

    print(f"Saved: {output_path}")

print("\nDONE - step type totals created.")