# Instructions for Extracting Riñihue Station Streamflow Data

## Quick Start

The script `extract_rinihue_streamflow.py` is ready to use. You need to provide access to the CAMELS-CL dataset first.

## Option 1: Install R (Easiest)

1. **Install R:**
   - macOS: `brew install r` or download from https://www.r-project.org/
   - Linux: `sudo apt-get install r-base` (Ubuntu/Debian) or use your distribution's package manager
   - Windows: Download installer from https://www.r-project.org/

2. **Install the camelsCL package:**
   ```bash
   Rscript -e "install.packages('camelsCL', repos='https://cloud.r-project.org')"
   ```

3. **Run the script:**
   ```bash
   python3 extract_rinihue_streamflow.py
   ```

The script will automatically use R to download the data for the Riñihue station.

## Option 2: Manual Download

1. **Visit the CAMELS-CL website:**
   - Go to https://www.cr2.cl/camels-cl/
   - Navigate to the download section

2. **Download the streamflow data:**
   - Download the file: `2_CAMELScl_streamflow_m3s.zip`
   - This contains streamflow data in m³/s for all stations
   - If not working, use https://explorador.cr2.cl/ to extract data manually since 1960

3. **Set up the data directory:**
   ```bash
   mkdir data
   # Extract the zip file to the data directory, or place the zip file there
   ```

4. **Run the script:**
   ```bash
   python3 extract_rinihue_streamflow.py
   ```

The script will automatically search for the Riñihue station data in the data directory.

## What the Script Does

1. **Downloads/Extracts Data:** Attempts multiple methods to get the CAMELS-CL streamflow data for Riñihue station
2. **Cleans Data:** Handles missing values using:
   - Forward fill (carries last valid value forward)
   - Backward fill (carries next valid value backward)  
   - Linear interpolation
   - Removes any remaining rows with missing values
3. **Saves CSV:** Creates `rinihue_streamflow_cleaned.csv` with the cleaned data
4. **Creates Plot:** Generates `rinihue_streamflow_plot.png` showing the time series
5. **Shows Summary:** Displays statistics including:
   - Raw data size in MB
   - Cleaned data size in MB
   - Number of records
   - Date range
   - Streamflow statistics (min, max, mean, median)

## Output Files

- `rinihue_streamflow_cleaned.csv`: Cleaned streamflow data (m³/s)
- `rinihue_streamflow_plot.png`: Time series visualization
- Console output: Complete summary with data sizes

## Troubleshooting

**If the script can't find the Riñihue station:**
- Check the CAMELS-CL attributes file for the correct station identifier
- The script searches for variations: "rinihue", "riñihue", "Rinihue", "RINIHUE"
- Ensure the data file contains streamflow data in m³/s

**If R is not found:**
- Make sure R is installed and `Rscript` is in your PATH
- On macOS/Linux, verify with: `which Rscript`

**If data download fails:**
- Try the manual download method (Option 2)
- Check your internet connection
- Verify the CAMELS-CL website is accessible

## Requirements

- Python 3.7+
- pandas, matplotlib, numpy, requests (install via `pip install -r requirements.txt`)
- R (optional, for automatic data download)
- camelsCL R package (optional, installed automatically if R is available)

