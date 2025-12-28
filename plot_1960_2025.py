#!/usr/bin/env python3
"""
Create a plot for Riñihue streamflow data from 1960 to 2025.
This script processes the downloaded XLSX file and creates the plot.
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

STATION_NAME = "Riñihue"
DATA_FILES = [
    "data/rinihue_streamflow.xlsx",
    "rinihue_streamflow_cleaned.csv",
    "data/rinihue_streamflow.csv"
]
PLOT_FILE = "rinihue_streamflow_plot_1960_2025.png"
OUTPUT_CSV = "rinihue_streamflow_cleaned_1960_2025.csv"

def find_data_file():
    """Find the data file."""
    for filepath in DATA_FILES:
        if os.path.exists(filepath):
            return filepath
    return None

def load_data(filepath):
    """Load data from file."""
    print(f"Loading data from {filepath}...")
    
    try:
        if filepath.endswith('.xlsx'):
            # Check if it's actually JSON (API response)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(100)
                if content.strip().startswith('{'):
                    print("File appears to be JSON (API response), not XLSX data.")
                    print("Please download the actual data file using: ./download_with_curl.sh")
                    return None
            
            try:
                df = pd.read_excel(filepath, engine='openpyxl')
            except:
                df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath, encoding='utf-8')
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
        if any(term in col_lower for term in ['date', 'time', 'fecha', 'dia', 'fecha']):
            date_col = col
            break
    
    # Find streamflow column - look for common names
    for col in df.columns:
        col_lower = str(col).lower()
        if any(term in col_lower for term in ['q', 'streamflow', 'flow', 'caudal', 'm3s', 'm³/s', 'discharge', 'valor']):
            # Make sure it's not a coordinate
            if 'longitud' not in col_lower and 'latitud' not in col_lower:
                streamflow_col = col
                break
    
    # If not found, use first numeric column (excluding coordinates and dates)
    if streamflow_col is None:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        exclude = ['longitud', 'latitud', 'lon', 'lat', 'x', 'y']
        if date_col and date_col in numeric_cols:
            numeric_cols.remove(date_col)
        numeric_cols = [col for col in numeric_cols if str(col).lower() not in exclude]
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
    print(f"Missing values: {missing_count} out of {len(df_clean)} ({missing_count/len(df_clean)*100:.1f}%)")
    
    if missing_count > 0:
        df_clean[streamflow_col] = df_clean[streamflow_col].ffill().bfill()
        remaining = df_clean[streamflow_col].isna().sum()
        if remaining > 0:
            df_clean[streamflow_col] = df_clean[streamflow_col].interpolate(method='linear')
        df_clean = df_clean.dropna(subset=[streamflow_col])
        print(f"After cleaning: {len(df_clean)} records")
    
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
            date_range_str = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
        else:
            year_range_str = "1960-2025"
            date_range_str = "1960-2025"
    else:
        year_range_str = "1960-2025"
        date_range_str = "1960-2025"
    
    print(f"Date range: {date_range_str}")
    
    # Create the plot
    plt.figure(figsize=(20, 7))
    plt.plot(dates_plot, df_plot[streamflow_col], linewidth=0.6, alpha=0.8, color='steelblue')
    plt.xlabel('Date', fontsize=14, fontweight='bold')
    plt.ylabel('Streamflow (m³/s)', fontsize=14, fontweight='bold')
    plt.title(f'{STATION_NAME} Station Streamflow ({year_range_str})', 
              fontsize=16, fontweight='bold', pad=20)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Format x-axis for long time series
    ax = plt.gca()
    if len(dates_plot) > 365:
        # Show year labels
        ax.xaxis.set_major_locator(plt.MaxNLocator(15))
        plt.xticks(rotation=45, ha='right')
    
    # Add statistics box
    stats_text = f"Records: {len(df_plot):,}\n"
    stats_text += f"Min: {df_plot[streamflow_col].min():.2f} m³/s\n"
    stats_text += f"Max: {df_plot[streamflow_col].max():.2f} m³/s\n"
    stats_text += f"Mean: {df_plot[streamflow_col].mean():.2f} m³/s\n"
    stats_text += f"Median: {df_plot[streamflow_col].median():.2f} m³/s"
    plt.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
             fontsize=11, verticalalignment='top', family='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=200, bbox_inches='tight')
    print(f"✓ Plot saved to {PLOT_FILE}")
    print(f"  File size: {os.path.getsize(PLOT_FILE) / 1024:.1f} KB")
    plt.close()
    
    return date_range_str

def main():
    """Main function."""
    print("=" * 70)
    print(f"Create Plot: {STATION_NAME} Station Streamflow (1960-2025)")
    print("=" * 70)
    
    # Find data file
    data_file = find_data_file()
    if not data_file:
        print("\nERROR: No data file found!")
        print("\nPlease download the data first:")
        print("  1. Run: ./download_with_curl.sh")
        print("  2. Or place the data file in one of these locations:")
        for f in DATA_FILES:
            print(f"     - {f}")
        return 1
    
    # Load data
    df = load_data(data_file)
    if df is None:
        return 1
    
    # Identify columns
    date_col, streamflow_col = identify_columns(df)
    
    if streamflow_col is None:
        print("\nERROR: Could not identify streamflow column.")
        print(f"Available columns: {df.columns.tolist()}")
        print("\nThe data file might contain map coordinates instead of time series.")
        print("Please ensure you downloaded the time series data, not the map data.")
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
    date_range = create_plot(df_clean, date_col, streamflow_col)
    
    print("\n" + "=" * 70)
    print("COMPLETE!")
    print("=" * 70)
    print(f"Date range: {date_range}")
    print(f"Number of records: {len(df_clean):,}")
    print(f"\nOutput files:")
    print(f"  - {OUTPUT_CSV}")
    print(f"  - {PLOT_FILE}")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    exit(main())

