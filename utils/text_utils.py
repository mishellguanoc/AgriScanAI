def format_label(label: str) -> str:
    """
    Translates raw model labels into human-readable English names.
    
    Examples:
    'Tomato_Bacterial_spot' -> 'Tomato Bacterial Spot'
    'Potato___Early_blight' -> 'Potato Early Blight'
    """
    if not label:
        return "Unknown"
    
    # Predefined map for specific known labels
    label_map = {
        'Tomato_Bacterial_spot': 'Tomato Bacterial Spot',
        'Tomato_Early_blight': 'Tomato Early Blight',
        'Tomato_Late_blight': 'Tomato Late Blight',
        'Tomato_Leaf_Mold': 'Tomato Leaf Mold',
        'Tomato_Septoria_leaf_spot': 'Tomato Septoria Leaf Spot',
        'Tomato_Spider_mites_Two_spotted_spider_mite': 'Tomato Spider Mites',
        'Tomato__Target_Spot': 'Tomato Target Spot',
        'Tomato__Tomato_YellowLeaf__Curl_Virus': 'Tomato Yellow Leaf Curl Virus',
        'Tomato__Tomato_mosaic_virus': 'Tomato Mosaic Virus',
        'Tomato_healthy': 'Tomato Healthy',
        'Potato___Early_blight': 'Potato Early Blight',
        'Potato___Late_blight': 'Potato Late Blight',
        'Potato___healthy': 'Potato Healthy',
        'Background': 'Background',
        'Potato': 'Potato',
        'Tomato': 'Tomato'
    }
    
    if label in label_map:
        return label_map[label]
    
    # Fallback: clean up underscores and capitalize
    cleaned = label.replace('___', ' ').replace('__', ' ').replace('_', ' ')
    return " ".join(word for word in cleaned.split() if word).title()

def translate_status(status: str) -> str:
    """
    Translates internal Spanish statuses to English for UI display.
    """
    status_map = {
        "Solicitado": "Requested",
        "Enrutado": "Routed",
        "Completado": "Completed",
        "Desechado": "Discarded",
        "Desechado/Background": "Discarded (Background)",
        "Error": "Error"
    }
    return status_map.get(status, status)
