import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
SHARED_DATA_DIR = BASE_DIR / "shared_data"
MODELS_WEIGHTS_DIR = BASE_DIR / "models_weights"

# Ensure shared data directory exists
SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Broker Configuration
BROKER_HOST = os.getenv("BROKER_HOST", "0.0.0.0")
BROKER_PORT = int(os.getenv("BROKER_PORT", 8000))
BROKER_WEBHOOK_URL = os.getenv("BROKER_WEBHOOK_URL", f"http://localhost:{BROKER_PORT}/webhook/status")

# =====================================================
# BASE URL for client-side requests (Streamlit -> Broker)
# For multi-machine demo: change this to the LAN IP of the Broker machine
# Example: BROKER_BASE_URL = "http://192.168.1.50:8000"
# =====================================================
BROKER_CLIENT_URL = os.getenv("BROKER_CLIENT_URL", f"http://localhost:{BROKER_PORT}")

# Queue Names
QUEUE_ROUTER = "router_q"
QUEUE_TOMATO = "tomato_q"
QUEUE_POTATO = "potato_q"

# Supabase Settings (used by Broker only)
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")
