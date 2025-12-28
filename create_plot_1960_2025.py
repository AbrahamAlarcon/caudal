#!/usr/bin/env python3
"""
Create a plot for Riñihue streamflow data from 1960 to 2025.
This script will download the data if needed and create the plot.
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import subprocess
import sys

STATION_NAME = "Riñihue"
DATA_FILE = "data/rinihue_streamflow.xlsx"
CLEANED_CSV = "rinihue_streamflow_cleaned.csv"
PLOT_FILE = "rinihue_streamflow_plot_1960_2025.png"

def download_data():
    """Download data using the curl script if file doesn't exist."""
    if not os.path.exists(DATA_FILE):
        print(f"Data file not found. Downloading...")
        print("Running download_with_curl.sh...")
        result = subprocess.run(['bash', 'download_with_curl.sh'], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        
        if not os.path.exists(DATA_FILE):
            print(f"ERROR: Could not download data file.")
            print("Please run: ./download_with_curl.sh")
            return False
    return True

def load_and_process_data():
    """Load and process the streamflow data."""
    print("Loading data...")
    
    # Try to load from cleaned CSV first
    if os.path.exists(CLEANED_CSV):
        print(f"Loading from {CLEANED_CSV}...")
        df = pd.read_csv(CLEANED_CSV)
    elif os.path.exists(DATA_FILE):
        print(f"Loading from {DATA_FILE}...")
        try:
            df = pd.read_excel(DATA_FILE, engine='openpyxl')
        except:
            df = pd.read_excel(DATA_FILE)
    else:
        print("ERROR: No data file found.")
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
        col_lower = col.lower()
        if 'date' in col_lower or 'time' in col_lower or 'fecha' in col_lower:
            date_col = col
            break
    
    # Find streamflow column
    for col in df.columns:
        col_lower = col.lower()
        if ('q' in col_lower or 'streamflow' in col_lower or 'flow' in col_lower or 
            'caudal' in col_lower or 'm3s' in col_lower or 'm³/s' in col_lower):
            streamflow_col = col
            break
    
    # If not found, use first numeric column (excluding date)
    if streamflow_col is None:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if date_col and date_col in numeric_cols:
            numeric_cols.remove(date_col)
        if len(numeric_cols) > 0:
            streamflow_col = numeric_cols[0]
    
    return date_col, streamflow_col

def create_plot(df, date_col, streamflow_col):
    """Create the plot for 1960-2025."""
    print(f"\nCreating plot: {PLOT_FILE}")
    
    # Process dates
    if date_col and date_col in df.columns:
        dates = pd.to_datetime(df[date_col], errors='coerce')
        print(f"Using date column: {date_col}")
    else:
        # Try to infer from index or create date range
        # If we have a lot of rows, assume it starts from 1960
        if len(df) > 20000:
            start_date = '1960-01-01'
        else:
            start_date = '1960-01-01'
        dates = pd.date_range(start=start_date, periods=len(df), freq='D')
        print(f"No date column found, generating dates from {start_date}")
    
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
            date_range_str = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
            year_range_str = f"{min_date.strftime('%Y')}-{max_date.strftime('%Y')}"
        else:
            date_range_str = "1960-2025"
            year_range_str = "1960-2025"
    else:
        date_range_str = "1960-2025"
        year_range_str = "1960-2025"
    
    print(f"Date range: {date_range_str}")
    print(f"Streamflow column: {streamflow_col}")
    
    # Create the plot
    plt.figure(figsize=(18, 6))
    plt.plot(dates_plot, df_plot[streamflow_col], linewidth=0.7, alpha=0.8, color='steelblue')
    plt.xlabel('Date', fontsize=13, fontweight='bold')
    plt.ylabel('Streamflow (m³/s)', fontsize=13, fontweight='bold')
    plt.title(f'{STATION_NAME} Station Streamflow ({year_range_str})', 
              fontsize=15, fontweight='bold')
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Format x-axis for better readability
    ax = plt.gca()
    if len(dates_plot) > 365:
        # For yearly data or more, show year labels
        ax.xaxis.set_major_locator(plt.MaxNLocator(12))
        plt.xticks(rotation=45, ha='right')
    
    # Add statistics text box
    stats_text = f"Min: {df_plot[streamflow_col].min():.2f} m³/s\n"
    stats_text += f"Max: {df_plot[streamflow_col].max():.2f} m³/s\n"
    stats_text += f"Mean: {df_plot[streamflow_col].mean():.2f} m³/s"
    plt.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
             fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=200, bbox_inches='tight')
    print(f"\n✓ Plot saved to {PLOT_FILE}")
    print(f"  File size: {os.path.getsize(PLOT_FILE) / 1024:.1f} KB")
    plt.close()
    
    return date_range_str

def main():
    """Main function."""
    print("=" * 70)
    print(f"Creating Plot for {STATION_NAME} Station Streamflow (1960-2025)")
    print("=" * 70)
    
    # Download data if needed
    if not download_data():
        return 1
    
    # Load data
    df = load_and_process_data()
    if df is None:
        return 1
    
    # Identify columns
    date_col, streamflow_col = identify_columns(df)
    
    if streamflow_col is None:
        print("\nERROR: Could not identify streamflow column.")
        print(f"Available columns: {df.columns.tolist()}")
        return 1
    
    print(f"\nIdentified columns:")
    print(f"  Date: {date_col if date_col else 'Not found (will generate)'}")
    print(f"  Streamflow: {streamflow_col}")
    
    # Create plot
    date_range = create_plot(df, date_col, streamflow_col)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Station: {STATION_NAME}")
    print(f"Date range: {date_range}")
    print(f"Number of records: {len(df)}")
    print(f"Plot file: {PLOT_FILE}")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    exit(main())

