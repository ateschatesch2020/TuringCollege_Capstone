import { scoreToColor } from "../lib/scoreColor";
import type { EvaluationRow } from "../types";

const METRICS = ["answer_relevancy", "faithfulness", "context_precision", "context_recall"] as const;

const LABELS: Record<(typeof METRICS)[number], string> = {
  answer_relevancy: "Answer Relevancy",
  faithfulness: "Faithfulness",
  context_precision: "Context Precision",
  context_recall: "Context Recall",
};

const TIPS: Record<(typeof METRICS)[number], string> = {
  answer_relevancy:
    "Formula: AR = mean cos_sim(generated_question, original_question). LLM generates N questions from the answer and measures their cosine similarity to the original question. High score → answer is on-topic.",
  faithfulness:
    "Formula: F = supported_claims / total_claims. Each claim in the answer is checked against the retrieved context. Claims not grounded in context reduce the score.",
  context_precision:
    "Formula: CP = relevant_contexts / total_retrieved_contexts. Measures the signal-to-noise ratio of retrieved chunks. High score → less irrelevant context retrieved.",
  context_recall:
    "Formula: CR = info_in_context / total_info_needed. Measures how much of the information required to produce the reference answer is present in the retrieved context. Low score → important context is missing.",
};

interface ResultsTableProps {
  title: string;
  rows: EvaluationRow[];
}

function HeaderTip({ metric }: { metric: (typeof METRICS)[number] }) {
  return (
    <th className="px-4 py-3 text-center metric-th">
      {LABELS[metric]}
      <div className="tip">
        <strong>{LABELS[metric]}</strong>
        <br />
        {TIPS[metric]}
      </div>
    </th>
  );
}

export default function ResultsTable({ title, rows }: ResultsTableProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3 mt-8 first:mt-0">
        <h2 className="text-lg font-semibold text-gray-700">{title}</h2>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>0</span>
          <div
            style={{
              width: 120,
              height: 12,
              borderRadius: 6,
              background: "linear-gradient(to right,#fee2e2,#fed7aa,#fef9c3,#d9f99d,#d1fae5)",
            }}
          />
          <span>1</span>
        </div>
      </div>
      <details className="mb-4">
        <summary className="cursor-pointer select-none text-sm font-medium text-indigo-600 hover:text-indigo-700 mb-2">
          Show question details
        </summary>
        <div className="overflow-x-auto rounded-xl shadow-sm border border-gray-200 mt-2">
          <table className="min-w-full text-xs text-gray-700 bg-white">
            <thead className="bg-gray-100 text-gray-600 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left w-8">#</th>
                <th className="px-4 py-3 text-left">Question</th>
                <th className="px-4 py-3 text-left">Expected Answer</th>
                <th className="px-4 py-3 text-left">RAG Answer</th>
                {METRICS.map((m) => (
                  <HeaderTip key={m} metric={m} />
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-400">{i + 1}</td>
                  <td className="px-4 py-3 max-w-xs">{r.question}</td>
                  <td className="px-4 py-3 max-w-xs text-gray-500">{r.expected_answer}</td>
                  <td className="px-4 py-3 max-w-xs text-gray-500">{r.rag_answer}</td>
                  {METRICS.map((m) => {
                    const v = r[m] ?? 0;
                    return (
                      <td key={m} className="px-4 py-3 text-center font-mono" style={{ background: scoreToColor(v) }}>
                        {v.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <div className="mt-4 bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Averages</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {METRICS.map((m) => {
            const avg = rows.reduce((s, r) => s + (r[m] ?? 0), 0) / rows.length;
            return (
              <div key={m} className="metric-card rounded-lg p-3 text-center" style={{ background: scoreToColor(avg) }}>
                <div className="text-xs text-gray-600 mb-1">{LABELS[m]}</div>
                <div className="text-xl font-bold text-gray-800">{avg.toFixed(3)}</div>
                <div className="tip">
                  <strong>{LABELS[m]}</strong>
                  <br />
                  {TIPS[m]}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
