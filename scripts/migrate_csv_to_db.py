import pandas as pd
from sqlalchemy import create_engine
import sys
import os

# Add project root to path to import db_manager models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_manager import Base, FileUpload, GeospatialData, DiagnosisResult

def migrate_v2_data(csv_path, db_url):
    print(f"Reading V2 data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        print(f"Found {len(df)} records in CSV.")
        
        print("Connecting to Supabase...")
        engine = create_engine(db_url)
        
        # 1. Create tables if they don't exist
        print("Ensuring tables exist...")
        Base.metadata.create_all(engine)
        
        print("Preparing data for 3-table insertion...")
        
        # Table 1: file_upload
        df_upload = df[['upload_id', 'received_timestamp']].copy()
        
        # Table 2: geospatial_data
        df_geospatial = df[['upload_id', 'latitude', 'longitude', 'elevation', 'captured_timestamp']].copy()
        
        # Table 3: diagnosis_result
        df_diagnosis = df[['upload_id', 'crop_type', 'predicted_disease', 'confidence_score', 'area_m2', 'severity']].copy()
        
        print("Uploading to 'file_upload' (Master)...")
        df_upload.to_sql('file_upload', engine, if_exists='append', index=False, method='multi')
        
        print("Uploading to 'geospatial_data'...")
        df_geospatial.to_sql('geospatial_data', engine, if_exists='append', index=False, method='multi')
        
        print("Uploading to 'diagnosis_result'...")
        df_diagnosis.to_sql('diagnosis_result', engine, if_exists='append', index=False, method='multi')
        
        print("Migration V2 completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate V2 CSV data to Normalized Supabase Schema")
    parser.add_argument("--csv", default="assets/epidemic_data_v2.csv", help="Path to the source CSV file")
    parser.add_argument("--url", help="Supabase SQLAlchemy connection string")
    
    args = parser.parse_args()
    
    if not args.url:
        print("Error: Please provide your Supabase Database URL using --url")
        sys.exit(1)
        
    migrate_v2_data(args.csv, args.url)
