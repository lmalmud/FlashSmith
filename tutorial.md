# FlashSmith (Azure OpenAI Chat) — Paste Notes → Flashcards & Practice

Build a tiny **one-page FastAPI app** that takes textbook notes and generates:
- **Flashcards** (Q↔A + cloze deletions)
- **Extra practice** (short-answer & MCQ)
- **CSV export** for Anki/Quizlet

This version uses **Azure OpenAI Chat Completions** with your **`gpt-35-turbo`** deployment (students typically have access to chat models). It relies on the official **OpenAI Python SDK** with the `AzureOpenAI` client.

---

## 0) Prereqs (5 min)
1. Ensure you have an **Azure for Students** subscription.
2. In **Azure AI Foundry** (ai.azure.com), create a **Project** (if you don’t have one), then deploy **`gpt-35-turbo`** under **Model catalog → Use model → Deploy (Azure OpenAI)**.

If you run into bugs, you can chat with Copilot as available through your Azure portal. At some point, you also may need to use Azure Cloud Shell. [Here's how](https://learn.microsoft.com/en-us/azure/cloud-shell/get-started/classic?tabs=azurecli) to get started.

### Azure Glossary
* **Workspace:** A workspace is an organizational container in Azure that helps you group related resources together. It makes it easier to manage and monitor the services you use for a specific project or development environment.
  * You might create a workspace to organize all the resources related to your project (such as your OpenAI deployment, storage accounts, and databases). This keeps everything together and makes management easier.
* **Resource:** A resource is any individual service or component that you create in Azure (for example, an OpenAI deployment, a database, or a storage account). Each resource has settings, pricing, and access rules, and is typically managed within a resource group.
* **Web App:** A Web App is an Azure service provided by Azure App Service that lets you quickly deploy and host web applications. It handles the underlying infrastructure so you can focus on your code. Your FastAPI application in the tutorial is deployed as a Web App, which means it runs on Azure’s managed environment and automatically scales based on demand.
  * The Web App hosts your application, and it can interact with other resources like the Azure OpenAI deployment through connections established by environment variables and API calls. This means your FastAPI app (running in a Web App) can call the OpenAI service to generate flashcards and practice questions.
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
This line is two commands (separated by &&). The first one creates a viftual environment named ```.venv``` to isolate the project's dependencies from the global Python isntallation. The second command activates the virtual environment so that the following Python and pip commands operate within it. Note you'll have to activate your virtual environment every time you start up. For windows, this is: ```py -m venv .venv && .venv\Scripts\activate```.

```bash
pip install -U pip
```
This updates pip (Python's pacakges installer) to the most recent version.

```bash
pip install fastapi uvicorn openai python-dotenv pydantic jinja2
```
This istalls the necessary pacages for this prokect
- **Fast API**: a web framework for building APIs
- **Uvicorn:** high-performance ASGI server to run FastAPI app
- **openai:** official OpenAI Python SDK allows your project to interact with OpenAI's API, such as sending chat completion requests and handling responses.
- **python-dotenv:** package loads environment variables from a ```.env``` file into your Python process, making it easier to manage configuration like API keys and endpoints without hardcoding them.
- **pydantic:** used for data validation and settings management. It lets you define data models with type hints, ensuring that the data (e.g., API inputs/outputs) conforms to the expected structure.
- **jinja2:** a templating engine that helps generate dynamic HTML content by rendering templates with data, which is useful for building your project's web interface.

---

## 3) Environment variables (1 min)

### 1. Adding variables to the example *and actual* virtual environment
Create `.env.example` in the main directory:

```bash
cat > .venv.example << 'EOF'
AZURE_OPENAI_ENDPOINT=https://<your-resource-name>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-azure-openai-key>
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_CHAT_DEPLOYMENT=<your-deployment-name>  # e.g., gpt35
EOF
```

Copy to `.venv/.env` and fill in the values. You'll need to make the ```.env``` file.
* You can find ```AZURE_OPENAI_ENDPOINT``` by going to Overview $\rightarrow$ View all endpoints $\rightarrow$ gpt-35-turbo $\rightarrow$ Endpoint $\rightarrow$ Target URI. This is also where you'll find ```AZURE_OPENAI_API_KEY```.
* **What is a ```.env``` file?** It is a simple text file of $\text{key}=\text{value}$ pairs for secrets and config. Our code will call ```load_dotenv()``` so these values will get loaded into ```os.environ`` at runtime in local dev.

> **Note**: `2024-10-21` is the latest GA API version. You can also use `2024-06-01` if needed.

### 2. Add GitHub secrets
If you are using GitHub as a version control system (you should be), you do not want this information to be publically shared. Here's how:
1. Local development (never commit secrets)
  * Put real values in ```.venv``` on your machine, only put placeholders in ```.env.example```
  * Add a ```.gitignore``` entry so that ```.env``` is never tracked. Nagivate to your root directory and:
  ```bash
  touch .gitignore
  echo ".venv\n.venv.*" > .gitignore
  ```
  * The first commands makes a new file caleld ```.gitignore``` and the second line adds the directory names to be ignored to the file.
2. GitHub Actions (build/deploy) - use GitHub Secrets
* Store your values in Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions $\rightarrow$ New repository secret:
  * AZURE_OPENAI_ENDPOINT
  * AZURE_OPENAI_API_KEY
  * AZURE_OPENAI_API_VERSION
  * AZURE_OPENAI_CHAT_DEPLOYMENT
These values will be encrypted in your GitHub actions workflow later. You can reference them in the GitHub Actions ```.yaml``` files by ``` ${{ secrets.AZURE_CREDENTIALS_JSON }}```

### 3. App runtime on Azure App Service
In the [Azure portal](https://portal.azure.com/), we'll create the Web App that we'll later use (in the deploy step). To create the app, within the portal: Azure Portal $\rightarrow$ App Services $\rightarrow$ Create $\rightarrow$ Web App
* Publish: Code
* Runtime stack: Python 3.11
* OS: Linux
* Region: your choice
* Plan: a small plan is fine for a demo

Now, you can add your environment variables. App Services $\rightarrow$ your app $\rightarrow$ Settings $\rightarrow$ Environment variables $\rightarrow$ App settings $\rightarrow$ Add each key/value (same names as above). App Service injects them as environment variables; values are hidden in the portal UI. Restart after changes.

You'll deploy with the Deployment Center (by connecting to your GitHub repo) or can write your own GitHub Action.

---

## 4) Backend (FastAPI) (8–10 min)
Write all of the following blocks of code in `app.py`. This uses **JSON mode** so the model returns a valid JSON object directly (no regex scraping).

### a. Imports + Setup
This first block imports Python modules and libraries needed for configuration, FastAPI routing, file handling, environment variables, data models, and the OpenAI client.
* It loads built-in modules (like os, json, csv, io) and external libraries (FastAPI, pydantic, dotenv, etc.).
* It also imports the Azure-specific OpenAI client from the OpenAI SDK.
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
```


## b) Config
This section loads environment variables (using python-dotenv) and sets up the required configuration variables needed by the app:
* Reads the Azure endpoint, API key, API version, and deployment name from environment variables.
* Instantiates the AzureOpenAI client—this client is used later to send chat requests.
```python
load_dotenv() # Loads in variables from virtual environment

# Set variables locally
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT") # your deployment name
```

### c. FastAPI App Setup
Here you configure your FastAPI application:
* Creates a FastAPI app instance.
* Mounts the static files directory (for CSS/JavaScript).
* Sets up the Jinja2 templates directory. This helps render the frontend UI when a user accesses the base URL.
```python
client = AzureOpenAI(
    azure_endpoint=AOAI_ENDPOINT,
    api_key=AOAI_KEY,
    api_version=AOAI_API_VERSION
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
```

### d. Schema Definitions (Pydantic Models)
[Pydantic](https://docs.pydantic.dev/latest/) is the most widely used data validation and serialization library for Python. Originally built in Rust, Pydantic is one of the fastest data validation libraries for python. It supports many standard data types and is powered by annotations as to integrate seamlessly with the rest of your code.

In this section, three Pydantic models are defined:
* **Flashcard:** Represents a flashcard with type, question, answer, and tags.
* **Practice:** Represents a practice item (either short-answer or multiple-choice) with additional optional choices and difficulty level.
* **GenResult:** Aggregates flashcards and practice items into one response model.
These models ensure that the data your API creates or processes follows a strict schema.
```python
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
```

### e. Prompt Templates
This block sets up static strings that define how the model should behave:
* ```SYSTEM_PROMPT:``` Provides the instruction for generating JSON output strictly following the defined schema.
* ```USER_TEMPLATE:``` Formats user input by inserting course, topic, and notes into a predefined template. This section makes sure that, when the API is called, the right context is sent to the OpenAI model.
```python
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
```

### f. Route Definitions
Next, we define the API endpoints. API endpoints are specific URLs that serve as the point of interaction between an API client (like a user) and an API server (your hosted Azure usage).
* GET "/" Route
  * Renders the main HTML template (index.html) using Jinja2 when the user accesses the root URL.
* POST "/api/generate" Route
  * Accepts user notes (and optional course/topic).
  * Formats a list of messages (system and user) to pass to the OpenAI API.
  * Calls the Azure OpenAI Chat API using the preconfigured client.
  * Parses the returned JSON into the GenResult schema and sends the JSON response back to the client.
  * Handles errors if the JSON returned by the API cannot be parsed or validated.
* POST "/api/export/echo" Route
  * Accepts a GenResult payload and a query parameter to determine if flashcards or practice data should be exported.
  * Writes the appropriate CSV headers and rows based on the type (flashcards or practice).
  * Returns the CSV file as a downloadable stream.
```python
# GET "/" Route
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

class GenerateBody(BaseModel):
    notes: str
    course: Optional[str] = ""
    topic: Optional[str] = ""

# POST "/api/generate" Route
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

# POST "/api/export/echo" Route
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
Now that the logic is done, let's add a UI.

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

## 9) Write a README with Model Documentation & Risk Awareness
Here is an example README for this project:
```
# FlashSmith (Azure)

Paste notes $\rightarrow$ generate flashcards and practice (short/MCQ). Export CSVs for Anki/Quizlet.

**Tech**: FastAPI + Azure AI Foundry serverless model (Phi-3.5-mini-instruct via Azure AI Inference).

- Serverless endpoint + key auth from Azure AI Foundry Model catalog.  
- Long context (128k) supports full textbook sections.

## How it works
1. Frontend posts notes/course/topic to `/api/generate`
2. Backend calls Chat Completions with strict JSON prompt
3. UI renders results + provides CSV downloads

## Run
```bash
pip install -r requirements.txt
cp .env.example .env  # fill in endpoint + key
uvicorn app:app --reload --port 8000
```
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
