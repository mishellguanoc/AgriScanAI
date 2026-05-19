import time
import requests
import os

BROKER_URL = "http://localhost:8000/diagnose"

def test_cp01_carga_exitosa():
    image_path = "/home/jaher/streamlit_project/AgriScanAI/testing/potato_early-blight.jpg"
    
    # Precondición: Verificar que el archivo exista
    assert os.path.exists(image_path), f"El archivo {image_path} no existe."

    # Datos de entrada usando la imagen proveída
    files = {"image": ("potato_early-blight.jpg", open(image_path, "rb"), "image/jpeg")}
    data = {
        "latitude": -34.6037,
        "longitude": -58.3816,
        "model": "Potato Disease Detection"
    }

    # Paso: Medir tiempo y hacer petición POST
    start_time = time.time()
    response = requests.post(BROKER_URL, files=files, data=data)
    elapsed_time = (time.time() - start_time) * 1000 # a milisegundos

    # Criterios de Aceptación
    # Devuelve código de éxito (200 OK / 202 Accepted)
    assert response.status_code in [200, 202], f"Falló con código {response.status_code}. Detalle: {response.text}"
    
    # El tiempo de respuesta es menor a 2s (2000ms)
    assert elapsed_time < 2000.0, f"Respuesta muy lenta: {elapsed_time:.2f}ms"
    
    # Devuelve un task_id/upload_id válido y estado 'Solicitado'
    json_response = response.json()
    assert "upload_id" in json_response
    assert json_response["status"] == "Solicitado"

    print(f"CP-01 Exitoso: Tarea {json_response['upload_id']} encolada en {elapsed_time:.2f}ms")

if __name__ == "__main__":
    test_cp01_carga_exitosa()
