"""
build_kb.py
Construye la base de conocimiento: chunks + índice FAISS
Ejecutar UNA SOLA VEZ después de limpiar los TXT
"""

import os
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.chunker import Chunker
from rag.faiss_manager import FAISSManager

def main():
    print("=" * 60)
    print("🌿 RAG_AgriScanAI - Construcción de Base de Conocimiento")
    print("=" * 60)
    
    # 1. Chunking
    print("\n📝 PASO 1: Generando chunks desde TXT limpios...")
    chunker = Chunker(chunk_size=400, overlap=80)
    chunks = chunker.chunk_folder("data/processed")
    
    if not chunks:
        print("❌ No se generaron chunks. Revisa la carpeta data/processed")
        return
    
    # 2. Guardar chunks intermedios (opcional, para depuración)
    import json
    with open("data/embeddings/chunks_debug.json", "w", encoding="utf-8") as f:
        # Guardar versión legible (solo primeros 200 chars de cada chunk)
        debug_chunks = [
            {"id": c['chunk_id'], "source": c['source'], "preview": c['text'][:200]}
            for c in chunks
        ]
        json.dump(debug_chunks, f, indent=2, ensure_ascii=False)
    print(f"   📄 Debug chunks guardado en data/embeddings/chunks_debug.json")
    
    # 3. Construir FAISS
    print("\n🔨 PASO 2: Construyendo índice FAISS...")
    faiss_mgr = FAISSManager()
    faiss_mgr.build(chunks)
    
    # 4. Guardar índice
    print("\n💾 PASO 3: Guardando índice...")
    os.makedirs("data/embeddings", exist_ok=True)
    faiss_mgr.save(
        index_path="data/embeddings/faiss_index.bin",
        chunks_path="data/embeddings/chunks.pkl"
    )
    
    # 5. Prueba rápida
    print("\n🔍 PASO 4: Probando búsqueda...")
    test_queries = [
        "¿Qué síntomas tiene el tizón tardío en papa?",
        "¿Cómo controlar la septoria en tomate?",
        "control biológico de enfermedades"
    ]
    
    for query in test_queries:
        print(f"\n   Pregunta: {query}")
        results = faiss_mgr.search(query, k=3)
        if results:
            for i, r in enumerate(results):
                print(f"      {i+1}. [{r['similarity_score']:.3f}] {r['source']}")
                print(f"         {r['text'][:120]}...")
        else:
            print(f"      ⚠️ No se encontraron resultados")
    
    print("\n" + "=" * 60)
    print("✅ BASE DE CONOCIMIENTO CONSTRUIDA CON ÉXITO")
    print("=" * 60)
    print("\n📌 Ahora puedes usar FAISSManager en tu rag.py")
    print("   Reemplaza la función retrieve() por búsqueda en FAISS")

if __name__ == "__main__":
    main()