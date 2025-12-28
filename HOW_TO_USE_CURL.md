# How to Use the curl Command to Download Riñihue Data

## The Issue

The CR2 explorador API returns map data (spatial coordinates) instead of time series data when accessed programmatically. However, your curl command should work when run directly from the command line.

## Method 1: Use the Provided Bash Script (Easiest)

I've created a script that contains your exact curl command:

```bash
./download_with_curl.sh
```

This will:
1. Create a `data/` directory
2. Download the data using your curl command
3. Save it as `data/rinihue_streamflow.xlsx`

Then run the Python script:
```bash
python3 extract_rinihue_streamflow.py
```

## Method 2: Run curl Manually

Copy and paste your curl command into the terminal:

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

**Important:** Add the `-o data/rinihue_streamflow.xlsx` flag at the end to save the file!

## What the curl Command Does

The curl command:
- Makes a request to the CR2 explorador API
- Requests daily streamflow data (`qflxDaily`) for station `10111001` (Riñihue)
- Requests the data in XLSX format
- Includes all necessary headers to mimic a browser request

## After Download

Once you have the XLSX file in the `data/` directory:

1. **Run the Python script:**
   ```bash
   python3 extract_rinihue_streamflow.py
   ```

2. The script will:
   - Find the XLSX file automatically
   - Extract the streamflow data
   - Clean missing values
   - Save as CSV: `rinihue_streamflow_cleaned.csv`
   - Generate plot: `rinihue_streamflow_plot.png`
   - Show summary with data sizes

## Troubleshooting

**If curl returns JSON instead of XLSX:**
- The API might return a JSON response with a download URL
- Look for a `url` field in the JSON response
- Download that URL separately:
  ```bash
  curl "<URL_FROM_JSON>" -o data/rinihue_streamflow.xlsx
  ```

**If you get an error:**
- Make sure you're connected to the internet
- Try opening https://explorador.cr2.cl/ in your browser first
- The API might require cookies - copy cookies from your browser and add them to the curl command with `-b 'cookie_string'`

**If the file is empty or corrupted:**
- Check the file size: `ls -lh data/rinihue_streamflow.xlsx`
- Try downloading again
- The API might have rate limits - wait a few minutes and try again

## Alternative: Use Browser

If curl doesn't work, you can:
1. Open https://explorador.cr2.cl/ in your browser
2. Navigate to the Riñihue station (ID: 10111001)
3. Export the data manually
4. Save it to the `data/` directory
5. Run the Python script

