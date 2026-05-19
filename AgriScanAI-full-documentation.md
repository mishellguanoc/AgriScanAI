---

# **AGRISCAN AI - COMPREHENSIVE TECHNICAL DOCUMENTATION**

## **Executive Summary**

AgriScan AI is a sophisticated, distributed, asynchronous agricultural disease detection and epidemiological monitoring platform designed for smallholder and commercial farmers in Ecuador and similar agricultural regions. The system leverages deep learning (ResNet18-based CNN models), semantic search (FAISS), Large Language Models (Groq's LLaMA 3.3-70b), and real-time geospatial analytics to provide crop disease diagnosis, knowledge-based consulting, and epidemiological outbreak tracking. The architecture is fundamentally decoupled, separating user-facing web interfaces from compute-intensive ML inference tasks, enabling independent scaling and fault isolation.

---

## **SYSTEM ARCHITECTURE**

### **1.1 Architectural Philosophy & Design Principles**

AgriScan AI adheres to several critical architectural principles:

#### **1.1.1 Asynchronous, Distributed Processing**
The core challenge addressed is that real-time image inference on a web server would degrade UI responsiveness and create bottlenecks during concurrent user uploads. The solution implements a **task-queue-based worker pool architecture** where:
- The frontend (Streamlit) initiates requests and immediately polls for completion
- A central broker (FastAPI) acts as a gateway, persisting data and distributing work
- Independent worker processes consume tasks from message queues and execute computationally expensive inference in isolation
- Workers report results back to the broker via webhook callbacks, decoupling them from the HTTP request-response cycle

This design ensures that:
- UI remains responsive regardless of model inference latency (typically 2-5 seconds per image)
- Multiple worker processes can scale horizontally to handle concurrent submissions
- System is resilient to worker failures; tasks can be retried from the queue

#### **1.1.2 Decoupled Frontend and Backend**
The Streamlit frontend does not directly load or execute PyTorch models. Instead, all ML computations are delegated to dedicated worker processes. This separation enables:
- Lightweight frontend deployment (only requires HTTP client, not CUDA/GPU drivers)
- Independent tech stack choices (Streamlit for UI, Python workers for ML)
- Easier testing, debugging, and updating of models without touching the frontend

#### **1.1.3 Multi-Stage Inference Pipeline**
Rather than a monolithic classifier, AgriScan AI implements a **routing architecture**:
1. **Router Worker (Stage 1):** A lightweight ResNet18 classifier determines if the input is a valid crop (Tomato or Potato) or background (face, floor, sky, etc.)
2. **Specialist Workers (Stage 2):** If valid, the image is routed to crop-specific disease detectors optimized for Tomato (10 disease classes) or Potato (3 disease classes)
3. **Filtering Logic:** Background detections are marked as "Desechado" (discarded) to prevent polluting the epidemiological map with irrelevant imagery

This multi-stage design:
- Reduces false positives
- Allows specialized model architectures per crop
- Implements early termination (reject invalid images before expensive downstream processing)

#### **1.1.4 Spatially-Aware Knowledge Integration**
The system combines:
- Real-time epidemiological database (PostgreSQL via Supabase)
- Semantic knowledge base (FAISS index of agricultural documents)
- Live GPS coordinates from user submissions
- Haversine distance calculations to identify nearby outbreaks

This integration enables the agronomic chatbot to provide **context-specific advice** ("Given 15 cases of Late Blight within 50km of your location...") rather than generic recommendations.

### **1.2 Core Architectural Tiers**

```
┌─────────────────────────────────────────────────────────────────┐
│                     TIER 1: USER INTERFACE                      │
│                        (Streamlit App)                          │
│                  - Crop Analysis Page                           │
│                  - Agronomic Assistant (RAG)                    │
│                  - Epidemiological Map Visualization            │
└─────────────────────┬──────────────────────   ────────────────────┘
                      │ HTTP/REST (async polling)
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                  TIER 2: API GATEWAY (Broker)                   │
│                     (FastAPI + uvicorn)                         │
│  Endpoints:                                                     │
│  - POST /diagnose (receive image, create ticket, queue job)     │
│  - PATCH /webhook/status/{task_id} (accept worker results)      │
│  - GET /status/{task_id} (query inference completion)           │
│                                                                 │
│  Internal Actions:                                              │
│  - Persist images to shared_data/ volume                        │
│  - Create initial DB records (status: "Solicitado")            │
│  - Route inference tasks to Redis queues                        │
│  - Update DB on webhook callbacks                              │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Redis Message Queues
                      ├──→ QUEUE_ROUTER ──┐
                      ├──→ QUEUE_TOMATO ──┤
                      └──→ QUEUE_POTATO ──┤
                                          ↓
┌─────────────────────────────────────────────────────────────────┐
│              TIER 3: DISTRIBUTED ML WORKER POOL                 │
│                  (Independent Python Processes)                 │
│                                                                 │
│  Router Worker: ResNet18(3-class)  [Background, Potato, Tomato]│
│    ↓ (routes valid crops to specialists)                        │
│                                                                 │
│  Tomato Worker: ResNet18(10-class) [10 tomato diseases + healthy]
│  Potato Worker: ResNet18(3-class)  [Early Blight, Late Blight, Healthy]
│                                                                 │
│  Each worker:                                                   │
│  - Monitors Redis queue via BLPOP (blocking pop)               │
│  - Loads image from shared_data/                               │
│  - Executes inference (forward pass)                           │
│  - Sends webhook PATCH to Broker with results                  │
└─────────────────────────────────────────────────────────────────┘
                      │ HTTP PATCH /webhook/status/{task_id}
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│              TIER 4: PERSISTENT DATA STORES                     │
│                                                                 │
│  PostgreSQL Database (Supabase):                                │
│  - file_upload (upload_id PK, status, received_timestamp)      │
│  - geospatial_data (upload_id FK, lat, lon, captured_at)       │
│  - diagnosis_result (upload_id FK, crop_type, disease,         │
│                       confidence, area_m2, severity)           │
│                                                                 │
│  Shared Filesystem (shared_data/):                              │
│  - Original uploaded images (named: {upload_id}.{ext})         │
│                                                                 │
│  FAISS Index + Chunks (local file):                            │
│  - 384-dimensional embeddings of knowledge base                │
│  - ~100+ agricultural document chunks                          │
│                                                                 │
│  Redis (In-Memory Queue Broker):                               │
│  - Task queues (router_q, tomato_q, potato_q)                 │
│  - Transient storage during processing                         │
└─────────────────────────────────────────────────────────────────┘
```

### **1.3 Communication Patterns**

#### **Synchronous Communication (Request-Response)**
- **Frontend → Broker:** `POST /diagnose` (multipart file upload + metadata)
- **Frontend → Broker:** `GET /status/{task_id}` (polling every 2 seconds)
- **RAG Component → Broker:** N/A (direct DB access via SQLAlchemy)

#### **Asynchronous Communication (Task Queue)**
- **Broker → Workers:** Redis `LPUSH` (left push) to queue, workers `BLPOP` (blocking right pop)
- **Workers → Broker:** HTTP `PATCH /webhook/status/{task_id}` (webhook callback)

#### **Database Communication**
- **Broker & Workers → DB:** SQLAlchemy ORM via psycopg2-binary (PostgreSQL adapter)
- **Frontend → DB:** Same ORM, with Streamlit caching decorators to minimize queries

---

## **TECHNOLOGY STACK & DEPENDENCIES**

### **2.1 Frontend Framework (Streamlit)**

**Version:** 1.56.0  
**Purpose:** Rapid prototyping of reactive web applications without explicit JavaScript/HTML/CSS backend.

**Why Streamlit?**
- Zero-boilerplate reactive UI: write Python, get interactive web app
- Built-in components for file uploads, camera input, forms, charts
- Excellent integration with scientific Python libraries (Pandas, Plotly, Folium)
- Automatic code-rerun model simplifies state management

**Key Streamlit Extensions & Integrations:**
- `streamlit-folium` (0.27.1): Embeds Folium maps within Streamlit pages
- `streamlit-js-eval`: Enables JavaScript execution for browser geolocation (HTML5 Geolocation API)

**CSS/Design System:**
The app uses a custom CSS "glass morphism" design system (defined in `app.py` lines 25-147) with:
- Custom font stack (`Inter` for body, `Outfit` for headers)
- Green accent gradient (`#2E7D32` to `#1B5E20`) representing agriculture
- Semi-transparent card containers with subtle borders
- Smooth transitions and hover effects

### **2.2 Backend Framework (FastAPI)**

**Version:** 0.136.0  
**Server:** uvicorn 0.45.0

**Purpose:** High-performance REST API for handling image uploads, task tracking, and webhook callbacks.

**Why FastAPI?**
- Automatic OpenAPI documentation
- Built-in async/await support (though broker endpoints are sync for simplicity)
- Pydantic validation for request/response bodies
- Significantly faster than Flask for concurrent connections

**Key Endpoints:**
1. `POST /diagnose` - Multipart form data (image file + GPS + model choice)
2. `PATCH /webhook/status/{task_id}` - Worker result callbacks
3. `GET /status/{task_id}` - UI polling endpoint

### **2.3 Message Queue (Redis)**

**Version:** 7.4.0  
**Role:** In-memory, distributed task queue broker

**Why Redis?**
- Extremely fast key-value store with list data structures
- BLPOP (blocking list pop) enables worker processes to wait for tasks without busy-polling
- Automatic cleanup (can set expiration on keys)
- Pub/Sub capabilities for future enhancements

**Queue Names & Semantics:**
- `router_q`: Incoming images for initial crop/background classification
- `tomato_q`: Valid tomato images for disease-specific inference
- `potato_q`: Valid potato images for disease-specific inference

**Queue Item Structure:**
```json
{
  "upload_id": "550e8400-e29b-41d4-a716-446655440000",
  "image_path": "/path/to/shared_data/550e8400-e29b-41d4-a716-446655440000.jpg",
  "crop_type": "Tomato" // added by router worker
}
```

### **2.4 Database (PostgreSQL via Supabase)**

**Adapter:** psycopg2-binary 2.9.11  
**ORM:** SQLAlchemy 2.0.49

**Why PostgreSQL + Supabase?**
- Relational schema matches epidemiological data model (uploads, locations, diagnoses)
- Supabase provides managed PostgreSQL with automatic backups
- UUID support for globally unique, collision-resistant IDs
- JSON/spatial query capabilities for future enhancements

**Database Schema:**

```
TABLE file_upload (
  upload_id UUID PRIMARY KEY,
  received_timestamp TIMESTAMP WITH TIMEZONE,
  status VARCHAR(50) DEFAULT 'Solicitado'
    -- Values: 'Solicitado', 'Enrutado', 'Completado', 'Desechado', 'Error'
);

TABLE geospatial_data (
  upload_id UUID PRIMARY KEY REFERENCES file_upload(upload_id),
  latitude FLOAT8 NULLABLE,
  longitude FLOAT8 NULLABLE,
  elevation FLOAT8 (always 0.0 for now),
  captured_timestamp TIMESTAMP WITH TIMEZONE NOT NULL
);

TABLE diagnosis_result (
  upload_id UUID PRIMARY KEY REFERENCES file_upload(upload_id),
  crop_type VARCHAR(50) NOT NULL,           -- 'Potato', 'Tomato'
  predicted_disease VARCHAR(100) NOT NULL,  -- Class label or 'Healthy'
  confidence_score FLOAT8 NOT NULL,         -- 0.0 to 1.0
  area_m2 INTEGER,                          -- Affected area, user-provided
  severity FLOAT8                           -- Normalized severity 0.0 to 1.0
);
```

**Status Lifecycle:**
- **Solicitado** (Requested): Initial state after broker receives image
- **Enrutado** (Routed): Router determined crop type, forwarding to specialist
- **Completado** (Completed): Specialist inference finished, disease identified
- **Desechado** (Discarded): Router classified as background, filtered out
- **Error**: Processing failed

### **2.5 Deep Learning Framework (PyTorch)**

**Versions:**
- `torch==2.11.0+cpu` (CPU-optimized wheel)
- `torchvision==0.26.0+cpu`
- `Pillow==12.1.1` (image loading and preprocessing)

**Why PyTorch?**
- Industry standard for computer vision
- Dynamic computation graphs simplify debugging
- Excellent model zoo (torchvision) with pre-trained ResNet variants

**Model Architecture:**
All models are **ResNet18** (shallow residual network, ~11.7M parameters) variants:
- **Router Model (agriscan_model.pth):** 3-class output (Background, Potato, Tomato)
- **Tomato Specialist (best_tomato_worker.pth):** 10-class output (9 diseases + Healthy)
- **Potato Specialist (best_potato_worker.pth):** 3-class output (Early Blight, Late Blight, Healthy)

**Image Preprocessing Pipeline:**
- **Router:** Resize(256) → CenterCrop(224) → ToTensor() → Normalize
- **Specialists:** Resize((224, 224)) → ToTensor() → Normalize
- **Normalization Constants:** ImageNet stats `[0.485, 0.456, 0.406]` for mean, `[0.229, 0.224, 0.225]` for std

### **2.6 Semantic Search & RAG (FAISS + Sentence-Transformers)**

**Dependencies:**
- `faiss-cpu==1.8.0+` (Facebook AI Similarity Search)
- `sentence-transformers==3.x` (sentence embeddings)

**Architecture:**
1. **Encoding Model:** `sentence-transformers/all-MiniLM-L6-v2`
   - 384-dimensional embeddings
   - Optimized for semantic similarity, not speed (suitable for offline indexing)
   - Handles multilingual text (English + Spanish)

2. **FAISS Index:** `IndexFlatIP` (Inner Product / Cosine Similarity after L2 normalization)
   - Stores ~100+ chunks extracted from agricultural documents
   - Similarity threshold: 0.20 (minimum score to include in RAG context)

3. **Retrieval Process:**
   - User query → encode to 384-dim vector
   - L2 normalize both query and index
   - Search top-k=15 most similar chunks
   - Filter by similarity ≥ 0.20
   - Return ranked results with source metadata

**Data Structure (Chunks):**
```python
{
  "text": "Late blight is caused by Phytophthora infestans...",
  "source": "INIAP Technical Guide - Potato Diseases",
  "similarity_score": 0.78  # computed at search time
}
```

### **2.7 Large Language Model (Groq API)**

**Model:** `llama-3.3-70b-versatile`  
**Client Library:** `groq==0.x.x`

**Why Groq?**
- **Speed:** ~200 tokens/second (vs. ~50-100 for typical LLM APIs)
- **Inference-optimized:** Purpose-built hardware + compiler
- **Cost-effective:** Per-token pricing with generous free tier
- **LLaMA 3.3-70B:** Strong reasoning, multilingual, instruction-tuned

**RAG Integration:**
The `ask()` function constructs a system prompt with two profiles:
- **Beginner (Farmer):** Simple language, practical examples
- **Expert (Agronomist):** Technical terminology, scientific references

Prompt structure:
```
[System Prompt - sets expertise level and language]
[User query history - last 6 messages for context]
[Context from FAISS retrieval]
[Live epidemiological data from database]
[Current user question]
[Instructions emphasizing use of provided context]
```

### **2.8 Geospatial & Mapping (Folium)**

**Version:** 0.20.0  
**Visualization:** Plotly 6.7.0 (temporal trends)

**Folium Components:**
- **Base Map:** CartoDB Positron tiles
- **Markers:** Circle markers sized by severity (radius = 8 + 10*severity)
- **Clustering:** MarkerCluster for dense regions
- **Heatmap:** KDE-based heatmap layer showing outbreak intensity
- **Export:** HTML to JPG conversion via Selenium

---

## **DIRECTORY STRUCTURE & MODULE ORGANIZATION**

### **3.1 Root Level**

```
AgriScanAI/
├── app.py                          # Main Streamlit entry point
├── requirements.txt                # Python dependencies
├── .streamlit/
│   └── secrets.toml               # Runtime secrets (not in git)
├── .env                           # Environment variables (local development)
└── .gitignore
```

### **3.2 Components Directory** (`components/`)

All Streamlit page components. Each module defines a page function that Streamlit renders as a tab.

#### **`components/header.py`**
**Responsibility:** Render application header with logo and title  
**Key Functions:**
- `show_header()`: Displays SVG logo, app name, and tagline with custom CSS styling
- Uses Streamlit's `st.columns()` for responsive layout
- Renders a gradient divider line

**Design Pattern:** Imported and called at top of `app.py` before tab creation

#### **`components/analysis.py`**
**Responsibility:** Main crop disease analysis workflow  
**Key Functions:**
- `analysis_page()`: Full analysis page with upload, inference, and results display

**Workflow:**
1. **Geolocation Capture** (lines 15-46):
   - Injects JavaScript via `streamlit.components.html()`
   - Calls HTML5 Geolocation API (`navigator.geolocation.getCurrentPosition()`)
   - Stores coordinates in Streamlit session state after 2-second delay

2. **Model Selection** (lines 49-58):
   - Dropdown to choose between:
     - Crop Type Detection (generic router)
     - Potato Disease Detection (specialist)
     - Tomato Disease Detection (specialist)

3. **Image Input** (lines 62-76):
   - Radio button: Camera input vs. file upload
   - Camera uses Streamlit's built-in camera component
   - File uploader accepts JPG/PNG

4. **EXIF Metadata Extraction** (lines 88-89):
   - Calls `extract_exif_data()` to pull GPS and timestamp from image EXIF tags
   - Fallback to browser geolocation if EXIF missing
   - User can manually override location

5. **Analysis Execution** (lines 103-161):
   - POST to Broker `/diagnose` endpoint with image, coordinates, model choice
   - Polls `/status/{task_id}` every 2 seconds until completion
   - Displays real-time status messages ("Waiting for ML Workers...", etc.)
   - On completion, stores result in `st.session_state["last_analysis"]` and reruns

6. **Results Display** (lines 196-243):
   - Premium card showing:
     - Disease name (large, bold)
     - Confidence score with color-coded progress bar
     - Area and severity input fields for map submission
   - "Submit to Map" button updates DB and clears cache for map refresh
   - "Reset" button for new analysis

**Key Session State Variables:**
- `geo_lat`, `geo_lon`: Browser geolocation
- `manual_lat`, `manual_lon`: User-overridden coordinates
- `last_analysis`: Dictionary holding results until submitted
- `rag_messages`: Conversation history (used by assistant, not analysis)

#### **`components/assistant.py`**
**Responsibility:** Agronomic RAG chatbot interface  
**Key Functions:**
- `assistant_page()`: Full chatbot UI with message history and input
- `_get_faiss()`: Cached FAISS loader (decorated with `@st.cache_resource`)

**Workflow:**
1. **Profile Selection** (lines 92-98):
   - Radio buttons: "Farmer" (beginner) or "Agronomist" (expert)
   - Influences system prompt and response style

2. **Message History** (lines 106-121):
   - Container with fixed height (380px) displaying past exchanges
   - Shows message role (user/assistant) and optional sources

3. **Input & Send** (lines 124-135):
   - Text input + send button in adjacent columns for chat UX
   - Custom CSS ensures equal heights

4. **Query Processing** (lines 138-167):
   - User message appended to session state
   - Last 6 messages retrieved for context
   - Calls `ask()` function from RAG core
   - Fetches live diagnosis context via `fetch_diagnosis_context()`
   - Assistant response + sources appended to history
   - Streamlit reruns to display new message

**Dependencies on RAG Core:**
- `rag.core.ask()` handles FAISS retrieval, prompt construction, and LLM call
- `utils.db_manager.fetch_diagnosis_context()` pulls epidemiological summary

#### **`components/map_view.py`**
**Responsibility:** Epidemiological visualization and filtering  
**Key Functions:**
- `map_page()`: Main map page
- `get_cached_map_html()`: Cached Folium map HTML generation

**Workflow:**
1. **Data Loading** (lines 60-61):
   - Calls `fetch_all_records()` which executes cached SQL JOIN
   - Returns DataFrame with 100+ potential records

2. **Filtering** (lines 67-110):
   - Plant type dropdown (All, Potato, Tomato, etc.)
   - Disease dropdown (All, disease names)
   - Date range picker (min to max available dates)
   - Filters applied as DataFrame boolean masks

3. **Map Rendering** (lines 115-117):
   - Calls `get_cached_map_html()` with filtered data
   - Folium creates:
     - Clustered circle markers (sized by severity)
     - Heatmap overlay (KDE from lat/lon/severity)
   - Rendered as HTML components in Streamlit

4. **Temporal Analysis** (lines 121-177):
   - Toggle: "Show temporal tendency"
   - If enabled, displays Plotly chart with dual-axis:
     - Bars: Daily case count
     - Line: Cumulative trend

5. **Export Options** (lines 180-204):
   - "Download Map as JPG": Uses Selenium to render HTML map and convert to image
   - "Download Data as CSV": Exports filtered DataFrame

**Performance Optimization:**
- Uses `@st.cache_data` decorator on `get_cached_map_html()` to avoid rebuilding map on every run
- Cache invalidated manually by `clear_db_cache()` when new records submitted
- Folium HTML embedded directly as `components.html()` for stability

### **3.3 Distributed Pipeline Directory** (`distributed_pipeline/`)

All asynchronous inference workers, broker, and shared utilities.

#### **`distributed_pipeline/config.py`**
**Responsibility:** Centralized configuration for distributed system  
**Key Variables:**
- `SHARED_DATA_DIR`: Path where Broker saves uploaded images (relative to repo root)
- `MODELS_WEIGHTS_DIR`: Path to .pth model files
- `REDIS_HOST`, `REDIS_PORT`: Redis connection details
- `BROKER_HOST`, `BROKER_PORT`: Server binding address
- `BROKER_CLIENT_URL`: URL that Streamlit/clients use to reach Broker (may differ on multi-machine deployment)
- `QUEUE_ROUTER`, `QUEUE_TOMATO`, `QUEUE_POTATO`: Redis queue names
- `SUPABASE_DB_URL`: PostgreSQL connection string (passed to Broker only)

**Design Pattern:** Imported in broker and all workers; centralized source of truth

#### **`distributed_pipeline/schemas.py`**
**Responsibility:** Pydantic data models for type validation  
**Models:**
- `InferenceTicket`: Payload sent via Redis between Broker and Workers
  - `upload_id` (str): Unique task ID
  - `image_path` (str): Full path to image in shared_data/
  - `crop_type` (Optional[str]): Set by router, used for routing decision

- `WebhookPayload`: Payload sent by workers to Broker webhook
  - `upload_id`, `status`, `crop_type`, `predicted_disease`, `confidence_score`, etc.

#### **`distributed_pipeline/broker.py`**
**Responsibility:** Central API gateway and task orchestrator  
**Architecture:**
- FastAPI application with 3 core endpoints
- SQLAlchemy integration for DB operations
- Redis client for queue management
- File storage for image persistence

**Endpoints:**

1. **`POST /diagnose`**
   - **Input:** Multipart form (image file, latitude, longitude, captured_at, model)
   - **Processing:**
     a. Generate UUID for task
     b. Save image to `shared_data/{uuid}.{ext}`
     c. Create initial DB ticket (status="Solicitado")
     d. Construct `InferenceTicket` JSON
     e. Route to appropriate queue (QUEUE_ROUTER, QUEUE_TOMATO, or QUEUE_POTATO)
   - **Output:** JSON `{"upload_id": "...", "status": "Solicitado", "queue": "..."}`
   - **Error Handling:**
     - 503 if Redis unavailable
     - 500 if DB creation fails

2. **`PATCH /webhook/status/{task_id}`**
   - **Input:** `WebhookPayload` (status, disease, confidence, etc.)
   - **Processing:**
     a. Parse UUID from URL
     b. Update `FileUpload` status in DB
     c. If status="Completado", create `DiagnosisResult` record
   - **Output:** JSON `{"message": "State updated successfully", "status": "..."}`
   - **Called By:** ML workers upon inference completion

3. **`GET /status/{task_id}`**
   - **Input:** UUID in URL
   - **Processing:**
     a. Query `FileUpload` and `DiagnosisResult` tables
     b. Construct response with status and diagnosis info
   - **Output:** JSON `{"status": "...", "disease": "...", "confidence": 0.95}`
   - **Called By:** Streamlit UI polling every 2 seconds

**Initialization:**
- Lines 16-21: Attempt Redis connection at startup; proceed even if fails
- Lines 24-42: Retry logic for Redis in `/diagnose` (pragmatic fallback)

#### **`distributed_pipeline/worker_utils.py`**
**Responsibility:** Shared webhook sender utility  
**Key Function:**
- `send_webhook(task_id, status, crop_type, disease, confidence)`: 
  - Constructs PATCH request to `{BROKER_WEBHOOK_URL}/{task_id}`
  - Includes all result metadata
  - 5-second timeout; logs on failure

**Design Pattern:** Imported by all workers (router, tomato, potato) to avoid code duplication

#### **`distributed_pipeline/router_worker.py`**
**Responsibility:** Stage 1 crop classifier (Background/Tomato/Potato)  
**Architecture:**
- Infinite loop with `redis_client.BLPOP(QUEUE_ROUTER)` (blocking)
- Loads and preprocesses image
- Runs inference
- Routes valid crops or discards background

**Model Details:**
- **Architecture:** ResNet18, no dropout (added to fully-connected layer in specialists)
- **Classes:** ['Background', 'Potato', 'Tomato'] (alphabetical order)
- **Preprocessing:** Resize(256) → CenterCrop(224) → ToTensor() → Normalize
- **Device:** CPU (no GPU acceleration)

**Processing Loop (lines 52-98):**
1. `redis_client.BLPOP(QUEUE_ROUTER)`: Blocks until message available
2. Parse JSON ticket
3. Load image from `ticket["image_path"]`
4. Convert to RGB (handle transparency)
5. Apply preprocessing transforms
6. Forward pass with `torch.no_grad()` (inference mode)
7. Softmax probabilities → argmax for class + confidence
8. **Decision Tree:**
   - If "Background": send webhook "Desechado", continue loop
   - If "Potato": append crop_type, push to QUEUE_POTATO, send webhook "Enrutado"
   - If "Tomato": append crop_type, push to QUEUE_TOMATO, send webhook "Enrutado"
9. Error handling: catch exceptions, send "Error" webhook, continue

**Key Implementation Detail (lines 17-23):**
Transforms include **CenterCrop(224)** (not direct Resize), ensuring consistent preprocessing with training data. Aspect ratio preservation prevents distortion of disease features.

#### **`distributed_pipeline/potato_worker.py`**
**Responsibility:** Stage 2 specialist for potato disease classification  
**Architecture:** Near-identical to tomato_worker, specialized for potatoes

**Model Details:**
- **Architecture:** ResNet18 with Dropout(0.5) in final layer
- **Classes:** ['Potato___Early_blight', 'Potato___Late_blight', 'Potato___healthy'] (3 classes, alphabetical)
- **Preprocessing:** Resize((224, 224)) → ToTensor() → Normalize (different from router; direct resize, not crop)

**Processing Loop:**
- Consumes from QUEUE_POTATO
- Loads image, applies transforms
- Inference
- Sends webhook to Broker with predicted disease + confidence

**Design Pattern:** Specialist models include Dropout for regularization (trained on subset of data; router trained on broader dataset)

#### **`distributed_pipeline/tomato_worker.py`**
**Responsibility:** Stage 2 specialist for tomato disease classification  
**Architecture:** Near-identical to potato_worker

**Model Details:**
- **Architecture:** ResNet18 with Dropout(0.5)
- **Classes:** ['Tomato_Bacterial_spot', 'Tomato_Early_blight', 'Tomato_Late_blight', 'Tomato_Leaf_Mold', 'Tomato_Septoria_leaf_spot', 'Tomato_Spider_mites_Two_spotted_spider_mite', 'Tomato__Target_Spot', 'Tomato__Tomato_YellowLeaf__Curl_Virus', 'Tomato__Tomato_mosaic_virus', 'Tomato_healthy'] (10 classes, alphabetical)
- **Preprocessing:** Resize((224, 224)) → ToTensor() → Normalize

**Processing Loop:**
- Identical to potato worker, reads from QUEUE_TOMATO
- Returns one of 10 disease classes

### **3.4 RAG Directory** (`rag/`)

Retrieval-Augmented Generation engine for the agronomic chatbot.

#### **`rag/faiss_manager.py`**
**Responsibility:** FAISS index lifecycle management  
**Key Class:** `FAISSManager`

**Methods:**
- `__init__(model_name)`: Initialize sentence-transformer model (384-dim embeddings)
- `build(chunks)`: Encode text chunks, normalize, create FAISS index, store
- `search(query, k=3)`: Encode query, search, filter by similarity threshold, return results
- `save(index_path, chunks_path)`: Persist index and chunks to disk (pickle)
- `load(index_path, chunks_path)`: Load from disk

**Architecture Details:**
- **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- **FAISS Index Type:** `IndexFlatIP` (Inner Product = Cosine similarity after L2 normalization)
- **Search Threshold:** 0.20 minimum similarity
- **Batch Processing:** Encodes 50+ chunks in single batch for efficiency

**Data Persistence:**
- Index stored as binary FAISS file (optimized format)
- Chunks stored as Python pickle (contains text + source metadata)

#### **`rag/core.py`**
**Responsibility:** RAG pipeline orchestration  
**Key Functions:**
- `load_faiss_index()`: Initialize FAISSManager (called with `@st.cache_resource` in assistant.py)
- `retrieve(query, faiss_manager, top_k=15)`: FAISS search + similarity threshold filtering
- `ask(query, faiss_manager, expertise, history, db_context)`: Full RAG pipeline

**`ask()` Function Detailed Flow:**

1. **Parameter Validation** (lines 73-81):
   - Check GROQ_API_KEY availability
   - Set default history=[]

2. **Semantic Retrieval** (lines 83-95):
   - Call `retrieve()` to get top-k chunks from FAISS
   - Filter by similarity ≥ 0.20
   - If empty, set error message

3. **Context Assembly** (lines 97-107):
   - Combine FAISS context with live DB context (epidemiological data)
   - DB context is formatted as natural-language summary (handled by `fetch_diagnosis_context()`)
   - Order: real-time data first (more relevant), then knowledge base

4. **System Prompt Selection** (line 110):
   - If expertise=="beginner": SYSTEM_BEGINNER (simple language)
   - Else: SYSTEM_EXPERT (technical terminology)

5. **Message Construction** (lines 127-130):
   - Array of role-content pairs:
     - System prompt sets tone
     - Last 6 messages from conversation history
     - User query with full context embedded

6. **LLM Call** (lines 133-139):
   - Groq client initialization with API key
   - `create()` call with:
     - model="llama-3.3-70b-versatile"
     - max_tokens=600 (limit response length)
     - temperature=0.3 (low randomness, deterministic)

7. **Result Extraction** (lines 141-143):
   - Extract `choices[0].message.content`
   - Build sources list (deduplicated)
   - Return dict with answer + sources

**System Prompts:**
- **BEGINNER:** "Eres un asistente agrícola amigable..." (friendly agricultural assistant, simple language, Spanish)
- **EXPERT:** "Eres un asistente técnico especializado..." (technical assistant, scientific terminology, Spanish)

**Key RAG Instruction (lines 119-125):**
Emphasizes: "USE the information from context. If context contains relevant data, USE IT even if not perfect. DO NOT say you don't have information if context has related data."

This aggressive context-use strategy prevents the LLM from saying "I don't know" when retrieval succeeded but confidence is low.

### **3.5 Utils Directory** (`utils/`)

Shared utilities and helper functions.

#### **`utils/config.py`**
**Responsibility:** Centralized environment configuration for entire app  
**Key Function:**
- `_get_secret(key, default)`: Dual-source retrieval
  - First attempts `st.secrets` (Streamlit runtime secrets)
  - Falls back to environment variables
  - Graceful degradation for non-Streamlit contexts (CLI workers)

**Configuration Variables:**
- `SUPABASE_DB_URL`: PostgreSQL connection string
- `BROKER_CLIENT_URL`: Broker address for Streamlit
- `GROQ_API_KEY`: LLM authentication
- `FAISS_INDEX_PATH`, `CHUNKS_PATH`: Knowledge base file paths
- `MODEL_WEIGHTS_PATH`: Model checkpoint location
- `LOGO_PATH`: Asset path

**Design Pattern:** Imported by all modules; central source of truth (prevents hardcoded paths/secrets)

#### **`utils/db_core.py`**
**Responsibility:** Backend database layer (no Streamlit dependencies)  
**Purpose:** Enable import from FastAPI workers without UI framework overhead

**Key Classes (SQLAlchemy ORM Models):**

1. **`FileUpload`**
   - Primary table for all submissions
   - Relations: one-to-one with GeospatialData and DiagnosisResult
   - Status lifecycle: Solicitado → Enrutado/Completado/Desechado/Error

2. **`GeospatialData`**
   - Stores GPS coordinates and capture timestamp
   - Foreign key to FileUpload
   - Nullable lat/lon (fallback to browser geo if EXIF missing)

3. **`DiagnosisResult`**
   - Stores inference output
   - Created only after worker reports "Completado"
   - Includes severity and affected area (user-provided)

**Key Functions:**

- `get_engine()`: SQLAlchemy engine factory
  - Reads `SUPABASE_DB_URL` via config module
  - Returns None if URL missing

- `create_initial_ticket(upload_id, lat, lon, captured_dt)`: 
  - Called by Broker's `/diagnose` endpoint
  - Creates FileUpload + GeospatialData records
  - Transaction: commit or rollback on error

- `update_ticket_status(upload_id, status, plant, disease, confidence, area_m2, severity)`:
  - Called by Broker's `/webhook/status/{task_id}` endpoint
  - Updates FileUpload status
  - If status="Completado", creates DiagnosisResult record

- `get_ticket_status(upload_id)`:
  - Called by Broker's `GET /status/{task_id}` endpoint
  - Returns current status + diagnosis (if available)

- `update_map_fields(upload_id, area_m2, severity)`:
  - Called by analysis.py "Submit to Map" button
  - Updates DiagnosisResult area/severity fields

#### **`utils/db_manager.py`**
**Responsibility:** Streamlit-facing database utilities with caching  
**Re-exports:** All functions from `db_core` for backward compatibility

**Key Functions:**

- `@st.cache_data fetch_all_records()`:
  - Executes SQL JOIN across file_upload, geospatial_data, diagnosis_result
  - Returns DataFrame with columns: plant, disease, area_m2, severity, lat, lon, date
  - Cached to avoid excessive DB queries
  - Called by map_page and assistant_page

- `fetch_diagnosis_context()`:
  - Queries `fetch_all_records()` (respects cache)
  - Generates natural-language summary:
     - Total detection count
     - Per-disease breakdown (detections, avg severity, avg area)
     - 10 most recent detections
  - Returns formatted string (~500-1000 chars) for RAG context injection

- `clear_db_cache()`:
  - Invalidates `fetch_all_records` cache
  - Called after "Submit to Map" succeeds
  - Forces next query to refresh from DB

**Caching Strategy:**
Uses Streamlit's `@st.cache_data` decorator to cache within a single session. Cache invalidated manually when new data submitted. This balances freshness (map reflects new submissions) with performance (no N+1 queries).

#### **`utils/image_utils.py`**
**Responsibility:** EXIF metadata extraction from images  
**Key Functions:**

- `get_decimal_from_dms(dms, ref)`:
  - Converts GPS DMS (Degrees/Minutes/Seconds) to decimal degrees
  - Handles cardinal directions (S/W negative)
  - Formula: degrees + (minutes/60) + (seconds/3600), adjusted for hemisphere

- `extract_exif_data(image_file)`:
  - Opens image with Pillow
  - Extracts EXIF dictionary
  - Decodes tag IDs to human-readable names
  - Retrieves:
    - DateTimeOriginal or DateTime tag → captured_timestamp
    - GPSInfo → GPSLatitude, GPSLongitude, refs → decimal coords
  - Returns: (lat, lon, captured_dt) or (None, None, current_time) on missing data
  - Errors handled gracefully (returns defaults)

**Called By:** `analysis.py` line 89 to extract metadata before upload

#### **`utils/text_utils.py`** (referenced but not shown)
**Inferred Responsibility:** Text formatting utilities  
**Likely Functions:**
- `format_label()`: Convert class names to human-readable format (e.g., "Potato___Early_blight" → "Potato - Early Blight")
- `translate_status()`: Convert status codes to user-facing strings (e.g., "Solicitado" → "Requested")

#### **`utils/map_export.py`** (referenced but not shown)
**Inferred Responsibility:** Map rendering to image files  
**Likely Functions:**
- `export_map_to_jpg(html_path)`: Use Selenium to render HTML → screenshot → JPG

### **3.6 Assets Directory** (`assets/`)

UI assets (logos, icons).

---

## **DATA FLOW & MANAGEMENT**

### **4.1 Complete Inference Pipeline Data Flow**

#### **Phase 1: Submission (Frontend → Broker)**

```
User Action:
  1. Opens Streamlit app
  2. Selects "Camera" or "Upload"
  3. Captures/selects image
  4. Optional: Allows HTML5 geolocation (browser prompt)
  5. Clicks "Run AI Analysis"
  ↓
Frontend Processing (analysis.py):
  1. Extract EXIF metadata (GPS, timestamp)
  2. Fallback to browser geolocation if no EXIF
  3. User can manually override coordinates
  4. Construct multipart request:
     - File: image bytes
     - Form data: latitude, longitude, captured_at, model
  ↓
HTTP POST to Broker:
  POST /diagnose
  Content-Type: multipart/form-data
  Body:
    image: <binary file>
    latitude: -0.35
    longitude: -78.50
    captured_at: 2026-05-06T14:30:00
    model: "Crop Type Detection"
```

#### **Phase 2: Broker Ingestion & Queuing**

```
Broker /diagnose Endpoint:
  1. Parse multipart form
  2. Generate UUID (upload_id)
  3. Save image to shared_data/{upload_id}.jpg
  4. Create DB records (status="Solicitado"):
     - FileUpload(upload_id, received_timestamp, status)
     - GeospatialData(upload_id, lat, lon, captured_at)
  5. Build InferenceTicket JSON:
     {
       "upload_id": "uuid",
       "image_path": "/path/to/shared_data/uuid.jpg"
     }
  6. Determine target queue:
     - If model=="Crop Type Detection" → QUEUE_ROUTER
     - Else if model=="Tomato..." → QUEUE_TOMATO
     - Else if model=="Potato..." → QUEUE_POTATO
  7. Redis LPUSH to target queue
  8. Return HTTP 200 with upload_id
  ↓
Frontend Polling (analysis.py):
  Loop (every 2 seconds):
    GET /status/{upload_id}
    Display: "Current State: Waiting for ML Workers..."
    Until status ∈ {"Completado", "Desechado", "Error"}
```

#### **Phase 3: Worker Processing**

```
Router Worker Loop:
  1. BLPOP QUEUE_ROUTER (blocking, waits for task)
  2. Parse InferenceTicket JSON
  3. Load image from disk
  4. Preprocess: Resize(256) → CenterCrop(224) → Normalize
  5. Model inference (CPU):
     outputs = resnet18_model(image_tensor)
     probs = softmax(outputs)
     confidence, pred_class = max(probs)
  6. Decision:
     - If pred_class == "Background":
         send_webhook(upload_id, "Desechado", ...)
         continue loop (discard, don't route)
     - Else if pred_class == "Tomato":
         ticket["crop_type"] = "Tomato"
         redis_client.RPUSH(QUEUE_TOMATO, json(ticket))
         send_webhook(upload_id, "Enrutado", ...)
     - Else if pred_class == "Potato":
         ticket["crop_type"] = "Potato"
         redis_client.RPUSH(QUEUE_POTATO, json(ticket))
         send_webhook(upload_id, "Enrutado", ...)
  7. Continue loop
  
Specialist Worker (Tomato or Potato):
  1. BLPOP QUEUE_TOMATO/QUEUE_POTATO
  2. Parse InferenceTicket (now has crop_type)
  3. Load image
  4. Preprocess: Resize((224,224)) → Normalize
  5. Model inference:
     outputs = specialist_resnet18(image_tensor)
     probs = softmax(outputs)
     confidence, pred_idx = max(probs)
     disease_name = CLASS_NAMES[pred_idx]  # e.g., "Potato___Late_blight"
  6. Send webhook:
     send_webhook(upload_id, "Completado", crop_type, disease_name, confidence)
```

#### **Phase 4: Broker Webhook Handling**

```
Worker sends HTTP PATCH:
  PATCH /webhook/status/{upload_id}
  JSON Body:
    {
      "upload_id": "uuid",
      "status": "Completado",
      "crop_type": "Tomato",
      "predicted_disease": "Tomato_Late_blight",
      "confidence_score": 0.92
    }
  ↓
Broker /webhook/status/{upload_id}:
  1. Parse WebhookPayload
  2. Find FileUpload record by upload_id
  3. Update status → "Completado"
  4. Create DiagnosisResult record:
     DiagnosisResult(
       upload_id=upload_id,
       crop_type="Tomato",
       predicted_disease="Tomato_Late_blight",
       confidence_score=0.92,
       area_m2=NULL,        # set later by user
       severity=NULL        # set later by user
     )
  5. Return HTTP 200
```

#### **Phase 5: Frontend Display & User Action**

```
Polling Returns status="Completado":
  1. Display results card:
     - Disease: "Tomato - Late Blight"
     - Confidence: 92.0%
  2. Show map integration section:
     - Area input field (m²)
     - Severity slider (0.0 - 1.0)
     - "Submit to Map" button
  
User Clicks "Submit to Map":
  1. Calls update_map_fields(upload_id, area_m2, severity)
  2. SQL UPDATE DiagnosisResult SET area_m2=..., severity=...
  3. clear_db_cache() invalidates fetch_all_records cache
  4. Delete last_analysis from session state
  5. Streamlit reruns (clears result card)
  
Map Page Refreshes:
  1. fetch_all_records() cache invalidated, queries DB
  2. Finds new DiagnosisResult with lat/lon
  3. Folium map regenerated with new marker
  4. Heatmap updated
```

### **4.2 Database State Transitions**

```
FileUpload Lifecycle:

┌──────────────────┐
│   Solicitado     │ (Initial state after POST /diagnose)
└────────┬─────────┘
         │ (if router predicts valid crop)
         ↓
┌──────────────────┐
│    Enrutado      │ (status from router_worker webhook)
└────────┬─────────┘
         │ (specialist worker completes)
         ↓
┌──────────────────┐  ┌──────────────────┐
│   Completado     │  │   Desechado      │ (if router predicts background)
└──────────────────┘  └──────────────────┘
         │
         ↓
    ┌────────────────────────────────┐
    │ DiagnosisResult created at     │
    │ this stage (only for Completado)
    └────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│ area_m2, severity updated by user    │
│ via "Submit to Map" button           │
└──────────────────────────────────────┘
```

**Desechado Records:**
- Created when router predicts "Background"
- Status updated in FileUpload
- No DiagnosisResult created (webhook has no disease prediction)
- Excluded from map via Streamlit filter (implicit: only records with DiagnosisResult are mapped)

**Error Records:**
- If exception during processing, webhook status="Error"
- FileUpload status updated to "Error"
- No DiagnosisResult (no disease prediction)

### **4.3 Cache Invalidation Strategy**

**Streamlit's `@st.cache_data` Semantics:**
- Cached functions rerun only if:
  - Input parameters change
  - Script reruns and cache is explicitly cleared
  - Cache expires (default: never, unless set)
- **Problem:** Without cache invalidation, map doesn't reflect newly submitted records

**Solution in AgriScanAI:**
1. `fetch_all_records()` decorated with `@st.cache_data` (no expiration)
2. On "Submit to Map" success:
   - `clear_db_cache()` calls `fetch_all_records.clear()`
   - Deletes all cached return values
3. Next `fetch_all_records()` call queries DB fresh
4. Map regenerated with new marker

**Alternative Approaches (not used):**
- TTL-based cache (inefficient; misses updates for 60+ seconds)
- Polling-based cache invalidation (adds complexity)
- Direct DB reads without caching (defeats optimization purpose)

### **4.4 Data Consistency Considerations**

#### **Race Conditions**
**Scenario:** User submits while another user's results update the database

**Current Handling:** PostgreSQL transactions ensure ACID compliance
- Each operation (INSERT, UPDATE) wrapped in transaction
- Isolation level: READ COMMITTED (default)
- No distributed locking (acceptable for low-concurrency scenario)

#### **Image File Cleanup**
**Current:** Images never deleted from `shared_data/` (disk usage grows unbounded)

**Recommended Future Enhancement:**
- Add retention policy (e.g., delete images >30 days old)
- Archive old records to cold storage
- Implement periodic cleanup job

#### **Redis Queue Durability**
**Current:** Redis stores queues in memory only
- **Advantage:** Extreme speed
- **Disadvantage:** Tasks lost if Redis restarts

**Recommended Future Enhancement:**
- Enable Redis persistence (RDB snapshots or AOF)
- Implement task replay logic on broker startup

---

## **CORE ALGORITHMS & BUSINESS LOGIC**

### **5.1 Multi-Stage Inference Architecture**

#### **Stage 1: Crop Type Detection (Router)**

**Problem Addressed:** Distinguish valid crop images from background/noise  
**Solution:** Binary/Ternary Classification

**Algorithm:**
```
Input: Image of unknown subject
Output: Class ∈ {'Background', 'Potato', 'Tomato'} + Confidence Score

1. Preprocess (deterministic):
   - Resize to 256×256
   - Center crop to 224×224 (preserves aspect ratio of crops)
   - Convert to tensor
   - Normalize with ImageNet statistics

2. Forward Pass (ResNet18):
   - Input: 224×224×3 tensor
   - Backbone: 18 residual blocks (shallow for speed)
   - Global average pooling
   - Fully-connected layer: 512 → 3
   - Output: [logit_bg, logit_potato, logit_tomato]

3. Softmax + Argmax:
   - probs = softmax([logit_bg, logit_potato, logit_tomato])
   - confidence = max(probs)
   - predicted_class = argmax(probs)

4. Decision Logic:
   - If predicted_class == "Background":
     Status="Desechado" (discard)
     Stop (prevent pollution of epidemiological map)
   - Else:
     Status="Enrutado" (routed)
     Push to specialist queue
     Await specialist result
```

**Training Data Characteristics (inferred):**
- Background: diverse images (faces, floors, buildings, etc.) to maximize generalization
- Potato: photos of potato plants with/without disease
- Tomato: photos of tomato plants with/without disease
- Classes likely collected via ImageFolder hierarchy: `data/train/Background/`, `data/train/Potato/`, `data/train/Tomato/`

**Why Center Crop vs. Direct Resize?**
- Center crop preserves aspect ratio of crop subjects
- Direct resize (used by specialists) acceptable when input is already known to be a valid crop
- Router's CenterCrop guards against distortion on unknown inputs

#### **Stage 2: Disease-Specific Classification (Specialists)**

**Problem Addressed:** Identify specific diseases within confirmed crop type  
**Solution:** Multi-class Classification with Dropout Regularization

**Algorithm (Potato Example):**
```
Input: Image confirmed to be potato (from router)
Output: Class ∈ {'Potato___Early_blight', 'Potato___Late_blight', 'Potato___healthy'} + Confidence

1. Preprocess:
   - Resize directly to 224×224 (not center crop; already validated)
   - Convert to tensor
   - Normalize with ImageNet statistics

2. Forward Pass (ResNet18 with Dropout):
   - Input: 224×224×3 tensor
   - Backbone: 18 residual blocks
   - Global average pooling
   - Dropout(0.5): Drop 50% of activations (regularization)
   - Fully-connected layer: 512 → 3
   - Output: [logit_early, logit_late, logit_healthy]

3. Softmax + Argmax:
   - probs = softmax([logit_early, logit_late, logit_healthy])
   - confidence = max(probs)
   - predicted_class = argmax(probs)

4. Webhook Report:
   - Status="Completado"
   - Disease=predicted_class
   - Confidence_score=confidence
```

**Tomato Specialist (Expanded):**
- **10 Classes:** 9 diseases + healthy
- **Diseases Include:**
  - Bacterial spot
  - Early blight
  - Late blight
  - Leaf Mold
  - Septoria leaf spot
  - Spider mites (Two-spotted)
  - Target Spot
  - Tomato Yellow Leaf Curl Virus (TYLCV)
  - Tomato mosaic virus (ToMV)
  - Healthy

**Dropout Justification:**
- Specialists trained on smaller dataset per crop (vs. router's broader dataset)
- Dropout reduces overfitting
- At inference (eval mode), dropout disabled, so full network used (pessimistic averaging during training, optimistic at inference)

### **5.2 Spatial Context Algorithm (RAG)**

#### **Problem Addressed**
Generic disease advice ("Late Blight is caused by...") doesn't account for local outbreak patterns. A farmer 50km from an outbreak needs different recommendations than one 500km away.

#### **Solution: Haversine Distance Calculation + Epidemiological Clustering**

**Algorithm:**
```
User Position: (lat_user, lon_user)
Database Records: List of [(lat_i, lon_i, disease_i, severity_i, date_i), ...]

Step 1: Calculate Distances
For each record (lat_i, lon_i):
  distance_km = haversine(lat_user, lon_user, lat_i, lon_i)
  
haversine(lat1, lon1, lat2, lon2):
  R = 6371  # Earth radius in km
  Δlat = lat2 - lat1 (radians)
  Δlon = lon2 - lon1 (radians)
  a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
  c = 2 * atan2(√a, √(1-a))
  return R * c

Step 2: Segment into Tiers
LOCAL  = records with distance_km < 50
REGIONAL = records with distance_km < 500
DISTANT = records with distance_km ≥ 500 (ignored)

Step 3: Aggregate by Disease
grouped = {
  "Late Blight": {
    "LOCAL": [severity1, severity2, ...],
    "REGIONAL": [severity3, severity4, ...]
  },
  "Early Blight": {...}
}

Step 4: Generate Summary Text
"""
=== REAL-TIME EPIDEMIOLOGICAL DATA ===
Total detections: 47
Date range: 2026-04-01 → 2026-05-06

Potato Late Blight: 23 total detections
  - LOCAL (<50km): 8 cases, avg severity 0.72
  - REGIONAL (<500km): 15 cases, avg severity 0.68

Potato Early Blight: 10 total detections
  - REGIONAL: 10 cases, avg severity 0.45
"""

Step 5: Inject into RAG Context
User Query: "What should I do about late blight?"
RAG Context = [FAISS retrieval] + [above epidemiological summary]
LLM Prompt becomes: "Given 8 cases of Late Blight within 50km..."
```

**Implementation Details:**
- Distance calculation handled in Python (math)
- Thresholds (50km, 500km) are configurable constants
- Aggregation uses Pandas groupby + mean/count
- Generated summary inserted into LLM prompt (see `fetch_diagnosis_context()`)

### **5.3 Semantic Search & Retrieval Augmentation**

#### **Problem Addressed**
LLM has general knowledge but lacks domain-specific agricultural data. Retrieval-Augmented Generation augments LLM responses with relevant document excerpts.

#### **Solution: FAISS-based Semantic Search**

**Algorithm:**
```
User Query: "What are the symptoms of potato late blight?"

Step 1: Encode Query
query_embedding = sentence_transformer.encode(query)
  → 384-dimensional vector

Step 2: L2 Normalize
query_normalized = query / ||query||

Step 3: FAISS Search
results = faiss_index.search(query_normalized, k=15)
Returns:
  - 15 nearest neighbor embeddings (indices)
  - Cosine similarity scores (Inner Product on normalized vectors)

Step 4: Filter by Similarity Threshold
relevant = [r for r in results if similarity_score >= 0.20]

Step 5: Extract & Format
context_text = "\n\n---\n\n".join([
  f"[Source: {chunk['source']}]\n{chunk['text']}"
  for chunk in relevant
])

Step 6: Pass to LLM
LLM prompt includes context_text + user query
LLM generates response using provided documents
```

**Why Cosine Similarity?**
- Normalized embeddings: `IndexFlatIP` (Inner Product) ≈ Cosine Similarity
- Cosine similarity captures semantic meaning regardless of vector magnitude
- Threshold (0.20) balances precision (only relevant) vs. recall (all relevant)

**Chunk Structure:**
```python
{
  "text": "Late blight is caused by Phytophthora infestans, a water-mold oomycete...",
  "source": "INIAP Technical Bulletin - Potato Diseases",
  "chunk_id": 5  # implicit, derived from index
}
```

### **5.4 Metadata Fallback Pipeline (GPS/Timestamp)**

#### **Problem Addressed**
GPS/timestamp data often missing or stripped from images. Fallback ensures capture context is preserved.

#### **Solution: Layered Retrieval Strategy**

**Algorithm:**
```
User uploads image:

Step 1: Extract EXIF Metadata
exif_data = image._getexif()
If exif_data exists:
  GPSInfo tag → extract GPS DMS values
  DateTimeOriginal or DateTime tag → extract timestamp
  Convert GPS DMS to decimal degrees via get_decimal_from_dms()
  Return (lat_exif, lon_exif, captured_dt_exif)
Else:
  Return (None, None, datetime.now())

Step 2: Fallback to Browser Geolocation
If exif_gps is None:
  Streamlit injects JavaScript:
    navigator.geolocation.getCurrentPosition((pos) => {
      lat = pos.coords.latitude
      lon = pos.coords.longitude
      // post back to Streamlit session state
    })
  Wait 2 seconds for geolocation permission
  Read from session_state.geo_lat, session_state.geo_lon
  If still None, user can manually input
Else:
  Use EXIF GPS

Step 3: Manual Override (Optional)
User can toggle "Override Location" checkbox
Enter custom lat/lon via number inputs
Overrides both EXIF and browser geo

Step 4: Send to Broker
POST /diagnose with final (lat, lon, timestamp)
```

**DMS to Decimal Conversion:**
```
Example GPS EXIF data:
  GPSLatitude: (1, 1), (23, 1), (34.56, 100)  # degrees, minutes, seconds
  GPSLatitudeRef: 'S'  # South = negative
  
Conversion:
  degrees = 1
  minutes = 23/60 ≈ 0.383
  seconds = 34.56/3600 ≈ 0.0096
  total = 1 + 0.383 + 0.0096 ≈ 1.39
  result = -1.39 (because 'S' = negative)
```

### **5.5 Distributed Routing Logic**

#### **Problem Addressed**
How does router worker decide where to route image? How do specialists know what to do?

#### **Solution: Hierarchical Task Routing**

**Algorithm:**
```
Broker Decision (POST /diagnose):
  model_choice = request.form["model"]
  
  if model_choice == "Crop Type Detection":
    target_queue = QUEUE_ROUTER  # send to router worker
  elif model_choice == "Tomato Disease Detection":
    target_queue = QUEUE_TOMATO  # skip router, go direct to specialist
  elif model_choice == "Potato Disease Detection":
    target_queue = QUEUE_POTATO  # skip router, go direct to specialist
  
  redis_client.lpush(target_queue, ticket_json)

Router Worker Decision (QUEUE_ROUTER):
  predicted_class = model.predict(image)  # output ∈ {Background, Potato, Tomato}
  
  if predicted_class == "Background":
    send_webhook(task_id, "Desechado", "Background")
    # stop; don't route further
  
  elif predicted_class == "Tomato":
    ticket["crop_type"] = "Tomato"
    redis_client.rpush(QUEUE_TOMATO, ticket_json)
    send_webhook(task_id, "Enrutado", "Tomato")
    # specialist will handle next
  
  elif predicted_class == "Potato":
    ticket["crop_type"] = "Potato"
    redis_client.rpush(QUEUE_POTATO, ticket_json)
    send_webhook(task_id, "Enrutado", "Potato")
    # specialist will handle next

Specialist Worker Decision (QUEUE_TOMATO or QUEUE_POTATO):
  predicted_disease = model.predict(image)  # output ∈ {Early_blight, Late_blight, ...}
  confidence = probability_of_predicted_class
  
  send_webhook(task_id, "Completado", crop_type, predicted_disease, confidence)
  # Broker receives webhook, updates database
```

**Key Insight:**
- User can skip router by selecting specialist directly ("Tomato Disease Detection")
- If router selected, it decides routing
- Routing is unidirectional (router → specialists, not back)

---

## **SETUP, BUILD & DEPLOYMENT**

### **6.1 Prerequisites & System Requirements**

#### **Software Requirements**
- **Python 3.9+** (3.10+ recommended for performance)
- **Git** (for version control, cloning repo)
- **Redis Server** (running locally or remotely)
  - Download: https://redis.io/download or use Docker: `docker run -d -p 6379:6379 redis`
- **PostgreSQL** (local or cloud-hosted; Supabase recommended)

#### **Hardware Recommendations**
- **CPU:** Multi-core processor (prefer 4+ cores for parallel workers)
- **RAM:** 8GB minimum (2GB per worker + Streamlit overhead)
- **Disk:** 10GB (images accumulate in `shared_data/`)
- **GPU:** Optional (models use CPU inference, so GPU acceleration not required)

#### **API Keys**
- **Groq API Key:** https://console.groq.com/keys (free tier: 10k tokens/day)
- **Supabase PostgreSQL URL:** https://supabase.com (free tier: 500MB database)

### **6.2 Local Development Setup**

#### **Step 1: Clone Repository & Create Virtual Environment**
```bash
git clone https://github.com/mishellguanoc/AgriScanAI.git
cd AgriScanAI

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### **Step 2: Install Dependencies**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Note:** The `--extra-index-url` in requirements.txt points to PyTorch CPU wheels. If you have CUDA-capable GPU, replace:
```bash
# In requirements.txt, change:
torch==2.11.0+cpu torchvision==0.26.0+cpu
# To:
torch==2.11.0 torchvision==0.26.0  # will use CUDA by default
```

#### **Step 3: Configure Secrets**
Create `.streamlit/secrets.toml`:
```toml
SUPABASE_DB_URL = "postgresql://postgres:password@db.supabase.co:5432/postgres"
GROQ_API_KEY = "gsk_xxxxxxxxxxxxx"
BROKER_CLIENT_URL = "http://localhost:8000"
FAISS_INDEX_PATH = "data/embeddings/faiss_index.bin"
CHUNKS_PATH = "data/embeddings/chunks.pkl"
MODEL_WEIGHTS_PATH = "model_weights/agriscan_model.pth"
```

Also create `.env` (for non-Streamlit contexts like workers):
```
SUPABASE_DB_URL=postgresql://postgres:password@db.supabase.co:5432/postgres
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
REDIS_HOST=localhost
REDIS_PORT=6379
BROKER_HOST=0.0.0.0
BROKER_PORT=8000
```

#### **Step 4: Verify Redis Installation**
```bash
# Start Redis (macOS/Linux)
redis-server
# Or on Windows, use WSL or Docker

# In another terminal, test connection
redis-cli ping
# Expected output: PONG
```

#### **Step 5: Create Directory Structure**
```bash
mkdir -p shared_data
mkdir -p model_weights
mkdir -p data/embeddings
mkdir -p assets
```

#### **Step 6: Obtain/Download Model Weights**
**Note:** Model weights not included in repo (too large). Acquire from:
- Author's Google Drive link (if provided)
- Retrain models using training notebooks (if available)
- For demo, create dummy models:
  ```python
  import torch
  import torch.nn as nn
  from torchvision import models
  
  # Create router model
  model = models.resnet18(weights=None)
  num_ftrs = model.fc.in_features
  model.fc = nn.Linear(num_ftrs, 3)
  torch.save(model.state_dict(), "model_weights/agriscan_model.pth")
  
  # Create specialist models (same process, adjust output dims)
  ```

#### **Step 7: Build FAISS Knowledge Base**
The repo should include a script to build the knowledge base:
```bash
python scripts/build_kb.py
# Creates:
#   - data/embeddings/faiss_index.bin
#   - data/embeddings/chunks.pkl
```

If not present, create manually:
```python
from rag.faiss_manager import FAISSManager

# Mock agricultural chunks
chunks = [
  {
    "text": "Late blight is caused by Phytophthora infestans...",
    "source": "INIAP Bulletin"
  },
  # ... more chunks ...
]

fm = FAISSManager()
fm.build(chunks)
fm.save("data/embeddings/faiss_index.bin", "data/embeddings/chunks.pkl")
```

#### **Step 8: Initialize Database**
```bash
# Using SQLAlchemy to create tables
python -c "
from utils.db_core import Base, get_engine
engine = get_engine()
Base.metadata.create_all(engine)
print('Tables created successfully')
"
```

### **6.3 Running the System Locally**

#### **Terminal 1: Start Redis**
```bash
redis-server
```

#### **Terminal 2: Start Broker**
```bash
cd AgriScanAI
source venv/bin/activate
python -m uvicorn distributed_pipeline.broker:app --host 0.0.0.0 --port 8000 --reload
# Expected output: "Uvicorn running on http://0.0.0.0:8000"
```

#### **Terminal 3: Start Router Worker**
```bash
cd AgriScanAI
source venv/bin/activate
python -m distributed_pipeline.router_worker
# Expected output: "Router Worker is waiting for tasks..."
```

#### **Terminal 4: Start Tomato Specialist Worker**
```bash
cd AgriScanAI
source venv/bin/activate
python -m distributed_pipeline.tomato_worker
# Expected output: "Tomato Worker is waiting for tasks..."
```

#### **Terminal 5: Start Potato Specialist Worker**
```bash
cd AgriScanAI
source venv/bin/activate
python -m distributed_pipeline.potato_worker
# Expected output: "Potato Worker is waiting for tasks..."
```

#### **Terminal 6: Start Streamlit Frontend**
```bash
cd AgriScanAI
source venv/bin/activate
streamlit run app.py
# Expected output: "You can now view your Streamlit app in your browser at http://localhost:8501"
```

Open browser: http://localhost:8501

### **6.4 Multi-Machine Deployment**

#### **Network Configuration**
For distributed deployment (broker on Server A, workers on Server B, frontend on Server C):

1. **Update `.env` on each machine:**
   ```
   # Server A (Broker)
   BROKER_HOST=0.0.0.0
   BROKER_PORT=8000
   REDIS_HOST=A.B.C.D  # Redis server IP
   REDIS_PORT=6379
   SUPABASE_DB_URL=...
   
   # Server B (Workers)
   REDIS_HOST=A.B.C.D  # same Redis
   BROKER_WEBHOOK_URL=http://A.B.C.D:8000/webhook/status
   
   # Server C (Streamlit)
   BROKER_CLIENT_URL=http://A.B.C.D:8000  # Broker IP
   ```

2. **Firewall Rules:**
   - Allow 6379 (Redis) from all machines
   - Allow 8000 (Broker) from all machines
   - Allow 8501 (Streamlit) from users

3. **Start Services:**
   - Server A: Redis, Broker, (optionally one worker)
   - Server B: Multiple workers
   - Server C: Streamlit

#### **Docker Deployment (Optional)**
```dockerfile
# Dockerfile for worker container
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "distributed_pipeline.router_worker"]
```

```bash
# Build and run
docker build -t agriscan-worker .
docker run -e REDIS_HOST=redis.example.com -e BROKER_WEBHOOK_URL=http://broker.example.com:8000/webhook/status agriscan-worker
```

### **6.5 Environment Variables Reference**

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `SUPABASE_DB_URL` | PostgreSQL connection | N/A | `postgresql://user:pass@host/db` |
| `GROQ_API_KEY` | LLM authentication | N/A | `gsk_xxxxx` |
| `BROKER_CLIENT_URL` | Streamlit → Broker URL | `http://localhost:8000` | `http://192.168.1.50:8000` |
| `BROKER_HOST` | Broker bind address | `0.0.0.0` | `0.0.0.0` |
| `BROKER_PORT` | Broker port | `8000` | `8000` |
| `REDIS_HOST` | Redis server | `localhost` | `redis.example.com` |
| `REDIS_PORT` | Redis port | `6379` | `6379` |
| `FAISS_INDEX_PATH` | FAISS index file | `data/embeddings/faiss_index.bin` | `/var/data/faiss.bin` |
| `CHUNKS_PATH` | Knowledge base chunks | `data/embeddings/chunks.pkl` | `/var/data/chunks.pkl` |
| `MODEL_WEIGHTS_PATH` | Router model weights | `model_weights/agriscan_model.pth` | `/models/router.pth` |

### **6.6 Troubleshooting Common Issues**

#### **Issue: Redis Connection Refused**
```
Error: Error 111 connecting to localhost:6379. Connection refused.
```
**Solution:**
- Verify Redis is running: `redis-cli ping`
- Check host/port in `.env`: `REDIS_HOST`, `REDIS_PORT`
- Restart Redis: `redis-server`

#### **Issue: Database Connection Failed**
```
Error: could not translate host name "db.supabase.co" to address
```
**Solution:**
- Verify internet connection
- Check `SUPABASE_DB_URL` is correct
- Test with psql: `psql "your_connection_string"`

#### **Issue: Model Weights Not Found**
```
Warning: Model not found at model_weights/agriscan_model.pth
```
**Solution:**
- Download weights and place in `model_weights/`
- Or create dummy model as described in Step 6

#### **Issue: Streamlit Geolocation Prompt Never Appears**
```
GPS Fetch failed or denied.
```
**Solution:**
- Requires HTTPS in production (HTTP localhost works for development)
- User must grant permission in browser prompt
- Fallback to manual location input

#### **Issue: Workers Process Tasks But Don't Report Results**
```
Processing ticket xxx
(no subsequent webhook message)
```
**Solution:**
- Verify `BROKER_WEBHOOK_URL` is correct
- Check Broker is accessible from worker machine
- Review worker logs for exceptions

---

## **OPERATIONAL GUIDELINES & BEST PRACTICES**

### **7.1 Monitoring & Observability**

#### **Health Checks**
```bash
# Check Redis connectivity
redis-cli PING
redis-cli INFO  # detailed stats

# Check Broker health
curl http://localhost:8000/docs  # OpenAPI docs
curl http://localhost:8000/status/00000000-0000-0000-0000-000000000000  # test endpoint

# Check Streamlit
curl http://localhost:8501  # should return HTML
```

#### **Log Aggregation**
Redirect logs to file for analysis:
```bash
# Broker
python -m uvicorn distributed_pipeline.broker:app > broker.log 2>&1 &

# Workers
python -m distributed_pipeline.router_worker > router_worker.log 2>&1 &
python -m distributed_pipeline.tomato_worker > tomato_worker.log 2>&1 &
python -m distributed_pipeline.potato_worker > potato_worker.log 2>&1 &

# Streamlit
streamlit run app.py > streamlit.log 2>&1 &
```

### **7.2 Performance Optimization**

#### **Model Inference Acceleration**
- Current: CPU-based inference (2-5 seconds per image)
- **Option 1:** GPU acceleration
  - Replace `torch.device('cpu')` with `torch.device('cuda')` if CUDA available
  - Expected speedup: 5-10x
  
- **Option 2:** Model quantization
  - Convert fp32 → int8 using PyTorch quantization API
  - Reduces model size, slightly faster inference

- **Option 3:** ONNX export
  - Convert PyTorch models to ONNX Runtime
  - Cross-platform optimization

#### **Database Query Optimization**
- Current: Full table scan on every map refresh
- **Optimization:**
  - Add indexes: `CREATE INDEX idx_status ON file_upload(status)`
  - Add indexes: `CREATE INDEX idx_crop ON diagnosis_result(crop_type)`
  - Implement pagination for large datasets

#### **Frontend Caching**
- Streamlit's `@st.cache_data` is already in use
- **Additional options:**
  - CDN for static assets (CSS, fonts, SVGs)
  - Browser caching headers for assets

### **7.3 Security Considerations**

#### **Input Validation**
- **Current:** Minimal validation (Pydantic for API, basic file type checks)
- **Recommendations:**
  - Validate file size (max 10MB)
  - Scan uploads for malware
  - Rate-limit `/diagnose` endpoint (10 requests/user/hour)
  - Validate GPS coordinates (lat -90 to 90, lon -180 to 180)

#### **Authentication & Authorization**
- **Current:** None (public endpoint)
- **Recommendations for production:**
  - Add user authentication (OAuth2, JWT)
  - Implement role-based access control (farmer, agronomist, admin)
  - API key for workers (verify webhook sender)

#### **Data Privacy**
- **Current:** All data stored in plaintext
- **Recommendations:**
  - Encrypt sensitive data at rest (database encryption, Supabase encryption)
  - TLS/SSL for all network communication
  - Implement GDPR compliance (user data export, deletion)

#### **Image Storage Security**
- **Current:** Images stored in shared_data/ with predictable names
- **Recommendations:**
  - Generate random filenames
  - Implement access control (only workers and owner can read)
  - Set automatic expiration (delete after 30 days)

### **7.4 Scalability Considerations**

#### **Horizontal Scaling**
- **Broker:** Stateless (except image storage); easy to scale behind load balancer
- **Workers:** Horizontally scalable; add more workers to reduce queue latency
- **Database:** Implement read replicas for analytics queries

#### **Vertical Scaling**
- **Workers:** Add more CPU cores to enable more parallel inference
- **GPU:** If using GPU, upgrade to better model (e.g., ResNet50)

#### **Queue Throughput**
- Current: ~3 images/second with 3 workers on CPU
- Estimate: 10-20 images/second with GPU cluster

---

## **CONCLUSION**

AgriScan AI represents a sophisticated integration of modern machine learning, distributed systems, and geospatial data analytics tailored for agricultural disease detection. The asynchronous, multi-stage architecture ensures responsiveness and scalability, while the RAG-based chatbot augments LLM responses with real-time epidemiological context and domain-specific knowledge.

**Key Strengths:**
1. **Decoupled Architecture:** UI remains responsive regardless of inference latency
2. **Multi-Stage Filtering:** Router reduces false positives before specialist inference
3. **Spatially-Aware Recommendations:** Haversine distances enable context-specific advice
4. **Modular Codebase:** Clear separation of concerns (frontend, broker, workers, database, RAG)
5. **Scalable Design:** Horizontal scaling of workers; distributed queuing

**Future Enhancement Opportunities:**
1. **Model Ensemble:** Combine multiple model predictions for improved accuracy
2. **Transfer Learning:** Fine-tune on regional crop disease datasets
3. **Real-time Alerts:** Notify farmers of nearby outbreaks via push notifications
4. **Historical Trend Analysis:** Predict disease spread using time-series forecasting
5. **Computer Vision Explanation:** Implement GradCAM or LIME to highlight disease regions
6. **Mobile App:** Native iOS/Android app (currently web-based Streamlit)
7. **Offline Mode:** Cache models locally for areas with poor connectivity

This documentation should serve as a comprehensive reference for developers maintaining, extending, or deploying AgriScan AI. The layered architecture and clear separation of concerns facilitate independent iteration and testing of each component.