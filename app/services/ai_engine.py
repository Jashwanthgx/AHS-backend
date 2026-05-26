import os
import re
import spacy
import pdfplumber
import json
from pydantic import BaseModel, Field
from openai import OpenAI, AuthenticationError, OpenAIError
from fpdf import FPDF
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# -------------------------------------------------------------------
# Module C: The Grader (Schema Definition)
# -------------------------------------------------------------------
class EvaluationResult(BaseModel):
    """
    Defines the exact JSON structure we want OpenAI to return.
    """
    score: int = Field(description="Integer score from 0 to 100 based on fit.")
    status: str = Field(description="Must be 'selected', 'manual_review', or 'rejected'.")
    reason: str = Field(description="A 2-sentence explanation for the decision.")
    matched_skills: list[str] = Field(description="List of skills from the JD found in the resume.")
    missing_skills: list[str] = Field(description="List of required skills missing from the resume.")
    flight_risk: bool = Field(default=False, description="True if the candidate seems overqualified or likely to leave quickly.")

# -------------------------------------------------------------------
# Core AI Engine Logic
# -------------------------------------------------------------------
class ATSEngine:
    def __init__(self):
        # We will attempt to initialize the OpenAI client here.
        # If the environment variable is missing, we catch it and set client to None
        try:
            self.client = OpenAI()
        except OpenAIError:
            self.client = None
            
        # Load spaCy NLP model for entity recognition
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise OSError("spaCy model 'en_core_web_sm' not found. Please run: python -m spacy download en_core_web_sm")

    def parse_pdf(self, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        extracted_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text + "\n"
        return extracted_text

    def sanitize_text(self, text: str) -> str:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        sanitized = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
        
        phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        sanitized = re.sub(phone_pattern, "[REDACTED_PHONE]", sanitized)
        
        doc = self.nlp(sanitized)
        entities = [(ent.start_char, ent.end_char) for ent in doc.ents if ent.label_ == "PERSON"]
        entities.sort(key=lambda x: x[0], reverse=True)
        
        for start, end in entities:
            sanitized = sanitized[:start] + "[REDACTED_NAME]" + sanitized[end:]
            
        return sanitized

    def grade_candidate(self, sanitized_text: str, job_description: str) -> EvaluationResult:
        prompt = f"""
        You are an expert Applicant Tracking System.
        Evaluate the candidate based purely on merit and how well they match the job description.
        
        Job Description:
        {job_description}
        
        Sanitized Resume:
        {sanitized_text}
        """
        
        try:
            if self.client is None:
                raise OpenAIError("OpenAI API Key is missing. Client was not initialized.")
                
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional, unbiased hiring assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format=EvaluationResult,
            )
            return completion.choices[0].message.parsed
            
        except (AuthenticationError, OpenAIError) as e:
            print(f"\n[!] Warning: OpenAI API Key missing or invalid ({e}). Skipping live grading step.")
            return EvaluationResult(
                score=0,
                status="manual_review",
                reason="Provide OpenAI API key to view live evaluation.",
                matched_skills=[],
                missing_skills=[],
                flight_risk=False
            )

# -------------------------------------------------------------------
# Backend Drop-in Compatibility
# -------------------------------------------------------------------
def evaluate_candidate(pdf_path: str, github_url: str = "", custom_answers: str = "") -> EvaluationResult:
    """
    Wrapper function to act as a drop-in replacement for the FastAPI backend.
    """
    engine = ATSEngine()
    
    raw_text = engine.parse_pdf(pdf_path)
    clean_text = engine.sanitize_text(raw_text)
    
    # We append github and custom answers to the clean text for the AI to consider
    additional_context = ""
    if github_url:
        additional_context += f"\n\nCandidate GitHub URL: {github_url}"
    if custom_answers:
        additional_context += f"\n\nCandidate Custom Answers: {custom_answers}"
        
    final_text = clean_text + additional_context
    
    dummy_jd = """
    Job Title: Software Engineer
    Requirements:
    - Strong programming skills
    - Good communication and team collaboration
    - Relevant technical experience
    """
    
    return engine.grade_candidate(final_text, dummy_jd)

# -------------------------------------------------------------------
# Step 2: Generate the Test File
# -------------------------------------------------------------------
def generate_dummy_pdf(output_path: str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="John Doe", ln=1, align='C')
    pdf.set_font("Arial", size=11)
    pdf.cell(200, 10, txt="Email: john.doe@example.com | Phone: 555-123-4567 | GitHub: github.com/johndoe", ln=1, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Summary", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, txt="Passionate and detail-oriented Software Engineer with 4 years of experience building scalable backend services and dynamic frontend applications. Proven ability to lead projects from conception to deployment.")
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Skills", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.cell(200, 7, txt="- Languages/Frameworks: Python, JavaScript, React, FastAPI, SQL", ln=1)
    pdf.cell(200, 7, txt="- Tools/DevOps: Git, Docker, GitHub Actions, AWS", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Experience", ln=1)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(200, 7, txt="Backend Engineer | Tech Solutions Inc. | 2021 - Present", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, txt="- Designed and implemented a microservices architecture using Python and FastAPI.\n- Optimized SQL database queries, reducing average API response times by 40%.\n- Integrated automated CI/CD pipelines using Git and Docker.")
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Projects", ln=1)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(200, 7, txt="Hostel Management System", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, txt="A full-stack application for managing hostel room allocations and student records. Built with React and Python, utilizing SQL for robust data storage and Docker for containerized deployment.")
    pdf.ln(3)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(200, 7, txt="Multiplayer Web Game", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, txt="Developed a real-time interactive game using WebSockets and JavaScript. Handled complex state synchronization across multiple client instances.")
    pdf.output(output_path)

# -------------------------------------------------------------------
# Step 3: Execute the Test
# -------------------------------------------------------------------
if __name__ == "__main__":
    dummy_pdf = "dummy_resume.pdf"
    print("[*] Generating dummy_resume.pdf with realistic data...")
    generate_dummy_pdf(dummy_pdf)
    
    try:
        print("[*] Parsing & Grading candidate...")
        result_obj = evaluate_candidate(dummy_pdf, github_url="github.com/johndoe", custom_answers="I am a quick learner.")
        print("\n=== FINAL OUTPUT ===")
        print(result_obj.model_dump_json(indent=2))
        print("=========================\n")
    except Exception as e:
        print(f"\n[!] An unexpected error occurred during execution: {e}")
