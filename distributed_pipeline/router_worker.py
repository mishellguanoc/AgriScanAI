import json
import requests
import redis
import traceback
import torch
from torchvision import models, transforms
import torch.nn as nn
from PIL import Image
from pathlib import Path

from distributed_pipeline.config import (
    REDIS_HOST, REDIS_PORT, QUEUE_ROUTER, QUEUE_TOMATO, QUEUE_POTATO, 
    BROKER_WEBHOOK_URL, MODELS_WEIGHTS_DIR
)

# 1. Configuration & Model Loading
print("Starting Router Worker (Level 1)...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Simple transforms (adjust to your actual model's expected input)
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

classes = ["Background", "Papa", "Tomate"]

try:
    model_path = MODELS_WEIGHTS_DIR / "agriscan_model.pth"
    # Provide a generic ResNet18 model shape to load the weights 
    # (Update this if your actual architecture is different)
    model = models.resnet18(pretrained=False)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, len(classes))
    
    if model_path.exists():
        model.load_state_dict(torch.load(model_path, map_location=device))
        print("Successfully loaded agriscan_model.pth")
    else:
        print(f"Warning: Model not found at {model_path}. Will yield mock predictions.")
        
    model.to(device)
    model.eval()
except Exception as e:
    print(f"Error loading model: {e}")

# 2. Redis Connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def send_webhook(task_id: str, status: str, crop_type: str = None):
    url = BROKER_WEBHOOK_URL.replace("/webhook/status", f"/webhook/status/{task_id}")
    payload = {
        "upload_id": task_id,
        "status": status,
        "crop_type": crop_type
    }
    try:
        requests.patch(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send webhook to {url}: {e}")

# 3. Consumer Loop
print("Router Worker is waiting for tasks...")
while True:
    try:
        # Block until a ticket is available in router_q
        _, message = redis_client.blpop(QUEUE_ROUTER)
        ticket = json.loads(message)
        
        task_id = ticket["upload_id"]
        image_path = ticket["image_path"]
        
        print(f"Processing ticket {task_id}")
        send_webhook(task_id, "Procesando en Router")
        
        # Load image
        img = Image.open(image_path).convert('RGB')
        img_t = transform(img).unsqueeze(0).to(device)
        
        # Predict
        if 'model_path' in locals() and model_path.exists():
            with torch.no_grad():
                outputs = model(img_t)
                _, preds = torch.max(outputs, 1)
                predicted_class = classes[preds[0].item()]
        else:
            # Mock behavior if model strictly isn't there
            predicted_class = "Tomate"
            
        print(f"Prediction for {task_id}: {predicted_class}")
        
        if "Background" in predicted_class or predicted_class.lower() == "background":
            # Early exit webhook
            send_webhook(task_id, "Desechado")
            print(f"Dropped {task_id} as background.")
            
        elif "Tomate" in predicted_class or predicted_class.lower() == "tomate":
            # Pass to Tomato Queue
            ticket["crop_type"] = "Tomate"
            redis_client.rpush(QUEUE_TOMATO, json.dumps(ticket))
            send_webhook(task_id, "Enrutado", "Tomate")
            print(f"Routed {task_id} to Tomato Workers.")
            
        elif "Papa" in predicted_class or predicted_class.lower() == "papa":
            # Pass to Potato Queue
            ticket["crop_type"] = "Papa"
            redis_client.rpush(QUEUE_POTATO, json.dumps(ticket))
            send_webhook(task_id, "Enrutado", "Papa")
            print(f"Routed {task_id} to Potato Workers.")
            
    except Exception as e:
        print(f"Critical error processing ticket: {e}")
        traceback.print_exc()
        try:
            if 'task_id' in locals():
                send_webhook(task_id, "Error")
        except:
            pass
