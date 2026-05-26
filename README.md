# Automated Hiring System (AHS) - Backend Engine

This repository houses the asynchronous FastAPI backend and machine learning evaluation services for the Automated Hiring System.

## 🛠️ Tech Stack & Dependencies
- **Core Framework:** Python 3.14 + FastAPI
- **Database Layer:** PostgreSQL + SQLAlchemy (AsyncPG dialect)
- **AI/NLP Frameworks:** OpenAI SDK (GPT-4o-mini) + spaCy (`en_core_web_sm`)
- **Utility Libraries:** `pdfplumber` (PDF parsing), `fpdf2` (Document building), `langdetect` (EEOC tracking)

---

## 📁 Repository Directory Layout

```text
AHS-backend/
├── app/
│   ├── api/             # Integration Gateway Endpoints
│   ├── core/            # App security rules and internal middleware
│   ├── models/          # SQLAlchemy Database Schemas (Physical Tables)
│   ├── schemas/         # Pydantic Request Validation Models
│   └── services/        # Core Execution Sub-Systems (AI & Analytics)
│       ├── ai_engine.py          # Resume Parser & PII Sanitizer (Member 3)
│       ├── github_reputation.py  # Asynchronous Git Profile Scraper (Member 3)
│       ├── bias_audit.py         # EEOC Disparate Impact Metrics (Member 3)
│       └── interview_agent.py    # Borderline LLM Conversational Screener (Member 3)
├── venv/                # Isolated Virtual Python Interpreter Environment
├── .env                 # Protected Environment Variable Store (Hidden Locally)
├── .gitignore           # Explicit Git System Exclusions Track
└── requirements.txt     # Global Application Dependencies Index
