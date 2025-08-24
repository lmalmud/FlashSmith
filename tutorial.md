# FlashSmith (Azure OpenAI Chat) — Paste Notes → Flashcards & Practice

Build a tiny **one-page FastAPI app** that takes textbook notes and generates:
- **Flashcards** (Q↔A + cloze deletions)
- **Extra practice** (short-answer & MCQ)
- **CSV export** for Anki/Quizlet

This version uses **Azure OpenAI Chat Completions** with your **`gpt-35-turbo`** deployment (students typically have access to chat models). It relies on the official **OpenAI Python SDK** with the `AzureOpenAI` client.

---

## 0) Prereqs (5 min)

**You do**
1. Ensure you have an **Azure for Students** subscription.
2. In **Azure AI Foundry** (ai.azure.com), create a **Project** (if you don’t have one), then deploy **`gpt-35-turbo`** under **Model catalog → Use model → Deploy (Azure OpenAI)**.
3. In **Models + endpoints → your deployment → Get keys**, copy your:
   - **Endpoint**: `https://<your-resource-name>.openai.azure.com/`
   - **API key**
   - **Deployment name** (e.g., `gpt35`)

**Why**
- We’ll call the **Azure OpenAI Chat Completions API** using your **deployment name** and **endpoint**.

---

## 1) Scaffold your app (2 min)

```bash
mkdir flashsmith && cd flashsmith
mkdir -p static templates
touch app.py requirements.txt .env.example static/app.js static/styles.css templates/index.html
```

Project layout:
```
flashsmith/
  app.py
  requirements.txt
  .env.example
  static/
    app.js
    styles.css
  templates/
    index.html
```

---

## 2) Install dependencies (2 min)

```bash
python -m venv .venv && source .venv/bin/activate
```
This line is two commands (separated by &&). The first one creates a viftual environment named ```.venv``` to isolate the project's dependencies from the global Python isntallation. The second command activates the virtual environment so that the following Python and pip commands operate within it. Note you'll have to activate your virtual environment every time you start up. For windows, this is: ```py -m venv .venv && .venv\Scripts\activate```

