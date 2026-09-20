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
existing item ("troubleshoot"), or (c) something else ("other").

Rules:
- "troubleshoot" includes: how to use, how to clean, how to fix, how to maintain, won't \
start, error message, parts replacement, setup/installation questions, troubleshooting, FAQ.
- "find_docs" includes: find/buy manuals, find drivers, find accessories, what ink/parts/\
batteries does it use, specs/features.
- "other": greetings, chit-chat, off-topic questions.

Extract the brand and a full, descriptive product name. Include the year, model, and trim \
level (e.g. "2017 Toyota Sienna LE", "Ninja CAFE Luxe3", "Canon GX1020"). Never output a \
single word or a short fragment as product_name. Respond ONLY with JSON in this shape:
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
(compatible accessories, e.g. replacement batteries, ink cartridges, filters).

IMPORTANT FILTERING RULES:
- Discard generic "collection of links" pages that aggregate many different manuals (e.g. \
"Links to Car Owner's Manuals From Every Brand", "Free Car Owner Manuals PDF", "All Manuals \
Directory"). Prefer official manufacturer pages or direct PDF links.
- Discard irrelevant or duplicate results.
- Only keep results that are directly about the specific product stated above.

Respond ONLY with JSON in this shape:
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


PRODUCT_GUESS_SYSTEM_PROMPT = """You identify consumer/household network devices from \
scan signals. Given a device's MAC vendor (manufacturer), hostname, and open TCP ports, \
produce a concise best-guess product label and a device type.

Rules:
- The label should read like a product a person would recognize, e.g. "Amazon Echo Dot", \
"Canon PIXMA Printer", "Synology NAS", "TP-Link Router", "Apple iPhone". If you only know \
the manufacturer, use the real manufacturer name followed by "device" (for example \
"Apple device", "Canon device"). Always substitute the actual vendor name — never output \
a placeholder like "<Vendor>". Never invent a specific model number you can't infer; keep \
it general when unsure.
- device_type must be one of: "printer", "router", "nas", "computer", "phone", \
"tv", "speaker", "camera", "iot", "generic".
- Keep the label under 40 characters. Do not include the IP or MAC.

Respond ONLY with JSON: {"label": string, "device_type": string}"""


def guess_product(vendor: str | None, hostname: str | None, open_ports: list[int]) -> dict:
    """Best-guess a friendly product label + device type from scan signals.

    Returns {"label": str, "device_type": str}. Raises LLMNotConfiguredError if
    no key is set (callers should treat that as "skip refinement").
    """
    client = _client()
    payload = {
        "vendor": vendor or "unknown",
        "hostname": hostname or "unknown",
        "open_ports": open_ports,
    }
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PRODUCT_GUESS_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    return json.loads(response.choices[0].message.content or "{}")


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = _client()
    response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in response.data]


def chat_completion(messages: list[dict]) -> str:
    client = _client()
    response = client.chat.completions.create(model=settings.openai_chat_model, messages=messages)
    return response.choices[0].message.content or ""
