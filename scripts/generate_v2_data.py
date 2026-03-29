import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uuid
import os

# Geographic Setup for Ecuador (15 Hubs)
HUBS = [
    # Sierra & Costa
    (-0.22, -78.51), # Quito/Pichincha
    (-1.24, -78.62), # Ambato/Tungurahua
    (-1.66, -78.65), # Riobamba/Chimborazo
    (-2.90, -79.00), # Cuenca/Azuay
    (-3.99, -79.20), # Loja
    (0.35, -78.11),  # Ibarra
    (-0.93, -78.61), # Latacunga/Cotopaxi
    (-1.02, -79.46), # Quevedo/Los Rios
    (-2.18, -79.80), # Guayaquil
    (-1.05, -80.30), # Portoviejo

    # Amazon / Oriente
    (-0.99, -77.81), # Tena/Napo
    (-1.49, -78.00), # Puyo/Pastaza
    (-2.30, -78.11), # Macas/Morona Santiago
    (0.08, -76.88),  # Nueva Loja/Sucumbios
    (-0.46, -76.98), # Coca/Orellana
]

def is_safe_location(lat, lon):
    # Boundary Clipper for Mainland Ecuador
    if not (-5.0 <= lat <= 1.4): return False
    if not (-81.2 <= lon <= -75.0): return False
    return True

def generate_v2_records(n=10000):
    data = []
    plants = ["Tomato", "Potato"]
    diseases = {
        "Tomato": ["Bacterial Spot", "Early Blight", "Late Blight", "Leaf Mold", "Septoria Leaf Spot", "Spider Mites", "Target Spot", "Yellow Leaf Curl Virus"],
        "Potato": ["Early Blight", "Late Blight", "Common Scab", "Black Scurf"]
    }
    
    start_date = datetime(2025, 3, 1)
    
    print(f"Generating {n} records...")
    
    count = 0
    while count < n:
        hub_lat, hub_lon = HUBS[np.random.randint(len(HUBS))]
        lat = np.random.normal(hub_lat, 0.15)
        lon = np.random.normal(hub_lon, 0.15)
        
        if is_safe_location(lat, lon):
            plant = np.random.choice(plants)
            disease = np.random.choice(diseases[plant])
            
            # Dates
            days_offset = np.random.randint(0, 390) # roughly 13 months
            captured_dt = start_date + timedelta(days=days_offset)
            # Add random time
            captured_dt = captured_dt + timedelta(hours=np.random.randint(0,23), minutes=np.random.randint(0,59))
            
            # received_timestamp is slightly after captured_dt (internet latency simulation)
            received_dt = captured_dt + timedelta(minutes=np.random.randint(5, 120))
            
            data.append({
                "upload_id": str(uuid.uuid4()),
                "received_timestamp": received_dt.isoformat(),
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "elevation": round(np.random.uniform(0, 3500), 2),
                "captured_timestamp": captured_dt.isoformat(),
                "crop_type": plant,
                "predicted_disease": disease,
                "confidence_score": round(np.random.uniform(0.75, 0.99), 4),
                "area_m2": np.random.randint(5, 5000),
                "severity": round(np.random.uniform(0.1, 1.0), 2)
            })
            count += 1
            if count % 2000 == 0:
                print(f"Generated {count}...")

    df = pd.DataFrame(data)
    output_path = "assets/epidemic_data_v2.csv"
    df.to_csv(output_path, index=False)
    print(f"Dataset V2 saved to {output_path}")

if __name__ == "__main__":
    generate_v2_records(10000)
