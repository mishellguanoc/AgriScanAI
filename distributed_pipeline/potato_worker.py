import json
import redis
import traceback
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

from distributed_pipeline.config import (
    REDIS_HOST, REDIS_PORT, QUEUE_POTATO, MODELS_WEIGHTS_DIR
)
from distributed_pipeline.worker_utils import send_webhook

print("Starting Potato Specialist Worker (Level 2)...")

# ── Disease model preprocessing (same as training notebook) ─────────────
inference_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# ── Disease model ───────────────────────────────────────────────────────
NUM_CLASSES = 3
MODEL_PATH = MODELS_WEIGHTS_DIR / "best_potato_worker.pth"
CLASS_NAMES = [
    'Potato___Early_blight',
    'Potato___Late_blight',
    'Potato___healthy'
]

try:
    model = models.resnet18(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(0.5),
        nn.Linear(num_ftrs, NUM_CLASSES)
    )
    if MODEL_PATH.exists():
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu'), weights_only=True))
        print("Successfully loaded best_potato_worker.pth")
    else:
        print(f"Warning: Model not found at {MODEL_PATH}")
    model.eval()
except Exception as e:
    print(f"Error loading disease model: {e}")
    traceback.print_exc()

# ── Crop-type classifier for cross-validation ───────────────────────────
CROP_MODEL_PATH = MODELS_WEIGHTS_DIR / "agriscan_model.pth"
CROP_CLASS_NAMES = ['Background', 'Potato', 'Tomato']
EXPECTED_CROP = "Potato"

crop_transforms = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

crop_model = None
try:
    crop_model = models.resnet18(weights=None)
    crop_model.fc = nn.Linear(crop_model.fc.in_features, len(CROP_CLASS_NAMES))
    if CROP_MODEL_PATH.exists():
        crop_model.load_state_dict(torch.load(CROP_MODEL_PATH, map_location=torch.device('cpu')))
        print("Successfully loaded crop classifier (agriscan_model.pth) for cross-validation")
    else:
        print(f"Warning: Crop classifier not found at {CROP_MODEL_PATH}")
        crop_model = None
    if crop_model:
        crop_model.eval()
except Exception as e:
    print(f"Warning: Could not load crop classifier for cross-validation: {e}")
    crop_model = None

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)



print("Potato Worker is waiting for tasks...")
while True:
    try:
        _, message = redis_client.blpop(QUEUE_POTATO)
        ticket = json.loads(message)
        
        task_id = ticket["upload_id"]
        image_path = ticket["image_path"]
        
        print(f"Processing ticket {task_id}")
        
        img = Image.open(image_path).convert('RGB')

        # ── Cross-validation: check if ticket came through router or directly ──
        was_routed = ticket.get("crop_type") is not None
        crop_verified = True
        crop_prediction = ticket.get("crop_type", EXPECTED_CROP)

        if not was_routed and crop_model is not None:
            # Direct submission — run crop classifier for cross-validation
            img_crop = crop_transforms(img).unsqueeze(0)
            with torch.no_grad():
                crop_outputs = crop_model(img_crop)
                crop_probs = torch.nn.functional.softmax(crop_outputs, dim=1)
                crop_conf, crop_pred = torch.max(crop_probs, 1)
                crop_prediction = CROP_CLASS_NAMES[crop_pred[0].item()]

            if crop_prediction == "Background":
                send_webhook(
                    task_id, "Desechado/Background", "Background",
                    crop_type_verified=False,
                    router_crop_prediction=crop_prediction,
                )
                print(f"Discarded {task_id} as background (crop classifier cross-validation).")
                continue

            crop_verified = (crop_prediction == EXPECTED_CROP)
            print(f"Crop cross-validation: predicted={crop_prediction}, expected={EXPECTED_CROP}, verified={crop_verified}")

        # ── Disease inference (always runs, even if incoherent) ─────────────
        img_t = inference_transforms(img).unsqueeze(0)
        
        with torch.no_grad():
            outputs = model(img_t)
            probs = torch.nn.functional.softmax(outputs, dim=1)
            conf, preds = torch.max(probs, 1)
            predicted_class = CLASS_NAMES[preds[0].item()]
            confidence = float(conf[0].item())
            
        print(f"Potato prediction: {predicted_class} ({confidence*100:.2f}%) | verified={crop_verified} | crop_pred={crop_prediction}")
        send_webhook(
            task_id, "Completado", EXPECTED_CROP, predicted_class, confidence,
            crop_type_verified=crop_verified,
            router_crop_prediction=crop_prediction,
        )
            
    except Exception as e:
        print(f"Critical error processing ticket: {e}")
        traceback.print_exc()
        try:
            if 'task_id' in locals():
                send_webhook(task_id, "Error")
        except:
            pass
