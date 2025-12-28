#!/usr/bin/env python3
"""
Extract and process streamflow data for Riñihue station from CAMELS-CL dataset.

This script can work in two modes:
1. If R and camelsCL package are available, it will download data automatically
2. If you have manually downloaded the CAMELS-CL data, place it in the data/ directory
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import subprocess
import numpy as np
import glob
import zipfile
from pathlib import Path
import requests
from io import BytesIO
import json
import urllib.parse
import sys

# Configuration
STATION_NAME = "Riñihue"
STATION_SEARCH_TERMS = ["rinihue", "riñihue", "Rinihue", "RINIHUE"]
OUTPUT_CSV = "rinihue_streamflow_cleaned.csv"
PLOT_FILE = "rinihue_streamflow_plot.png"
TEMP_R_SCRIPT = "temp_extract_data.R"
TEMP_RAW_CSV = "rinihue_streamflow_raw.csv"
DATA_DIR = "data"

def download_from_cr2_explorador(station_id="10111001"):
    """Download data from CR2 explorador API using the provided curl command format."""
    print(f"Attempting to download data from CR2 explorador API for station {station_id}...")
    
    # Decode the parameters from the curl command
    # The station ID 10111001 appears to be Riñihue
    options = {
        "variable": {
            "id": "qflxDaily",
            "var": "caudal",
            "intv": "daily",
            "season": "year",
            "stat": "mean",
            "minFrac": 80
        },
        "time": {
            "start": -315604800,  # 1960-01-01
            "end": 1767236399,    # 2025-12-31 23:59:59
            "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        },
        "anomaly": {
            "enabled": False,
            "type": "dif",
            "rank": "no",
            "start_year": 1980,
            "end_year": 2010,
            "minFrac": 70
        },
        "map": {
            "stat": "mean",
            "minFrac": 10,
            "borderColor": "7F7F7F",
            "colorRamp": "Jet",
            "showNaN": False,
            "limits": {
                "range": [5, 95],
                "size": [4, 12],
                "type": "prc"
            }
        },
        "series": {
            "sites": [station_id],
            "start": None,
            "end": None
        },
        "export": {
            "map": "CSV",
            "series": "CSV",  # Try CSV instead of XLSX - might be more reliable
            "view": {
                "frame": "Chile",
                "map": "roadmap",
                "clat": -39.76670000000001,
                "clon": -72.475,
                "zoom": 5,
                "width": 354,
                "height": 543
            }
        },
        "action": ["export"]  # Request export
    }
    
    # Encode options as URL parameter
    options_json = json.dumps(options, separators=(',', ':'))
    options_encoded = urllib.parse.quote(options_json)
    
    url = f"https://explorador.cr2.cl/request.php?options={options_encoded}"
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,es;q=0.8,gl;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'https://explorador.cr2.cl/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    
    try:
        print(f"Requesting data from CR2 explorador API...")
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            
            if 'xlsx' in content_type.lower() or 'excel' in content_type.lower():
                # Save XLSX file temporarily
                xlsx_path = os.path.join(DATA_DIR, "rinihue_streamflow.xlsx")
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(xlsx_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"Downloaded XLSX file: {len(response.content) / (1024 * 1024):.2f} MB")
                
                # Read XLSX with pandas
                try:
                    df = pd.read_excel(xlsx_path, engine='openpyxl')
                    print(f"Successfully read XLSX file with shape: {df.shape}")
                    return df, len(response.content) / (1024 * 1024)
                except ImportError:
                    print("openpyxl not installed. Installing...")
                    subprocess.run([sys.executable, '-m', 'pip', 'install', 'openpyxl'], check=True)
                    df = pd.read_excel(xlsx_path, engine='openpyxl')
                    return df, len(response.content) / (1024 * 1024)
                except Exception as e:
                    print(f"Error reading XLSX: {e}")
                    # Try alternative engine
                    try:
                        df = pd.read_excel(xlsx_path)
                        return df, len(response.content) / (1024 * 1024)
                    except Exception as e2:
                        print(f"Alternative read also failed: {e2}")
                        return None, 0
            elif 'json' in content_type.lower() or response.text.strip().startswith('{'):
                # Try to parse as JSON
                try:
                    data = response.json()
                    print("Received JSON response")
                    print(f"Response: {json.dumps(data, indent=2)[:500]}")
                    
                    # The response contains export URLs
                    # Look for series export URL first (this is what we want)
                    export_data = data.get('export', {})
                    series_url = export_data.get('series', {}).get('url')
                    
                    # If no series URL, check if there's a direct series export
                    if not series_url and 'series' in export_data:
                        # Sometimes the URL might be directly in series
                        if isinstance(export_data.get('series'), str):
                            series_url = export_data.get('series')
                        elif isinstance(export_data.get('series'), dict) and 'url' in export_data.get('series', {}):
                            series_url = export_data['series']['url']
                    
                    # Only use map as last resort (it's spatial data, not time series)
                    if not series_url:
                        print("Warning: No series URL found, trying map URL (this may not be time series data)")
                        map_data = export_data.get('map', {})
                        if isinstance(map_data, dict):
                            series_url = map_data.get('url')
                        elif isinstance(map_data, str):
                            series_url = map_data
                    
                    if series_url:
                        print(f"Found export URL: {series_url}")
                        # Download the actual file
                        file_response = requests.get(series_url, headers=headers, timeout=60)
                        if file_response.status_code == 200:
                            # Determine file type from URL or content
                            if series_url.endswith('.xlsx') or 'xlsx' in file_response.headers.get('Content-Type', '').lower():
                                xlsx_path = os.path.join(DATA_DIR, "rinihue_streamflow.xlsx")
                                os.makedirs(DATA_DIR, exist_ok=True)
                                with open(xlsx_path, 'wb') as f:
                                    f.write(file_response.content)
                                try:
                                    df = pd.read_excel(xlsx_path, engine='openpyxl')
                                except:
                                    df = pd.read_excel(xlsx_path)
                                return df, len(file_response.content) / (1024 * 1024)
                            elif series_url.endswith('.csv') or 'csv' in file_response.headers.get('Content-Type', '').lower():
                                csv_path = os.path.join(DATA_DIR, "rinihue_streamflow.csv")
                                os.makedirs(DATA_DIR, exist_ok=True)
                                with open(csv_path, 'wb') as f:
                                    f.write(file_response.content)
                                df = pd.read_csv(csv_path)
                                return df, len(file_response.content) / (1024 * 1024)
                            else:
                                # Try to detect format
                                temp_path = os.path.join(DATA_DIR, "rinihue_streamflow_download")
                                with open(temp_path, 'wb') as f:
                                    f.write(file_response.content)
                                # Try XLSX first
                                try:
                                    df = pd.read_excel(temp_path, engine='openpyxl')
                                    os.rename(temp_path, temp_path + '.xlsx')
                                    return df, len(file_response.content) / (1024 * 1024)
                                except:
                                    try:
                                        df = pd.read_csv(temp_path)
                                        os.rename(temp_path, temp_path + '.csv')
                                        return df, len(file_response.content) / (1024 * 1024)
                                    except:
                                        return None, 0
                    else:
                        print("No export URL found in JSON response")
                        return None, 0
                except json.JSONDecodeError:
                    print("Response is not valid JSON")
                    return None, 0
                except Exception as e:
                    print(f"Error processing JSON response: {e}")
                    return None, 0
            else:
                # Check if it's HTML (error page)
                if 'html' in content_type.lower():
                    print(f"Received HTML response (might be an error page)")
                    print(f"Response preview: {response.text[:500]}")
                    # The API might require different parameters or authentication
                    return None, 0
                
                # Try to save and read as CSV or other format
                print(f"Unexpected content type: {content_type}")
                # Try saving as file and reading
                temp_path = os.path.join(DATA_DIR, "rinihue_streamflow_temp")
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                
                # Try different formats
                for ext in ['.xlsx', '.csv', '.txt']:
                    try:
                        if ext == '.xlsx':
                            df = pd.read_excel(temp_path)
                        else:
                            df = pd.read_csv(temp_path)
                        os.rename(temp_path, temp_path + ext)
                        return df, len(response.content) / (1024 * 1024)
                    except:
                        continue
                
                return None, 0
        else:
            print(f"API request failed with status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None, 0
            
    except Exception as e:
        print(f"Error downloading from CR2 explorador: {e}")
        import traceback
        traceback.print_exc()
        return None, 0

def download_camels_data_direct():
    """Try to download CAMELS-CL data directly from the web."""
    print("Attempting to download CAMELS-CL data directly...")
    
    # Try multiple possible URLs
    urls = [
        "http://www.cr2.cl/download/camels-cl/2_CAMELScl_streamflow_m3s.zip",
        "https://www.cr2.cl/wp-content/uploads/2020/01/2_CAMELScl_streamflow_m3s.zip",
        "https://camels.cr2.cl/data/2_CAMELScl_streamflow_m3s.zip",
        "https://www.cr2.cl/camels-cl/data/2_CAMELScl_streamflow_m3s.zip",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.cr2.cl/camels-cl/'
    }
    
    for url in urls:
        try:
            print(f"Trying URL: {url}")
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            if response.status_code == 200:
                print(f"Successfully downloaded data from {url}")
                raw_size_mb = len(response.content) / (1024 * 1024)
                print(f"Downloaded {raw_size_mb:.2f} MB")
                
                # Save to temporary zip file
                zip_path = os.path.join(DATA_DIR, "camels_streamflow.zip")
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(zip_path, 'wb') as f:
                    f.write(response.content)
                
                return zip_path, raw_size_mb
            else:
                print(f"Failed with status code {response.status_code}")
        except Exception as e:
            print(f"Error with {url}: {e}")
            continue
    
    return None, 0

def check_r_available():
    """Check if R is available."""
    try:
        result = subprocess.run(['which', 'Rscript'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def create_r_script():
    """Create an R script to download and export the data."""
    r_script = f"""
