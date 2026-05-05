#!/bin/bash

# start_tunnel.sh
# Starts a public tunnel and displays a mobile-optimized QR code for instant clicking.

echo "Starting secure tunnel for AgriScan AI..."
echo "------------------------------------------------"

# Create a temporary log file
TEMP_LOG=$(mktemp)
# Run SSH in the background
ssh -o StrictHostKeyChecking=no -R 80:localhost:8501 nokey@localhost.run > "$TEMP_LOG" 2>&1 &
SSH_PID=$!

# Wait for the URL
echo "Generating public link..."
URL=""
while [ -z "$URL" ]; do
    sleep 1
    URL=$(grep -oE "https://[a-zA-Z0-9.-]+\.lhr\.life" "$TEMP_LOG" | head -n 1 | tr -d '[:space:]')
    
    if ! kill -0 $SSH_PID 2>/dev/null; then
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

trap "kill $SSH_PID; rm $TEMP_LOG; exit" INT
wait
