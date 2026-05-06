"""
rag/core.py
Lógica central del RAG: retrieval semántico con FAISS + generación con Groq/LLaMA 3.
Reemplaza a rag.py del proyecto RAG_AgriScanAI.
"""

import os
from groq import Groq
from rag.faiss_manager import FAISSManager
from utils.config import GROQ_API_KEY, FAISS_INDEX_PATH, CHUNKS_PATH

# ── Prompts del sistema ────────────────────────────────────────────────────
SYSTEM_BEGINNER = """Eres un asistente agrícola amigable que ayuda a agricultores rurales del Ecuador.
Usa lenguaje simple y cotidiano, evita términos científicos o explícalos con ejemplos prácticos.
Si no tienes información suficiente, dilo claramente y recomienda consultar al INIAP o MAG.
Responde siempre en español."""

SYSTEM_EXPERT = """Eres un asistente técnico especializado en fitopatología y agronomía tropical andina.
Usa terminología científica precisa, cita mecanismos de acción, nombres de patógenos y protocolos técnicos.
Si no tienes información suficiente, indícalo y refiere a fuentes como INIAP, MAG o literatura indexada.
Responde siempre en español."""

# ── Inicialización del índice FAISS ────────────────────────────────────────
# Esta función debe llamarse desde app.py con @st.cache_resource
def load_faiss_index() -> FAISSManager:
    """
    Carga el índice FAISS desde disco.
    Usar con @st.cache_resource en app.py para que solo cargue una vez.
    """
    fm = FAISSManager()
    fm.load(
        index_path=FAISS_INDEX_PATH,
        chunks_path=CHUNKS_PATH
    )
    return fm

# ── Retrieval semántico ────────────────────────────────────────────────────
def retrieve(query: str, faiss_manager: FAISSManager, top_k: int = 15) -> list:
    """
    Busca los chunks más relevantes usando similitud semántica (cosine via FAISS).
    Filtra por umbral mínimo de similitud 0.30.
    """
    results = faiss_manager.search(query, k=top_k)
    return [r for r in results if r["similarity_score"] >= 0.20]

# ── Generación con Groq / LLaMA 3 ─────────────────────────────────────────
def ask(
    query: str,
    faiss_manager: FAISSManager,
    expertise: str = "beginner",
    history: list = None,
    db_context: str = "",
) -> dict:
    """
    Pipeline RAG completo:
      1. Recupera chunks relevantes con FAISS
      2. Opcionalmente antepone datos en tiempo real de la BD (db_context)
      3. Construye contexto y prompt
      4. Llama a Groq (LLaMA 3.3-70b)
      5. Retorna respuesta + fuentes usadas

    Args:
        query:        Pregunta del usuario
        faiss_manager: Instancia de FAISSManager ya cargada
        expertise:    'beginner' (agricultor) | 'expert' (agrónomo)
        history:      Lista de mensajes previos [{"role": ..., "content": ...}]
        db_context:   Resumen en texto de los registros epidemiológicos en vivo
                      generado por fetch_diagnosis_context(). Si está vacío se omite.

    Returns:
        {"answer": str, "sources": list[str]}
    """
    if history is None:
        history = []

    api_key = GROQ_API_KEY
    if not api_key:
        return {
            "answer": "⚠️ No se encontró la API key de Groq. Revisa tu archivo .streamlit/secrets.toml",
            "sources": []
        }

    # 1. Retrieval semántico (FAISS)
    retrieved = retrieve(query, faiss_manager)

    # 2. Construir contexto FAISS
    if retrieved:
        faiss_context = "\n\n---\n\n".join([
            f"[Fuente: {c['source']} | Relevancia: {c['similarity_score']:.2f}]\n{c['text']}"
            for c in retrieved
        ])
        sources = list(dict.fromkeys(c["source"] for c in retrieved))
    else:
        faiss_context = "No se encontró información relevante en la base de conocimiento para esta consulta."
        sources = []

    # 3. Combinar contexto: datos en tiempo real primero, luego base de conocimiento
    context_parts = []
    if db_context:
        context_parts.append(
            "### DATOS EN TIEMPO REAL (registros epidemiológicos de la plataforma)\n\n"
            + db_context
        )
    context_parts.append(
        "### BASE DE CONOCIMIENTO (documentos agrícolas)\n\n" + faiss_context
    )
    context = "\n\n" + "\n\n".join(context_parts)

    # 4. Construir mensajes
    system_prompt = SYSTEM_BEGINNER if expertise == "beginner" else SYSTEM_EXPERT

    user_message = f"""Tienes acceso a los siguientes fragmentos de documentos agrícolas. LEE TODO EL CONTEXTO CUIDADOSAMENTE antes de responder.

CONTEXTO:
{context}

PREGUNTA: {query}

INSTRUCCIONES IMPORTANTES:
1. USA la información del contexto para responder. Si hay información relevante, ÚSALA aunque no sea perfecta.
2. Si hay DATOS EN TIEMPO REAL disponibles, úsalos para responder preguntas sobre la situación actual de enfermedades en el campo.
3. NO digas que no tienes información si el contexto contiene datos relacionados con la pregunta.
4. Si el contexto menciona síntomas, tratamientos, fungicidas o prácticas — inclúyelos en tu respuesta.
5. Solo recomienda el INIAP o MAG si realmente no hay NADA relevante en el contexto.
6. Responde en español de forma clara y útil."""

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

    # 5. Llamar a Groq
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=600,
        temperature=0.3
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": sources
    }