# Install camelsCL if not available
if (!requireNamespace("camelsCL", quietly = TRUE)) {{
    install.packages("camelsCL", repos = "https://cloud.r-project.org")
}}

library(camelsCL)
library(zoo)

# Try to get data for Riñihue station
success <- FALSE
station_ids <- c("{STATION_NAME}", "rinihue", "Rinihue", "RINIHUE")

for (sid in station_ids) {{
    tryCatch({{
        data <- getData(x = sid, tscale = "daily")
        
        # Extract streamflow column (Qobs_m3s)
        if ("Qobs_m3s" %in% names(data)) {{
            streamflow <- data$Qobs_m3s
        }} else {{
            streamflow <- data[, grep("Q|streamflow|flow", names(data), ignore.case = TRUE)[1]]
        }}
        
        # Convert to data frame with dates
        df <- data.frame(
            date = index(streamflow),
            streamflow_m3s = as.numeric(coredata(streamflow))
        )
        
        # Save raw data
        write.csv(df, "{TEMP_RAW_CSV}", row.names = FALSE)
        
        cat("SUCCESS: Data extracted for", sid, "\\n")
        cat("Records:", nrow(df), "\\n")
        success <- TRUE
        break
    }}, error = function(e) {{
        # Continue to next ID
    }})
}}

