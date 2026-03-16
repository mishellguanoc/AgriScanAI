import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
import streamlit as st

CLASS_NAMES = ['Background', 'Potato', 'Tomato']


@st.cache_resource
def load_model():

    model = models.resnet18(weights=None)

    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, len(CLASS_NAMES))

    model.load_state_dict(
        torch.load(
            "models_weights/agriscan_model.pth",
            map_location=torch.device('cpu')
        )
    )

    model.eval()

    return model


def preprocess_image(image):

    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(
            [0.485, 0.456, 0.406],
            [0.229, 0.224, 0.225]
        )
    ])

    return transform(image).unsqueeze(0)


def predict_crop(image):

    model = load_model()

    input_tensor = preprocess_image(image)

    with torch.no_grad():

        outputs = model(input_tensor)

        probs = torch.nn.functional.softmax(outputs, dim=1)

        confidence, predicted = torch.max(probs, 1)

        predicted_class = CLASS_NAMES[predicted.item()]
        confidence = confidence.item()

    return predicted_class, confidence