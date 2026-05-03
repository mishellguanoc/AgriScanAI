"""
src/faiss_manager.py
Construye y maneja el índice FAISS para búsqueda semántica
"""

import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer
from typing import List, Dict

class FAISSManager:
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        """
        Inicializa el modelo de embeddings (384 dimensiones)
        """
        print(f"📦 Cargando modelo: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.chunks = None
        self.dimension = 384  # del modelo all-MiniLM-L6-v2
    
    def build(self, chunks: List[Dict]) -> tuple:
        """
        Construye el índice FAISS a partir de los chunks
        """
        if not chunks:
            raise ValueError("No hay chunks para indexar")
        
        print(f"🔨 Construyendo embeddings para {len(chunks)} chunks...")
        
        # Extraer textos
        texts = [chunk['text'] for chunk in chunks]
        
        # Generar embeddings (vectores)
        embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # Normalizar para usar cosine similarity
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        # Crear índice FAISS (Inner Product = cosine similarity en vectores normalizados)
        self.dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.dimension)  # IP = Inner Product
        self.index.add(embeddings.astype('float32'))
        self.chunks = chunks
        
        print(f"✅ Índice FAISS creado:")
        print(f"   - Dimensiones: {self.dimension}")
        print(f"   - Vectores indexados: {self.index.ntotal}")
        
        return self.index, self.chunks
    
    def search(self, query: str, k: int = 3) -> List[Dict]:
        """
        Busca los k chunks más relevantes para la query.
        Retorna lista de chunks con su score de similitud.
        """
        if self.index is None or self.chunks is None:
            raise ValueError("FAISS no inicializado. Llama a build() o load() primero.")
        
        # Convertir query a embedding
        query_vector = self.model.encode([query])
        query_vector = query_vector / np.linalg.norm(query_vector, axis=1, keepdims=True)
        
        # Buscar en FAISS
        scores, indices = self.index.search(query_vector.astype('float32'), k)
        
        # Construir resultados
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and score > 0.3:  # umbral mínimo de relevancia
                results.append({
                    **self.chunks[idx],
                    'similarity_score': float(score)
                })
        
        return results
    
    def save(self, index_path: str, chunks_path: str):
        """
        Guarda el índice FAISS y los chunks en disco
        """
        if self.index is None or self.chunks is None:
            raise ValueError("No hay índice para guardar")
        
        faiss.write_index(self.index, index_path)
        with open(chunks_path, 'wb') as f:
            pickle.dump(self.chunks, f)
        
        print(f"💾 Guardado:")
        print(f"   - Índice FAISS: {index_path}")
        print(f"   - Chunks: {chunks_path}")
    
    def load(self, index_path: str, chunks_path: str):
        """
        Carga el índice FAISS y los chunks desde disco
        """
        self.index = faiss.read_index(index_path)
        with open(chunks_path, 'rb') as f:
            self.chunks = pickle.load(f)
        
        print(f"📂 Cargado:")
        print(f"   - Índice FAISS: {self.index.ntotal} vectores")
        print(f"   - Chunks: {len(self.chunks)} chunks")
        
        return self.index, self.chunks