from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
import shutil
import uuid
from datetime import datetime
import redis
import os
import traceback

from distributed_pipeline.config import (
    SHARED_DATA_DIR, REDIS_HOST, REDIS_PORT, QUEUE_ROUTER, QUEUE_TOMATO, QUEUE_POTATO, BROKER_HOST, BROKER_PORT
)
from distributed_pipeline.schemas import InferenceTicket, WebhookPayload
from utils.db_core import create_initial_ticket, update_ticket_status, get_ticket_status

app = FastAPI(title="AgriScanAI Broker")

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
except Exception as e:
    redis_client = None
    print(f"Failed to initialize Redis client: {e}")

@app.post("/diagnose")
async def diagnose(
    image: UploadFile = File(...),
    latitude: float = Form(0.0),
    longitude: float = Form(0.0),
    model: str = Form("Crop Type Detection")
):
    if not redis_client:
        try:
            rc = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            rc.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="Redis broker is not available")
    else:
        try:
            redis_client.ping()
            rc = redis_client
        except Exception:
            raise HTTPException(status_code=503, detail="Redis broker is not reachable")
            
    upload_id = uuid.uuid4()
    
    # 1. DB Save 
    dt = datetime.now()
    db_success = create_initial_ticket(upload_id, latitude, longitude, dt)
    if not db_success:
        raise HTTPException(status_code=500, detail="Failed to create database record")
        
    try:
        # Físico
        file_extension = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
        saved_filename = f"{upload_id}{file_extension}"
        file_path = SHARED_DATA_DIR / saved_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
            
        ticket = InferenceTicket(
            upload_id=str(upload_id),
            image_path=str(file_path)
        )
        
        target_queue = QUEUE_ROUTER
        if model == "Tomato Disease Detection":
            target_queue = QUEUE_TOMATO
        elif model == "Potato Disease Detection":
            target_queue = QUEUE_POTATO
            
        rc.lpush(target_queue, ticket.model_dump_json())
        
        return {
            "message": "Ticket created successfully", 
            "upload_id": str(upload_id), 
            "status": "Solicitado",
            "queue": target_queue
        }
    except Exception as e:
        print(f"Error en /diagnose:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/webhook/status/{task_id}")
async def update_status(task_id: str, payload: WebhookPayload):
    try:
        uid = uuid.UUID(task_id)
        success = update_ticket_status(
            upload_id=uid, 
            status=payload.status, 
            plant=payload.crop_type, 
            disease=payload.predicted_disease, 
            confidence=payload.confidence_score
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update database record")
        return {"message": "State updated successfully", "status": payload.status}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    try:
        uid = uuid.UUID(task_id)
        result = get_ticket_status(uid)
        if result.get("status") == "Not_Found":
            raise HTTPException(status_code=404, detail="Task not found")
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("distributed_pipeline.broker:app", host=BROKER_HOST, port=BROKER_PORT, reload=True)
