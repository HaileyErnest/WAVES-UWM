from pathlib import Path
import pandas as pd
import numpy as np
import re


# ============================================================
# SETTINGS
# ============================================================

# Folder containing your original raw CSV files
INPUT_FOLDER = Path("raw")

# New folder where processed files will be saved
OUTPUT_FOLDER = Path("processed")

OUTPUT_FOLDER.mkdir(exist_ok=True)


# These are the ONLY Behavior values that count as steps
STEP_TYPES = {
    "obs steps": "obs_steps",
    "ambulatory": "ambulatory",
    "mini": "mini"
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_column_names(df):
    """
    Removes extra spaces from column names.
    """
    df.columns = [str(col).strip() for col in df.columns]
    return df


def find_column(df, possible_names):
    """
    Finds a column even if capitalization/spaces differ slightly.
    """

    normalized = {
        str(col).strip().lower(): col
        for col in df.columns
    }

    for name in possible_names:
        if name.lower() in normalized:
            return normalized[name.lower()]

    return None


def parse_observation_id(observation_id):
    """
    Example:

        1013_2_Uwisc_StepCount_CN

    becomes:

        pid = 1013
        observation = 2
    """

    observation_id = str(observation_id).strip()

    match = re.match(r"^(\d{4})_(\d+)", observation_id)

    if match is None:
        raise ValueError(
            f"Could not extract pid/session from Observation id: "
            f"{observation_id}"
        )

    pid = match.group(1)
    observation = int(match.group(2))

    return pid, observation


def seconds_to_hms(seconds):
    """
    Converts:
        65 -> 00:01:05

    This is only a display column.
    """

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ============================================================
# MAIN PROCESSING FUNCTION
# ============================================================

def process_step_file(file_path):

    print(f"Processing: {file_path.name}")

    # --------------------------------------------------------
    # 1. READ CSV
    # --------------------------------------------------------

    df = pd.read_csv(file_path)

    df = clean_column_names(df)


    # --------------------------------------------------------
    # 2. FIND REQUIRED COLUMNS
    # --------------------------------------------------------

    observation_id_col = find_column(
        df,
        [
            "Observation id",
            "Observation ID"
        ]
    )

    time_col = find_column(
        df,
        [
            "Time"
        ]
    )

    behavior_col = find_column(
        df,
        [
            "Behavior"
        ]
    )

    event_type_col = find_column(
        df,
        [
            "Behavior type",
            "Behavior Type",
            "Event type",
            "Event Type"
        ]
    )

    duration_col = find_column(
        df,
        [
            "Media duration",
            "Media duration (s)",
            "Media duration (sec)"
        ]
    )


    # --------------------------------------------------------
    # Check required columns
    # --------------------------------------------------------

    required = {
        "Observation id": observation_id_col,
        "Time": time_col,
        "Behavior": behavior_col
    }

    missing = [
        name
        for name, column in required.items()
        if column is None
    ]

    if missing:
        raise ValueError(
            f"{file_path.name}: missing columns: {missing}\n"
            f"Actual columns are:\n{list(df.columns)}"
        )


    # --------------------------------------------------------
    # Try extra logic to detect Behavior type
    # --------------------------------------------------------

    if event_type_col is None:

        for col in df.columns:

            name = str(col).strip().lower()

            # Look for a behavior-related column
            # containing START / STOP / POINT
            if "behavior" in name and col != behavior_col:

                values = (
                    df[col]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )

                if values.isin(
                    ["START", "STOP", "POINT"]
                ).any():

                    event_type_col = col
                    break


    if event_type_col is None:
        raise ValueError(
            f"{file_path.name}: I could not identify the column "
            f"containing START / STOP / POINT.\n"
            f"Columns found:\n{list(df.columns)}"
        )


    # --------------------------------------------------------
    # 3. GET PID + SESSION
    # --------------------------------------------------------

    observation_ids = (
        df[observation_id_col]
        .dropna()
        .astype(str)
    )

    if len(observation_ids) == 0:
        raise ValueError(
            f"{file_path.name}: no Observation id found."
        )

    observation_id = observation_ids.iloc[0]

    pid, observation = parse_observation_id(
        observation_id
    )


    # --------------------------------------------------------
    # 4. CLEAN IMPORTANT VARIABLES
    # --------------------------------------------------------

    df["_time"] = pd.to_numeric(
        df[time_col],
        errors="coerce"
    )

    df["_behavior"] = (
        df[behavior_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["_event_type"] = (
        df[event_type_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )


    # --------------------------------------------------------
    # 5. DETERMINE SESSION LENGTH
    # --------------------------------------------------------

    duration = None

    if duration_col is not None:

        duration_values = pd.to_numeric(
            df[duration_col],
            errors="coerce"
        )

        if duration_values.notna().any():
            duration = duration_values.max()


    # If Media duration isn't available,
    # use the final recorded Time instead
    if duration is None or pd.isna(duration):

        duration = df["_time"].max()


    if pd.isna(duration):
        raise ValueError(
            f"{file_path.name}: could not determine session duration."
        )


    # Ceil ensures the final partial second exists
    n_seconds = int(np.ceil(duration))


    # --------------------------------------------------------
    # 6. CREATE ONE ROW FOR EVERY SECOND
    # --------------------------------------------------------

    result = pd.DataFrame({
        "pid": pid,
        "observation": observation,
        "relative_time": np.arange(
            0,
            n_seconds,
            dtype=int
        )
    })


    # Optional human-readable version
    result["relative_time_hms"] = (
        result["relative_time"]
        .apply(seconds_to_hms)
    )


    # --------------------------------------------------------
    # 7. FIND VALID STEP EVENTS
    # --------------------------------------------------------

    step_events = df[
        (df["_event_type"] == "POINT") &
        (df["_behavior"].isin(STEP_TYPES.keys())) &
        (df["_time"].notna())
    ].copy()


    # --------------------------------------------------------
    # Put each event into its one-second epoch
    #
    # Examples:
    #
    # 56.600 -> second 56
    # 57.333 -> second 57
    # 65.867 -> second 65
    #
    # --------------------------------------------------------

    step_events["_second"] = np.floor(
        step_events["_time"]
    ).astype(int)


    # --------------------------------------------------------
    # 8. TOTAL STEPS PER SECOND
    # --------------------------------------------------------

    total_counts = (
        step_events
        .groupby("_second")
        .size()
    )


    result["steps_do"] = (
        result["relative_time"]
        .map(total_counts)
        .fillna(0)
        .astype(int)
    )


    # --------------------------------------------------------
    # 9. OPTIONAL COUNTS FOR EACH STEP TYPE
    # --------------------------------------------------------

    for behavior_name, output_column in STEP_TYPES.items():

        behavior_counts = (
            step_events[
                step_events["_behavior"] == behavior_name
            ]
            .groupby("_second")
            .size()
        )

        result[output_column] = (
            result["relative_time"]
            .map(behavior_counts)
            .fillna(0)
            .astype(int)
        )


    # --------------------------------------------------------
    # 10. NON-CODABLE INTERVALS
    # --------------------------------------------------------

    noncodable_events = df[
        (df["_behavior"] == "noncodable") &
        (
            df["_event_type"]
            .isin(["START", "STOP"])
        ) &
        (df["_time"].notna())
    ].copy()


    noncodable_events = (
        noncodable_events
        .sort_values("_time")
    )


    intervals = []

    current_start = None


    for _, row in noncodable_events.iterrows():

        event = row["_event_type"]
        event_time = row["_time"]


        if event == "START":

            current_start = event_time


        elif event == "STOP":

            if current_start is not None:

                intervals.append(
                    (
                        current_start,
                        event_time
                    )
                )

                current_start = None


    # If START occurred but no STOP appeared,
    # treat the rest of the recording as non-codable
    if current_start is not None:

        intervals.append(
            (
                current_start,
                duration
            )
        )


    # --------------------------------------------------------
    # 11. MARK CODABLE VS NON-CODABLE
    # --------------------------------------------------------

    result["codable"] = "codable"


    for start, stop in intervals:

        # Conservative rule:
        # If ANY portion of a 1-second epoch overlaps
        # the non-codable period, mark it non-codable.
        #
        # Example:
        # Noncodable starts at 55.7
        #
        # second 55 represents [55,56)
        # therefore it overlaps 55.7 -> 56
        # and becomes non_codable.

        overlap = (
            (result["relative_time"] < stop) &
            (
                result["relative_time"] + 1
                > start
            )
        )

        result.loc[
            overlap,
            "codable"
        ] = "non_codable"


    # --------------------------------------------------------
    # 12. PUT COLUMNS IN CLEAN ORDER
    # --------------------------------------------------------

    result = result[
        [
            "pid",
            "observation",
            "relative_time",
            "relative_time_hms",
            "codable",
            "steps_do",
            "obs_steps",
            "ambulatory",
            "mini"
        ]
    ]


    return result


# ============================================================
# RUN ALL CSV FILES
# ============================================================

all_results = []


csv_files = sorted(
    INPUT_FOLDER.glob("*.csv")
)


if len(csv_files) == 0:

    raise FileNotFoundError(
        f"No CSV files found inside:\n"
        f"{INPUT_FOLDER.resolve()}"
    )


for file_path in csv_files:

    try:

        result = process_step_file(
            file_path
        )


        # ----------------------------------------------------
        # Save intermediate file
        #
        # Example:
        #
        # 1013_2_Uwisc_StepCount_CN.csv
        #
        # becomes
        #
        # 1013_2_Uwisc_StepCount_CN_seconds.csv
        # ----------------------------------------------------

        output_name = (
            file_path.stem
            + "_seconds.csv"
        )

        output_path = (
            OUTPUT_FOLDER
            / output_name
        )

        result.to_csv(
            output_path,
            index=False
        )


        all_results.append(result)

        print(
            f"  Saved: {output_path}"
        )


    except Exception as e:

        print(
            f"\nERROR processing {file_path.name}"
        )

        print(e)

        print()


# ============================================================
# COMBINE ALL PARTICIPANTS
# ============================================================

if len(all_results) > 0:

    combined = pd.concat(
        all_results,
        ignore_index=True
    )


    # --------------------------------------------------------
    # FULL QC VERSION
    #
    # Keeps non-codable rows so you can inspect them.
    # --------------------------------------------------------

    combined_path = (
        OUTPUT_FOLDER
        / "all_steps_second_by_second.csv"
    )

    combined.to_csv(
        combined_path,
        index=False
    )


    # --------------------------------------------------------
    # WAVES CLEAN VERSION
    #
    # Removes non-codable seconds.
    #
    # The formal WAVES codebook says the dataset submitted
    # should have non-codable / missing observations removed.
    # --------------------------------------------------------

    waves_clean = combined[
        combined["codable"] == "codable"
    ].copy()


    clean_path = (
        OUTPUT_FOLDER
        / "all_steps_WAVES_clean.csv"
    )

    waves_clean.to_csv(
        clean_path,
        index=False
    )


    print("\nDONE")
    print("-----------------------------")

    print(
        f"Files processed: "
        f"{len(all_results)}"
    )

    print(
        f"Total second-level rows: "
        f"{len(combined):,}"
    )

    print(
        f"Codable WAVES rows: "
        f"{len(waves_clean):,}"
    )

    print(
        f"\nOutputs saved in:\n"
        f"{OUTPUT_FOLDER.resolve()}"
    )