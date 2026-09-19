from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings


class LLMNotConfiguredError(RuntimeError):
    """Raised when no OpenAI API key has been configured yet."""


def _client() -> OpenAI:
    # Checked at call time (not import time) so the key can be added to .env later.
    if not settings.openai_api_key:
        raise LLMNotConfiguredError(
            "OPENAI_API_KEY is not configured yet. Add it to your .env file to enable chat."
        )
    return OpenAI(api_key=settings.openai_api_key)


INTENT_SYSTEM_PROMPT = """You are the intent-extraction step of a household knowledge-base \
assistant. Given a user's chat message, decide whether they want to (a) find manuals, \
drivers, or accessories for a product ("find_docs"), (b) troubleshoot a problem with an \
existing item ("troubleshoot"), or (c) something else ("other"). Extract the brand and \
model/product name if mentioned. Respond ONLY with JSON in this shape:
{"intent": "find_docs"|"troubleshoot"|"other", "brand": string|null, "model": string|null, \
"product_name": string|null, "query": string}"""


def extract_intent(message: str) -> dict:
    client = _client()
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
    )
    return json.loads(response.choices[0].message.content or "{}")


CATEGORIZE_SYSTEM_PROMPT = """You are categorizing raw web search results about a specific \
product for a household knowledge-base. For each relevant result, classify it into exactly \
one of: "manual" (owner/user manual or troubleshooting guide), "troubleshooting" (a dedicated \
troubleshooting/FAQ page), "driver" (software/driver/installer download page), or "accessory" \
(compatible accessories, e.g. replacement batteries, ink cartridges, filters). Discard \
irrelevant or duplicate results. Respond ONLY with JSON in this shape:
{"documents": [{"doc_type": "manual"|"troubleshooting"|"driver"|"accessory", "title": string, \
"source_url": string, "reason": string}]}"""


def categorize_search_results(product_name: str, results: list[dict]) -> list[dict]:
    client = _client()
    user_content = json.dumps({"product": product_name, "results": results})
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": CATEGORIZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    parsed = json.loads(response.choices[0].message.content or "{}")
    return parsed.get("documents", [])


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = _client()
    response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in response.data]


def chat_completion(messages: list[dict]) -> str:
    client = _client()
    response = client.chat.completions.create(model=settings.openai_chat_model, messages=messages)
    return response.choices[0].message.content or ""
