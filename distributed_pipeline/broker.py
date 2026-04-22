from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
import shutil
import uuid
from datetime import datetime
import redis
import os

from distributed_pipeline.config import (
    SHARED_DATA_DIR, REDIS_HOST, REDIS_PORT, QUEUE_ROUTER, BROKER_HOST, BROKER_PORT
)
from distributed_pipeline.schemas import InferenceTicket, WebhookPayload
from utils.db_manager import create_initial_ticket, update_ticket_status

app = FastAPI(title="AgriScanAI Broker")

# Initialize Redis client pointing to the centralized config
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    # Don't ping here since it blocks startup if redis isn't running yet, we check on request.
except Exception as e:
    redis_client = None
    print(f"Failed to initialize Redis client: {e}")

@app.post("/diagnose")
async def diagnose(
    image: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    capture_dt: str = Form(None)
):
    if not redis_client:
        # Re-attempt connection
        rc = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        try:
            rc.ping()
        except:
            raise HTTPException(status_code=503, detail="Redis broker is not available")
    else:
        try:
            redis_client.ping()
            rc = redis_client
        except:
            raise HTTPException(status_code=503, detail="Redis broker is not reachable")
            
    upload_id = uuid.uuid4()
    
    # Save file physically to shared volume (or folder)
    file_extension = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
    saved_filename = f"{upload_id}{file_extension}"
    file_path = SHARED_DATA_DIR / saved_filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")
        
    # Parse datetime
    dt = datetime.now()
    if capture_dt:
        try:
            dt = datetime.fromisoformat(capture_dt.replace("Z", "+00:00"))
        except ValueError:
            pass

    # 1. Save initial ticket to Supabase via our DB manager
    db_success = create_initial_ticket(upload_id, latitude, longitude, dt)
    if not db_success:
        raise HTTPException(status_code=500, detail="Failed to create database record")
        
    # 2. Push to Redis for the Router Worker (Level 1)
    ticket = InferenceTicket(
        upload_id=str(upload_id),
        image_path=str(file_path)
    )
    
    try:
        rc.lpush(QUEUE_ROUTER, ticket.model_dump_json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue ticket to Redis: {e}")
        
    return {
        "message": "Ticket created successfully", 
        "upload_id": str(upload_id), 
        "status": "Solicitado",
        "queue": QUEUE_ROUTER
    }

@app.patch("/webhook/status/{task_id}")
async def update_status(task_id: str, payload: WebhookPayload):
    """Webhook URL that workers will call via PATCH to update the progress."""
    db_success = update_ticket_status(
        upload_id=uuid.UUID(task_id),
        status=payload.status,
        plant=payload.crop_type,
        disease=payload.predicted_disease,
        confidence=payload.confidence_score,
        area_m2=payload.area_m2,
        severity=payload.severity
    )
    
    if not db_success:
        raise HTTPException(status_code=500, detail="Failed to update database record")
        
    return {"message": "State updated successfully", "status": payload.status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("distributed_pipeline.broker:app", host=BROKER_HOST, port=BROKER_PORT, reload=True)
