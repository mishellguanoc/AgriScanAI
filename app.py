import streamlit as st
from components.header import show_header
from components.analysis import analysis_page
from components.assistant import assistant_page
from components.map_view import map_page
from utils.db_manager import fetch_all_records
from utils.pwa_utils import enable_pwa

# Hide developer options in the 3-dot menu (theme is handled in-app).
try:
    st.set_option("client.toolbarMode", "viewer")
except Exception:
    # Older/newer Streamlit versions may not support this option.
    pass

# =========================
# CONFIG SIEMPRE ARRIBA
# =========================
st.set_page_config(
    page_title="AgriScan AI",
    layout="wide"
)

# Ensure mobile browsers use real device width so CSS media queries work.
st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
    unsafe_allow_html=True,
)

# Enable PWA features
enable_pwa()

from streamlit_js_eval import streamlit_js_eval


# ── Consent + permission bridge ───────────────────────────────────────────
# This component both displays the consent overlay and returns permission state
# to Python. Returning a value lets Streamlit rerun once with coordinates in
# session_state; a plain HTML overlay cannot do that until a manual reload.
_CONSENT_AND_LOCATION_JS = r"""
(function() {
  return new Promise(function(resolve) {
    var pd;
    try { pd = window.parent.document; } catch(e) {
      resolve({consent: false, error: "parent_document_unavailable"});
      return;
    }

    function readLocation(done) {
      if (!navigator.geolocation) {
        done({geo_error: "Browser does not support geolocation."});
        return;
      }
      navigator.geolocation.getCurrentPosition(
        function(position) {
          done({
            coords: {
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              accuracy: position.coords.accuracy
            },
            timestamp: position.timestamp
          });
        },
        function(error) {
          done({geo_error: error.message, geo_code: error.code});
        },
        {enableHighAccuracy: true, timeout: 10000, maximumAge: 300000}
      );
    }

    function requestCamera(done) {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          done();
          return;
        }
        navigator.mediaDevices.getUserMedia({video: true})
          .then(function(stream) {
            stream.getTracks().forEach(function(track) { track.stop(); });
            done();
          })
          .catch(function() { done(); });
      } catch(e) {
        done();
      }
    }

    function resolveWithLocation() {
      readLocation(function(locationPayload) {
        resolve(Object.assign({consent: true}, locationPayload || {}));
      });
    }

    if (localStorage.getItem("agriscan_consent") === "true") {
      resolveWithLocation();
      return;
    }

    var existing = pd.getElementById("agriscan-consent-overlay");
    if (existing) existing.remove();

    var ov = pd.createElement("div");
    ov.id = "agriscan-consent-overlay";
    ov.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.55);z-index:999999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);opacity:0;transition:opacity 0.25s ease;";

    ov.innerHTML = '<div style="background:var(--background-color,#0e1117);border:1px solid rgba(128,128,128,0.15);border-radius:20px;padding:32px 28px 26px;max-width:460px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);font-family:Inter,sans-serif;color:var(--text-color,#fafafa);">'
      + '<h3 style="font-family:Outfit,sans-serif;font-weight:700;margin:0 0 14px 0;">Bienvenido a AgriScan AI</h3>'
      + '<p style="opacity:0.8;margin-bottom:20px;font-size:0.9rem;line-height:1.5;">Para ofrecer seguimiento epidemiológico y análisis agrícola en tiempo real, esta aplicación requiere acceso a:</p>'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">'
        + '<div style="background:rgba(46,125,50,0.1);border-radius:8px;padding:10px;color:#2E7D32;flex-shrink:0;">'
          + '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>'
        + '</div>'
        + '<div><b style="font-family:Outfit,sans-serif;">Cámara</b><br><span style="font-size:0.8rem;opacity:0.7;">Imágenes de cultivos para diagnóstico con IA.</span></div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:22px;">'
        + '<div style="background:rgba(232,163,23,0.1);border-radius:8px;padding:10px;color:#E8A317;flex-shrink:0;">'
          + '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
        + '</div>'
        + '<div><b style="font-family:Outfit,sans-serif;">Ubicación</b><br><span style="font-size:0.8rem;opacity:0.7;">Georreferencia hallazgos para el mapa epidemiológico.</span></div>'
      + '</div>'
      + '<p style="font-size:0.72rem;opacity:0.45;font-style:italic;margin-bottom:20px;">Tus datos se procesan de forma segura y solo para inteligencia agrícola.</p>'
      + '<button id="agriscan-consent-btn" style="width:100%;padding:12px;border:none;border-radius:10px;background:linear-gradient(135deg,#2E7D32,#1B5E20);color:#fff;font-family:Outfit,sans-serif;font-weight:600;font-size:1rem;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.2);transition:opacity 0.2s;">Entendido</button>'
    + '</div>';

    pd.body.appendChild(ov);
    requestAnimationFrame(function() { ov.style.opacity = "1"; });

    pd.getElementById("agriscan-consent-btn").addEventListener("click", function() {
      localStorage.setItem("agriscan_consent", "true");
      ov.style.opacity = "0";
      setTimeout(function() { ov.remove(); }, 250);
      requestCamera(resolveWithLocation);
    });
  });
})()
"""

