#!/bin/bash

# start_tunnel.sh
# Starts a public tunnel and displays a mobile-optimized QR code for instant clicking.

echo "Starting secure tunnel for AgriScan AI..."
echo "------------------------------------------------"

# Ensure cloudflared is downloaded
if [ ! -f "cloudflared-linux-amd64" ]; then
    echo "Downloading Cloudflare Tunnel..."
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod +x cloudflared-linux-amd64
fi

# Create a temporary log file
TEMP_LOG=$(mktemp)
# Run Cloudflare Tunnel in the background
./cloudflared-linux-amd64 tunnel --url http://localhost:8501 > "$TEMP_LOG" 2>&1 &
TUNNEL_PID=$!

# Wait for the URL
echo "Generating public link..."
URL=""
while [ -z "$URL" ]; do
    sleep 1
    URL=$(grep -oE "https://[a-zA-Z0-9.-]+\.trycloudflare\.com" "$TEMP_LOG" | head -n 1 | tr -d '[:space:]')
    
    if ! kill -0 $TUNNEL_PID 2>/dev/null; then
        echo "Error: Tunnel failed."
        rm "$TEMP_LOG"
        exit 1
    fi
done

clear
echo "Tunnel Ready!"
echo "------------------------------------------------"
echo "SCAN TO OPEN APP INSTANTLY:"
echo ""

# We use a special 'qr' utility via curl that is optimized for mobile browser detection.
# We also print the clickable link as a fallback.
curl -s "https://qrcode.show/$URL"

echo ""
echo "------------------------------------------------"
echo "CLICKABLE LINK:"
echo -e "\033[1;4;34m$URL\033[0m"
echo "------------------------------------------------"
echo "Press Ctrl+C to close the tunnel."

trap "kill $TUNNEL_PID; rm $TEMP_LOG; exit" INT
wait
