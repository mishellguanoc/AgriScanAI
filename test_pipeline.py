import requests
import time
import sys
import json

BROKER_URL = "http://localhost:8000"
# Using the local file that exists in the directory
TEST_IMAGE = "tomato_healthy.JPG"

def run_test():
    print(f"--- 1. Submitting {TEST_IMAGE} to Broker ---")
    url = f"{BROKER_URL}/diagnose"
    
    try:
        with open(TEST_IMAGE, "rb") as f:
            files = {"image": (TEST_IMAGE, f, "image/jpeg")}
            data = {"latitude": "0.0", "longitude": "0.0"}
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
    except FileNotFoundError:
        print(f"Error: {TEST_IMAGE} not found in this directory. Please provide a valid image.")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Broker. Please ensure uvicorn is running on port 8000.")
        sys.exit(1)
        
    try:
        result = response.json()
        task_id = result.get("upload_id")
        print(f"Success! Task ID: {task_id}")
        print(f"Initial Status: {result.get('status')}")
    except json.JSONDecodeError:
        print("Error interpreting Broker response.")
        sys.exit(1)

    print("\n--- 2. Polling for results (AJAX Mock) ---")
    status_url = f"{BROKER_URL}/status/{task_id}"
    
    while True:
        try:
            res = requests.get(status_url)
            res.raise_for_status()
            current_status = res.json()
            
            estado = current_status.get("status")
            print(f"[{time.strftime('%H:%M:%S')}] Estado Actual: {estado}")
            
            if estado in ["Completado", "Desechado", "Error", "Desechado/Background"]:
                if estado == "Completado":
                    disease = current_status.get("disease")
                    confidence = current_status.get("confidence")
                    print(f"\n✅ DIAGNÓSTICO FINAL: {disease} (Confianza: {confidence}%)")
                else:
                    print(f"\n⚠️ TERMINADO CON ESTADO: {estado}")
                break
                
            time.sleep(2)
        except KeyboardInterrupt:
            print("\nPrueba cancelada por el usuario.")
            break
        except Exception as e:
            print(f"Error during polling: {e}")
            break

if __name__ == "__main__":
    run_test()
