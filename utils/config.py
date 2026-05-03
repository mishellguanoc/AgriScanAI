"""
utils/config.py
Configuración centralizada del proyecto AgriScan AI.
Todas las rutas y variables de entorno en un solo lugar.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Base de datos (sistema distribuido) ───────────────────────────────────
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")

# ── Broker del sistema distribuido ────────────────────────────────────────
BROKER_CLIENT_URL = os.getenv("BROKER_CLIENT_URL", "http://localhost:8000")

# ── RAG (Groq + FAISS) ────────────────────────────────────────────────────
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
FAISS_INDEX_PATH  = os.getenv("FAISS_INDEX_PATH", "data/embeddings/faiss_index.bin")
CHUNKS_PATH       = os.getenv("CHUNKS_PATH",      "data/embeddings/chunks.pkl")

# ── Modelo de clasificación de imágenes ───────────────────────────────────
MODEL_WEIGHTS_PATH = os.getenv("MODEL_WEIGHTS_PATH", "model_weights/agriscan_model.pth")

# ── Assets ────────────────────────────────────────────────────────────────
LOGO_PATH = os.path.join("assets", "AgriScanLogoBW.svg")