import sys
import os

# Agregar el directorio principal al PATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importamos la clase principal de RAG desde el backend (ajustar import si es distinto en tu entorno real)
from rag.core import load_faiss_index, ask

def test_cp08_orquestacion_multimodal():
    # Precondiciones (Mockeando el output de la arquitectura)
    # Output de la red ResNet
    prediccion_cnn = "Tizón Temprano"
    confianza_cnn = 0.98
    
    # Output simulado del mapa (fetch_contextual_diagnosis)
    contexto_espacial = """
    === CONTEXTO EPIDEMIOLÓGICO ===
    En un radio de 10km hay 50 detecciones recientes de Tomate / Tizón Temprano.
    ===============================
    """
    
    # Input del agricultor
    user_prompt = "¿Debería preocuparme por mi planta de acuerdo a mi diagnóstico y la zona?"
    
    # Ensamblaje dinámico del System Prompt (como se hace en la app real)
    context_fusion = (
        f"El usuario acaba de escanear una planta. "
        f"Diagnóstico de la IA (CNN): {prediccion_cnn} (Confianza: {confianza_cnn*100}%).\n"
        f"Situación epidemiológica local:\n{contexto_espacial}"
    )
    
    # Ejecutar RAG
    print("Iniciando RAG System con contexto inyectado...")
    try:
        faiss_manager = load_faiss_index()
    except Exception as e:
        print(f"Warning: Podría no cargar FAISS sin embeddings locales. Error: {e}")
        faiss_manager = None # O usar un mock si FAISS no está inicializado

    # Si FAISS no carga para tests unitarios locales, mockearemos
    class MockFAISS:
        def search(self, q, k): return []
    
    faiss = faiss_manager if faiss_manager else MockFAISS()

    response = ask(
        query=user_prompt,
        faiss_manager=faiss,
        expertise="beginner",
        db_context=context_fusion
    )
    
    respuesta_llm = response["answer"]
    
    # Criterios de Aceptación (NLP Assertion)
    respuesta_lower = respuesta_llm.lower()
    
    # El LLM debe mencionar o entender la enfermedad detectada por la CNN
    assert "tizón temprano" in respuesta_lower, "Fallo: El LLM ignoró el output de la CNN en su respuesta."
    
    # El LLM debe referenciar el contexto espacial/mapa
    assert "50" in respuesta_lower or "zona" in respuesta_lower or "brote" in respuesta_lower, \
        "Fallo: El LLM ignoró el contexto epidemiológico espacial en su respuesta."

    print("CP-08 Exitoso: El LLM integró correctamente CNN + Mapa en su razonamiento.")
    print(f"Respuesta generada:\n{respuesta_llm}")

if __name__ == "__main__":
    test_cp08_orquestacion_multimodal()
