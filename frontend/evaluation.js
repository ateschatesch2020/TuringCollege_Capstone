const API_URL = "http://localhost:8001";

const params = new URLSearchParams(window.location.search);
const filename = params.get("file") || "";

document.getElementById("fileLabel").textContent = filename
  ? `Document: ${filename}`
  : "No document selected.";

function scoreToColor(value) {
  const stops = [
    [0,    [254, 226, 226]],
    [0.25, [255, 237, 213]],
    [0.5,  [254, 249, 195]],
    [0.75, [217, 249, 157]],
    [1.0,  [209, 250, 229]],
  ];
  value = Math.max(0, Math.min(1, value));
  let lo = stops[0], hi = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (value <= stops[i + 1][0]) { lo = stops[i]; hi = stops[i + 1]; break; }
  }
  const t = (hi[0] - lo[0]) === 0 ? 0 : (value - lo[0]) / (hi[0] - lo[0]);
  const [r, g, b] = [0, 1, 2].map(c => Math.round(lo[1][c] + t * (hi[1][c] - lo[1][c])));
  return `rgb(${r},${g},${b})`;
}

function renderTable(results) {
  const tbody = document.getElementById("resultsBody");
  tbody.innerHTML = results.map((r, i) => {
    const metrics = ["answer_relevancy", "faithfulness", "context_precision", "context_recall"];
    const metricCells = metrics.map(m => {
      const v = r[m] ?? 0;
      const bg = scoreToColor(v);
      return `<td class="px-4 py-3 text-center font-mono" style="background:${bg}">${v.toFixed(2)}</td>`;
    }).join("");
    return `<tr class="hover:bg-gray-50">
      <td class="px-4 py-3 text-gray-400">${i + 1}</td>
      <td class="px-4 py-3 max-w-xs">${escHtml(r.question)}</td>
      <td class="px-4 py-3 max-w-xs text-gray-500">${escHtml(r.expected_answer)}</td>
      <td class="px-4 py-3 max-w-xs text-gray-500">${escHtml(r.rag_answer)}</td>
      ${metricCells}
    </tr>`;
  }).join("");

  // Averages
  const metrics = ["answer_relevancy", "faithfulness", "context_precision", "context_recall"];
  const labels = {
    answer_relevancy: "Answer Relevancy",
    faithfulness: "Faithfulness",
    context_precision: "Context Precision",
    context_recall: "Context Recall",
  };
  const tips = {
    answer_relevancy: "Formula: AR = mean cos_sim(generated_question, original_question)<br><br>LLM generates N questions from the answer and measures their cosine similarity to the original question. High score → answer is on-topic.",
    faithfulness: "Formula: F = supported_claims / total_claims<br><br>Each claim in the answer is checked against the retrieved context. Claims not grounded in context reduce the score.",
    context_precision: "Formula: CP = relevant_contexts / total_retrieved_contexts<br><br>Measures the signal-to-noise ratio of retrieved chunks. High score → less irrelevant context retrieved.",
    context_recall: "Formula: CR = info_in_context / total_info_needed<br><br>Measures how much of the information required to produce the reference answer is present in the retrieved context. Low score → important context is missing.",
  };
  const grid = document.getElementById("averagesGrid");
  grid.innerHTML = metrics.map(m => {
    const avg = results.reduce((s, r) => s + (r[m] ?? 0), 0) / results.length;
    const bg = scoreToColor(avg);
    return `<div class="metric-card rounded-lg p-3 text-center" style="background:${bg}">
      <div class="text-xs text-gray-600 mb-1">${labels[m]}</div>
      <div class="text-xl font-bold text-gray-800">${avg.toFixed(3)}</div>
      <div class="tip"><strong>${labels[m]}</strong><br>${tips[m]}</div>
    </div>`;
  }).join("");
}

function escHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

document.getElementById("runBtn").addEventListener("click", async () => {
  if (!filename) {
    alert("No document specified in URL.");
    return;
  }

  const numQuestions = parseInt(document.getElementById("numQuestions").value, 10) || 20;
  const runBtn = document.getElementById("runBtn");
  const progressSection = document.getElementById("progressSection");
  const stageName = document.getElementById("stageName");
  const progressBar = document.getElementById("progressBar");
  const resultsSection = document.getElementById("resultsSection");
  const errorSection = document.getElementById("errorSection");

  runBtn.disabled = true;
  runBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Running...';
  progressSection.classList.remove("hidden");
  resultsSection.classList.add("hidden");
  errorSection.classList.add("hidden");

  try {
    const res = await fetch(`${API_URL}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, num_questions: numQuestions }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Request failed");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        let evt;
        try { evt = JSON.parse(line.slice(5).trim()); } catch { continue; }
        if (evt.error) throw new Error(evt.error);
        stageName.textContent = evt.stage || "";
        progressBar.style.width = (evt.progress ?? 0) + "%";
        if (evt.stage === "Complete" && evt.results) {
          progressSection.classList.add("hidden");
          resultsSection.classList.remove("hidden");
          renderTable(evt.results);
        }
      }
    }
  } catch (e) {
    progressSection.classList.add("hidden");
    errorSection.classList.remove("hidden");
    document.getElementById("errorMsg").textContent = e.message;
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Evaluation';
  }
});
