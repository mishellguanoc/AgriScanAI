import sys
import os
import time

# Agregar el directorio principal al PATH para poder importar los módulos de utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.db_manager import fetch_all_records

def test_cp06_rendimiento_espacial():
    print("Consultando la base de datos existente...")
    
    # Realizar la consulta que alimenta el mapa
    start_time = time.time()
    df_mapa = fetch_all_records()
    elapsed_time = time.time() - start_time

    num_records = len(df_mapa)
    print(f"Registros extraídos: {num_records}")

    # Criterio de Aceptación (Query)
    # Debe extraer los registros en menos de 5 segundos
    assert elapsed_time < 5.0, f"Query demasiado lenta: {elapsed_time:.2f}s"
    
    # Comprobar que hay más de 10,000 registros
    assert num_records >= 10000, f"Se esperaban al menos 10000 registros, pero se encontraron {num_records}."

    print(f"CP-06 Exitoso: {num_records} registros extraídos en {elapsed_time:.2f}s. "
          f"Margen seguro para renderizado de clústeres en Folium.")

if __name__ == "__main__":
    test_cp06_rendimiento_espacial()
