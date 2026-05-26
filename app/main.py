import os
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine, Base, get_db
from app.models.schemas import Application
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Directly import Member 3's drop-in evaluation module
from app.services.ai_engine import evaluate_candidate

app = FastAPI(title="Automated Hiring System API Pipeline")

# Setup a local folder to store incoming resume PDFs temporarily
UPLOAD_DIR = "uploaded_resumes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Enable CORS so Member 1's React application can talk to your server securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Comment out or delete these lines so your data is saved long-term:
        # await conn.execute(text("DROP TABLE IF EXISTS applications CASCADE;"))
        # await conn.execute(text("DROP TABLE IF EXISTS jobs CASCADE;"))
        # await conn.execute(text("DROP TABLE IF EXISTS companies CASCADE;"))
        
        # Keep this line so it safely updates missing tables without deleting data:
        await conn.run_sync(Base.metadata.create_all)
    print("[*] Database pipeline synchronized successfully!")

@app.post("/api/v1/apply")
async def process_new_application(
    job_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    github_url: str = Form(""),
    custom_answers: str = Form(""),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Save the incoming uploaded PDF file from Member 1's frontend to local disk
        file_location = os.path.join(UPLOAD_DIR, resume.filename)
        with open(file_location, "wb") as f:
            f.write(await resume.read())

        # Pass the saved PDF path right into Member 3's AI evaluation script
        ai_result = evaluate_candidate(
            pdf_path=file_location, 
            github_url=github_url, 
            custom_answers=custom_answers
        )

        # Create a persistent database row utilizing your SQLAlchemy Application model
        new_application = Application(
            job_id=job_id,
            full_name=full_name,
            email=email,
            resume_path=file_location,
            ai_score=ai_result.score,       
            ai_reasoning=ai_result.reason   
        )

        # Commit records permanently to your PostgreSQL database
        db.add(new_application)
        await db.commit()
        await db.refresh(new_application)

        # Return a clean JSON response back to Member 1's React UI
        return {
            "status": "success",
            "message": "Candidate application processed and graded successfully!",
            "id": new_application.id,
            "evaluation": {
                "score": ai_result.score,
                "status": ai_result.status,
                "reason": ai_result.reason,
                "matched_skills": ai_result.matched_skills,
                "missing_skills": ai_result.missing_skills,
                "flight_risk": ai_result.flight_risk
            }
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Pipeline integration error: {str(e)}")