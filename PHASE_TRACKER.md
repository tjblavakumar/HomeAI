# HomeAI — Phase Tracker

Track progress here as implementation proceeds. Check items off with `[x]` when done.

## Phase 0 — Scaffolding
- [x] Backend project skeleton (FastAPI + SQLAlchemy, `requirements.txt`)
- [x] Frontend project skeleton (Next.js + Tailwind, `package.json`)
- [x] `.env` / config module (`OPENAI_API_KEY`, `TAVILY_API_KEY`)
- [x] SQLite DB created with `Category` seed data (Electronics, Appliances, Furniture, Tools, Other)

## Phase 1 — Catalog core
- [x] `Item` / `Category` SQLAlchemy models + Pydantic schemas
- [x] Category CRUD API (`GET /categories` with item counts)
- [x] Item CRUD API (`GET/POST /items`, `GET /categories/{id}/items`)
- [x] Dashboard UI: category scorecards with counts
- [x] Category → item list UI
- [x] Item detail page (docs section empty placeholder)
- [x] Manual add-item form (frontend + backend wiring)

## Phase 2 — Web search & doc discovery
- [x] `search_provider.py`: Tavily wrapper
- [x] `search_provider.py`: DuckDuckGo fallback
- [x] `llm.py`: OpenAI tool-calling orchestration for `search_product_docs`
- [x] `POST /chat` endpoint: intent routing (add/search vs troubleshoot)
- [x] Frontend `ChatBox` component
- [x] Frontend `DocumentPicker` checkbox list (grouped by doc type)

## Phase 3 — Selection, storage & RAG ingestion
- [x] `POST /documents/select` endpoint
- [x] `ingestion.py`: download manual/troubleshooting/accessory docs
- [x] `ingestion.py`: text extraction (pypdf/pdfplumber/trafilatura)
- [x] `ingestion.py`: chunking + OpenAI embeddings + Chroma upsert
- [x] Driver docs: link-only storage, `link_only` status, no indexing
- [x] Background execution via FastAPI `BackgroundTasks`

## Phase 4 — RAG troubleshooting chat
- [x] `rag.py`: Chroma retrieval (optionally scoped to item/category)
- [x] `rag.py`: grounded answer generation with citations
- [x] Chat endpoint/UI updated to show grounded answers + source links

## Phase 5 — OCR / barcode add-item
- [x] `ocr.py`: pytesseract text extraction from photo
- [x] `ocr.py`: pyzbar barcode decoding
- [x] Upload endpoint for photos
- [x] Frontend photo upload widget + prefilled add-item form
- [x] System packages installed on target machine (`tesseract-ocr`, `libzbar0`) — see readme.txt

## Phase 6 — Dockerization & polish
STATUS: DEFERRED (OPEN) — holding off until after manual end-to-end testing with
real API keys and any follow-up changes from that testing. Resume when ready to
package for Docker.
- [ ] `Dockerfile.backend`
- [ ] `Dockerfile.frontend`
- [ ] `docker-compose.yml` with volumes (`data/uploads`, `data/chroma`, `data/app.db`)
- [ ] `readme.txt` finalized with docker-compose run instructions
- [ ] Unit tests: `search_provider`, `ingestion`, `rag` (mocked external calls)
- [ ] Manual E2E test pass (add item → search → select → ingest → troubleshoot chat)

## Open Considerations (revisit during implementation)
- [ ] Decide: chat history persistence scope (per-item vs fully ephemeral)
- [ ] Decide: duplicate item detection behavior (warn vs block vs allow silently)
