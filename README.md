# 🌱 AgriScan AI

### Distributed Agricultural Monitoring Platform

AgriScan AI is a **smart agricultural monitoring system** that combines **computer vision, machine learning, and geospatial analysis** to detect crop diseases and monitor epidemic outbreaks in agricultural regions.

The platform allows farmers, researchers, and agricultural technicians to **analyze crop images, identify diseases, and visualize outbreaks on a regional map**.

---

## 🚀 Features

### 🌿 Crop Image Analysis

* Upload or capture images of crop leaves.
* AI-powered classification using a trained **ResNet18 deep learning model**.
* Identifies:

  * Crop type
  * Plant diseases
  * Background detection
* Displays prediction confidence.

---

### 🤖 Agronomic Virtual Assistant

* Interactive assistant to answer agricultural questions.
* Provides recommendations about:

  * Crop diseases
  * Prevention methods
  * Treatments and best practices.

---

### 🗺️ Epidemiological Map

Interactive map for **monitoring crop disease outbreaks**.

Features include:

* 📍 Disease outbreak markers
* 🔥 Heatmap visualization of disease spread
* 🌾 Filters by crop type
* 🦠 Filters by disease type
* 📊 Affected area statistics
* 📥 Export data as CSV
* 📸 Export the map as JPG

---

## 🧠 AI Model

The platform integrates a **deep learning model based on ResNet18** trained to classify agricultural images.

**Classes detected**

* Background
* Potato
* Tomato

The model processes images using standard **ImageNet normalization and preprocessing pipelines**.

---

## 🛠️ Technologies Used

* Python
* Streamlit
* PyTorch
* TorchVision
* Folium
* Streamlit-Folium
* Selenium
* Pandas
* Pillow

---

## 📂 Project Structure

```
AgriScanProject
│
├── app.py
│
├── components
│   ├── header.py
│   ├── analysis.py
│   ├── assistant.py
│   └── map_view.py
│
├── models
│   └── crop_classifier.py
│
├── utils
│   └── map_export.py
│
├── assets
│   └── logo.png
│
├── models_weights
│   └── agriscan_model.pth
│
└── requirements.txt
```

---

## ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/mishellguanoc/AgriScanAI.git
cd AgriScanAI
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

---

## 📊 Example Workflow

1️⃣ Upload or capture an image of a crop leaf.
2️⃣ The AI model analyzes the image.
3️⃣ The system predicts the crop type or disease.
4️⃣ The map visualizes outbreaks in agricultural regions.

---

## 🌍 Applications

AgriScan AI can be used for:

* Precision agriculture
* Crop disease monitoring
* Agricultural research
* Smart farming systems
* Early detection of crop epidemics

---

## 👨‍💻 Authors

* **Mishell Guano**
* **Erick Olivo**
* **Jaher Herrera**

---

## 📜 License

This project is intended for **academic and research purposes**.
