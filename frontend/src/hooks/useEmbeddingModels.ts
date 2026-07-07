import { useEffect, useState } from "react";
import { API_URL } from "../lib/api";
import type { EmbeddingModelOption } from "../types";

export function useEmbeddingModels() {
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModelOption[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/embedding-models`);
        const data = await res.json();
        setEmbeddingModels(data.embedding_models ?? []);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  return embeddingModels;
}
