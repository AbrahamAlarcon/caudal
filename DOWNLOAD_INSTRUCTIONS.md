# Where to Download CAMELS-CL Dataset

## Official Download Sources

### Option 1: Direct Download from CR2 Website (Recommended)

1. **Visit the official CAMELS-CL website:**
   - Main site: https://www.cr2.cl/camels-cl/
   - Direct download: http://www.cr2.cl/download/camels-cl/

2. **Download the streamflow data:**
   - Look for the file: `2_CAMELScl_streamflow_m3s.zip`
   - This contains streamflow data in m³/s for all stations including Riñihue

3. **Extract and use:**
   - Extract the zip file
   - Place it in the `data/` directory in this project
   - Run: `python3 extract_rinihue_streamflow.py`

### Option 2: Using R Package (Automatic Download)

If you have R installed, the `camelsCL` package can automatically download the data:

1. **Install R:**
   - macOS: `brew install r` or download from https://www.r-project.org/
   - Linux: `sudo apt-get install r-base`
   - Windows: Download from https://www.r-project.org/

2. **Install the camelsCL package:**
   ```bash
   Rscript -e "install.packages('camelsCL', repos='https://cloud.r-project.org')"
   ```

3. **Run the Python script:**
   ```bash
   python3 extract_rinihue_streamflow.py
   ```
   
   The script will automatically use R to download the data for Riñihue station.

### Option 3: Using Python hydrodataset Package

The `hydrodataset` Python package can help download CAMELS-CL data:

1. **Install the package:**
   ```bash
   pip install hydrodataset
   ```

2. **Note:** According to the documentation, `hydrodataset` may require manual download for CAMELS-CL due to web connection issues, but it can help with data processing.

## Alternative Sources

- **GitLab Repository:** https://gitlab.com/hgarcesf/camelsCL (R package source)
- **CRAN:** https://cran.r-project.org/web/packages/camelsCL/ (R package)

## What You Need

For the Riñihue station extraction, you specifically need:
- **File:** `2_CAMELScl_streamflow_m3s.zip` (streamflow data in m³/s)
- **Optional:** `1_CAMELScl_attributes.zip` (station attributes/metadata - helpful for finding station codes)

## Quick Start

The easiest approach is:

1. **Visit:** http://www.cr2.cl/download/camels-cl/
2. **Download:** `2_CAMELScl_streamflow_m3s.zip`
3. **Create data directory:**
   ```bash
   mkdir data
   ```
4. **Extract or place the zip file in the `data/` directory**
5. **Run the script:**
   ```bash
   python3 extract_rinihue_streamflow.py
   ```

The script will automatically find and extract the Riñihue station data from the zip file.

