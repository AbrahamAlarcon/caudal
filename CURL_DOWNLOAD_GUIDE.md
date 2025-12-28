# Using curl to Download Riñihue Streamflow Data

## Quick Method: Use the Provided Script

The easiest way is to use the bash script I created:

```bash
./download_with_curl.sh
```

This will download the data to `data/rinihue_streamflow.xlsx`, then you can run:

```bash
python3 extract_rinihue_streamflow.py
```

## Manual curl Command

If you want to run the curl command manually, here's how:

### Option 1: Save as XLSX file

```bash
mkdir -p data

curl 'https://explorador.cr2.cl/request.php?options=\{%22variable%22:\{%22id%22:%22qflxDaily%22,%22var%22:%22caudal%22,%22intv%22:%22daily%22,%22season%22:%22year%22,%22stat%22:%22mean%22,%22minFrac%22:80\},%22time%22:\{%22start%22:946684800,%22end%22:1766793600,%22months%22:\[1,2,3,4,5,6,7,8,9,10,11,12\]\},%22anomaly%22:\{%22enabled%22:false,%22type%22:%22dif%22,%22rank%22:%22no%22,%22start_year%22:1980,%22end_year%22:2010,%22minFrac%22:70\},%22map%22:\{%22stat%22:%22mean%22,%22minFrac%22:10,%22borderColor%22:%227F7F7F%22,%22colorRamp%22:%22Jet%22,%22showNaN%22:false,%22limits%22:\{%22range%22:\[5,95\],%22size%22:\[4,12\],%22type%22:%22prc%22\}\},%22series%22:\{%22sites%22:\[%2210111001%22\],%22start%22:null,%22end%22:null\},%22export%22:\{%22map%22:%22CSV%22,%22series%22:%22XLSX%22,%22view%22:\{%22frame%22:%22Chile%22,%22map%22:%22roadmap%22,%22clat%22:-39.76670000000001,%22clon%22:-72.475,%22zoom%22:5,%22width%22:354,%22height%22:543\}\},%22action%22:\[%22export%22\]\}' \
  -H 'Accept: application/json, text/javascript, */*; q=0.01' \
  -H 'Accept-Language: en-US,en;q=0.9,es;q=0.8,gl;q=0.7' \
  -H 'Connection: keep-alive' \
  -H 'Referer: https://explorador.cr2.cl/' \
  -H 'Sec-Fetch-Dest: empty' \
  -H 'Sec-Fetch-Mode: cors' \
  -H 'Sec-Fetch-Site: same-origin' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -H 'sec-ch-ua: "Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -o data/rinihue_streamflow.xlsx
```

### Option 2: The Python Script Will Try This Automatically

The updated `extract_rinihue_streamflow.py` script now includes a function that uses the CR2 explorador API automatically. Just run:

```bash
python3 extract_rinihue_streamflow.py
```

It will try multiple methods in this order:
1. R and camelsCL package (if R is installed)
2. **CR2 explorador API (using your curl command format)** ← NEW!
3. Direct download from CR2 website
4. Manual download from data/ directory
5. Existing raw CSV file

## Understanding the curl Command

The curl command makes a request to the CR2 explorador API with these key parameters:

- **Station ID**: `10111001` (appears to be Riñihue station)
- **Variable**: `qflxDaily` (daily streamflow/caudal)
- **Time range**: From 2000-01-01 to 2025-12-31
- **Export format**: XLSX for series data

## What Happens After Download

1. The XLSX file is saved to `data/rinihue_streamflow.xlsx`
2. The Python script reads it using pandas
3. Data is cleaned (missing values handled)
4. Saved as CSV: `rinihue_streamflow_cleaned.csv`
5. Plot generated: `rinihue_streamflow_plot.png`
6. Summary displayed with data sizes in MB

## Troubleshooting

**If curl fails:**
- Check your internet connection
- Verify the CR2 explorador website is accessible: https://explorador.cr2.cl/
- The API might require cookies - try opening the website in a browser first, then copy the cookies

**If XLSX file can't be read:**
- Make sure `openpyxl` is installed: `pip install openpyxl`
- The file might be corrupted - try downloading again

**If station ID is wrong:**
- The station ID `10111001` might not be Riñihue
- Check the CR2 explorador website to find the correct station ID
- Update the script or curl command with the correct ID

