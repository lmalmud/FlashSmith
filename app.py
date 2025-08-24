'''
app.py
'''

import os, json, csv, io
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError
from openai import AzureOpenAI  # Azure OpenAI client in OpenAI SDK

# --- Config ---
load_dotenv()
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")  # your deployment name

client = AzureOpenAI(
    azure_endpoint=AOAI_ENDPOINT,
    api_key=AOAI_KEY,
    api_version=AOAI_API_VERSION
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Schemas ---
class Flashcard(BaseModel):
    type: str = Field(description="qna or cloze")
    question: str
    answer: str
    tags: List[str] = []

class Practice(BaseModel):
    type: str = Field(description="short or mcq")
    prompt: str
    solution: str
    choices: Optional[List[str]] = None
    difficulty: str = "easy"

class GenResult(BaseModel):
    flashcards: List[Flashcard]
    practice: List[Practice]

SYSTEM_PROMPT = (
    "You are an expert study buddy. Given raw notes, produce STRICT JSON only, "
    "matching this schema:\n"
    "{\n"
    '  "flashcards": [\n'
    '     {"type":"qna|cloze","question":"...","answer":"...","tags":["topic","subtopic"]}\n'
    "  ],\n"
    '  "practice": [\n'
    '     {"type":"short|mcq","prompt":"...","solution":"...","choices":["A","B","C","D"],"difficulty":"easy|med|hard"}\n'
    "  ]\n"
    "}\n"
    "Guidelines:\n"
    "- Prefer 8–12 flashcards; include at least 3 cloze deletions.\n"
    "- 4–6 practice items; at least 2 MCQ with plausible distractors.\n"
    "- Keep answers concise and factual; if a formula appears, include it.\n"
    "- Use tags (e.g., course/topic) for grouping.\n"
    "Return ONLY JSON per schema—no commentary."
)

USER_TEMPLATE = (
    "Course: {course}\nTopic: {topic}\n"
    "Notes:\n\"\"\"\n{notes}\n\"\"\"\n"
)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

class GenerateBody(BaseModel):
    notes: str
    course: Optional[str] = ""
    topic: Optional[str] = ""

@app.post("/api/generate")
def generate(body: GenerateBody):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(course=body.course, topic=body.topic, notes=body.notes)}
    ]
    # JSON mode: ask the model to return a single, valid JSON object
    resp = client.chat.completions.create(
        model=CHAT_DEPLOYMENT,             # your deployment name
        messages=messages,
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    raw = resp.choices[0].message.content
    try:
        data = json.loads(raw)
        result = GenResult(**data)
        return JSONResponse(result.model_dump())
    except (ValidationError, json.JSONDecodeError) as e:
        return JSONResponse({"error": f"Parse error: {str(e)}", "raw": raw}, status_code=500)

@app.post("/api/export/echo")
def export_echo(payload: GenResult, kind: str = "flashcards"):
    buf = io.StringIO()
    writer = csv.writer(buf)
    if kind == "flashcards":
        writer.writerow(["Type","Question","Answer","Tags"])
        for c in payload.flashcards:
            writer.writerow([c.type, c.question, c.answer, ";".join(c.tags)])
        content = buf.getvalue().encode()
        return StreamingResponse(io.BytesIO(content), media_type="text/csv",
                                 headers={"Content-Disposition":"attachment; filename=flashcards.csv"})
    elif kind == "practice":
        writer.writerow(["Type","Prompt","Solution","Choices","Difficulty"])
        for p in payload.practice:
            writer.writerow([p.type, p.prompt, p.solution, ";".join(p.choices or []), p.difficulty])
        content = buf.getvalue().encode()
        return StreamingResponse(io.BytesIO(content), media_type="text/csv",
                                 headers={"Content-Disposition":"attachment; filename=practice.csv"})
    else:
        return JSONResponse({"error": "Unknown kind"}, status_code=400)
