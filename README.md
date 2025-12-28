# CAMELS-CL Streamflow Data Extraction for Riñihue Station

This project extracts, cleans, and visualizes streamflow data (in m³/s) for the Riñihue station from the CAMELS-CL dataset.

## Requirements

- Python 3.7+
- Required Python packages: `pandas`, `matplotlib`, `numpy`, `requests`

Install dependencies:
```bash
pip install -r requirements.txt
```

## Data Access

The CAMELS-CL dataset can be accessed through one of the following methods:

### Method 1: Using R (Recommended)

1. Install R from https://www.r-project.org/
2. Install the `camelsCL` package:
   ```bash
   Rscript -e "install.packages('camelsCL', repos='https://cloud.r-project.org')"
   ```
3. Run the Python script - it will automatically use R to download the data

### Method 2: Manual Download

1. Visit the CAMELS-CL website: https://www.cr2.cl/camels-cl/
2. Download the streamflow data file: `2_CAMELScl_streamflow_m3s.zip`
2. Create a `data` directory in this folder
3. Extract the zip file to the `data` directory
4. Run the Python script

## Usage

Run the extraction script:

```bash
python3 extract_rinihue_streamflow.py
```

The script will:
1. Attempt to download/extract data for the Riñihue station
2. Clean the data by handling missing values
3. Save cleaned data to `rinihue_streamflow_cleaned.csv`
4. Generate a plot saved as `rinihue_streamflow_plot.png`
5. Display a summary including data sizes in MB

## Output

- `rinihue_streamflow_cleaned.csv`: Cleaned streamflow data in CSV format
- `rinihue_streamflow_plot.png`: Time series plot of streamflow data
- Console output: Summary statistics including raw and cleaned data sizes

## Data Cleaning

The script handles missing values using:
1. Forward fill (carry last valid value forward)
2. Backward fill (carry next valid value backward)
3. Linear interpolation
4. Removal of any remaining rows with missing values

## Notes

- The script automatically searches for the Riñihue station data using various naming conventions
- If the station is not found, check the CAMELS-CL attributes file for the correct station identifier
- The script provides detailed error messages and suggestions if data cannot be found

