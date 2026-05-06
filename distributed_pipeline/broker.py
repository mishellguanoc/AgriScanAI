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
from utils.db_core import create_initial_ticket, update_ticket_status, get_ticket_status, delete_ticket

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
    captured_at: str = Form(None),
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
    
    # 1. Save image to shared volume
    try:
        file_extension = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
        saved_filename = f"{upload_id}{file_extension}"
        file_path = SHARED_DATA_DIR / saved_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    except Exception as e:
        print(f"Error saving image:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")

    # 2. DB Save (with image_path)
    dt = None
    if captured_at:
        try:
            dt = datetime.fromisoformat(captured_at)
        except Exception:
            dt = datetime.now()
    else:
        dt = datetime.now()
        
    db_success = create_initial_ticket(upload_id, latitude, longitude, dt, image_path=str(file_path))
    if not db_success:
        # Clean up the saved image if DB fails
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail="Failed to create database record")
        
    try:
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

        # Background/discarded: clean up DB records and image file entirely
        if payload.status in ["Desechado", "Desechado/Background"]:
            delete_ticket(uid)
            # Delete image from shared_data
            for ext in ['.jpg', '.jpeg', '.png']:
                img_path = SHARED_DATA_DIR / f"{task_id}{ext}"
                if img_path.exists():
                    img_path.unlink()
                    print(f"[broker] Deleted image: {img_path}")
            return {"message": "Background discarded and cleaned up", "status": payload.status}

        success = update_ticket_status(
            upload_id=uid, 
            status=payload.status, 
            plant=payload.crop_type, 
            disease=payload.predicted_disease, 
            confidence=payload.confidence_score,
            crop_type_verified=payload.crop_type_verified,
            router_crop_prediction=payload.router_crop_prediction,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update database record")
        return {"message": "State updated successfully", "status": payload.status}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

@app.post("/flag")
async def flag_incorrect(
    image: UploadFile = File(...),
    latitude: float = Form(0.0),
    longitude: float = Form(0.0),
    captured_at: str = Form(None),
    original_prediction: str = Form("Background"),
):
    """
    Allows users to flag a discarded (background) image as incorrectly classified.
    Creates a new DB record with status 'Flagged_Incorrect' and saves the image
    to shared_data for future reinforcement learning / review.
    """
    upload_id = uuid.uuid4()

    dt = None
    if captured_at:
        try:
            dt = datetime.fromisoformat(captured_at)
        except Exception:
            dt = datetime.now()
    else:
        dt = datetime.now()

    # Save image to shared volume
    try:
        file_extension = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
        saved_filename = f"{upload_id}{file_extension}"
        file_path = SHARED_DATA_DIR / saved_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save flagged image: {e}")

    # Create ticket with image_path
    db_success = create_initial_ticket(upload_id, latitude, longitude, dt, image_path=str(file_path))
    if not db_success:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail="Failed to create database record for flagged image")

    # Create a DiagnosisResult marked as flagged for review
    update_ticket_status(
        upload_id=upload_id,
        status="Flagged_Incorrect",
        plant="Unknown",
        disease=f"Flagged_{original_prediction}",
        confidence=0.0,
        crop_type_verified=False,
        router_crop_prediction=original_prediction,
    )

    return {
        "message": "Image flagged for review. Thank you for helping improve our models.",
        "upload_id": str(upload_id),
        "status": "Flagged_Incorrect",
    }

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
