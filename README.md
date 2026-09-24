# UWM Step Processing

Code for converting UWM step-counting observations into second-by-second data for the WAVES project.

## Files

### `step_conversion.py`
Converts raw observation CSVs into second-by-second files.

Counts:
- OBS Steps
- Ambulatory
- Mini

`steps_do` is the total of these three step types. Exercise and shuffle are not counted. Codable/non-codable status is retained.

### `step_type_totals.py`
Calculates total OBS Steps, Ambulatory, Mini, and overall steps for each participant/trial.

### `processed_final.py`
Creates a codable-only version of the processed data by removing non-codable seconds.

### `validate_processed_steps.py`
Validates processed step counts against the raw observation data, second by second and by step type, and checks the saved step totals.
