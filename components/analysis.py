import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from streamlit_js_eval import get_geolocation
from utils.image_utils import extract_exif_data
from utils.db_manager import update_map_fields, clear_db_cache, fetch_contextual_diagnosis
from utils.config import BROKER_CLIENT_URL
from utils.text_utils import format_label, translate_status
from utils.rag_utils import reverse_geocode, build_diagnosis_context
from rag.core import load_faiss_index, ask_diagnosis_analysis


@st.cache_resource
def _get_faiss():
    return load_faiss_index()


# ── Scoped CSS for the crop analysis tab ───────────────────────────────────
_CHATBOT_CSS = """
<style>
/* ===== SECTION HEADERS ===== */
.section-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 20px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--glass-border);
}

.section-header .section-icon {
    width: 40px; height: 40px;
    border-radius: 12px;
    background: linear-gradient(135deg, #2E7D32, #1B5E20);
    display: flex; align-items: center; justify-content: center;
    color: #fff; flex-shrink: 0;
    box-shadow: 0 3px 10px rgba(46,125,50,0.2);
}

.section-header .section-text h3 {
    margin: 0 !important;
    padding: 0 !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.2rem !important;
    color: var(--text-color) !important;
    letter-spacing: -0.01em;
    line-height: 1.3;
}

.section-header .section-text .section-desc {
    margin: 2px 0 0 0;
    font-size: 0.78rem;
    color: var(--text-color);
    opacity: 0.5;
    font-weight: 500;
    letter-spacing: 0.01em;
}

/* ===== STEP WORKFLOW INDICATOR ===== */
.workflow-steps {
    display: flex;
    align-items: center;
    gap: 0;
    margin-bottom: 28px;
    padding: 16px 20px;
    background: var(--secondary-background-color);
    border: 1px solid var(--glass-border);
    border-radius: 14px;
}

.workflow-step {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
}

.workflow-step .step-num {
    width: 30px; height: 30px;
    border-radius: 50%;
    background: rgba(128,128,128,0.1);
    border: 2px solid rgba(128,128,128,0.2);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 0.82rem;
    color: var(--text-color);
    opacity: 0.4;
    flex-shrink: 0;
    transition: all 0.3s ease;
}

.workflow-step.active .step-num {
    background: linear-gradient(135deg, #2E7D32, #1B5E20);
    border-color: #2E7D32;
    color: #fff;
    opacity: 1;
    box-shadow: 0 2px 8px rgba(46,125,50,0.3);
}

.workflow-step.completed .step-num {
    background: #2E7D32;
    border-color: #2E7D32;
    color: #fff;
    opacity: 1;
}

.workflow-step .step-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-color);
    opacity: 0.4;
    transition: opacity 0.3s ease;
}

.workflow-step.active .step-label,
.workflow-step.completed .step-label {
    opacity: 0.85;
}

.workflow-connector {
    flex: 0.5;
    height: 2px;
    background: rgba(128,128,128,0.15);
    margin: 0 4px;
    border-radius: 1px;
}

.workflow-connector.done {
    background: linear-gradient(90deg, #2E7D32, #43A047);
}

/* ===== METADATA BADGES ===== */
.meta-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    margin-bottom: 6px;
}

.meta-badge.gps-found {
    background: rgba(46, 125, 50, 0.08);
    border: 1px solid rgba(46, 125, 50, 0.2);
    color: #2E7D32;
}

.meta-badge.gps-missing {
    background: rgba(232, 163, 23, 0.08);
    border: 1px solid rgba(232, 163, 23, 0.2);
    color: #E8A317;
}

.meta-badge.timestamp {
    background: rgba(128,128,128,0.06);
    border: 1px solid var(--glass-border);
    color: var(--text-color);
    opacity: 0.7;
}

/* ===== IMAGE CONTAINER ===== */
.image-frame {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid var(--glass-border);
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

/* ===== DIAGNOSTIC REPORT PANEL ===== */
.diag-report-panel {
    background: var(--secondary-background-color);
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 28px 32px 20px 32px;
    margin-top: 8px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.04);
}

.diag-report-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 6px;
}

.diag-report-header .diag-icon {
    width: 36px; height: 36px;
    border-radius: 10px;
    background: linear-gradient(135deg, #2E7D32, #1B5E20);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-size: 1.1rem; flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(46,125,50,0.18);
}

.diag-report-header h4 {
    margin: 0 !important;
    padding: 0 !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.15rem !important;
    color: var(--text-color) !important;
    letter-spacing: -0.01em;
}

.diag-report-subtitle {
    font-size: 0.78rem;
    color: var(--text-color);
    opacity: 0.5;
    margin-bottom: 18px;
    padding-left: 48px;
    font-weight: 500;
    letter-spacing: 0.01em;
}

.diag-location-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(46, 125, 50, 0.07);
    border: 1px solid rgba(46, 125, 50, 0.18);
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.78rem;
    color: var(--text-color);
    margin-bottom: 14px;
    font-weight: 500;
}

.diag-location-badge .pin {
    color: #2E7D32;
    font-size: 0.85rem;
}

/* ===== CHAT CONTAINER REFINEMENTS ===== */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div > [data-testid="stChatMessage"]) {
    border: 1px solid var(--glass-border) !important;
    border-radius: 14px !important;
    background: var(--background-color) !important;
}

/* ===== RESULTS CARD POLISH ===== */
.results-card {
    background: var(--secondary-background-color);
    border: 1px solid var(--glass-border);
    border-radius: 18px;
    padding: 26px 28px;
    margin-bottom: 16px;
    box-shadow: 0 4px 18px rgba(0,0,0,0.06);
    position: relative;
    overflow: hidden;
}

.results-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #2E7D32, #43A047, #66BB6A);
    border-radius: 18px 18px 0 0;
}

.results-card .label {
    color: var(--text-color);
    opacity: 0.5;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-family: 'Inter', sans-serif;
}

.results-card .disease-name {
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--text-color);
    margin-bottom: 22px;
    line-height: 1.2;
    font-family: 'Outfit', sans-serif;
}

.results-card .conf-bar-bg {
    flex-grow: 1;
    background: rgba(128,128,128,0.12);
    height: 10px;
    border-radius: 5px;
    overflow: hidden;
}

.results-card .conf-bar-fill {
    height: 100%;
    border-radius: 5px;
    transition: width 1s cubic-bezier(0.22, 1, 0.36, 1);
}

.results-card .conf-value {
    font-weight: 800;
    font-size: 1.1rem;
    min-width: 58px;
    text-align: right;
    font-family: 'Outfit', sans-serif;
}

/* ===== MAP INTEGRATION CARD ===== */
.map-card {
    background: var(--secondary-background-color);
    border: 1px solid var(--glass-border);
    border-radius: 18px;
    padding: 22px 26px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
    margin-top: 12px;
}

.map-card-title {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 0.88rem;
    color: var(--text-color);
    opacity: 0.65;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.map-card-title svg {
    opacity: 0.5;
}

/* ===== SOURCE TAGS ===== */
.source-tag {
    display: inline-block;
    background: rgba(46,125,50,0.08);
    border: 1px solid rgba(46,125,50,0.15);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.68rem;
    color: #2E7D32;
    font-weight: 600;
    margin-right: 4px;
    margin-top: 6px;
}

/* ===== PAGE TITLE ===== */
/* NOTE: page title typography is normalized globally in app.py */

/* ===== INPUT SUMMARY CARD ===== */
.input-summary-card {
    background: var(--secondary-background-color);
    border: 1px solid var(--glass-border);
    border-radius: 14px;
    padding: 18px 22px;
    margin-top: 14px;
}

.input-summary-title {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 0.95rem;
    color: var(--text-color);
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--glass-border);
}

.input-summary-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
}

.input-summary-row + .input-summary-row {
    border-top: 1px solid rgba(128,128,128,0.06);
}

.input-summary-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem;
    color: var(--text-color);
    opacity: 0.5;
    font-weight: 500;
}

.input-summary-value {
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem;
    color: var(--text-color);
    font-weight: 600;
    text-align: right;
}
</style>
"""


