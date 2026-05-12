"""
components/assistant.py
Asistente agronómico con RAG (FAISS + Groq/LLaMA 3).
"""

import streamlit as st
from rag.core import load_faiss_index, ask
from utils.db_manager import fetch_diagnosis_context

@st.cache_resource
def _get_faiss():
    return load_faiss_index()


def assistant_page():

# ── Estilos  ───────────────────
    st.markdown("""
        <style>
        /* ------------------------------------------------------------------ */
        /* Scoped assistant layout polish (avoid global effects)               */
        /* ------------------------------------------------------------------ */
        .st-key-assistant_header .agriscan-page-title {
            margin: 0 0 8px 0;
        }

        .st-key-assistant_header .assistant-title-row {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        }

        .st-key-assistant_header .assistant-title-text {
            min-width: 0;
            flex: 1 1 200px;
        }

        .st-key-assistant_header .assistant-title-text h1 {
            word-break: break-word;
            overflow-wrap: break-word;
            min-width: 0;
        }

        .st-key-assistant_header .assistant-title-text p {
            word-break: break-word;
            overflow-wrap: break-word;
        }

        .st-key-assistant_header .assistant-badges {
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
            margin-top: 2px;
            flex-shrink: 0;
            flex-basis: auto;
        }

        .st-key-assistant_header a.model-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(46, 125, 50, 0.08);
            border: 1px solid rgba(46, 125, 50, 0.18);
            color: #2E7D32 !important;
            text-decoration: none !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 0.78rem;
            font-weight: 600;
            line-height: 1;
            white-space: nowrap;
        }

        .st-key-assistant_header a.model-badge:hover {
            background: rgba(46, 125, 50, 0.12);
            border-color: rgba(46, 125, 50, 0.28);
        }

        /* Controls row: align profile + clear, tighten spacing */
        .st-key-assistant_controls {
            margin-top: 6px;
            margin-bottom: 6px;
        }

        /* Improve radio alignment (dot + label baseline) */
        .st-key-assistant_controls div[data-testid="stRadio"] label {
            align-items: center !important;
        }
        .st-key-assistant_controls div[data-testid="stRadio"] label > div {
            margin-top: 0 !important;
        }
        .st-key-assistant_controls div[data-testid="stRadio"] label p {
            margin: 0 !important;
            line-height: 1.15 !important;
            padding-top: 0 !important;
        }

        .st-key-assistant_controls .assistant-controls-caption,
        .st-key-assistant_controls .assistant-controls-caption p {
            margin-top: 6px !important;
            font-size: 0.95rem !important;
            opacity: 0.72 !important;
            font-weight: 500 !important;
        }

        /* Ajustar altura del input text */
        .stTextInput input {
            height: 52px !important;
            line-height: 2 !important;
            font-size: 1rem !important;
            padding: 1.2rem 20px 3rem 5px !important; /* top, right, bottom, left */
        }

        /* Send button */
        .st-key-rag_input_row div[data-testid="column"]:nth-of-type(2) .stButton button[kind="primary"],
        .st-key-rag_input_row div[data-testid="column"]:nth-of-type(2) .stButton button[data-testid="baseButton-primary"] {
            height: 52px !important;
            padding: 0rem 20px 0.5rem 5px !important; 
            font-size: 5rem !important;
            line-height: 1 !important;
            background-color: #6FAF6A !important;
            color: white !important;
            border: none !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 8px !important;
        }

        .st-key-rag_input_row div[data-testid="column"]:nth-of-type(2) .stButton button[kind="primary"]:hover,
        .st-key-rag_input_row div[data-testid="column"]:nth-of-type(2) .stButton button[data-testid="baseButton-primary"]:hover {
            background-color: #0a4425 !important;
            color: white !important;
        }

        /* Clear button (Export Map style) */
        /* Global button theme in app.py makes everything green; force this button to look like Export Map */
        .st-key-rag_clear_btn .stButton > button,
        .st-key-rag_clear_btn .stButton > button[data-testid="baseButton-secondary"] {
            border: 1px solid #2E7D32 !important;
            background: transparent !important;
            background-image: none !important;
            color: #2E7D32 !important;
            border-radius: 8px !important;
            height: 42px !important;
            padding: 0 12px !important;
            box-shadow: none !important;
            transform: none !important;
        }
        .st-key-rag_clear_btn .stButton > button p {
            color: #2E7D32 !important;
            font-weight: 600 !important;
        }
        .st-key-rag_clear_btn .stButton > button:hover {
            background-color: rgba(46,125,50,0.05) !important;
            border-color: #1b5e20 !important;
        }
        .st-key-rag_clear_btn .stButton > button:hover p {
            color: #1b5e20 !important;
        }

        /* Remove the outer "card" look around the clear button column */
        .st-key-rag_clear_btn,
        .st-key-rag_clear_btn div[data-testid="stVerticalBlock"],
        .st-key-rag_clear_btn div[data-testid="stVerticalBlock"] > div,
        .st-key-rag_clear_btn div[data-testid="stVerticalBlock"] > div > div {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            margin: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }

        /* Page title typography is normalized globally in app.py */
        /* (Note) model badge styling is scoped above for assistant header */

        /* Alinear columnas en la parte inferior (only the input row) */
        .st-key-rag_input_row div[data-testid="column"]:nth-of-type(1),
        .st-key-rag_input_row div[data-testid="column"]:nth-of-type(2) {
            display: flex !important;
            align-items: flex-end !important;
        }

        /* Quitar margen extra */
        .stTextInput {
            margin-bottom: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # ── Wrapper con padding lateral ────────────────────────────────────────
    _, col_main, _ = st.columns([0.08, 0.84, 0.08])

    with col_main:

        with st.container(key="assistant_header"):
            st.markdown(
                """
                <div class="agriscan-page-title">
                    <div class="assistant-title-row">
                        <div class="assistant-title-text">
                            <h1>Asistente Agronómico</h1>
                            <p class="agriscan-page-subtitle">
                                Consulta síntomas, tratamientos, prevención y contexto local de brotes.
                            </p>
                        </div>
                        <div class="assistant-badges">
                            <a class="model-badge" href="https://console.groq.com/docs/models" target="_blank" rel="noopener noreferrer">
                                Impulsado por LLaMA 3.3-70b vía Groq
                            </a>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── Cargar FAISS ───────────────────────────────────────────────────
        try:
            faiss_manager = _get_faiss()
        except Exception as e:
            st.error(f"No se pudo cargar la base de conocimiento: {e}")
            st.info("Ejecuta `scripts/build_kb.py` para generar el índice.")
            return

        # ── Session state ──────────────────────────────────────────────────
        if "rag_messages" not in st.session_state:
            st.session_state.rag_messages = []

        # ── Controles: perfil + clear ──────────────────────────────────────
        with st.container(key="assistant_controls"):
            col_role, col_clear = st.columns([5, 1], vertical_alignment="center")
            with col_role:
                role = st.radio(
                    "Perfil",
                    ["beginner", "expert"],
                    format_func=lambda x: "Agricultor" if x == "beginner" else "Agrónomo",
                    horizontal=True,
                    label_visibility="collapsed",
                )
            with col_clear:
                with st.container(key="rag_clear_btn"):
                    if st.button("Limpiar", use_container_width=True):
                        st.session_state.rag_messages = []
                        st.rerun()

            st.markdown(
                '<div class="assistant-controls-caption">'
                'Agricultor: explicaciones simples • Agrónomo: técnico y detallado'
                "</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Historial ──────────────────────────────────────────────────────
        chat_container = st.container(height=380)
        with chat_container:
            if not st.session_state.rag_messages:
                st.markdown(
                    "<div style='text-align:center; color:#3a3737; padding-top:60px; font-size:2rem;'>"
                    "<b>Empieza preguntando por una enfermedad,<br>"
                    "tratamiento o método preventivo</b>"
                    "</div>",
                    unsafe_allow_html=True
                )
            for msg in st.session_state.rag_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("sources"):
                        st.caption("Fuente: " + " · ".join(msg["sources"]))

        # ── Input: Enter should submit ─────────────────────────────────────
        with st.container(key="rag_input_row"):
            with st.form(key="rag_chat_form", clear_on_submit=True):
                col_input, col_btn = st.columns([5, 1])
                with col_input:
                    query = st.text_input(
                        "query",
                        placeholder="Ej. ¿Cuáles son los síntomas del tizón tardío en papa?",
                        label_visibility="collapsed",
                        key="rag_input_field",
                    )
                with col_btn:
                    send = st.form_submit_button("Enviar", type="primary", use_container_width=True)

        # ── Procesar ──────────────────────────────────────────────────────
        if send and query.strip():
            st.session_state.rag_messages.append({"role": "user", "content": query})

            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.rag_messages[-6:]
                if m["role"] in ("user", "assistant")
            ]

            with st.spinner("Consultando la base de conocimiento..."):
                try:
                    db_context = fetch_diagnosis_context()
                    result = ask(
                        query=query,
                        faiss_manager=faiss_manager,
                        expertise=role,
                        history=history,
                        db_context=db_context,
                    )
                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"]
                    })
                except Exception as e:
                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": f"Error: {e}",
                        "sources": []
                    })
            st.rerun()