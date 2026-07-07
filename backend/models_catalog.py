"""Catalog of selectable chat models: 3 frontier + 3 open-source models,
all live OpenRouter model ids. Restricted to the set this account's
OpenRouter data-policy/guardrail settings currently allow -- most other
providers return "No endpoints available matching your guardrail
restrictions and data policy" until that account setting is loosened."""

MODEL_CATALOG = [
    {"id": "openai/gpt-4o", "label": "GPT-4o", "provider_name": "OpenAI", "type": "frontier", "size_gb": None},
    {"id": "anthropic/claude-haiku-4.5", "label": "Claude Haiku 4.5", "provider_name": "Anthropic", "type": "frontier", "size_gb": None},
    {"id": "google/gemini-2.5-flash", "label": "Gemini 2.5 Flash", "provider_name": "Google", "type": "frontier", "size_gb": None},

    {"id": "minimax/minimax-m2.7", "label": "MiniMax M2.7", "provider_name": "MiniMax", "type": "open_source", "size_gb": None},
    {"id": "deepseek/deepseek-v4-flash", "label": "DeepSeek V4 Flash", "provider_name": "DeepSeek", "type": "open_source", "size_gb": 170},
    {"id": "deepseek/deepseek-v4-pro", "label": "DeepSeek V4 Pro", "provider_name": "DeepSeek", "type": "open_source", "size_gb": 960},
]

DEFAULT_MODEL_ID = "openai/gpt-4o"


def get_model(model_id: str) -> dict | None:
    return next((m for m in MODEL_CATALOG if m["id"] == model_id), None)


EMBEDDING_MODEL_CATALOG = [
    {"id": "openai", "label": "OpenAI text-embedding-3-small", "provider_name": "OpenAI (via OpenRouter)", "dimensions": 1536, "location": "api"},
    {"id": "huggingface", "label": "all-MiniLM-L6-v2 (open-source)", "provider_name": "HuggingFace / sentence-transformers", "dimensions": 384, "location": "local"},
]

DEFAULT_EMBEDDING_MODEL_ID = "openai"


def get_embedding_model_info(embedding_model_id: str) -> dict | None:
    return next((m for m in EMBEDDING_MODEL_CATALOG if m["id"] == embedding_model_id), None)
