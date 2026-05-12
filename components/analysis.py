import streamlit as st
import streamlit.components.v1 as components
import base64
import io
from PIL import Image
from streamlit_js_eval import get_geolocation
from utils.image_utils import extract_exif_data
from utils.db_manager import update_map_fields, clear_db_cache, fetch_contextual_diagnosis
from utils.config import BROKER_CLIENT_URL
from utils.device_history import clear_device_history, get_device_history, save_history_record
from utils.email_utils import is_valid_email, send_diagnosis_email
from utils.text_utils import format_label_es, translate_status
from utils.rag_utils import reverse_geocode, build_diagnosis_context
from rag.core import load_faiss_index, ask_diagnosis_analysis


@st.cache_resource
def _get_faiss():
    return load_faiss_index()


def _make_thumbnail_data_url(img: Image.Image, max_px: int = 240) -> str:
    thumb = img.copy()
    thumb.thumbnail((max_px, max_px))
    buffer = io.BytesIO()
    thumb.save(buffer, format="JPEG", quality=72, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _history_record_from_analysis(res: dict, thumbnail: str | None = None) -> dict:
    captured_at = res.get("dt")
    return {
        "id": str(res.get("upload_id") or f"{res.get('disease', 'diagnostico')}-{captured_at}"),
        "plant": format_label_es(res.get("plant", "N/D")),
        "disease": format_label_es(res.get("disease", "N/D")),
        "confidence": float(res.get("confidence", 0.0)),
        "captured_at": captured_at.isoformat() if hasattr(captured_at, "isoformat") else str(captured_at or "N/D"),
        "lat": res.get("lat"),
        "lon": res.get("lon"),
        "upload_id": res.get("upload_id"),
        "thumbnail": thumbnail,
    }


def _normalize_history_item(item: dict | None) -> dict | None:
    if not item:
        return None
    normalized = dict(item)
    normalized["plant"] = format_label_es(normalized.get("plant", "N/D"))
    normalized["disease"] = format_label_es(normalized.get("disease", "N/D"))
    try:
        normalized["confidence"] = float(normalized.get("confidence", 0.0))
    except (TypeError, ValueError):
        normalized["confidence"] = 0.0
    if not normalized.get("id"):
        normalized["id"] = str(
            normalized.get("upload_id")
            or f"{normalized.get('disease', 'diagnostico')}-{normalized.get('captured_at', 'N/D')}"
        )
    return normalized


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

@media screen and (max-width: 600px) {
    .workflow-steps {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        padding: 12px 14px;
        gap: 0;
        flex-wrap: nowrap;
        margin-bottom: 18px;
    }
    .workflow-step {
        flex: 0 0 auto;
        min-width: 80px;
    }
    .workflow-connector {
        flex: 0 0 20px;
        min-width: 20px;
    }
    .workflow-step .step-label {
        font-size: 0.75rem !important;
        line-height: 1.2 !important;
    }
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
        st.warning(f"Base de conocimiento no disponible: {e}")
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
            <h4>Informe inteligente de diagnóstico</h4>
        </div>
        <div class="diag-report-subtitle">
            Análisis de campo generado con recuperación RAG y LLaMA 3.3-70b
        </div>
        {location_badge_html}
    """, unsafe_allow_html=True)

    # ── Session state for analysis chat ─────────────────────────────────
    if "analysis_chat" not in st.session_state:
        st.session_state.analysis_chat = []

    # ── Auto-generate initial report if chat is empty ───────────────────
    if not st.session_state.analysis_chat:
        auto_query = (
            f"Responde en español. Proporciona un análisis diagnóstico completo para {res['disease']} "
            f"detectado en {res['plant']} con {res['confidence'] * 100:.1f}% de confianza. "
            f"Incluye el patógeno probable, condiciones favorables, opciones de tratamiento "
            f"y estrategias de prevención."
        )
        if has_location:
            auto_query += (
                f" El campo está ubicado cerca de {loc_summary}. "
                f"Considera el clima local y las condiciones agroecológicas."
            )

        with st.spinner("Generando informe inteligente de diagnóstico..."):
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
                    "content": f"No se pudo generar el informe: {e}",
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
                        f'Referencias: {sources_html}</div>',
                        unsafe_allow_html=True,
                    )

    # ── Follow-up input (Enter submits) ─────────────────────────────────
    with st.form(key="analysis_followup_form", clear_on_submit=True):
        col_q, col_send = st.columns([5.5, 1])
        with col_q:
            follow_up = st.text_input(
                "follow_up",
                placeholder="Haz una pregunta de seguimiento sobre este diagnóstico...",
                label_visibility="collapsed",
                key="analysis_followup_input",
            )
        with col_send:
            send_followup = st.form_submit_button("Enviar", use_container_width=True)

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

        with st.spinner("Consultando la base de conocimiento..."):
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
            <h1>Análisis de Imágenes de Cultivo</h1>
            <p class="agriscan-page-subtitle">Diagnóstico agrícola con IA mediante inferencia distribuida</p>
        </div>
    """, unsafe_allow_html=True)

    if "_device_history_cache" not in st.session_state:
        st.session_state["_device_history_cache"] = []

    pending_history = _normalize_history_item(st.session_state.get("_pending_history_record"))
    if pending_history and save_history_record(
        pending_history,
        component_key=f"agriscan_history_save_{pending_history.get('id', 'pending')}",
    ):
        st.session_state["_device_history_cache"] = [
            pending_history,
            *[
                _normalize_history_item(item)
                for item in st.session_state.get("_device_history_cache", [])
                if item and item.get("id") != pending_history["id"]
            ],
        ][:20]
        st.session_state.pop("_pending_history_record", None)

    local_history = [
        item
        for item in (
            _normalize_history_item(item)
            for item in get_device_history(component_key="agriscan_history_read_analysis")
        )
        if item
    ]
    if local_history:
        st.session_state["_device_history_cache"] = local_history

    current_history = []
    if st.session_state.get("last_analysis"):
        current_history.append(_history_record_from_analysis(st.session_state["last_analysis"]))

    # Show the section always. Include pending/current records immediately while
    # the browser localStorage component completes its next render cycle.
    history_by_id = {}
    for item in [
        *st.session_state.get("_device_history_cache", []),
        *(local_history or []),
        *current_history,
        pending_history,
    ]:
        item = _normalize_history_item(item)
        if item and item.get("id"):
            history_by_id[item["id"]] = item
    visible_history = list(history_by_id.values())[:20]

    with st.expander("Historial de análisis en este dispositivo", expanded=bool(visible_history)):
        st.caption("Guardado solo en este navegador. No se sincroniza con la base de datos.")
        if not visible_history:
            st.info("Aún no hay diagnósticos guardados en este dispositivo.")
        else:
            cols = st.columns(2)
            for idx, item in enumerate(visible_history[:6]):
                with cols[idx % 2]:
                    thumb = item.get("thumbnail")
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    conf = float(item.get("confidence", 0.0)) * 100
                    st.markdown(
                        f"""
                        <div class="input-summary-card" style="margin-bottom:10px;">
                            <div class="input-summary-title">{item.get('disease', 'N/D')}</div>
                            <div class="input-summary-row"><span class="input-summary-label">Cultivo</span><span class="input-summary-value">{item.get('plant', 'N/D')}</span></div>
                            <div class="input-summary-row"><span class="input-summary-label">Confianza</span><span class="input-summary-value">{conf:.1f}%</span></div>
                            <div class="input-summary-row"><span class="input-summary-label">Fecha</span><span class="input-summary-value">{item.get('captured_at', 'N/D')}</span></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button("Restaurar resumen", key=f"restore_history_{item.get('id', idx)}"):
                        item = _normalize_history_item(item) or item
                        st.session_state["restored_history_item"] = item
                        st.session_state["last_analysis"] = {
                            "plant": format_label_es(item.get("plant", "N/D")),
                            "disease": format_label_es(item.get("disease", "N/D")),
                            "confidence": float(item.get("confidence", 0.0)),
                            "lat": item.get("lat"),
                            "lon": item.get("lon"),
                            "dt": item.get("captured_at"),
                            "upload_id": item.get("upload_id"),
                        }
                        st.session_state.pop("analysis_chat", None)
                        st.rerun()
        if st.button("Borrar historial de este dispositivo", key="clear_device_history"):
            if clear_device_history(component_key="agriscan_history_clear_analysis"):
                st.session_state.pop("restored_history_item", None)
                st.session_state.pop("_pending_history_record", None)
                st.session_state["_device_history_cache"] = []
                st.rerun()

    if st.session_state.get("restored_history_item"):
        item = st.session_state["restored_history_item"]
        conf = float(item.get("confidence", 0.0)) * 100
        st.info(
            f"Resumen restaurado: {format_label_es(item.get('disease', 'N/D'))} en {format_label_es(item.get('plant', 'N/D'))} "
            f"({conf:.1f}% de confianza)."
        )

    # --- Automatic Geolocation Fetch (only after permissions acknowledged) ---
    if "geo_lat" not in st.session_state:
        st.session_state.geo_lat = None
    if "geo_lon" not in st.session_state:
        st.session_state.geo_lon = None

    if (
        st.session_state.get("permissions_acknowledged")
        and (st.session_state.geo_lat is None or st.session_state.geo_lon is None)
    ):
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
                <div class="step-label">Configurar y subir</div>
            </div>
            <div class="workflow-connector {conn1_cls}"></div>
            <div class="workflow-step {step2_cls}">
                <div class="step-num">2</div>
                <div class="step-label">Análisis IA</div>
            </div>
            <div class="workflow-connector {conn2_cls}"></div>
            <div class="workflow-step {step3_cls}">
                <div class="step-num">3</div>
                <div class="step-label">Resultados e informe</div>
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
                <h3>Configuración del análisis</h3>
                <p class="section-desc">Selecciona un modelo de detección para tu muestra</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    model_choice = st.selectbox(
        "Selecciona modelo de IA",
        [
            "Crop Type Detection",
            "Potato Disease Detection",
            "Tomato Disease Detection",
        ],
        format_func=lambda x: {
            "Crop Type Detection": "Detección de tipo de cultivo",
            "Potato Disease Detection": "Detección de enfermedades en papa",
            "Tomato Disease Detection": "Detección de enfermedades en tomate",
        }.get(x, x),
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
                <h3>Imagen de entrada</h3>
                <p class="section-desc">Captura o sube una imagen del cultivo para analizarla</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    option = st.radio(
        "Elige el método de entrada",
        ["Subir imagen", "Cámara"],
        horizontal=True
    )

    if option == "Cámara":
        image_file = st.camera_input("Capturar imagen")
    else:
        image_file = st.file_uploader(
            "Subir imagen",
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
                if st.button("Ejecutar análisis con IA", use_container_width=True, type="primary"):
                    import requests, time
                    url_diagnose = f"{BROKER_CLIENT_URL}/diagnose"
                    task_id = None

                    f_lat = st.session_state.get("manual_lat", float(lat) if lat else 0.0)
                    f_lon = st.session_state.get("manual_lon", float(lon) if lon else 0.0)

                    with st.spinner("Subiendo imagen e iniciando análisis distribuido..."):
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
                            st.error(f"Error al conectar con el Broker: {e}")

                    if task_id:
                        status_placeholder = st.empty()
                        with st.spinner("Esperando a los nodos de inferencia..."):
                            while True:
                                try:
                                    status_res = requests.get(f"{BROKER_CLIENT_URL}/status/{task_id}")
                                    if status_res.status_code == 404:
                                        # Ticket was deleted — background discard
                                        st.session_state["last_discard"] = {
                                            "lat": f_lat, "lon": f_lon, "dt": cap_dt,
                                        }
                                        st.warning("Descartado: se predijo como fondo.")
                                        break
                                    if status_res.status_code == 200:
                                        current = status_res.json()
                                        estado = current.get("status")
                                        status_placeholder.info(f"Estado actual: {translate_status(estado)}")

                                        if estado in ["Completado", "Desechado", "Error", "Desechado/Background"]:
                                            if estado == "Completado":
                                                raw_pred = current.get("disease", "Unknown")
                                                plant_pred = format_label_es(raw_pred)
                                                confidence = current.get("confidence", 0.0)
                                                st.session_state["last_analysis"] = {
                                                    "plant": {
                                                        "Crop Type Detection": "Cultivo",
                                                        "Potato Disease Detection": "Papa",
                                                        "Tomato Disease Detection": "Tomate",
                                                    }.get(model_choice, "Cultivo"),
                                                    "disease": plant_pred,
                                                    "confidence": float(confidence),
                                                    "lat": f_lat, "lon": f_lon, "dt": cap_dt,
                                                    "upload_id": task_id
                                                }
                                                st.session_state["_pending_history_record"] = _history_record_from_analysis(
                                                    st.session_state["last_analysis"],
                                                    thumbnail=_make_thumbnail_data_url(img),
                                                )
                                                st.session_state.pop("analysis_chat", None)
                                                st.success("Análisis completado.")
                                                st.rerun()
                                            elif estado in ["Desechado", "Desechado/Background"]:
                                                st.session_state["last_discard"] = {
                                                    "lat": f_lat, "lon": f_lon, "dt": cap_dt,
                                                }
                                                st.warning("Descartado: se predijo como fondo.")
                                            else:
                                                st.warning(f"Análisis finalizado con estado: {translate_status(estado)}")
                                            break
                                    time.sleep(2)
                                except Exception as e:
                                    st.error(f"Error al consultar el estado: {e}")
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
                            <h3 style="font-size:1rem !important;">Metadatos y ubicación</h3>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                has_gps = lat is not None and lon is not None and lat != 0.0

                if not has_gps:
                    st.markdown("""
                        <div class="meta-badge gps-missing">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                            No se encontraron coordenadas GPS
                        </div>
                    """, unsafe_allow_html=True)
                    if st.checkbox("Establecer ubicación manualmente"):
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
                            Ubicación detectada ({lat:.4f}, {lon:.4f})
                        </div>
                    """, unsafe_allow_html=True)
                    if st.checkbox("Sobrescribir ubicación"):
                        c1, c2 = st.columns(2)
                        with c1:
                            final_lat = st.number_input("Lat", value=float(lat), format="%.6f", key="manual_lat")
                        with c2:
                            final_lon = st.number_input("Lon", value=float(lon), format="%.6f", key="manual_lon")
                    else:
                        st.session_state.manual_lat = float(lat)
                        st.session_state.manual_lon = float(lon)

                ts_display = cap_dt.strftime('%Y-%m-%d %H:%M:%S') if cap_dt else 'N/D'
                st.markdown(f"""
                    <div class="meta-badge timestamp">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        Capturado: {ts_display}
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
                        'margin:10px 0 2px 0;">¿Incorrecto?</p>',
                        unsafe_allow_html=True,
                    )
                    with st.container():
                        st.markdown('<div class="flag-ghost-btn">', unsafe_allow_html=True)
                        if st.button("Marcar para revisión", key="flag_incorrect_btn"):
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
                                    st.success("Marcado. Gracias.")
                                    st.session_state.pop("last_discard", None)
                                else:
                                    st.error(f"No se pudo marcar: {flag_res.text}")
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
                        <div class="label">Resultado del diagnóstico</div>
                        <div class="disease-name">{res['disease']}</div>
                        <div class="label">Nivel de confianza</div>
                        <div style="display:flex; align-items:center; gap:14px; margin-top:6px;">
                            <div class="conf-bar-bg">
                                <div class="conf-bar-fill" style="width:{conf_pct}%; background:linear-gradient(90deg, {color}, {color}dd);"></div>
                            </div>
                            <div class="conf-value" style="color:{color};">{conf_pct:.1f}%</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                with st.expander("Enviar diagnóstico por correo", expanded=False):
                    with st.form("send_diagnosis_email_form", clear_on_submit=False):
                        email_to = st.text_input(
                            "Correo electrónico",
                            placeholder="productor@ejemplo.com",
                            key="diagnosis_email_to",
                        )
                        send_email = st.form_submit_button(
                            "Enviar reporte",
                            type="primary",
                            use_container_width=True,
                        )

                    if send_email:
                        if not is_valid_email(email_to):
                            st.error("Ingresa un correo electrónico válido.")
                        else:
                            with st.spinner("Enviando reporte..."):
                                try:
                                    send_diagnosis_email(
                                        email_to,
                                        res,
                                        st.session_state.get("analysis_chat", []),
                                    )
                                    st.success("Reporte enviado correctamente.")
                                except Exception as e:
                                    st.error(f"No se pudo enviar el correo: {e}")

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
                            <h3 style="font-size:0.95rem !important;">Imagen analizada</h3>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                st.image(img, use_container_width=True)

                # ── Input Summary Card ──────────────────────────────
                model_display = {
                    "Crop Type Detection": "Detección de tipo de cultivo",
                    "Potato Disease Detection": "Detección de enfermedades en papa",
                    "Tomato Disease Detection": "Detección de enfermedades en tomate",
                }.get(model_choice, model_choice or "N/D")
                file_name = getattr(image_file, 'name', 'N/D')
                file_size_kb = f"{getattr(image_file, 'size', 0) / 1024:.1f} KB"
                ts_display = cap_dt.strftime('%b %d, %Y %H:%M') if cap_dt else 'N/D'

                st.markdown(f"""
                    <div class="input-summary-card">
                        <div class="input-summary-title">Resumen de entrada</div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Modelo de detección</span>
                            <span class="input-summary-value">{model_display}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Método de entrada</span>
                            <span class="input-summary-value">{option}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Archivo</span>
                            <span class="input-summary-value">{file_name}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Tamaño</span>
                            <span class="input-summary-value">{file_size_kb}</span>
                        </div>
                        <div class="input-summary-row">
                            <span class="input-summary-label">Analizado</span>
                            <span class="input-summary-value">{ts_display}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                if st.button("Reiniciar análisis", use_container_width=True):
                    st.session_state.pop("analysis_chat", None)
                    del st.session_state["last_analysis"]
                    st.rerun()

            # ── Map Integration (full-width below) ──────────────────
            st.markdown("""
                <div class="map-card-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>
                    </svg>
                    Integración con el mapa
                </div>
            """, unsafe_allow_html=True)

            map_c1, map_c2 = st.columns(2)
            with map_c1:
                area = st.number_input("Área afectada (m\u00b2)", min_value=1, value=100)
            with map_c2:
                severity = st.slider("Estimación de severidad", 0.0, 1.0, 0.5,
                                     help="¿Qué tan afectado está el cultivo? 0 = manchas leves, 1 = pérdida total")

            if st.button("Enviar al mapa epidemiológico", type="primary", use_container_width=True):
                success = update_map_fields(res["upload_id"], area, severity)
                if success:
                    clear_db_cache()
                    st.balloons()
                    st.success("Compartido correctamente.")
                    st.session_state.pop("analysis_chat", None)
                    del st.session_state["last_analysis"]
                    st.rerun()