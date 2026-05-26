from datetime import datetime  
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from app.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=True)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    custom_questions = Column(JSON, nullable=True) # To dynamically feed Member 1's frontend form

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    resume_path = Column(String, nullable=False)
    ai_score = Column(Integer, default=0)
    ai_reasoning = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    