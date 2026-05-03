"""
src/chunker.py
Divide textos limpios en chunks con metadata (para FAISS)
"""

import os
import re
from typing import List, Dict

class Chunker:
    def __init__(self, chunk_size: int = 400, overlap: int = 80):
        """
        chunk_size: tamaño objetivo de cada chunk en caracteres
        overlap: cuántos caracteres del chunk anterior se mantienen
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_file(self, txt_path: str) -> List[Dict]:
        """
        Lee un archivo TXT y lo divide en chunks.
        Retorna lista de chunks con metadata.
        """
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Limpiar espacios extra
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        if not text or len(text) < 50:
            print(f"  ⚠️ {os.path.basename(txt_path)}: texto muy corto ({len(text)} chars), omitiendo")
            return []
        
        # Detectar fuente del nombre del archivo
        source_name = os.path.basename(txt_path).replace('.txt', '.pdf')
        
        # Dividir en párrafos
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = ""
        chunk_idx = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Si agregar este párrafo excede el tamaño y ya tenemos contenido
            if len(current_chunk) + len(para) > self.chunk_size and len(current_chunk) > 100:
                # Guardar chunk actual
                chunks.append(self._create_chunk(current_chunk, source_name, chunk_idx))
                chunk_idx += 1
                
                # Mantener overlap del final del chunk anterior
                if self.overlap > 0 and len(current_chunk) > self.overlap:
                    current_chunk = current_chunk[-self.overlap:] + "\n\n"
                else:
                    current_chunk = ""
            
            current_chunk += para + "\n\n"
        
        # Último chunk
        if current_chunk and len(current_chunk) > 50:
            chunks.append(self._create_chunk(current_chunk, source_name, chunk_idx))
        
        return chunks
    
    def _create_chunk(self, text: str, source: str, idx: int) -> Dict:
        """Crea la estructura del chunk con metadata automática"""
        text_lower = text.lower()
        
        # Detectar cultivos
        crops = []
        if 'papa' in text_lower or 'patata' in text_lower:
            crops.append('papa')
        if 'tomate' in text_lower:
            crops.append('tomate')
        if not crops:
            crops = ['general']
        
        # Detectar enfermedades
        diseases = []
        disease_map = {
            'tizón tardío': 'late_blight',
            'phytophthora': 'late_blight',
            'tizón temprano': 'early_blight',
            'alternaria': 'early_blight',
            'septoria': 'septoria',
            'mancha bacteriana': 'bacterial_spot',
            'punta morada': 'purple_tip',
            'control biológico': 'biological_control'
        }
        
        for keyword, disease in disease_map.items():
            if keyword in text_lower:
                diseases.append(disease)
        
        return {
            'chunk_id': f"{source.replace('.pdf', '')}_{idx}",
            'text': text,
            'source': source,
            'crops': crops,
            'diseases': diseases if diseases else ['general'],
            'length': len(text)
        }
    
    def chunk_folder(self, folder_path: str) -> List[Dict]:
        """
        Procesa todos los TXT de una carpeta y retorna todos los chunks.
        """
        all_chunks = []
        
        txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
        
        if not txt_files:
            print(f"❌ No se encontraron archivos .txt en {folder_path}")
            return []
        
        print(f"📄 Procesando {len(txt_files)} archivos TXT...")
        
        for filename in txt_files:
            filepath = os.path.join(folder_path, filename)
            print(f"  → {filename}")
            
            chunks = self.chunk_file(filepath)
            print(f"     ✓ {len(chunks)} chunks generados")
            all_chunks.extend(chunks)
        
        print(f"\n📊 Total chunks generados: {len(all_chunks)}")
        return all_chunks