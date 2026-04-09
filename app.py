import streamlit as st
from components.header import show_header
from components.analysis import analysis_page
from components.assistant import assistant_page
from components.map_view import map_page, get_cached_map_html
from utils.db_manager import fetch_all_records


# =========================
# ⚙️ CONFIG SIEMPRE ARRIBA
# =========================
st.set_page_config(
    page_title="AgriScan AI",
    layout="wide"
)

# =========================
# 🌙 TEMA (TOGGLE EN SIDEBAR)
# =========================
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

with st.sidebar:
    st.title("⚙️ Configuración")
    st.session_state.dark_mode = st.toggle(" Dark Mode", value=st.session_state.dark_mode)

# =========================
# 🎨 COLORES
# =========================
if st.session_state.dark_mode:
    bg_color = "#0E1117"
    text_color = "#FAFAFA"
    card_color = "#1A1D23"
    button_color = "#4CAF50"
else:
    bg_color = "#F5F7FA"
    text_color = "#111111"
    card_color = "#FFFFFF"
    button_color = "#2E7D32"

# =========================
# 💄 CSS PRO (FIX COMPLETO)
# =========================
st.markdown(f"""
<style>

/* ===== FONDO GLOBAL ===== */
.stApp {{
    background-color: {bg_color};
    color: {text_color};
}}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {{
    background-color: {card_color};
    border-right: 1px solid rgba(255,255,255,0.08);
}}

/* ===== TITULOS ===== */
h1, h2, h3 {{
    color: {text_color} !important;
    font-weight: 700;
}}

/* ===== SELECTBOX ===== */
div[data-baseweb="select"] > div {{
    background-color: {card_color} !important;
    color: {text_color} !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}}

div[data-baseweb="select"] span {{
    color: {text_color} !important;
}}

/* ===== INPUTS ===== */
input {{
    background-color: {card_color} !important;
    color: {text_color} !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
}}

/* ===== RADIO BUTTONS ===== */
div[role="radiogroup"] > label {{
    background: {card_color};
    padding: 12px;
    border-radius: 12px;
    margin-bottom: 8px;
    border: 1px solid rgba(255,255,255,0.1);
}}

/* ===== FILE UPLOADER ===== */
section[data-testid="stFileUploader"] > div {{
    background: {card_color} !important;
    border-radius: 12px !important;
    border: 2px dashed rgba(255,255,255,0.2) !important;
    padding: 20px;
}}

section[data-testid="stFileUploader"] small {{
    color: gray !important;
}}

/* ===== BOTONES ===== */
.stButton>button {{
    background: linear-gradient(135deg, {button_color}, #1E88E5);
    color: white;
    border-radius: 12px;
    padding: 10px 20px;
    border: none;
    font-weight: 600;
}}

.stButton>button:hover {{
    transform: scale(1.05);
    opacity: 0.9;
}}

/* ===== TABS ===== */
button[data-baseweb="tab"] {{
    color: {text_color} !important;
    font-weight: 600;
}}

button[aria-selected="true"] {{
    border-bottom: 3px solid {button_color} !important;
}}

/* ===== TEXTO ===== */
label, .stMarkdown, p {{
    color: {text_color} !important;
}}

/* ===== OCULTAR MENU ===== */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}

</style>
""", unsafe_allow_html=True)

# =========================
# 🚀 PRELOAD DATA
# =========================
initial_data = fetch_all_records()
if not initial_data.empty:
    get_cached_map_html(initial_data)

# =========================
# 🧱 UI
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