permission_payload = streamlit_js_eval(
    js_expressions=_CONSENT_AND_LOCATION_JS,
    key="agriscan_permission_bridge",
)
if isinstance(permission_payload, dict) and permission_payload.get("consent"):
    st.session_state.permissions_acknowledged = True
    coords = permission_payload.get("coords") or {}
    if coords.get("latitude") is not None and coords.get("longitude") is not None:
        st.session_state.geo_lat = coords["latitude"]
        st.session_state.geo_lon = coords["longitude"]

# Do not render the app until the permission bridge has responded. Otherwise
# the map paints once without GPS and then paints again when coordinates arrive.
if permission_payload is None:
    st.stop()

@st.cache_data(show_spinner=False)
def _warm_db_cache() -> bool:
    # `fetch_all_records` is already cached; this ensures the first DB call happens
    # before any visible UI is rendered.
    fetch_all_records()
    return True


if not st.session_state.get("_agriscan_db_warmed", False):
    _warm_db_cache()
    st.session_state["_agriscan_db_warmed"] = True

# Usaremos variables de Streamlit en el CSS para máxima compatibilidad.

# =========================
# 🎨 CSS PREMIUM DESIGN SYSTEM
# =========================
st.markdown("""
<style>
/* Font options that stay close to the existing "Outfit" look:
   - Urbanist (implemented): slightly taller/more elegant geometry
   - Plus Jakarta Sans (fallback option): `family=Plus+Jakarta+Sans:wght@400;500;600;700;800` */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Urbanist:wght@400;500;600;700;800&display=swap');

/* ===== CORE STYLING ===== */
/* Remove excessive top padding to bring content up */
.stApp [data-testid="stDecoration"] {
    display: none !important;
}

.stApp header[data-testid="stHeader"] {
    display: block !important;
    visibility: visible !important;
    overflow: visible !important; /* avoid clipping the 3-dot popover */
}

.stApp [data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    overflow: visible !important; /* avoid clipping the 3-dot popover */
}

.stApp [data-testid="stAppViewContainer"] {
    padding-top: 0 !important;
}

.stApp .block-container {
    margin-top: 0 !important;
}

.block-container {
    padding-top: 0.5rem !important;
}

@media screen and (max-width: 768px) {
    .block-container {
        padding-top: 0.25rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
}

:root {
    --glass-bg: var(--secondary-background-color);
    --glass-border: rgba(128, 128, 128, 0.15);
    --accent-gradient: linear-gradient(135deg, #2E7D32, #1B5E20);
}

.stApp {
    background-color: transparent;
    font-family: 'Inter', sans-serif;
    /* Slightly increase baseline text size across the app */
    font-size: 15px;
}

/* ===== TITLES & HEADERS ===== */
h1, h2, h3, [data-testid="stHeader"] {
    font-family: 'Urbanist', 'Outfit', sans-serif !important;
    letter-spacing: -0.02em;
}

h1 { font-weight: 800 !important; }
h2 { font-weight: 700 !important; }

/* ===== NORMALIZED PAGE TITLE BLOCK ===== */
.agriscan-page-title {
    margin: 0 0 10px 0;
}

.agriscan-page-title h1 {
    margin: 0 0 6px 0 !important;
    font-family: 'Urbanist', 'Outfit', sans-serif !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
    line-height: 1.06 !important;
}

/* Standard subtitle styling (based on Crop Analysis) */
.agriscan-page-subtitle {
    margin: 0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.98rem;
    color: var(--text-color);
    opacity: 0.72;
    font-weight: 500;
    line-height: 1.35;
}

/* Make helper descriptions/captions readable (used across tabs) */
.stCaption,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
.stCaption p {
    color: var(--text-color) !important;
    opacity: 0.76 !important;
    font-weight: 500 !important;
    font-size: 0.96rem !important;
    line-height: 1.45 !important;
}

.section-desc,
.section-header .section-text .section-desc,
.workflow-step .step-label,
.step-desc,
.dash-card-subtitle {
    color: var(--text-color) !important;
    opacity: 0.76 !important;
    font-weight: 500 !important;
    font-size: 0.96rem !important;
    line-height: 1.45 !important;
}

/* Widget labels (e.g., "Choose input method") skew small by default */
div[data-testid="stRadio"] [data-testid="stWidgetLabel"] p,
div[data-testid="stRadio"] label p {
    font-size: 0.96rem !important;
    line-height: 1.35 !important;
    opacity: 0.9 !important;
}

@media screen and (max-width: 768px) {
    .agriscan-page-title {
        margin-bottom: 8px;
    }
    .agriscan-page-title h1 {
        font-size: 1.55rem !important;
        margin-bottom: 4px !important;
    }
    .agriscan-page-subtitle {
        font-size: 0.9rem;
    }
}

/* ===== IMAGE FIXES ===== */
[data-testid="stImage"] {
    overflow: visible !important;
}

[data-testid="stImage"] > div {
    border-radius: 14px !important;
    overflow: hidden !important;
}

[data-testid="stImage"] img {
    border-radius: 14px !important;
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
div[data-baseweb="tab-list"] {
    width: 100% !important;
    display: grid !important;
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    gap: 0 !important;
    align-items: stretch !important;
}

/* BaseWeb tabs wrap the label in inner spans; style both the button and its children. */
button[data-baseweb="tab"],
div[data-baseweb="tab"] {
    font-family: 'Outfit', sans-serif !important;
    font-weight: 500 !important;
    font-size: clamp(0.9rem, 0.52vw + 0.6rem, 1.25rem) !important;
    color: var(--text-color) !important;
    opacity: 0.75;
    padding: 14px 18px !important;
    width: 100% !important;
    justify-content: center !important;
    border-radius: 12px 12px 0 0 !important;
    transition: all 0.2s ease !important;
    letter-spacing: -0.01em !important;
    line-height: 1.1 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    min-height: 56px !important;
}

button[data-baseweb="tab"] *,
div[data-baseweb="tab"] * {
    font-family: 'Outfit', sans-serif !important;
    font-weight: 500 !important;
    font-size: inherit !important;
    line-height: inherit !important;
    white-space: inherit !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

button[data-baseweb="tab"]:hover {
    opacity: 0.9;
    background-color: rgba(128,128,128,0.05);
}

button[aria-selected="true"] {
    opacity: 1 !important;
    color: #2E7D32 !important;
    font-weight: 700 !important;
    border-bottom: 3px solid #2E7D32 !important;
    background-color: rgba(46,125,50,0.05);
}

@media screen and (max-width: 768px) {
    button[data-baseweb="tab"],
    div[data-baseweb="tab"] {
        font-size: 0.82rem !important;
        padding: 10px 4px !important;
        min-height: 44px !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word !important;
        line-height: 1.2 !important;
        text-align: center !important;
    }
    button[data-baseweb="tab"] *,
    div[data-baseweb="tab"] * {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word !important;
    }
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
    "Análisis de Cultivo",
    "Asistente Agronómico",
    "Mapa Epidemiológico"
])

with tabs[0]:
    _, col_main, _ = st.columns([0.08, 0.84, 0.08])
    with col_main:
        analysis_page()

with tabs[1]:
    assistant_page()

with tabs[2]:
    _, col_main, _ = st.columns([0.08, 0.84, 0.08])
    with col_main:
        map_page()