```bash
pip install -U pip
```
This updates pip (Python's pacakges installer) to the most recent version.

```bash
pip install fastapi uvicorn azure-ai-inference python-dotenv pydantic jinja2
```
This istalls the necessary pacages for this prokect
- **Fast API**: a web framework for building APIs
- **Uvicorn:** high-performance ASGI server to run FastAPI app
- **Azure AI Inference**: to call your serverless endpoint. This is how we interact with the serverless models.

---

## 3) Environment variables (1 min)

Create `.env.example`:

```bash
cat > .env.example << 'EOF'
AZURE_OPENAI_ENDPOINT=https://<your-resource-name>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-azure-openai-key>
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_CHAT_DEPLOYMENT=<your-deployment-name>  # e.g., gpt35
EOF
```

Copy to `.env` and fill in the values.

> **Note**: `2024-10-21` is the latest GA API version. You can also use `2024-06-01` if needed.

---

## 4) Backend (FastAPI) — paste this into `app.py` (8–10 min)

This uses **JSON mode** so the model returns a valid JSON object directly (no regex scraping).

```python
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
```

---

## 5) Minimal UI

**`templates/index.html`**
```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>FlashSmith (Azure OpenAI)</title>
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body>
  <main>
    <h1>FlashSmith</h1>
    <form id="gen-form">
      <input id="course" placeholder="Course (optional)" />
      <input id="topic" placeholder="Topic (optional)" />
      <textarea id="notes" placeholder="Paste notes here..." rows="12"></textarea>
      <button type="submit">Generate</button>
    </form>

    <section id="results" hidden>
      <h2>Flashcards</h2>
      <div id="cards"></div>
      <button id="dl-cards">Download Flashcards CSV</button>

      <h2>Practice</h2>
      <div id="practice"></div>
      <button id="dl-practice">Download Practice CSV</button>
    </section>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
```

**`static/app.js`**
```javascript
const el = (id) => document.getElementById(id);
let lastPayload = null;

el("gen-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const notes = el("notes").value.trim();
  const course = el("course").value.trim();
  const topic = el("topic").value.trim();
  if (!notes) return;

  el("results").hidden = true;
  const r = await fetch("/api/generate", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ notes, course, topic })
  });
  const data = await r.json();
  if (data.error) { alert(data.error); return; }

  lastPayload = data;
  el("cards").innerHTML = data.flashcards.map(c =>
    `<details><summary><strong>${c.type.toUpperCase()}</strong> — ${c.question}</summary><p><em>${c.answer}</em><br><small>tags: ${c.tags.join(", ")}</small></p></details>`
  ).join("");

  el("practice").innerHTML = data.practice.map(p =>
    `<details><summary><strong>${p.type.toUpperCase()}</strong> — ${p.prompt}</summary><p><em>${p.solution}</em>${p.choices?.length ? "<br>Choices: " + p.choices.join(", ") : ""}<br><small>${p.difficulty}</small></p></details>`
  ).join("");

  el("results").hidden = false;
});

async function download(kind) {
  if (!lastPayload) return;
  const r = await fetch(`/api/export/echo?kind=${encodeURIComponent(kind)}`, {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify(lastPayload)
  });
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${kind}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

el("dl-cards").onclick = () => download("flashcards");
el("dl-practice").onclick = () => download("practice");
```

**`static/styles.css`**
```css
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; }
main { max-width: 900px; margin: auto; }
textarea, input { width: 100%; margin: .5rem 0; padding: .6rem; }
button { padding: .6rem 1rem; }
details { border: 1px solid #ddd; border-radius: 8px; margin: .5rem 0; padding: .4rem .8rem; }
```

---

## 6) Requirements

**`requirements.txt`**
```
fastapi
uvicorn
openai
python-dotenv
pydantic
jinja2
```

---

## 7) Run locally (2 min)

```bash
# macOS/Linux
export $(grep -v '^#' .env | xargs)
uvicorn app:app --reload --port 8000
# open http://localhost:8000
```

> If your notes are very long, split them into sections or add token counting/truncation. `gpt-35-turbo` deployments commonly use 4k or 16k context depending on the specific version you deploy.

---

## 8) Deploy (optional)

- Push to **GitHub** and deploy to **Azure App Service (Linux, Python)**.
- In the App Service → **Configuration**, add your 4 env vars: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_CHAT_DEPLOYMENT`.
- Start with a simple startup command like: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker app:app`.

---

## Troubleshooting

- **401/403**: Ensure your **endpoint** ends with `.openai.azure.com/`, your **API key** is correct, and the **deployment name** you pass in `model=` matches your Azure OpenAI deployment.
- **429 (rate limit)**: Reduce request rate or request higher quotas in the portal.
- **JSON parsing error**: Keep `response_format={"type": "json_object"}` and ensure the system prompt clearly says “Return ONLY JSON”. Retry with smaller temperature (0.1–0.2).

---

## References

- **Chat completions how-to (Azure OpenAI)**: https://learn.microsoft.com/azure/ai-foundry/openai/how-to/chatgpt  
- **Chat completions quickstart**: https://learn.microsoft.com/azure/ai-foundry/openai/chatgpt-quickstart  
- **JSON mode (Azure OpenAI)**: https://learn.microsoft.com/azure/ai-foundry/openai/how-to/json-mode  
- **Structured outputs / JSON mode availability**: https://learn.microsoft.com/azure/ai-foundry/openai/how-to/structured-outputs  
- **API version lifecycle (latest GA 2024-10-21)**: https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle  
- **Quotas & limits**: https://learn.microsoft.com/azure/ai-foundry/openai/quotas-limits

---

### You’re done!
Paste, run, then ship. Record a 15‑sec screen capture for your README (paste notes → generate → download CSV) and you’ve got a sharp portfolio demo.
