import { useEffect, useState } from "react";
import { API_URL } from "../lib/api";
import type { ModelOption } from "../types";

export function useModels() {
  const [models, setModels] = useState<ModelOption[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/models`);
        const data = await res.json();
        setModels(data.models ?? []);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  return models;
}