# ── System prompt for the inline diagnosis chatbot ─────────────────────────
SYSTEM_ANALYSIS = """You are an expert agronomic field advisor embedded in the AgriScan AI diagnostic platform.
You have just received the results of an AI-powered crop disease analysis, including the predicted disease, model confidence score, GPS coordinates, and reverse-geocoded location data.

Your role:
1. Provide a thorough, actionable agronomic analysis of the diagnosed condition.
2. Consider the geographic region and local climate when recommending treatments, resistant cultivars, and prevention strategies.
3. If coordinates place the field in a known agricultural region (e.g., Ecuadorian highlands, coastal lowlands), tailor advice to that agroecological zone.
4. Include: disease description, likely causal pathogen, favorable conditions, recommended chemical/biological treatments, cultural practices, and monitoring steps.
5. If the crop appears healthy, confirm it and suggest preventive best practices for the region.
6. Keep answers clear, structured with headers, and professional.
7. Always respond in the same language the user writes in. Default to English unless the user writes in Spanish or another language."""


def ask_diagnosis_analysis(
    query: str,
    faiss_manager: FAISSManager,
    diagnosis_context: str,
    history: list = None,
    db_context: str = "",
) -> dict:
    """
    Specialized RAG pipeline for the inline diagnosis chatbot in the
    Crop Analysis tab.  Differs from `ask()` in that it:
      - Uses a diagnosis-oriented system prompt (SYSTEM_ANALYSIS)
      - Always injects the current scan's diagnosis context
      - Searches FAISS for disease-specific agronomic knowledge
      - Produces structured, region-aware field recommendations

    Args:
        query:              User question or 'auto' for auto-generated report
        faiss_manager:      Loaded FAISSManager instance
        diagnosis_context:  Text from build_diagnosis_context()
        history:            Chat history [{role, content}, ...]
        db_context:         Epidemiological DB summary (optional)

    Returns:
        {"answer": str, "sources": list[str]}
    """
    if history is None:
        history = []

    api_key = GROQ_API_KEY
    if not api_key:
        return {
            "answer": "Groq API key not configured. Check .streamlit/secrets.toml.",
            "sources": []
        }

    # 1. Semantic retrieval — search for disease-specific content
    retrieved = retrieve(query, faiss_manager)

    # 2. Build FAISS context
    if retrieved:
        faiss_context = "\n\n---\n\n".join([
            f"[Source: {c['source']} | Relevance: {c['similarity_score']:.2f}]\n{c['text']}"
            for c in retrieved
        ])
        sources = list(dict.fromkeys(c["source"] for c in retrieved))
    else:
        faiss_context = "No directly matching documents found in the knowledge base."
        sources = []

    # 3. Combine all context layers
    context_parts = [diagnosis_context]
    if db_context:
        context_parts.append(
            "### REAL-TIME EPIDEMIOLOGICAL DATA (platform database)\n\n" + db_context
        )
    context_parts.append(
        "### AGRONOMIC KNOWLEDGE BASE\n\n" + faiss_context
    )
    context = "\n\n".join(context_parts)

    # 4. Build messages
    user_message = f"""You have access to the following diagnosis results and agronomic reference material. READ ALL CONTEXT CAREFULLY before responding.

CONTEXT:
{context}

USER QUESTION: {query}

INSTRUCTIONS:
1. USE the diagnosis context (plant type, disease, confidence, location) to frame your analysis.
2. If location data is available, tailor recommendations to the region's climate, altitude, and typical growing conditions.
3. USE the agronomic knowledge base to provide scientifically accurate recommendations.
4. If real-time epidemiological data is available, mention relevant regional trends.
5. Structure your response with clear sections (e.g., Diagnosis Summary, Pathogen Info, Treatment, Prevention).
6. Be actionable — give specific product names, dosages, and timing when possible.
7. Respond in the same language the user writes in."""

    messages = [{"role": "system", "content": SYSTEM_ANALYSIS}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

    # 5. Call Groq
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1200,
        temperature=0.3
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": sources
    }