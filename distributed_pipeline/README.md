# 🌿 AgriScan AI — Distributed Inference Pipeline

> **Autor:** Eolivo  
> **Rama:** `feature/async-distributed-pipeline`  
> **Descripción:** Este módulo implementa un pipeline asíncrono de inferencia distribuida usando el patrón **Source → Broker → Worker** sobre el proyecto AgriScan AI de mis compañeros.

---

## 📐 Arquitectura

```
[Frontend Streamlit] ──HTTP POST──▶ [FastAPI Broker]
                                          │
                                    [Redis Queue]
                                    ┌─────┴──────┐
                                    ▼            ▼
                             [Router Worker]   (bypass)
                             agriscan_model.pth
                              Background / Tomato / Potato
                                    │
                          ┌─────────┴──────────┐
                          ▼                    ▼
                   [Tomato Worker]      [Potato Worker]
              best_tomato_worker.pth  best_potato_worker.pth
                   10 enfermedades      3 enfermedades
                          │                    │
                          └─────────┬──────────┘
                                    ▼
                            [PATCH Webhook] ──▶ [Broker] ──▶ [Supabase DB]
                                    ▲
                             GET /status/{id}
                                    │
                            [Frontend polling]
```

---

## 📁 Estructura de Archivos

```
distributed_pipeline/
├── config.py          # Variables de entorno y rutas centralizadas
├── schemas.py         # Contratos Pydantic (InferenceTicket, WebhookPayload)
├── broker.py          # API Gateway FastAPI (POST /diagnose, PATCH /webhook, GET /status)
├── router_worker.py   # Clasificador Nivel 1 (Background / Tomate / Papa)
├── tomato_worker.py   # Especialista enfermedades de Tomate (10 clases)
├── potato_worker.py   # Especialista enfermedades de Papa (3 clases)
├── DEMO_GUIDE.md      # Guía para demo con 2 computadoras en LAN
└── README.md          # Este archivo
```

---

## ⚙️ Requisitos Previos

1. **Redis** corriendo localmente (`redis-server`)
2. **Pesos de los modelos** en `models_weights/`:
   - `agriscan_model.pth`
   - `best_tomato_worker.pth`
   - `best_potato_worker.pth`
3. **Archivo `.env`** en la raíz del proyecto:
   ```env
   SUPABASE_DB_URL="postgresql://postgres.<ID>:<PASSWORD>@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
   ```

4. **Dependencias instaladas:**
   ```bash
   pip install fastapi uvicorn redis python-multipart python-dotenv pydantic
   ```

---

## 🚀 Cómo Ejecutar (Modo Local — 1 sola computadora)

Abrir **5 terminales** en la carpeta raíz del proyecto con el venv activado (`source venv/bin/activate`):

| Terminal | Comando |
|----------|---------|
| 1 — Broker | `python -m uvicorn distributed_pipeline.broker:app --host 0.0.0.0 --port 8000 --reload` |
| 2 — Router Worker | `python -m distributed_pipeline.router_worker` |
| 3 — Tomato Worker | `python -m distributed_pipeline.tomato_worker` |
| 4 — Potato Worker | `python -m distributed_pipeline.potato_worker` |
| 5 — Frontend | `streamlit run app.py` |

✅ Verificar que cada Worker imprima `Successfully loaded <nombre_modelo>.pth`

---

## 🗃️ Modelos de IA

### Clasificador de Tipo de Hoja (`agriscan_model.pth`)
- **Arquitectura:** ResNet18, capa `fc` → `nn.Linear(512, 3)` (sin Dropout)
- **Preprocesamiento:** `Resize(256)` → `CenterCrop(224)` → `Normalize`
- **Clases:** `['Background', 'Potato', 'Tomato']` (orden alfabético)

### Especialista Tomate (`best_tomato_worker.pth`)
- **Arquitectura:** ResNet18 + `nn.Sequential(Dropout(0.5), Linear(512, 10))`
- **Preprocesamiento:** `Resize((224, 224))` → `Normalize`
- **Clases (10):**  `Tomato_Bacterial_spot, Tomato_Early_blight, Tomato_Late_blight, Tomato_Leaf_Mold, Tomato_Septoria_leaf_spot, Tomato_Spider_mites..., Tomato__Target_Spot, Tomato__Tomato_YellowLeaf__Curl_Virus, Tomato__Tomato_mosaic_virus, Tomato_healthy`

### Especialista Papa (`best_potato_worker.pth`)
- **Arquitectura:** ResNet18 + `nn.Sequential(Dropout(0.5), Linear(512, 3))`
- **Preprocesamiento:** `Resize((224, 224))` → `Normalize`
- **Clases (3):** `Potato___Early_blight, Potato___Late_blight, Potato___healthy`

---

## 🔁 Flujo de una Petición

1. Usuario sube imagen y escoge modelo en Streamlit.
2. `analysis.py` hace `POST /diagnose` al Broker con la imagen y el `model` elegido.
3. El Broker guarda la imagen en `shared_data/`, inserta registro en Supabase y **encola el ticket en Redis**:
   - Si eligió "Crop Type Detection" → cola `router_q`
   - Si eligió "Tomato Disease Detection" → cola `tomato_q` directamente (bypass)
   - Si eligió "Potato Disease Detection" → cola `potato_q` directamente (bypass)
4. El Worker correspondiente consume el ticket, carga la imagen, pasa el tensor por el modelo y hace `PATCH /webhook/status/{id}` al Broker con el resultado.
5. Mientras tanto, el frontend hace polling con `GET /status/{id}` cada 2 segundos hasta recibir estado `Completado` o `Desechado`.
6. El resultado se muestra en la UI con la enfermedad y el porcentaje de confianza.

---

## 🌐 Demo Multi-Máquina

Ver [DEMO_GUIDE.md](./DEMO_GUIDE.md) para instrucciones paso a paso de cómo ejecutar el sistema en **2 computadoras en la misma red WiFi**.

Para cambiar a modo LAN sin modificar código, usar la variable de entorno antes de lanzar Streamlit:

```bash
export BROKER_CLIENT_URL="http://<IP_DE_JAHER>:8000"
streamlit run app.py
```

---

## 🤝 Integración con el Frontend de los Compañeros

- **NO se modificó** `app.py` ni la carpeta `components/` más allá de `components/analysis.py`.
- `components/analysis.py` solo cambió el botón "Run AI Analysis" para enviar la imagen al Broker vía HTTP en lugar de llamar a PyTorch directamente.
- El Mapa Epidemiológico (`map_view.py`) sigue funcionando igual, leyendo directamente de Supabase.
