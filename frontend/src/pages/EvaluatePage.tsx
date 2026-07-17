import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useEvaluation } from "../hooks/useEvaluation";
import { useModels } from "../hooks/useModels";
import { useEmbeddingModels } from "../hooks/useEmbeddingModels";
import { useSessionInfo } from "../hooks/useSessionInfo";
import ResultsTable from "./ResultsTable.tsx";
import ModelSelect from "../components/Common/ModelSelect.tsx";
import type { EvaluationRow, StrategyRow } from "../types";

const STRATEGIES = [
  { id: "semantic", label: "Semantic Search" },
  { id: "semantic_hybrid", label: "Semantic + Keyword Search (Hybrid)" },
  { id: "recursive", label: "RecursiveTextSplitter Search" },
  { id: "recursive_hybrid", label: "RecursiveTextSplitter + Keyword Search (Hybrid)" },
] as const;

export default function EvaluatePage() {
  const [params] = useSearchParams();
  const filename = params.get("file") || "";
  const sessionId = params.get("session_id") || "";

  const [numQuestions, setNumQuestions] = useState(20);
  const [answerModelId, setAnswerModelId] = useState("");
  const [judgeModelId, setJudgeModelId] = useState("");
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(["semantic", "semantic_hybrid"]);
  const [results, setResults] = useState<EvaluationRow[] | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const { stage, progress, running, error, evaluate } = useEvaluation();
  const models = useModels();
  const embeddingModels = useEmbeddingModels();
  const sessionInfo = useSessionInfo(sessionId || null);
  const embeddingInfo = embeddingModels.find((m) => m.id === sessionInfo?.embedding_model);

  useEffect(() => {
    if (!judgeModelId && models.length > 0) {
      setJudgeModelId(models.find((m) => m.type === "frontier")?.id ?? models[0].id);
    }
  }, [judgeModelId, models]);

  useEffect(() => {
    if (!answerModelId && models.length > 0) {
      setAnswerModelId(models.find((m) => m.type === "open_source")?.id ?? models[0].id);
    }
  }, [answerModelId, models]);

  const toggleStrategy = (id: string) => {
    setSelectedStrategies((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  };

  const handleRun = async () => {
    if (!filename) {
      alert("No document specified in URL.");
      return;
    }
    if (selectedStrategies.length === 0) {
      alert("Select at least one comparison strategy.");
      return;
    }
    setResults(null);
    setErrorMsg(null);
    try {
      await evaluate(filename, sessionId, numQuestions, answerModelId, judgeModelId, selectedStrategies, (evt) => {
        if (evt.stage === "Complete" && Array.isArray(evt.results)) {
          setResults(evt.results as EvaluationRow[]);
        }
      });
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const strategiesInResults = STRATEGIES.filter((s) => results?.some((r) => s.id in r.results));

  const rowsForStrategy = (strategyId: string): StrategyRow[] =>
    results?.map((r) => ({
      question: r.question,
      expected_answer: r.expected_answer,
      ...(r.results[strategyId] ?? { rag_answer: "" }),
    })) ?? [];

  return (
    <div className="flex-1 h-full overflow-y-auto bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
            <i className="fa-solid fa-chart-bar text-indigo-500"></i>
            RAGAs Evaluation
          </h1>
          <p className="text-sm text-gray-500 mt-1">{filename ? `Document: ${filename}` : "No document selected."}</p>
          {embeddingInfo && (
            <p className="text-xs text-gray-400 mt-1">
              <i className="fa-solid fa-database mr-1"></i>
              Embeddings: {embeddingInfo.label} ({embeddingInfo.dimensions}d) — fixed for this session
            </p>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Number of test questions</label>
              <input
                type="number"
                min={1}
                max={50}
                value={numQuestions}
                onChange={(e) => setNumQuestions(parseInt(e.target.value, 10) || 20)}
                className="w-28 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Answer model (RAG)</label>
              <ModelSelect
                models={models}
                value={answerModelId}
                onChange={setAnswerModelId}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Judge model (evaluator)</label>
              <ModelSelect
                models={models}
                value={judgeModelId}
                onChange={setJudgeModelId}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <button
              onClick={handleRun}
              disabled={running || selectedStrategies.length === 0}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors disabled:opacity-50"
            >
              <i className={`fa-solid ${running ? "fa-circle-notch fa-spin" : "fa-play"}`}></i>{" "}
              {running ? "Running..." : "Run Evaluation"}
            </button>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Comparisons to run</label>
            <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-gray-600">
              {STRATEGIES.map((s) => (
                <label key={s.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedStrategies.includes(s.id)}
                    onChange={() => toggleStrategy(s.id)}
                    className="rounded accent-indigo-600"
                  />
                  <span>{s.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {running && !results && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6">
            <p className="text-sm text-gray-600 mb-2">{stage || "Starting..."}</p>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-indigo-500 h-2 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {results && (
          <div>
            {strategiesInResults.map((s) => (
              <ResultsTable key={s.id} title={s.label} rows={rowsForStrategy(s.id)} />
            ))}
          </div>
        )}

        {(errorMsg || error) && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            <i className="fa-solid fa-circle-exclamation mr-2"></i>
            <span>{errorMsg || error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
