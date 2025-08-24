// app.js

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