def _render_analysis_chatbot(res: dict):
    """
    Renders the inline diagnostic chatbot panel below the diagnosis results.
    Auto-triggers an initial analysis on first load, then allows follow-ups.

    Args:
        res: The last_analysis dict from session_state containing
             disease, plant, confidence, lat, lon, dt, upload_id.
    """
    # ── Load FAISS ──────────────────────────────────────────────────────
    try:
        faiss_manager = _get_faiss()
    except Exception as e:
        st.warning(f"Knowledge base unavailable: {e}")
        return

    # ── Resolve location from coordinates ───────────────────────────────
    lat = res.get("lat", 0.0)
    lon = res.get("lon", 0.0)
    location_info = reverse_geocode(lat, lon)

    # ── Build the diagnosis context string ──────────────────────────────
    diag_ctx = build_diagnosis_context(
        disease=res["disease"],
        plant=res["plant"],
        confidence=res["confidence"],
        lat=lat,
        lon=lon,
        captured_at=res.get("dt"),
        location_info=location_info,
    )

    # ── Panel header ────────────────────────────────────────────────────
    loc_summary = location_info.get("summary", "")
    has_location = loc_summary and loc_summary != "Location not available."

    location_badge_html = ""
    if has_location:
        location_badge_html = f'<div class="diag-location-badge"><span class="pin">&#9673;</span><span>{loc_summary}</span></div>'

    st.markdown(f"""
        <div class="diag-report-header">
            <div class="diag-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10 9 9 9 8 9"/>
                </svg>
            </div>
            <h4>Diagnostic Intelligence Report</h4>
        </div>
        <div class="diag-report-subtitle">
            AI-generated field analysis powered by RAG retrieval and LLaMA 3.3-70b
        </div>
        {location_badge_html}
    """, unsafe_allow_html=True)

    # ── Session state for analysis chat ─────────────────────────────────
    if "analysis_chat" not in st.session_state:
        st.session_state.analysis_chat = []

    # ── Auto-generate initial report if chat is empty ───────────────────
    if not st.session_state.analysis_chat:
        auto_query = (
            f"Provide a comprehensive diagnostic analysis for {res['disease']} "
            f"detected on {res['plant']} with {res['confidence'] * 100:.1f}% confidence. "
            f"Include the likely pathogen, favorable conditions, treatment options, "
            f"and prevention strategies."
        )
        if has_location:
            auto_query += (
                f" The field is located near {loc_summary}. "
                f"Consider the local climate and agroecological conditions."
            )

        with st.spinner("Generating diagnostic intelligence report..."):
            try:
                db_ctx = fetch_contextual_diagnosis(lat, lon)
                result = ask_diagnosis_analysis(
                    query=auto_query,
                    faiss_manager=faiss_manager,
                    diagnosis_context=diag_ctx,
                    history=[],
                    db_context=db_ctx,
                )
                st.session_state.analysis_chat.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result.get("sources", []),
                })
            except Exception as e:
                st.session_state.analysis_chat.append({
                    "role": "assistant",
                    "content": f"Unable to generate report: {e}",
                    "sources": [],
                })

    # ── Render chat history ─────────────────────────────────────────────
    chat_container = st.container(height=440)
    with chat_container:
        for msg in st.session_state.analysis_chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    sources_html = " ".join(
                        f'<span class="source-tag">{s}</span>' for s in msg["sources"]
                    )
                    st.markdown(
                        f'<div style="margin-top:8px; opacity:0.7; font-size:0.72rem; '
                        f'font-weight:600; color:var(--text-color);">'
                        f'References: {sources_html}</div>',
                        unsafe_allow_html=True,
                    )

    # ── Follow-up input ─────────────────────────────────────────────────
    col_q, col_send = st.columns([5.5, 1])
    with col_q:
        follow_up = st.text_input(
            "follow_up",
            placeholder="Ask a follow-up question about this diagnosis...",
            label_visibility="collapsed",
            key="analysis_followup_input",
        )
    with col_send:
        send_followup = st.button("Send", key="analysis_send_btn", use_container_width=True)

    if send_followup and follow_up.strip():
        st.session_state.analysis_chat.append({
            "role": "user",
            "content": follow_up,
        })

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.analysis_chat[-8:]
            if m["role"] in ("user", "assistant")
        ]

        with st.spinner("Consulting knowledge base..."):
            try:
                db_ctx = fetch_contextual_diagnosis(lat, lon)
                result = ask_diagnosis_analysis(
                    query=follow_up,
                    faiss_manager=faiss_manager,
                    diagnosis_context=diag_ctx,
                    history=history,
                    db_context=db_ctx,
                )
                st.session_state.analysis_chat.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result.get("sources", []),
                })
            except Exception as e:
                st.session_state.analysis_chat.append({
                    "role": "assistant",
                    "content": f"Error: {e}",
                    "sources": [],
                })
        st.rerun()


