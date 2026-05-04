#!/bin/bash

# stop_services.sh
# This script stops the background services started by start_services.sh.

echo "🛑 Stopping AgriScan AI Backend Services..."

# 1. Stop the Broker API
if [ -f broker.pid ]; then
    PID=$(cat broker.pid)
    echo "Stopping Broker (PID: $PID)..."
    kill $PID 2>/dev/null
    rm broker.pid
else
    echo "Broker PID file not found."
fi

# 2. Stop the ML Workers
for worker in router_worker tomato_worker potato_worker; do
    if [ -f "${worker}.pid" ]; then
        PID=$(cat "${worker}.pid")
        echo "Stopping ${worker} (PID: $PID)..."
        kill $PID 2>/dev/null
        rm "${worker}.pid"
    else
        echo "${worker} PID file not found."
    fi
done

# 3. Stop Redis
echo "Stopping Redis server..."
redis-cli shutdown 2>/dev/null

echo "✅ All background services stopped!"
