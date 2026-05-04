"""
distributed_pipeline/worker_utils.py
Shared utilities for all ML Workers.
Centralizes the webhook sender so that URL and payload structure
are defined in a single place, using config.py as the source of truth.
"""

import requests
from distributed_pipeline.config import BROKER_WEBHOOK_URL


def send_webhook(
    task_id: str,
    status: str,
    crop_type: str = None,
    disease: str = None,
    confidence: float = 0.0,
):
    """
    Sends a PATCH request to the Broker webhook endpoint to update
    the status of a task in the database.

    Args:
        task_id:    The UUID string of the task to update.
        status:     New status (e.g. 'Completado', 'Enrutado', 'Desechado', 'Error').
        crop_type:  Crop identified by the router ('Tomato', 'Potato', 'Background').
        disease:    Predicted disease label from a specialist worker.
        confidence: Confidence score in the 0.0–1.0 range.
    """
    url = f"{BROKER_WEBHOOK_URL}/{task_id}"
    payload = {
        "upload_id": task_id,
        "status": status,
        "crop_type": crop_type,
        "predicted_disease": disease,
        "confidence_score": confidence,
    }
    try:
        r = requests.patch(url, json=payload, timeout=5)
        print(f"Webhook sent [{status}] → {r.status_code}")
    except Exception as e:
        print(f"Failed to send webhook to {url}: {e}")
