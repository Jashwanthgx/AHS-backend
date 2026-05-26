from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
import app.models.schemas  # This forces SQLAlchemy to recognize the models

app = FastAPI(title="AHS Backend API Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This lifespan hook handles database table generation at startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # This scans schemas.py and creates tables if they don't exist in PostgreSQL
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
def home():
    return {"status": "online", "message": "Database connected and API running!"}
