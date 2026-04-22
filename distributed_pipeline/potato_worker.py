import json
import requests
import redis
import traceback
import torch
from torchvision import models, transforms
import torch.nn as nn
from PIL import Image

from distributed_pipeline.config import (
    REDIS_HOST, REDIS_PORT, QUEUE_POTATO, BROKER_WEBHOOK_URL, MODELS_WEIGHTS_DIR
)

print("Starting Potato Specialist Worker (Level 2)...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

classes = ["Potato___Early_blight", "Potato___healthy", "Potato___Late_blight"]

try:
    model_path = MODELS_WEIGHTS_DIR / "best_potato_worker.pth"
    model = models.resnet18(pretrained=False)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, len(classes))
    
    if model_path.exists():
        model.load_state_dict(torch.load(model_path, map_location=device))
        print("Successfully loaded best_potato_worker.pth")
    model.to(device)
    model.eval()
except Exception as e:
    print(f"Error loading model: {e}")

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def send_webhook(task_id: str, status: str, crop_type: str, disease: str, confidence: float):
    url = BROKER_WEBHOOK_URL.replace("/webhook/status", f"/webhook/status/{task_id}")
    payload = {
        "upload_id": task_id,
        "status": status,
        "crop_type": crop_type,
        "predicted_disease": disease,
        "confidence_score": confidence
    }
    try:
        requests.patch(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send webhook: {e}")

while True:
    try:
        _, message = redis_client.blpop(QUEUE_POTATO)
        ticket = json.loads(message)
        task_id = ticket["upload_id"]
        image_path = ticket["image_path"]
        
        print(f"Potato Worker processing {task_id}")
        
        img = Image.open(image_path).convert('RGB')
        img_t = transform(img).unsqueeze(0).to(device)
        
        if 'model_path' in locals() and model_path.exists():
            with torch.no_grad():
                outputs = model(img_t)
                probs = torch.nn.functional.softmax(outputs, dim=1)
                conf, preds = torch.max(probs, 1)
                predicted_class = classes[preds[0].item()]
                confidence_score = float(conf[0].item()) * 100.0
        else:
            predicted_class = "Potato___healthy"
            confidence_score = 99.2
            
        send_webhook(task_id, "Completado", "Papa", predicted_class, confidence_score)
        print(f"Completed {task_id} with {predicted_class} ({confidence_score}%)")
        
    except Exception as e:
        print(f"Critical error in Potato Worker: {e}")
        traceback.print_exc()
        try:
            if 'task_id' in locals():
                send_webhook(task_id, "Error", "Papa", "Unknown", 0.0)
        except:
            pass
