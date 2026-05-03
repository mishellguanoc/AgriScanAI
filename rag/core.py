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
def retrieve(query: str, faiss_manager: FAISSManager, top_k: int = 8) -> list:
    """
    Busca los chunks más relevantes usando similitud semántica (cosine via FAISS).
    Filtra por umbral mínimo de similitud 0.30.
    """
    results = faiss_manager.search(query, k=top_k)
    return [r for r in results if r["similarity_score"] >= 0.30]

# ── Generación con Groq / LLaMA 3 ─────────────────────────────────────────
def ask(query: str, faiss_manager: FAISSManager, expertise: str = "beginner", history: list = None) -> dict:
    """
    Pipeline RAG completo:
      1. Recupera chunks relevantes con FAISS
      2. Construye contexto y prompt
      3. Llama a Groq (LLaMA 3.3-70b)
      4. Retorna respuesta + fuentes usadas

    Args:
        query:        Pregunta del usuario
        faiss_manager: Instancia de FAISSManager ya cargada
        expertise:    'beginner' (agricultor) | 'expert' (agrónomo)
        history:      Lista de mensajes previos [{"role": ..., "content": ...}]

    Returns:
        {"answer": str, "sources": list[str]}
    """
    if history is None:
        history = []

    api_key = GROQ_API_KEY
    if not api_key:
        return {
            "answer": "⚠️ No se encontró la API key de Groq. Revisa tu archivo .env",
            "sources": []
        }

    # 1. Retrieval
    retrieved = retrieve(query, faiss_manager)

    # 2. Construir contexto
    if retrieved:
        context = "\n\n---\n\n".join([
            f"[Fuente: {c['source']} | Relevancia: {c['similarity_score']:.2f}]\n{c['text']}"
            for c in retrieved
        ])
        sources = list(dict.fromkeys(c["source"] for c in retrieved))  # orden preservado, sin duplicados
    else:
        context = "No se encontró información relevante en la base de conocimiento para esta consulta."
        sources = []

    # 3. Construir mensajes
    system_prompt = SYSTEM_BEGINNER if expertise == "beginner" else SYSTEM_EXPERT

    user_message = f"""Información recuperada de la base de conocimiento agrícola:
---
{context}
---

Consulta: {query}

Responde basándote ÚNICAMENTE en la información proporcionada. 
Si la información no está disponible, indícalo claramente y recomienda consultar al INIAP o MAG."""

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

    # 4. Llamar a Groq
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