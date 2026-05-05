"""
utils/config.py
Configuración centralizada del proyecto AgriScan AI.
Todas las rutas y variables de entorno en un solo lugar.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """
    Read a secret preferring st.secrets (Streamlit runtime) over env vars.
    Falls back gracefully when running outside Streamlit (e.g. CLI workers).
    """
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# ── Base de datos (sistema distribuido) ───────────────────────────────────
SUPABASE_DB_URL = _get_secret("SUPABASE_DB_URL")

# ── Broker del sistema distribuido ────────────────────────────────────────
BROKER_CLIENT_URL = _get_secret("BROKER_CLIENT_URL", "http://localhost:8000")

# ── RAG (Groq + FAISS) ────────────────────────────────────────────────────
GROQ_API_KEY      = _get_secret("GROQ_API_KEY")
FAISS_INDEX_PATH  = _get_secret("FAISS_INDEX_PATH", "data/embeddings/faiss_index.bin")
CHUNKS_PATH       = _get_secret("CHUNKS_PATH",      "data/embeddings/chunks.pkl")

# ── Modelo de clasificación de imágenes ───────────────────────────────────
MODEL_WEIGHTS_PATH = _get_secret("MODEL_WEIGHTS_PATH", "model_weights/agriscan_model.pth")

# ── Assets ────────────────────────────────────────────────────────────────
LOGO_PATH = os.path.join("assets", "AgriScanLogoBW.svg")