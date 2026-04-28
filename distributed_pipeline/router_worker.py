import json
import requests
import redis
import traceback
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

from distributed_pipeline.config import (
    REDIS_HOST, REDIS_PORT, QUEUE_ROUTER, QUEUE_TOMATO, QUEUE_POTATO, 
    BROKER_WEBHOOK_URL, MODELS_WEIGHTS_DIR
)

print("Starting Router Worker (Level 1)...")

# 1. Preprocesamiento EXACTO igual al entrenamiento (Resize 256 + CenterCrop 224)
inference_transforms = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# 2. Clases en ORDEN ALFABÉTICO exacto tal como ImageFolder las creo
NUM_CLASSES = 3
MODEL_PATH = MODELS_WEIGHTS_DIR / "agriscan_model.pth"
CLASS_NAMES = ['Background', 'Potato', 'Tomato']

# 3. Arquitectura sin Dropout (exactamente la que se usó en entrenamiento)
try:
    model = models.resnet18(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, NUM_CLASSES)

    if MODEL_PATH.exists():
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
        print("Successfully loaded agriscan_model.pth")
    else:
        print(f"Warning: Model not found at {MODEL_PATH}")
        
    model.eval()
except Exception as e:
    print(f"Error loading model: {e}")
    traceback.print_exc()

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def send_webhook(task_id: str, status: str, crop_type: str = None):
    url = f"http://localhost:8000/webhook/status/{task_id}"
    payload = {
        "upload_id": task_id,
        "status": status,
        "crop_type": crop_type
    }
    try:
        r = requests.patch(url, json=payload, timeout=5)
        print(f"Webhook sent to broker: {status} ({r.status_code})")
    except Exception as e:
        print(f"Failed to send webhook to {url}: {e}")

print("Router Worker is waiting for tasks...")
while True:
    try:
        _, message = redis_client.blpop(QUEUE_ROUTER)
        ticket = json.loads(message)
        
        task_id = ticket["upload_id"]
        image_path = ticket["image_path"]
        
        print(f"Processing ticket {task_id} | Image: {image_path}")
        
        img = Image.open(image_path).convert('RGB')
        img_t = inference_transforms(img).unsqueeze(0)
        
        with torch.no_grad():
            outputs = model(img_t)
            probs = torch.nn.functional.softmax(outputs, dim=1)
            conf, preds = torch.max(probs, 1)
            predicted_class = CLASS_NAMES[preds[0].item()]
            confidence = float(conf[0].item()) * 100.0
            
        print(f"Router prediction: {predicted_class} ({confidence:.2f}%)")
        
        if predicted_class == 'Background':
            send_webhook(task_id, "Desechado", "Background")
            print(f"Dropped {task_id} as background.")
            
        elif predicted_class == 'Tomato':
            ticket["crop_type"] = "Tomato"
            redis_client.rpush(QUEUE_TOMATO, json.dumps(ticket))
            send_webhook(task_id, "Enrutado", "Tomato")
            print(f"Routed {task_id} to Tomato Worker.")
            
        elif predicted_class == 'Potato':
            ticket["crop_type"] = "Potato"
            redis_client.rpush(QUEUE_POTATO, json.dumps(ticket))
            send_webhook(task_id, "Enrutado", "Potato")
            print(f"Routed {task_id} to Potato Worker.")
            
    except Exception as e:
        print(f"Critical error processing ticket: {e}")
        traceback.print_exc()
        try:
            if 'task_id' in locals():
                send_webhook(task_id, "Error")
        except:
            pass
