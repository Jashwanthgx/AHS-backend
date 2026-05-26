from sqlalchemy import Column, String, Integer, ForeignKey, Text, JSON
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

class Applicant(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    resume_path = Column(String, nullable=True)  # Local storage path to the PDF
    ai_score = Column(Integer, nullable=True) # Calculated later by Member 3
    ai_reasoning = Column(Text, nullable=True)  # Calculated later by Member 3
    