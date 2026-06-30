const API_URL = "http://localhost:8001";

const params = new URLSearchParams(window.location.search);
const filename = params.get("file") || "";

document.getElementById("fileLabel").textContent = filename
  ? `Document: ${filename}`
  : "No document selected.";

function metricColor(value) {
  if (value >= 0.75) return "#d1fae5";
  if (value >= 0.35) return "#fef9c3";
  return "#fee2e2";
}

function renderTable(results) {
  const tbody = document.getElementById("resultsBody");
  tbody.innerHTML = results.map((r, i) => {
    const metrics = ["answer_relevancy", "faithfulness", "context_precision", "context_recall"];
    const metricCells = metrics.map(m => {
      const v = r[m] ?? 0;
      const bg = metricColor(v);
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
  const grid = document.getElementById("averagesGrid");
  grid.innerHTML = metrics.map(m => {
    const avg = results.reduce((s, r) => s + (r[m] ?? 0), 0) / results.length;
    const bg = metricColor(avg);
    return `<div class="rounded-lg p-3 text-center" style="background:${bg}">
      <div class="text-xs text-gray-600 mb-1">${labels[m]}</div>
      <div class="text-xl font-bold text-gray-800">${avg.toFixed(3)}</div>
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
