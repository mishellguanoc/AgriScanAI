"""
utils/db_core.py
Pure backend database layer — NO Streamlit dependencies.
This module is safe to import from FastAPI, workers, or any non-UI process.

The Streamlit-specific functions (fetch_all_records, save_diagnosis_to_db)
remain in db_manager.py which imports from here.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import os
from datetime import datetime
from utils.config import _get_secret

Base = declarative_base()


class FileUpload(Base):
    __tablename__ = 'file_upload'
    upload_id = Column(UUID(as_uuid=True), primary_key=True)
    received_timestamp = Column(DateTime(timezone=True))
    status = Column(String(50), nullable=True, default="Solicitado")
    image_path = Column(String(512), nullable=True)

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
    crop_type_verified = Column(Boolean, default=False)
    router_crop_prediction = Column(String(50), nullable=True)

    upload = relationship("FileUpload", back_populates="diagnosis")


def get_engine():
    """Returns a SQLAlchemy engine, preferring st.secrets over env vars."""
    db_url = _get_secret("SUPABASE_DB_URL")
    if db_url:
        return create_engine(db_url)
    return None


def create_initial_ticket(upload_id: uuid.UUID, lat: float, lon: float, captured_dt: datetime, image_path: str = None):
    """Creates the initial FileUpload and GeospatialData records when a job is submitted."""
    engine = get_engine()
    if not engine:
        return False
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        upload = FileUpload(
            upload_id=upload_id,
            received_timestamp=datetime.now(),
            status="Solicitado",
            image_path=image_path
        )
        session.add(upload)
        geo = GeospatialData(
            upload_id=upload_id,
            latitude=lat if lat is not None else None,
            longitude=lon if lon is not None else None,
            elevation=0.0,
            captured_timestamp=captured_dt if captured_dt is not None else datetime.now()
        )
        session.add(geo)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[db_core] Error creating ticket: {e}")
        return False
    finally:
        session.close()


def update_ticket_status(
    upload_id: uuid.UUID,
    status: str,
    plant: str = None,
    disease: str = None,
    confidence: float = None,
    area_m2: float = 0.0,
    severity: float = 0.0,
    crop_type_verified: bool = False,
    router_crop_prediction: str = None,
):
    """Updates status and creates DiagnosisResult when a worker completes."""
    engine = get_engine()
    if not engine:
        return False
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        upload = session.query(FileUpload).filter_by(upload_id=upload_id).first()
        if upload:
            upload.status = status

        if status in ("Completado", "Flagged_Incorrect") and plant and disease:
            diag = DiagnosisResult(
                upload_id=upload_id,
                crop_type=plant,
                predicted_disease=disease,
                confidence_score=confidence or 0.0,
                area_m2=area_m2,
                severity=severity,
                crop_type_verified=crop_type_verified,
                router_crop_prediction=router_crop_prediction,
            )
            session.add(diag)

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[db_core] Error updating ticket: {e}")
        return False
    finally:
        session.close()


def get_ticket_status(upload_id: uuid.UUID):
    """Retrieves the current status and diagnosis of a ticket."""
    engine = get_engine()
    if not engine:
        return {"status": "Error", "disease": None}
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        upload = session.query(FileUpload).filter_by(upload_id=upload_id).first()
        if not upload:
            return {"status": "Not_Found", "disease": None}

        result = {"status": upload.status, "disease": None, "confidence": None}
        diag = session.query(DiagnosisResult).filter_by(upload_id=upload_id).first()
        if diag:
            result["disease"] = diag.predicted_disease
            result["confidence"] = diag.confidence_score

        return result
    except Exception as e:
        return {"status": f"Error: {e}", "disease": None}
    finally:
        session.close()


def delete_ticket(upload_id: uuid.UUID):
    """Deletes FileUpload, GeospatialData, and any DiagnosisResult for the given upload_id.
    Used to clean up background/discarded images that should not persist in the DB."""
    engine = get_engine()
    if not engine:
        return False
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        if isinstance(upload_id, str):
            upload_id = uuid.UUID(upload_id)
        # Delete in correct order (foreign keys)
        session.query(DiagnosisResult).filter_by(upload_id=upload_id).delete()
        session.query(GeospatialData).filter_by(upload_id=upload_id).delete()
        session.query(FileUpload).filter_by(upload_id=upload_id).delete()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[db_core] Error deleting ticket: {e}")
        return False
    finally:
        session.close()


def update_map_fields(upload_id, area_m2: float, severity: float):
    """Updates the area and severity fields of an existing DiagnosisResult."""
    engine = get_engine()
    if not engine:
        return False
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        if isinstance(upload_id, str):
            upload_id = uuid.UUID(upload_id)
        diag = session.query(DiagnosisResult).filter_by(upload_id=upload_id).first()
        if diag:
            diag.area_m2 = area_m2
            diag.severity = severity
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"[db_core] Error updating map fields: {e}")
        return False
    finally:
        session.close()
