from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ARRAY, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
import time

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/motorcycle_stay_agent")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Database Models
class Destination(Base):
    __tablename__ = "destinations"
    
    id = Column(String, primary_key=True, index=True)  # Will be generated from lat+long
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    long = Column(Float, nullable=False)
    image_urls = Column(ARRAY(String), default=[])  # List of image URLs
    created_at = Column(BigInteger, default=lambda: int(time.time() * 1000))
    
    @staticmethod
    def generate_id(lat: float, long: float) -> str:
        """Generate ID from latitude and longitude coordinates"""
        # Round to 6 decimal places (about 1 meter precision)
        lat_rounded = round(lat, 6)
        long_rounded = round(long, 6)
        return f"{lat_rounded}_{long_rounded}"

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine) 