import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from typing import List

# 1. Force Python to read the .env file FIRST
load_dotenv()

# 2. Grab the key safely and give it to the client
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

class Message(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class InterviewResult(BaseModel):
    final_score: int
    decision: str           # "upgrade" | "downgrade" | "hold"
    new_status: str         # "selected" | "manual_review" | "rejected"
    dimension_scores: dict  # {"technical_depth": 88, ...}
    summary: str

SYSTEM_PROMPT = """You are a senior technical interviewer conducting a focused 3-question screen.
The candidate is borderline — scored 80-84 on resume review.
Your job is to ask progressively deeper questions about the specific role they applied for.
After the 3rd answer, respond ONLY with a JSON object:
{
  "final_score": <int 0-100>,
  "decision": <"upgrade"|"downgrade"|"hold">,
  "new_status": <"selected"|"manual_review"|"rejected">,
  "dimension_scores": {
    "technical_depth": <int>,
    "communication": <int>,
    "architecture_sense": <int>,
    "problem_solving": <int>
  },
  "summary": "<2-sentence reasoning>"
}
Until then, ask ONE follow-up question at a time. Be direct and technical.
"""

def run_interview_turn(
    job_title: str,
    job_description: str,
    conversation: List[Message]
) -> str:
    """
    Process one turn of the AI interview. Returns the AI's next question,
    or a JSON result block after 3 candidate answers.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\nRole: {job_title}\nJD: {job_description}"}
    ]
    for msg in conversation:
        messages.append({"role": msg.role, "content": msg.content})

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=500,
    )
    return completion.choices[0].message.content

def parse_final_result(raw: str) -> InterviewResult | None:
    """Try to parse a final JSON result if the interview is complete."""
    try:
        data = json.loads(raw)
        return InterviewResult(**data)
    except Exception:
        return None
