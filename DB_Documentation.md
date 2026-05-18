# AgriScanAI Broker API Documentation

This document outlines the API endpoints exposed by the AgriScanAI Broker service for interacting with the backend and distributed workers.

---

## 1. Submit Diagnosis Request
Initiates a new diagnosis pipeline, saves the image, creates a database ticket, and pushes the job to the Redis queue.

*   **Endpoint:** `/diagnose`
*   **Method:** `POST`
*   **Content-Type:** `multipart/form-data`

### Request Body (Form-Data)
| Key | Type | Required | Description | Default |
| :--- | :--- | :--- | :--- | :--- |
| `image` | File | Yes | The crop image to be analyzed. | - |
| `latitude` | Float | No | The GPS latitude of the scan. | `0.0` |
| `longitude` | Float | No | The GPS longitude of the scan. | `0.0` |
| `captured_at` | String | No | ISO 8601 timestamp of capture. | `datetime.now()` |
| `model` | String | No | Intended model ("Crop Type Detection", "Tomato Disease Detection", "Potato Disease Detection"). | `"Crop Type Detection"` |

### Success Response
*   **Code:** `200 OK`
*   **Content-Type:** `application/json`
```json
{
  "message": "Ticket created successfully",
  "upload_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "Solicitado",
  "queue": "router_queue"
}
```

---

## 2. Update Task Status (Webhook)
Used by the worker nodes to report the completion status and diagnosis results back to the broker and database. If the status is "Desechado" or "Desechado/Background", the system purges the image and database ticket.

*   **Endpoint:** `/webhook/status/{task_id}`
*   **Method:** `PATCH`
*   **Content-Type:** `application/json`

### Path Variables
*   `task_id` (String/UUID): The `upload_id` generated during `/diagnose`.

### Request Body (JSON)
```json
{
  "upload_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "Completado",
  "crop_type": "Tomato",
  "predicted_disease": "Blight",
  "confidence_score": 0.95,
  "area_m2": 150.5,
  "severity": 0.8,
  "crop_type_verified": true,
  "router_crop_prediction": "Tomato"
}
```
*(Note: `upload_id` and `status` are required. All other fields are optional depending on the status.)*

### Success Response
*   **Code:** `200 OK`
*   **Content-Type:** `application/json`
```json
{
  "message": "State updated successfully",
  "status": "Completado"
}
```

---

## 3. Flag Incorrect Prediction
Allows users to flag a discarded/background image as incorrectly classified by the model, saving it for future reinforcement learning.

*   **Endpoint:** `/flag`
*   **Method:** `POST`
*   **Content-Type:** `multipart/form-data`

### Request Body (Form-Data)
| Key | Type | Required | Description | Default |
| :--- | :--- | :--- | :--- | :--- |
| `image` | File | Yes | The image being flagged. | - |
| `latitude` | Float | No | The GPS latitude of the scan. | `0.0` |
| `longitude` | Float | No | The GPS longitude of the scan. | `0.0` |
| `captured_at` | String | No | ISO 8601 timestamp of capture. | `datetime.now()` |
| `original_prediction`| String | No | The prediction given by the system. | `"Background"` |

### Success Response
*   **Code:** `200 OK`
*   **Content-Type:** `application/json`
```json
{
  "message": "Image flagged for review. Thank you for helping improve our models.",
  "upload_id": "660e8400-e29b-41d4-a716-446655441111",
  "status": "Flagged_Incorrect"
}
```

---

## 4. Get Task Status
Retrieves the current processing state and any resulting diagnosis for a specific ticket.

*   **Endpoint:** `/status/{task_id}`
*   **Method:** `GET`

### Path Variables
*   `task_id` (String/UUID): The `upload_id` of the diagnosis request.

### Success Response
*   **Code:** `200 OK`
*   **Content-Type:** `application/json`
```json
{
  "status": "Completado",
  "disease": "Tomato_Blight",
  "confidence": 0.98
}
```
*(Note: If the ticket is still processing, `disease` and `confidence` may be `null`.)*

### Error Response
*   **Code:** `404 Not Found`
```json
{
  "detail": "Task not found"
}
```