if (!success) {{
    stop("Could not find data for Riñihue station")
}}
"""
    with open(TEMP_R_SCRIPT, 'w') as f:
        f.write(r_script)
    return TEMP_R_SCRIPT

def download_data_with_r():
    """Use R to download the CAMELS-CL data."""
    print("Creating R script to download data...")
    r_script_path = create_r_script()
    
    print("Running R script to download CAMELS-CL data...")
    print("(This may take a few minutes as it downloads the dataset if not already cached)")
    
    try:
        result = subprocess.run(
            ['Rscript', r_script_path],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        print("R script output:")
        print(result.stdout)
        if result.stderr:
            print("R script errors/warnings:")
            print(result.stderr)
        
        if result.returncode != 0:
            raise RuntimeError(f"R script failed with return code {result.returncode}")
        
        if not os.path.exists(TEMP_RAW_CSV):
            raise FileNotFoundError(f"Expected output file {TEMP_RAW_CSV} was not created")
        
        return True
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("R script timed out after 10 minutes")
    except FileNotFoundError:
        raise RuntimeError("R is not installed or not in PATH")
    finally:
        if os.path.exists(r_script_path):
            os.remove(r_script_path)

def find_station_in_directory(data_dir):
    """Search for Riñihue station data in a directory."""
    print(f"Searching for Riñihue station data in {data_dir}...")
    
    # Look for zip files, CSV, TXT, and XLSX files
    zip_files = glob.glob(os.path.join(data_dir, "*.zip"))
    csv_files = glob.glob(os.path.join(data_dir, "**/*.csv"), recursive=True)
    txt_files = glob.glob(os.path.join(data_dir, "**/*.txt"), recursive=True)
    xlsx_files = glob.glob(os.path.join(data_dir, "**/*.xlsx"), recursive=True)
    
    all_files = zip_files + csv_files + txt_files + xlsx_files
    
    for filepath in all_files:
        filename_lower = os.path.basename(filepath).lower()
        
        # Check filename
        if any(term in filename_lower for term in STATION_SEARCH_TERMS):
            print(f"Found potential station file: {filepath}")
            return filepath
        
        # If it's a zip file, check contents
        if filepath.endswith('.zip'):
            try:
                with zipfile.ZipFile(filepath, 'r') as zf:
                    # First, try to find by filename
                    for name in zf.namelist():
                        if any(term in name.lower() for term in STATION_SEARCH_TERMS):
                            print(f"Found station file in zip: {filepath} -> {name}")
                            # Extract and return path
                            zf.extract(name, data_dir)
                            return os.path.join(data_dir, name)
                    
                    # If not found by name, check file contents
                    print("Searching zip file contents for Riñihue data...")
                    for name in zf.namelist():
                        if name.endswith('.csv') or name.endswith('.txt'):
                            try:
                                # Read first part of file
                                with zf.open(name) as f:
                                    content = f.read(1000).decode('utf-8', errors='ignore').lower()
                                    if any(term in content for term in STATION_SEARCH_TERMS):
                                        print(f"Found station data in zip file: {filepath} -> {name}")
                                        zf.extract(name, data_dir)
                                        return os.path.join(data_dir, name)
                            except:
                                continue
            except Exception as e:
                print(f"Error reading zip file {filepath}: {e}")
                continue
        
        # Check file contents (first few lines)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = f.read(500).lower()
                if any(term in first_lines for term in STATION_SEARCH_TERMS):
                    print(f"Found station data in file: {filepath}")
                    return filepath
        except:
            continue
    
    return None

def load_data_from_file(filepath):
    """Load data from a file (CSV, TXT, XLSX, or other formats)."""
    print(f"Loading data from {filepath}...")
    
    # Check if it's an Excel file
    if filepath.endswith('.xlsx') or filepath.endswith('.xls'):
        try:
            df = pd.read_excel(filepath, engine='openpyxl')
            return df
        except ImportError:
            print("openpyxl not installed. Installing...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'openpyxl'], check=True)
            df = pd.read_excel(filepath, engine='openpyxl')
            return df
        except Exception as e:
            # Try without engine specification
            try:
                df = pd.read_excel(filepath)
                return df
            except Exception as e2:
                raise ValueError(f"Could not read Excel file {filepath}: {e2}")
    
    # Try different methods to read text-based files
    try:
        # Try CSV first
        df = pd.read_csv(filepath, encoding='utf-8')
    except:
        try:
            # Try with different encoding
            df = pd.read_csv(filepath, encoding='latin-1')
        except:
            try:
                # Try tab-separated
                df = pd.read_csv(filepath, sep='\t', encoding='utf-8')
            except:
                try:
                    # Try space-separated
                    df = pd.read_csv(filepath, sep=r'\s+', encoding='utf-8')
                except Exception as e:
                    raise ValueError(f"Could not read file {filepath}: {e}")
    
    return df

def clean_data(df):
    """Clean the data by handling missing values."""
    print("\nCleaning data...")
    
    df_clean = df.copy()
    
    # Identify streamflow column
    streamflow_col = None
    for col in df_clean.columns:
        col_lower = col.lower()
        if 'q' in col_lower or 'streamflow' in col_lower or 'flow' in col_lower or 'discharge' in col_lower or 'm3s' in col_lower:
            streamflow_col = col
            break
    
    if streamflow_col is None:
        # Use the first numeric column after date
        numeric_cols = df_clean.select_dtypes(include=[np.number]).columns.tolist()
        
        # Exclude date/time columns if they were converted to numeric
        date_cols = [col for col in df_clean.columns if 'date' in col.lower() or 'time' in col.lower()]
        numeric_cols = [col for col in numeric_cols if col not in date_cols]
        
        if len(numeric_cols) > 0:
            streamflow_col = numeric_cols[0]
            print(f"Using column '{streamflow_col}' as streamflow data")
        else:
            # Last resort: show available columns and ask user
            print(f"\nAvailable columns: {df_clean.columns.tolist()}")
            print(f"Data preview:")
            print(df_clean.head())
            raise ValueError(f"Could not identify streamflow column. Available columns: {df_clean.columns.tolist()}")
    else:
        print(f"Identified streamflow column: {streamflow_col}")
    
    # Check for missing values
    missing_count = df_clean[streamflow_col].isna().sum()
    total_count = len(df_clean)
    missing_pct = (missing_count / total_count) * 100 if total_count > 0 else 0
    
    print(f"Missing values: {missing_count} out of {total_count} ({missing_pct:.2f}%)")
    
    # Handle missing values: forward fill, then backward fill, then interpolate
    print("Handling missing values...")
    # Use newer pandas syntax for forward/backward fill
    df_clean[streamflow_col] = df_clean[streamflow_col].ffill().bfill()
    
    # If still missing values, use interpolation
    if df_clean[streamflow_col].isna().sum() > 0:
        df_clean[streamflow_col] = df_clean[streamflow_col].interpolate(method='linear')
    
    # Remove any remaining rows with missing values
    initial_len = len(df_clean)
    df_clean = df_clean.dropna(subset=[streamflow_col])
    final_len = len(df_clean)
    
    if initial_len != final_len:
        print(f"Removed {initial_len - final_len} rows with remaining missing values")
    
    print(f"Final data shape: {df_clean.shape}")
    print(f"Missing values after cleaning: {df_clean[streamflow_col].isna().sum()}")
    
    return df_clean, streamflow_col

def create_plot(df, streamflow_col, output_file):
    """Create a plot of the streamflow data."""
    print(f"\nCreating plot: {output_file}")
    
    # Identify date column
    date_col = None
    for col in df.columns:
        col_lower = col.lower()
        if 'date' in col_lower or 'time' in col_lower or 'fecha' in col_lower:
            date_col = col
            break
    
    if date_col is None:
        # If no date column, try to infer from data length
        # Assume data starts from 1960-01-01 if we have a lot of data points
        if len(df) > 20000:  # More than ~55 years of daily data
            start_date = '1960-01-01'
        else:
            start_date = '1970-01-01'
        dates = pd.date_range(start=start_date, periods=len(df), freq='D')
        print(f"No date column found, using generated dates starting from {start_date}")
    else:
        print(f"Using date column: {date_col}")
        dates = pd.to_datetime(df[date_col], errors='coerce')
        if dates.isna().all():
            dates = pd.date_range(start='1960-01-01', periods=len(df), freq='D')
    
    # Filter data to 1960-2025 range if dates are available
    if date_col and not dates.isna().all():
        # Filter to 1960-2025
        mask = (dates >= pd.Timestamp('1960-01-01')) & (dates <= pd.Timestamp('2025-12-31'))
        df_plot = df[mask].copy()
        dates_plot = dates[mask]
        
        if len(df_plot) == 0:
            print("Warning: No data in 1960-2025 range, plotting all available data")
            df_plot = df
            dates_plot = dates
        else:
            print(f"Filtered to {len(df_plot)} records in 1960-2025 range")
    else:
        df_plot = df
        dates_plot = dates
    
    # Get date range for title
    if len(dates_plot) > 0 and not dates_plot.isna().all():
        valid_dates = dates_plot.dropna()
        if len(valid_dates) > 0:
            date_range_str = f"{valid_dates.min().strftime('%Y')}-{valid_dates.max().strftime('%Y')}"
        else:
            date_range_str = "1960-2025"
    else:
        date_range_str = "1960-2025"
    
    # Create plot with larger figure for long time series
    plt.figure(figsize=(16, 6))
    plt.plot(dates_plot, df_plot[streamflow_col], linewidth=0.6, alpha=0.8, color='steelblue')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Streamflow (m³/s)', fontsize=12)
    plt.title(f'{STATION_NAME} Station Streamflow ({date_range_str})', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    # Format x-axis for better readability with long time series
    if len(dates_plot) > 1000:
        # For long time series, show fewer date labels
        ax = plt.gca()
        ax.xaxis.set_major_locator(plt.MaxNLocator(10))
        plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Plot saved to {output_file}")
    print(f"Date range: {date_range_str}")
    plt.close()

def main():
    """Main function to orchestrate the data extraction and processing."""
    print("=" * 60)
    print("CAMELS-CL Streamflow Data Extraction for Riñihue Station")
    print("=" * 60)
    
    try:
        df_raw = None
        raw_size_mb = 0
        
        # Try method 1: Use R if available
        if check_r_available():
            print("\nMethod 1: Using R and camelsCL package...")
            try:
                download_data_with_r()
                df_raw = pd.read_csv(TEMP_RAW_CSV)
                raw_size_mb = os.path.getsize(TEMP_RAW_CSV) / (1024 * 1024)
                print("Successfully downloaded data using R")
            except Exception as e:
                print(f"R method failed: {e}")
                print("Trying alternative method...")
        
        # Method 2: Try CR2 explorador API
        if df_raw is None:
            print("\nMethod 2: Attempting download from CR2 explorador API...")
            df_api, api_size_mb = download_from_cr2_explorador("10111001")
            if df_api is not None and len(df_api) > 0:
                df_raw = df_api
                raw_size_mb = api_size_mb
                print("Successfully downloaded data from CR2 explorador API")
        
        # Method 3: Try direct download
        if df_raw is None:
            print("\nMethod 3: Attempting direct download...")
            zip_path, zip_size_mb = download_camels_data_direct()
            if zip_path and os.path.exists(zip_path):
                # Extract and find station data
                station_file = find_station_in_directory(DATA_DIR)
                if station_file:
                    df_raw = load_data_from_file(station_file)
                    raw_size_mb = zip_size_mb  # Use zip size as raw size
                    print("Successfully downloaded and extracted data")
        
        # Method 4: Look for manually downloaded data
        if df_raw is None:
            print("\nMethod 4: Searching for manually downloaded data...")
            if os.path.exists(DATA_DIR):
                station_file = find_station_in_directory(DATA_DIR)
                if station_file:
                    df_raw = load_data_from_file(station_file)
                    raw_size_mb = os.path.getsize(station_file) / (1024 * 1024)
                else:
                    print(f"No Riñihue station data found in {DATA_DIR}")
            else:
                print(f"Data directory {DATA_DIR} does not exist")
        
        # Method 5: Check if raw CSV already exists
        if df_raw is None and os.path.exists(TEMP_RAW_CSV):
            print("\nMethod 5: Using existing raw data file...")
            df_raw = pd.read_csv(TEMP_RAW_CSV)
            raw_size_mb = os.path.getsize(TEMP_RAW_CSV) / (1024 * 1024)
        
        if df_raw is None:
            print("\n" + "=" * 60)
            print("ERROR: Could not find or download data")
            print("=" * 60)
            print("\nPlease use one of the following methods:")
            print("\n1. Install R and the camelsCL package:")
            print("   - Install R from https://www.r-project.org/")
            print("   - Run: Rscript -e \"install.packages('camelsCL')\"")
            print("   - Then run this script again")
            print("\n2. Manually download the CAMELS-CL dataset:")
            print("   - Visit: http://www.cr2.cl/download/camels-cl/")
            print("   - Or: https://www.cr2.cl/camels-cl/")
            print("   - Download: 2_CAMELScl_streamflow_m3s.zip")
            print("   - Create a 'data' directory: mkdir data")
            print("   - Place the zip file in the 'data' directory")
            print("   - Then run this script again")
            print("\nSee DOWNLOAD_INSTRUCTIONS.md for detailed download information.")
            print("=" * 60)
            return 1
        
        # Process the data
        print(f"\nRaw data shape: {df_raw.shape}")
        print(f"Columns: {df_raw.columns.tolist()}")
        print(f"\nFirst few rows:")
        print(df_raw.head())
        print(f"\nRaw data size: {raw_size_mb:.2f} MB")
        
        # Clean data
        df_clean, streamflow_col = clean_data(df_raw)
        
        # Save cleaned data
        print(f"\nSaving cleaned data to {OUTPUT_CSV}...")
        df_clean.to_csv(OUTPUT_CSV, index=False)
        clean_size_mb = os.path.getsize(OUTPUT_CSV) / (1024 * 1024)
        print(f"Cleaned data saved: {clean_size_mb:.2f} MB")
        
        # Create plot
        create_plot(df_clean, streamflow_col, PLOT_FILE)
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Station: {STATION_NAME}")
        print(f"Raw data size: {raw_size_mb:.2f} MB")
        print(f"Cleaned data size: {clean_size_mb:.2f} MB")
        print(f"Number of records: {len(df_clean)}")
        
        # Get date range
        date_col = None
        for col in df_clean.columns:
            if 'date' in col.lower():
                date_col = col
                break
        if date_col:
            dates = pd.to_datetime(df_clean[date_col], errors='coerce')
            valid_dates = dates.dropna()
            if len(valid_dates) > 0:
                print(f"Date range: {valid_dates.min()} to {valid_dates.max()}")
        
        print(f"Streamflow column: {streamflow_col}")
        if len(df_clean) > 0:
            print(f"\nStreamflow statistics:")
            print(f"  Min: {df_clean[streamflow_col].min():.2f} m³/s")
            print(f"  Max: {df_clean[streamflow_col].max():.2f} m³/s")
            print(f"  Mean: {df_clean[streamflow_col].mean():.2f} m³/s")
            print(f"  Median: {df_clean[streamflow_col].median():.2f} m³/s")
        
        print(f"\nOutput files:")
        print(f"  - {OUTPUT_CSV}")
        print(f"  - {PLOT_FILE}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
