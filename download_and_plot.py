#!/usr/bin/env python3
"""
Download Riñihue streamflow data (1960-2025) and create a plot.
This script handles the CR2 explorador API response and creates the plot.
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import requests
import json
import urllib.parse

STATION_NAME = "Riñihue"
STATION_ID = "10111001"
PLOT_FILE = "rinihue_streamflow_plot_1960_2025.png"
OUTPUT_CSV = "rinihue_streamflow_cleaned_1960_2025.csv"

def download_data():
    """Download data from CR2 explorador API."""
    print("Downloading data from CR2 explorador API...")
    
    # API request parameters for 1960-2025
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
            "end": 1767236399,    # 2025-12-31
            "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        },
        "series": {
            "sites": [STATION_ID],
            "start": None,
            "end": None
        },
        "export": {
            "series": "CSV",  # Request CSV format
        },
        "action": ["export"]
    }
    
    # Encode options
    options_json = json.dumps(options, separators=(',', ':'))
    options_encoded = urllib.parse.quote(options_json)
    url = f"https://explorador.cr2.cl/request.php?options={options_encoded}"
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://explorador.cr2.cl/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        print("Making API request...")
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            # Check if response is JSON
            try:
                data = response.json()
                print("Received JSON response")
                
                # Look for series export URL
                export_data = data.get('export', {})
                series_url = export_data.get('series', {}).get('url')
                
                if series_url:
                    print(f"Found download URL: {series_url}")
                    # Download the actual data file
                    file_response = requests.get(series_url, headers=headers, timeout=120)
                    if file_response.status_code == 200:
                        # Save as CSV
                        csv_path = "data/rinihue_streamflow_raw.csv"
                        os.makedirs("data", exist_ok=True)
                        with open(csv_path, 'wb') as f:
                            f.write(file_response.content)
                        print(f"Downloaded data to {csv_path}")
                        return csv_path
                    else:
                        print(f"Failed to download file: {file_response.status_code}")
                else:
                    print("No series URL found in response")
                    print(f"Response: {json.dumps(data, indent=2)}")
            except json.JSONDecodeError:
                # Response might be CSV directly
                csv_path = "data/rinihue_streamflow_raw.csv"
                os.makedirs("data", exist_ok=True)
                with open(csv_path, 'wb') as f:
                    f.write(response.content)
                print(f"Downloaded CSV directly to {csv_path}")
                return csv_path
        else:
            print(f"API request failed: {response.status_code}")
            print(response.text[:500])
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    return None

def load_and_process_data(filepath):
    """Load and process the streamflow data."""
    print(f"\nLoading data from {filepath}...")
    
    # Try different methods to read the file
    try:
        if filepath.endswith('.xlsx'):
            df = pd.read_excel(filepath, engine='openpyxl')
        else:
            # Try CSV with different encodings
            try:
                df = pd.read_csv(filepath, encoding='utf-8')
            except:
                df = pd.read_csv(filepath, encoding='latin-1')
    except Exception as e:
        print(f"Error reading file: {e}")
        return None
    
    print(f"Data shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"\nFirst few rows:")
    print(df.head())
    
    return df

def identify_columns(df):
    """Identify date and streamflow columns."""
    date_col = None
    streamflow_col = None
    
    # Find date column
    for col in df.columns:
        col_lower = str(col).lower()
        if any(term in col_lower for term in ['date', 'time', 'fecha', 'fecha', 'dia']):
            date_col = col
            break
    
    # Find streamflow column
    for col in df.columns:
        col_lower = str(col).lower()
        if any(term in col_lower for term in ['q', 'streamflow', 'flow', 'caudal', 'm3s', 'm³/s', 'discharge']):
            streamflow_col = col
            break
    
    # If not found, use first numeric column (excluding date)
    if streamflow_col is None:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if date_col and date_col in numeric_cols:
            numeric_cols.remove(date_col)
        if len(numeric_cols) > 0:
            streamflow_col = numeric_cols[0]
            print(f"Using first numeric column as streamflow: {streamflow_col}")
    
    return date_col, streamflow_col

def clean_data(df, streamflow_col):
    """Clean the data."""
    print(f"\nCleaning data...")
    df_clean = df.copy()
    
    # Handle missing values
    missing_count = df_clean[streamflow_col].isna().sum()
    print(f"Missing values: {missing_count} out of {len(df_clean)}")
    
    if missing_count > 0:
        df_clean[streamflow_col] = df_clean[streamflow_col].ffill().bfill()
        if df_clean[streamflow_col].isna().sum() > 0:
            df_clean[streamflow_col] = df_clean[streamflow_col].interpolate(method='linear')
        df_clean = df_clean.dropna(subset=[streamflow_col])
    
    return df_clean

def create_plot(df, date_col, streamflow_col):
    """Create the plot for 1960-2025."""
    print(f"\nCreating plot: {PLOT_FILE}")
    
    # Process dates
    if date_col and date_col in df.columns:
        dates = pd.to_datetime(df[date_col], errors='coerce')
        print(f"Using date column: {date_col}")
    else:
        # Generate dates starting from 1960
        dates = pd.date_range(start='1960-01-01', periods=len(df), freq='D')
        print("No date column found, generating dates from 1960-01-01")
    
    # Filter to 1960-2025 range
    if not dates.isna().all():
        mask = (dates >= pd.Timestamp('1960-01-01')) & (dates <= pd.Timestamp('2025-12-31'))
        df_plot = df[mask].copy()
        dates_plot = dates[mask]
        
        if len(df_plot) == 0:
            print("Warning: No data in 1960-2025 range, using all available data")
            df_plot = df
            dates_plot = dates
        else:
            print(f"Filtered to {len(df_plot)} records in 1960-2025 range")
    else:
        df_plot = df
        dates_plot = dates
    
    # Get actual date range
    if len(dates_plot) > 0 and not dates_plot.isna().all():
        valid_dates = dates_plot.dropna()
        if len(valid_dates) > 0:
            min_date = valid_dates.min()
            max_date = valid_dates.max()
            year_range_str = f"{min_date.strftime('%Y')}-{max_date.strftime('%Y')}"
        else:
            year_range_str = "1960-2025"
    else:
        year_range_str = "1960-2025"
    
    # Create the plot
    plt.figure(figsize=(18, 7))
    plt.plot(dates_plot, df_plot[streamflow_col], linewidth=0.7, alpha=0.8, color='steelblue')
    plt.xlabel('Date', fontsize=13, fontweight='bold')
    plt.ylabel('Streamflow (m³/s)', fontsize=13, fontweight='bold')
    plt.title(f'{STATION_NAME} Station Streamflow ({year_range_str})', 
              fontsize=16, fontweight='bold', pad=20)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Format x-axis
    ax = plt.gca()
    if len(dates_plot) > 365:
        ax.xaxis.set_major_locator(plt.MaxNLocator(12))
        plt.xticks(rotation=45, ha='right')
    
    # Add statistics
    stats_text = f"Records: {len(df_plot):,}\n"
    stats_text += f"Min: {df_plot[streamflow_col].min():.2f} m³/s\n"
    stats_text += f"Max: {df_plot[streamflow_col].max():.2f} m³/s\n"
    stats_text += f"Mean: {df_plot[streamflow_col].mean():.2f} m³/s"
    plt.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
             fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=200, bbox_inches='tight')
    print(f"✓ Plot saved to {PLOT_FILE}")
    print(f"  File size: {os.path.getsize(PLOT_FILE) / 1024:.1f} KB")
    plt.close()

def main():
    """Main function."""
    print("=" * 70)
    print(f"Download and Plot: {STATION_NAME} Station Streamflow (1960-2025)")
    print("=" * 70)
    
    # Download data
    data_file = download_data()
    if not data_file:
        print("\nCould not download data. Please check your connection or try manually.")
        return 1
    
    # Load data
    df = load_and_process_data(data_file)
    if df is None:
        return 1
    
    # Identify columns
    date_col, streamflow_col = identify_columns(df)
    
    if streamflow_col is None:
        print("\nERROR: Could not identify streamflow column.")
        print(f"Available columns: {df.columns.tolist()}")
        return 1
    
    print(f"\nIdentified columns:")
    print(f"  Date: {date_col if date_col else 'Not found (will generate from 1960)'}")
    print(f"  Streamflow: {streamflow_col}")
    
    # Clean data
    df_clean = clean_data(df, streamflow_col)
    
    # Save cleaned data
    df_clean.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✓ Cleaned data saved to {OUTPUT_CSV}")
    print(f"  File size: {os.path.getsize(OUTPUT_CSV) / (1024*1024):.2f} MB")
    
    # Create plot
    create_plot(df_clean, date_col, streamflow_col)
    
    print("\n" + "=" * 70)
    print("COMPLETE!")
    print("=" * 70)
    print(f"Output files:")
    print(f"  - {OUTPUT_CSV}")
    print(f"  - {PLOT_FILE}")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    exit(main())

