from pathlib import Path
import pandas as pd

INPUT_FOLDER = Path("processed")
OUTPUT_FOLDER = Path("processed final")

OUTPUT_FOLDER.mkdir(exist_ok=True)

files = sorted(INPUT_FOLDER.glob("*_seconds.csv"))

print(f"Found {len(files)} files.\n")

for file in files:
    print(f"Processing: {file.name}")

    df = pd.read_csv(file)

    # Keep ONLY codable seconds.
    # All columns and values otherwise remain exactly the same.
    df = df[df["codable"].astype(str).str.strip().str.lower() == "codable"]

    output_file = OUTPUT_FOLDER / file.name
    df.to_csv(output_file, index=False)

    print(f"Saved: {output_file}")

print("\nDONE")