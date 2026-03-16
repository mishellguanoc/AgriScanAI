import kagglehub
import os
import random
import shutil
from collections import defaultdict

# Descargar dataset
path = kagglehub.dataset_download("emmarex/plantdisease")

print("Dataset descargado en:", path)

# Ruta correcta
dataset_path = os.path.join(path, "PlantVillage", "PlantVillage")

# Carpeta de salida
output_dir = "plants_only_sample"
os.makedirs(output_dir, exist_ok=True)

plants = defaultdict(list)

# Recorrer carpetas
for folder in os.listdir(dataset_path):

    folder_path = os.path.join(dataset_path, folder)

    # asegurarse que sea carpeta
    if not os.path.isdir(folder_path):
        continue

    # nombre de la planta (antes de ___)
    plant_name = folder.split("___")[0]

    for file in os.listdir(folder_path):

        img_path = os.path.join(folder_path, file)

        # asegurarse que sea archivo (imagen)
        if os.path.isfile(img_path):
            plants[plant_name].append(img_path)

# seleccionar 10 imágenes por planta
for plant, images in plants.items():

    selected = random.sample(images, min(10, len(images)))

    plant_dir = os.path.join(output_dir, plant)
    os.makedirs(plant_dir, exist_ok=True)

    for img in selected:
        filename = os.path.basename(img)
        shutil.copy(img, os.path.join(plant_dir, filename))

print("Proceso terminado")