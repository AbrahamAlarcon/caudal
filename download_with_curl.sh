#!/bin/bash
# Script to download Riñihue streamflow data using curl
# This uses the CR2 explorador API
# Date range: 1960-01-01 to 2025-12-31

# Create data directory if it doesn't exist
mkdir -p data

# Download the data using the curl command
# The API returns XLSX format
curl 'https://explorador.cr2.cl/request.php?options=\{%22variable%22:\{%22id%22:%22qflxDaily%22,%22var%22:%22caudal%22,%22intv%22:%22daily%22,%22season%22:%22year%22,%22stat%22:%22mean%22,%22minFrac%22:80\},%22time%22:\{%22start%22:-315604800,%22end%22:1767236399,%22months%22:\[1,2,3,4,5,6,7,8,9,10,11,12\]\},%22anomaly%22:\{%22enabled%22:false,%22type%22:%22dif%22,%22rank%22:%22no%22,%22start_year%22:1980,%22end_year%22:2010,%22minFrac%22:70\},%22map%22:\{%22stat%22:%22mean%22,%22minFrac%22:10,%22borderColor%22:%227F7F7F%22,%22colorRamp%22:%22Jet%22,%22showNaN%22:false,%22limits%22:\{%22range%22:\[5,95\],%22size%22:\[4,12\],%22type%22:%22prc%22\}\},%22series%22:\{%22sites%22:\[%2210111001%22\],%22start%22:null,%22end%22:null\},%22export%22:\{%22map%22:%22CSV%22,%22series%22:%22XLSX%22,%22view%22:\{%22frame%22:%22Chile%22,%22map%22:%22roadmap%22,%22clat%22:-39.76670000000001,%22clon%22:-72.475,%22zoom%22:5,%22width%22:354,%22height%22:543\}\},%22action%22:\[%22export%22\]\}' \
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

echo "Download complete! File saved to data/rinihue_streamflow.xlsx"
echo "Now run: python3 extract_rinihue_streamflow.py"

