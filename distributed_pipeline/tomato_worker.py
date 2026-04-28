import json
import requests
import redis
import traceback
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

from distributed_pipeline.config import (
    REDIS_HOST, REDIS_PORT, QUEUE_TOMATO, BROKER_WEBHOOK_URL, MODELS_WEIGHTS_DIR
)

print("Starting Tomato Specialist Worker (Level 2)...")

# 1. Preprocesamiento (exactamente igual al notebook de entrenamiento)
inference_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# 2. Clases en orden alfabético (igual que ImageFolder en entrenamiento)
NUM_CLASSES = 10
MODEL_PATH = MODELS_WEIGHTS_DIR / "best_tomato_worker.pth"
CLASS_NAMES = [
    'Tomato_Bacterial_spot',
    'Tomato_Early_blight',
    'Tomato_Late_blight',
    'Tomato_Leaf_Mold',
    'Tomato_Septoria_leaf_spot',
    'Tomato_Spider_mites_Two_spotted_spider_mite',
    'Tomato__Target_Spot',
    'Tomato__Tomato_YellowLeaf__Curl_Virus',
    'Tomato__Tomato_mosaic_virus',
    'Tomato_healthy'
]

# 3. Arquitectura CON Dropout (igual que en entrenamiento de especialistas)
try:
    model = models.resnet18(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(0.5),
        nn.Linear(num_ftrs, NUM_CLASSES)
    )
    if MODEL_PATH.exists():
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu'), weights_only=True))
        print("Successfully loaded best_tomato_worker.pth")
    else:
        print(f"Warning: Model not found at {MODEL_PATH}")
    model.eval()
except Exception as e:
    print(f"Error loading model: {e}")
    traceback.print_exc()

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def send_webhook(task_id: str, status: str, crop_type: str = "Tomato", disease: str = None, confidence: float = 0.0):
    url = f"http://localhost:8000/webhook/status/{task_id}"
    payload = {
        "upload_id": task_id,
        "status": status,
        "crop_type": crop_type,
        "predicted_disease": disease,
        "confidence_score": confidence
    }
    try:
        r = requests.patch(url, json=payload, timeout=5)
        print(f"Webhook sent: {status} ({r.status_code})")
    except Exception as e:
        print(f"Failed to send webhook to {url}: {e}")

print("Tomato Worker is waiting for tasks...")
while True:
    try:
        _, message = redis_client.blpop(QUEUE_TOMATO)
        ticket = json.loads(message)
        
        task_id = ticket["upload_id"]
        image_path = ticket["image_path"]
        
        print(f"Processing ticket {task_id}")
        
        img = Image.open(image_path).convert('RGB')
        img_t = inference_transforms(img).unsqueeze(0)
        
        with torch.no_grad():
            outputs = model(img_t)
            probs = torch.nn.functional.softmax(outputs, dim=1)
            conf, preds = torch.max(probs, 1)
            predicted_class = CLASS_NAMES[preds[0].item()]
            confidence = float(conf[0].item())
            
        print(f"Tomato prediction: {predicted_class} ({confidence*100:.2f}%)")
        send_webhook(task_id, "Completado", "Tomato", predicted_class, confidence)
            
    except Exception as e:
        print(f"Critical error processing ticket: {e}")
        traceback.print_exc()
        try:
            if 'task_id' in locals():
                send_webhook(task_id, "Error")
        except:
            pass
