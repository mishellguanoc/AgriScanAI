import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import pandas as pd

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
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
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
