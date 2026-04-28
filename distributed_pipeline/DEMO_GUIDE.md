# 🌐 Guía de Demostración Distribuida — AgriScan AI

> Esta guía es para presentar el sistema en clases usando **2 computadoras en la misma red local (mismo WiFi)**.
> Seguir ESTRICTAMENTE el orden de los pasos.

---

## 🖥️ Roles
| Rol | Computadora |
|-----|------------|
| **Servidor** (Broker + Workers) | Tu compañero (Jaher) |
| **Cliente** (Frontend Streamlit) | Tú (Eolivo) |

---

## PASO 1 — Obtener la IP del Servidor (Computadora de Jaher)

En la computadora de Jaher, abrir una terminal y ejecutar:

```bash
ip a | grep "inet " | grep -v 127.0.0.1
```

Buscar la línea que dice algo como `inet 192.168.X.X`. **Anotar esa IP**, la necesitarás en el Paso 4.

---

## PASO 2 — Arrancar Redis en la computadora de Jaher

```bash
redis-server
```

Debe imprimir `Ready to accept connections`. Dejar esta terminal abierta.

---

## PASO 3 — Arrancar los Workers en la computadora de Jaher

Abrir **3 terminales** adicionales en la carpeta del proyecto. En cada una activar el venv y ejecutar uno de los siguientes comandos:

**Terminal A (Router Worker):**
```bash
source venv/bin/activate
python -m distributed_pipeline.router_worker
```
Verificar que aparezca: `Successfully loaded agriscan_model.pth`

**Terminal B (Tomato Worker):**
```bash
source venv/bin/activate
python -m distributed_pipeline.tomato_worker
```
Verificar que aparezca: `Successfully loaded best_tomato_worker.pth`

**Terminal C (Potato Worker):**
```bash
source venv/bin/activate
python -m distributed_pipeline.potato_worker
```
Verificar que aparezca: `Successfully loaded best_potato_worker.pth`

---

## PASO 4 — Arrancar el Broker en la computadora de Jaher

Abrir una terminal más y ejecutar:

```bash
source venv/bin/activate
python -m uvicorn distributed_pipeline.broker:app --host 0.0.0.0 --port 8000
```

> ⚠️ El `--host 0.0.0.0` es crítico: hace que el Broker sea accesible desde cualquier equipo en la misma red, no solo desde `localhost`.

Verificar que aparezca: `Uvicorn running on http://0.0.0.0:8000`

---

## PASO 5 — Configurar el Frontend para apuntar al Servidor (Computadora de Eolivo)

En el archivo `components/analysis.py`, cambiar la línea:

```python
url_diagnose = "http://localhost:8000/diagnose"
```

Por la IP real de la computadora de Jaher, por ejemplo:

```python
url_diagnose = "http://192.168.1.50:8000/diagnose"
```

Y más abajo, la línea del polling:
```python
status_res = requests.get(f"http://localhost:8000/status/{task_id}")
```
Cambiarla a:
```python
status_res = requests.get(f"http://192.168.1.50:8000/status/{task_id}")
```

> Reemplazar `192.168.1.50` con la IP real que obtuviste en el Paso 1.

---

## PASO 6 — Arrancar el Frontend en la computadora de Eolivo

```bash
source venv/bin/activate
streamlit run app.py
```

---

## ✅ Verificación Final (Prueba de Fuego)

1. Abrir el Streamlit en el navegador: `http://localhost:8501`
2. Ir a la pestaña **Crop Analysis**
3. Subir una imagen de hoja de tomate o papa
4. Dar clic en **🚀 Run AI Analysis**
5. **Mostrarlo a la clase:** El frontend de la computadora de Eolivo envía la imagen a la red → La computadora de Jaher la recibe, la clasifica con PyTorch y responde → El frontend muestra el diagnóstico.

---

## 🔄 Cómo Revertir a Modo Local (Solo una computadora)

Cuando quieras trabajar solo:
1. Revertir las URLs en `components/analysis.py` de vuelta a `http://localhost:8000/...`
2. Ejecutar todos los workers y el broker en tu propia computadora.

---

## 🎤 Puntos Clave para la Presentación

- **"El frontend NO sabe nada de PyTorch"**: Solo hace una petición HTTP, igual que cualquier app web.
- **"Los Workers pueden estar en cualquier parte del mundo"**: Solo necesitan acceso al mismo Redis.
- **"La arquitectura es escalable"**: Podríamos añadir 10 Tomato Workers en paralelo y el sistema los balancearía automáticamente.
- **"Fault Tolerant"**: Si un Worker falla, el mensaje permanece en la cola de Redis hasta que otro Worker lo consuma.
