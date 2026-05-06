from pydantic import BaseModel
from typing import Optional

class InferenceTicket(BaseModel):
    """Payload sent via Redis queues between Broker and Workers."""
    upload_id: str
    image_path: str
    crop_type: Optional[str] = None

class WebhookPayload(BaseModel):
    """Payload sent by workers to Broker REST API to update task status."""
    upload_id: str
    status: str
    crop_type: Optional[str] = None
    predicted_disease: Optional[str] = None
    confidence_score: Optional[float] = None
    area_m2: Optional[float] = 0.0
    severity: Optional[float] = 0.0
    crop_type_verified: Optional[bool] = None
    router_crop_prediction: Optional[str] = None