def analysis_page():

    # ── Inject scoped CSS ───────────────────────────────────────────────
    st.markdown(_CHATBOT_CSS, unsafe_allow_html=True)

    # ── Page title ──────────────────────────────────────────────────────
    st.markdown("""
        <div class="agriscan-page-title">
            <h1>Crop Image Analysis</h1>
            <p class="agriscan-page-subtitle">AI-powered crop diagnostics via distributed inference pipeline</p>
        </div>
    """, unsafe_allow_html=True)

    # --- Automatic Geolocation Fetch (only after permissions acknowledged) ---
    if "geo_lat" not in st.session_state:
        st.session_state.geo_lat = None
    if "geo_lon" not in st.session_state:
        st.session_state.geo_lon = None

    if st.session_state.get("permissions_acknowledged"):
        # Avoid StreamlitDuplicateElementKey: get_geolocation() defaults to key='getLocation()'
        loc = get_geolocation(component_key="agriscan_geo_analysis")
        if loc and "coords" in loc:
            st.session_state.geo_lat = loc["coords"]["latitude"]
            st.session_state.geo_lon = loc["coords"]["longitude"]

    # ── Determine workflow state for step indicator ──────────────────
    analysis_done = ("last_analysis" in st.session_state
                     and st.session_state["last_analysis"].get("upload_id") is not None)

    step1_cls = "completed" if analysis_done else "active"
    step2_cls = "completed" if analysis_done else ""
    step3_cls = "active" if analysis_done else ""
    conn1_cls = "done" if analysis_done else ""
    conn2_cls = ""

    st.markdown(f"""
        <div class="workflow-steps">
            <div class="workflow-step {step1_cls}">
                <div class="step-num">1</div>
                <div class="step-label">Configure & Upload</div>
            </div>
            <div class="workflow-connector {conn1_cls}"></div>
            <div class="workflow-step {step2_cls}">
                <div class="step-num">2</div>
                <div class="step-label">AI Analysis</div>
            </div>
            <div class="workflow-connector {conn2_cls}"></div>
            <div class="workflow-step {step3_cls}">
                <div class="step-num">3</div>
                <div class="step-label">Results & Report</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Section: Analysis Configuration ─────────────────────────────
    st.markdown("""
        <div class="section-header">
            <div class="section-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                </svg>
            </div>
            <div class="section-text">
                <h3>Analysis Configuration</h3>
                <p class="section-desc">Select a detection model for your crop sample</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    model_choice = st.selectbox(
        "Select AI Model",
        [
            "Crop Type Detection",
            "Potato Disease Detection",
            "Tomato Disease Detection"
        ],
        label_visibility="collapsed"
    )

    st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)

    # ── Section: Image Input ────────────────────────────────────────
    st.markdown("""
        <div class="section-header">
            <div class="section-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
                </svg>
            </div>
            <div class="section-text">
                <h3>Image Input</h3>
                <p class="section-desc">Capture or upload a crop image for analysis</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    option = st.radio(
        "Choose input method",
        ["Upload Image", "Camera"],
        horizontal=True
    )

    if option == "Camera":
        image_file = st.camera_input("Capture image")
    else:
        image_file = st.file_uploader(
            "Upload image",
            type=["jpg","jpeg","png"]
        )

    if image_file is not None:
        st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)

        # Extract metadata once (needed in both pre- and post-analysis)
        # We must extract EXIF first, then seek(0) to reset the file pointer before reading the image
        lat_exif, lon_exif, cap_dt = extract_exif_data(image_file)
        
        image_file.seek(0)
        img = Image.open(image_file).convert("RGB")
        
        lat = lat_exif if lat_exif is not None else st.session_state.geo_lat
        lon = lon_exif if lon_exif is not None else st.session_state.geo_lon

        if not analysis_done:
            # ── PRE-ANALYSIS: image + metadata + run button ─────────
            col_img, col_meta = st.columns([1, 1])

            with col_img:
                st.image(img, use_container_width=True)

            with col_meta:
                if st.button("Run AI Analysis", use_container_width=True, type="primary"):
                    import requests, time
                    url_diagnose = f"{BROKER_CLIENT_URL}/diagnose"
                    task_id = None

                    f_lat = st.session_state.get("manual_lat", float(lat) if lat else 0.0)
                    f_lon = st.session_state.get("manual_lon", float(lon) if lon else 0.0)

                    with st.spinner("Uploading and starting distributed analysis..."):
                        try:
                            image_file.seek(0)
                            files = {"image": (image_file.name, image_file, "image/jpeg")}
                            data = {
                                "latitude": f_lat,
                                "longitude": f_lon,
                                "captured_at": cap_dt.isoformat() if cap_dt else None,
                                "model": model_choice
                            }
                            res = requests.post(url_diagnose, files=files, data=data)
                            res.raise_for_status()
                            task_id = res.json().get("upload_id")
                        except Exception as e:
                            st.error(f"Error connecting to Broker: {e}")

                    if task_id:
                        status_placeholder = st.empty()
                        with st.spinner("Waiting for ML Workers..."):
                            while True:
                                try:
                                    status_res = requests.get(f"{BROKER_CLIENT_URL}/status/{task_id}")
                                    if status_res.status_code == 404:
                                        # Ticket was deleted — background discard
                                        st.session_state["last_discard"] = {
                                            "lat": f_lat, "lon": f_lon, "dt": cap_dt,
                                        }
                                        st.warning("Discarded — predicted as background.")
                                        break
                                    if status_res.status_code == 200:
                                        current = status_res.json()
                                        estado = current.get("status")
                                        status_placeholder.info(f"Current State: {translate_status(estado)}")

                                        if estado in ["Completado", "Desechado", "Error", "Desechado/Background"]:
                                            if estado == "Completado":
                                                raw_pred = current.get("disease", "Unknown")
                                                plant_pred = format_label(raw_pred)
                                                confidence = current.get("confidence", 0.0)
                                                st.session_state["last_analysis"] = {
                                                    "plant": model_choice.split(" ")[0] if model_choice != "Crop Type Detection" else "Crop",
                                                    "disease": plant_pred,
                                                    "confidence": float(confidence),
                                                    "lat": f_lat, "lon": f_lon, "dt": cap_dt,
                                                    "upload_id": task_id
                                                }
                                                st.session_state.pop("analysis_chat", None)
                                                st.success("Analysis complete!")
                                                st.rerun()
                                            elif estado in ["Desechado", "Desechado/Background"]:
                                                st.session_state["last_discard"] = {
                                                    "lat": f_lat, "lon": f_lon, "dt": cap_dt,
                                                }
                                                st.warning("Discarded — predicted as background.")
                                            else:
                                                st.warning(f"Analysis Finished with status: {translate_status(estado)}")
                                            break
                                    time.sleep(2)
                                except Exception as e:
                                    st.error(f"Error checking status: {e}")
                                    break

                # ── Metadata with styled badges ─────────────────────
                st.markdown("""
                    <div class="section-header" style="margin-top:4px;">
                        <div class="section-icon" style="width:32px; height:32px; border-radius:9px;">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
                            </svg>
                        </div>
                        <div class="section-text">
                            <h3 style="font-size:1rem !important;">Metadata & Location</h3>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                has_gps = lat is not None and lon is not None and lat != 0.0

                if not has_gps:
                    st.markdown("""
                        <div class="meta-badge gps-missing">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                            No GPS coordinates found
                        </div>
                    """, unsafe_allow_html=True)
                    if st.checkbox("Set Location Manually"):
                        c1, c2 = st.columns(2)
                        with c1:
                            final_lat = st.number_input("Lat", value=0.0, format="%.6f", key="manual_lat")
                        with c2:
                            final_lon = st.number_input("Lon", value=0.0, format="%.6f", key="manual_lon")
                    else:
                        st.session_state.manual_lat = 0.0
                        st.session_state.manual_lon = 0.0
                else:
                    st.markdown(f"""
                        <div class="meta-badge gps-found">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                            Location detected ({lat:.4f}, {lon:.4f})
                        </div>
                    """, unsafe_allow_html=True)
                    if st.checkbox("Override Location"):
                        c1, c2 = st.columns(2)
                        with c1:
                            final_lat = st.number_input("Lat", value=float(lat), format="%.6f", key="manual_lat")
                        with c2:
                            final_lon = st.number_input("Lon", value=float(lon), format="%.6f", key="manual_lon")
                    else:
                        st.session_state.manual_lat = float(lat)
                        st.session_state.manual_lon = float(lon)

                ts_display = cap_dt.strftime('%Y-%m-%d %H:%M:%S') if cap_dt else 'N/A'
                st.markdown(f"""
                    <div class="meta-badge timestamp">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        Captured: {ts_display}
                    </div>
                """, unsafe_allow_html=True)

            # ── Flag as Incorrect (subtle, non-prominent) ──────────────
            if st.session_state.get("last_discard") is not None:
                import requests as req_flag
                discard_info = st.session_state["last_discard"]
                st.markdown("""
                    <style>
                    .flag-ghost-btn .stButton > button {
                        background: transparent !important;
                        color: var(--text-color) !important;
                        opacity: 0.3 !important;
                        font-size: 0.7rem !important;
                        padding: 3px 10px !important;
                        border: 1px dashed rgba(128,128,128,0.25) !important;
                        box-shadow: none !important;
                        font-weight: 500 !important;
                        font-family: 'Inter', sans-serif !important;
                        letter-spacing: 0;
                    }
                    .flag-ghost-btn .stButton > button:hover {
                        opacity: 0.55 !important;
                        transform: none !important;
                        border-style: solid !important;
                    }
                    </style>
                """, unsafe_allow_html=True)
                _, fc, _ = st.columns([3, 2, 3])
                with fc:
                    st.markdown(
                        '<p style="text-align:center; font-size:0.7rem; opacity:0.3; '
                        'margin:10px 0 2px 0;">Incorrect?</p>',
                        unsafe_allow_html=True,
                    )
                    with st.container():
                        st.markdown('<div class="flag-ghost-btn">', unsafe_allow_html=True)
                        if st.button("Flag for review", key="flag_incorrect_btn"):
                            try:
                                image_file.seek(0)
                                files = {"image": (image_file.name, image_file, "image/jpeg")}
                                data = {
                                    "latitude": discard_info.get("lat", 0.0),
                                    "longitude": discard_info.get("lon", 0.0),
                                    "captured_at": discard_info["dt"].isoformat() if discard_info.get("dt") else None,
                                    "original_prediction": "Background",
                                }
                                flag_res = req_flag.post(f"{BROKER_CLIENT_URL}/flag", files=files, data=data)
                                if flag_res.status_code == 200:
                                    st.success("Flagged. Thank you.")
                                    st.session_state.pop("last_discard", None)
                                else:
                                    st.error(f"Failed to flag: {flag_res.text}")
                            except Exception as e:
                                st.error(f"Error: {e}")
                        st.markdown('</div>', unsafe_allow_html=True)

        else:
            # ── POST-ANALYSIS LAYOUT ────────────────────────────────
            res = st.session_state["last_analysis"]
            conf_pct = res['confidence'] * 100
            color = "#2E7D32" if conf_pct > 80 else "#E8A317" if conf_pct > 50 else "#C62828"

            # ── Two-column layout: Image + Summary (left) | Report (right)
            col_image, col_report = st.columns([1, 1.15])

            with col_report:
                # ── Diagnosis Result Card ───────────────────────────
                st.markdown(f"""
                    <div class="results-card">
                        <div class="label">Diagnosis Result</div>
                        <div class="disease-name">{res['disease']}</div>
                        <div class="label">Confidence Score</div>
                        <div style="display:flex; align-items:center; gap:14px; margin-top:6px;">
                            <div class="conf-bar-bg">
                                <div class="conf-bar-fill" style="width:{conf_pct}%; background:linear-gradient(90deg, {color}, {color}dd);"></div>
                            </div>
                            <div class="conf-value" style="color:{color};">{conf_pct:.1f}%</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                # ── Diagnostic Intelligence Report (inline) ─────────
                _render_analysis_chatbot(res)

            with col_image:
                # ── Analyzed Image ──────────────────────────────────
                st.markdown("""
                    <div class="section-header" style="margin-top:0; padding-bottom:10px;">
                        <div class="section-icon" style="width:30px; height:30px; border-radius:8px;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
                            </svg>
                        </div>
                        <div class="section-text">
                            <h3 style="font-size:0.95rem !important;">Analyzed Image</h3>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                st.image(img, use_container_width=True)

                # ── Input Summary Card ──────────────────────────────
                model_display = model_choice if model_choice else "N/A"
                file_name = getattr(image_file, 'name', 'N/A')
                file_size_kb = f"{getattr(image_file, 'size', 0) / 1024:.1f} KB"
                ts_display = cap_dt.strftime('%b %d, %Y %H:%M') if cap_dt else 'N/A'

                st.markdown(f"""
                    <div class="input-summary-card">
                        <div class="input-summary-title">Input Summary</div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Detection Model</span>
                            <span class="input-summary-value">{model_display}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Input Method</span>
                            <span class="input-summary-value">{option}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">File Name</span>
                            <span class="input-summary-value">{file_name}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">File Size</span>
                            <span class="input-summary-value">{file_size_kb}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Analyzed At</span>
                            <span class="input-summary-value">{ts_display}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                if st.button("Reset Analysis", use_container_width=True):
                    st.session_state.pop("analysis_chat", None)
                    del st.session_state["last_analysis"]
                    st.rerun()

            # ── Map Integration (full-width below) ──────────────────
            st.markdown("""
                <div class="map-card-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>
                    </svg>
                    Map Integration
                </div>
            """, unsafe_allow_html=True)

            map_c1, map_c2 = st.columns(2)
            with map_c1:
                area = st.number_input("Affected area (m\u00b2)", min_value=1, value=100)
            with map_c2:
                severity = st.slider("Disease severity estimate", 0.0, 1.0, 0.5,
                                     help="How severely is the crop affected? 0 = minor spotting, 1 = total loss")

            if st.button("Submit to Epidemiological Map", type="primary", use_container_width=True):
                success = update_map_fields(res["upload_id"], area, severity)
                if success:
                    clear_db_cache()
                    st.balloons()
                    st.success("Shared!")
                    st.session_state.pop("analysis_chat", None)
                    del st.session_state["last_analysis"]
                    st.rerun()