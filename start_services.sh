#!/bin/bash

# start_services.sh
# This script starts all the background services required for the AgriScan AI distributed pipeline.

echo "🚀 Starting AgriScan AI Backend Services..."

# 1. Start Redis Server (Daemonized)
echo "Starting Redis server..."
redis-server --daemonize yes

# Determine the absolute path to the venv Python binary.
# nohup spawns subprocesses that do NOT inherit the sourced venv,
# so we must pass the full path explicitly.
VENV_DIR="$(cd .. && pwd)/.venv"
if [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_BIN="$VENV_DIR/bin/python"
else
    echo "⚠️ Warning: Virtual environment not found at $VENV_DIR. Falling back to system Python."
    PYTHON_BIN="python"
fi

# 2. Start the Broker API
echo "Starting FastAPI Broker on port 8000..."
nohup $PYTHON_BIN -m uvicorn distributed_pipeline.broker:app --host 0.0.0.0 --port 8000 > broker.log 2>&1 &
echo $! > broker.pid

# 3. Start the ML Workers
echo "Starting Router Worker..."
nohup $PYTHON_BIN -m distributed_pipeline.router_worker > router.log 2>&1 &
echo $! > router_worker.pid

echo "Starting Tomato Worker..."
nohup $PYTHON_BIN -m distributed_pipeline.tomato_worker > tomato.log 2>&1 &
echo $! > tomato_worker.pid

echo "Starting Potato Worker..."
nohup $PYTHON_BIN -m distributed_pipeline.potato_worker > potato.log 2>&1 &
echo $! > potato_worker.pid

echo ""
echo "✅ All background services are running!"
echo "You can now run your frontend with: streamlit run app.py"
echo "To stop these services later, run: ./stop_services.sh"
