import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import pandas as pd
import uuid
from datetime import datetime

Base = declarative_base()

class FileUpload(Base):
    __tablename__ = 'file_upload'
    upload_id = Column(UUID(as_uuid=True), primary_key=True)
    received_timestamp = Column(DateTime(timezone=True))
    
    geospatial = relationship("GeospatialData", back_populates="upload", uselist=False)
    diagnosis = relationship("DiagnosisResult", back_populates="upload", uselist=False)

class GeospatialData(Base):
    __tablename__ = 'geospatial_data'
    upload_id = Column(UUID(as_uuid=True), ForeignKey('file_upload.upload_id'), primary_key=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    elevation = Column(Float)
    captured_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    upload = relationship("FileUpload", back_populates="geospatial")

class DiagnosisResult(Base):
    __tablename__ = 'diagnosis_result'
    upload_id = Column(UUID(as_uuid=True), ForeignKey('file_upload.upload_id'), primary_key=True)
    crop_type = Column(String(50), nullable=False)
    predicted_disease = Column(String(100), nullable=False)
    confidence_score = Column(Float, nullable=False)
    area_m2 = Column(Integer)
    severity = Column(Float)
    
    upload = relationship("FileUpload", back_populates="diagnosis")

def get_engine():
    try:
        db_url = st.secrets["SUPABASE_DB_URL"]
        return create_engine(db_url)
    except KeyError:
        st.error("Supabase Database URL not found in .streamlit/secrets.toml")
        return None

@st.cache_data
def fetch_all_records():
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        # Complex Join logic to fetch unified data for the map
        query = """
            SELECT 
                d.crop_type as plant,
                d.predicted_disease as disease,
                d.area_m2,
                d.severity,
                g.latitude as lat,
                g.longitude as lon,
                g.captured_timestamp::date as date
            FROM file_upload f
            JOIN geospatial_data g ON f.upload_id = g.upload_id
            JOIN diagnosis_result d ON f.upload_id = d.upload_id
        """
        df = pd.read_sql(query, engine)
        
        # Ensure date is in proper format for filtering
        df['date'] = pd.to_datetime(df['date']).dt.date
        return df
    except Exception as e:
        st.error(f"Error fetching joined data from Supabase: {e}")
        return pd.DataFrame()

def save_diagnosis_to_db(plant, disease, confidence, lat, lon, captured_dt, area_m2=0, severity=0.0):
    # saves normalized data to supabase
    # performs a single transaction across file_upload, geospatial_data, and diagnosis_result.
    
    engine = get_engine()
    if engine is None:
        return False
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        new_id = uuid.uuid4()
        
        # file_upload
        upload = FileUpload(
            upload_id=new_id,
            received_timestamp=datetime.now()
        )
        session.add(upload)
        
        # geospatial_data
        geo = GeospatialData(
            upload_id=new_id,
            latitude=lat, 
            longitude=lon,
            elevation=0.0,
            captured_timestamp=captured_dt or datetime.now()
        )
        session.add(geo)
        
        # 3. Detail: diagnosis_result
        diag = DiagnosisResult(
            upload_id=new_id,
            crop_type=plant,
            predicted_disease=disease,
            confidence_score=confidence,
            area_m2=area_m2,
            severity=severity
        )
        session.add(diag)
        
        session.commit()
        
        # CRITICAL: Clear cache so the map updates instantly on next tab switch
        st.cache_data.clear()
        return True
        
    except Exception as e:
        session.rollback()
        st.error(f"Database Save Error: {e}")
        return False
    finally:
        session.close()
