import streamlit as st
from components.header import show_header
from components.analysis import analysis_page
from components.assistant import assistant_page
from components.map_view import map_page, get_cached_map_html
from utils.db_manager import fetch_all_records
from utils.pwa_utils import enable_pwa

# =========================
# CONFIG SIEMPRE ARRIBA
# =========================
st.set_page_config(
    page_title="AgriScan AI",
    layout="wide"
)

# Enable PWA features
enable_pwa()

# Usaremos variables de Streamlit en el CSS para máxima compatibilidad.

# =========================
# 🎨 CSS PREMIUM DESIGN SYSTEM
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Outfit:wght@400;600;700;800&display=swap');

/* ===== CORE STYLING ===== */
:root {
    --glass-bg: var(--secondary-background-color);
    --glass-border: rgba(128, 128, 128, 0.15);
    --accent-gradient: linear-gradient(135deg, #2E7D32, #1B5E20);
}

.stApp {
    background-color: transparent;
    font-family: 'Inter', sans-serif;
}

/* ===== TITLES & HEADERS ===== */
h1, h2, h3, [data-testid="stHeader"] {
    font-family: 'Outfit', sans-serif !important;
    letter-spacing: -0.02em;
}

h1 { font-weight: 800 !important; }
h2 { font-weight: 700 !important; }

/* ===== LOGO FIX (NO CLIPPING) ===== */
/* Remove any rounding or overflow from the logo container */
[data-testid="stImage"] {
    overflow: visible !important;
}

[data-testid="stImage"] > div {
    border-radius: 0 !important;
    overflow: visible !important;
}

[data-testid="stImage"] img {
    border-radius: 0 !important;
    mix-blend-mode: difference;
    filter: brightness(1.2); /* Boost visibility */
    transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

[data-testid="stImage"] img:hover {
    transform: scale(1.05);
}

/* ===== CARDS & CONTAINERS ===== */
div[data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"] {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 25px;
    margin-bottom: 20px;
    /* Removed backdrop-filter: blur(10px) because it creates a stacking context preventing mix-blend-mode difference from working against the body */
    transition: all 0.3s ease;
}

/* ===== SELECTBOX & INPUTS ===== */
div[data-baseweb="select"] > div, input {
    background-color: var(--background-color) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    color: var(--text-color) !important;
    /* Native padding and heights are kept to avoid cropping text */
    transition: border-color 0.2s ease !important;
}

div[data-baseweb="select"] > div:hover, input:focus {
    border-color: #2E7D32 !important;
}

/* ===== BUTTONS ===== */
.stButton > button {
    background: var(--accent-gradient) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
    font-family: 'Outfit', sans-serif !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(46, 125, 50, 0.2) !important;
    opacity: 0.95;
}

/* ===== TABS ===== */
button[data-baseweb="tab"] {
    font-family: 'Outfit', sans-serif !important;
    font-weight: 600 !important;
    color: var(--text-color) !important;
    opacity: 0.7;
}

button[aria-selected="true"] {
    opacity: 1 !important;
    border-bottom: 3px solid #2E7D32 !important;
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background-color: var(--secondary-background-color) !important;
    backdrop-filter: blur(20px);
    border-right: 1px solid var(--glass-border);
}

/* ===== DIVIDER ===== */
hr {
    border: none;
    height: 1px;
    background: linear-gradient(to right, transparent, var(--glass-border), transparent);
    margin: 30px 0;
}

/* ===== HIDE FOOTER REDUNDANCY ===== */
footer { visibility: hidden; }

</style>
""", unsafe_allow_html=True)

# UI
# =========================
show_header()

tabs = st.tabs([
    "Crop Analysis",
    "Agronomic Assistant",
    "Epidemiological Map"
])

with tabs[0]:
    analysis_page()

with tabs[1]:
    assistant_page()

with tabs[2]:
    map_page()