# HomeAI — Implementation Plan

## Decisions
- Run locally on a Linux dev box first; Dockerize later (docker-compose) for portability.
- Backend: Python, FastAPI. Frontend: React + Next.js.
- LLM: OpenAI (GPT-4o/4.1 for chat + tool calling, `text-embedding-3-small` for embeddings).
- Web search: Tavily API (primary, free tier) + `duckduckgo-search` library (free, no-key
  fallback), behind a pluggable `SearchProvider` interface so providers can be swapped.
- Vector DB: Chroma (local, embedded, persisted to disk).
- Metadata DB: SQLite via SQLAlchemy (file-based, migrates easily into a Docker volume).
- Drivers/installers: store only the manufacturer download URL — never host the file,
  never index into RAG.
- Manuals/troubleshooting guides/accessory-info docs: downloaded, stored on the local
  filesystem, and indexed into RAG (chunked + embedded).
- Auth: none — trusted home LAN only for v1 (documented gap, easy to add later).
- Categories: fixed starter set (Electronics, Appliances, Furniture, Tools, Other) plus
  user-defined custom categories.
- Item input: manual form, chat free-text, and photo/barcode OCR — all three supported.
- Scope: full end-to-end flow in v1, functional UI (polish not required).

## Architecture Overview
```
Next.js frontend  <-- REST/JSON -->  FastAPI backend
                                        |-- SQLite (items, categories, documents metadata)
                                        |-- Chroma (vector store, persisted dir)
                                        |-- Local filesystem (uploaded manuals, photos)
                                        |-- OpenAI API (chat + embeddings)
                                        |-- Tavily API / duckduckgo-search (web search)
```

## Data Model (SQLite via SQLAlchemy)
- `Category(id, name, icon, is_custom)`
- `Item(id, name, brand, model_number, category_id, purchase_store, purchase_date, photo_path, notes, created_at)`
- `Document(id, item_id, doc_type[manual|troubleshooting|driver|accessory], title, source_url, local_path, indexed_status[pending|downloaded|indexed|failed|link_only], selected_at)`
- `Conversation` / `ChatMessage` (minimal — chat history per item, for context continuity)

## Project Folder Structure
```
backend/
  app/
    main.py
    api/            # routers: items.py, categories.py, chat.py, documents.py, upload.py
    models/         # SQLAlchemy models
    schemas/        # Pydantic schemas
    services/
      search_provider.py   # Tavily + DuckDuckGo fallback, unified interface
      llm.py               # OpenAI chat + tool-calling orchestration
      rag.py               # chunking, embedding, Chroma query/upsert
      ingestion.py         # download selected docs, extract text, index
      ocr.py               # pytesseract + pyzbar for photo/barcode add-item
    db.py
    config.py
  tests/
  requirements.txt
frontend/            # Next.js app: Dashboard, CategoryList, ItemDetail, ChatBox, DocumentPicker
data/
  uploads/            # downloaded manuals + item photos
  chroma/             # persisted vector store
  app.db              # sqlite file
docker/
  Dockerfile.backend
  Dockerfile.frontend
  docker-compose.yml
.env.example           # OPENAI_API_KEY, TAVILY_API_KEY
```

## Core Flows
1. **Dashboard**: scorecards per category with item counts (`GET /categories` with counts)
   → click → item list (`GET /categories/{id}/items`).
2. **Add item**: (a) manual form, (b) chat free text (e.g. "I bought a Ninja CAFE Luxe3
   from Costco"), (c) photo/barcode OCR upload → prefill form → confirm → creates `Item` row.
3. **Chat-driven doc discovery**: user message → LLM (function/tool calling) decides intent:
   - `search_product_docs(brand, model, category)` → calls `search_provider` (Tavily,
     fallback DDG) → LLM parses/dedupes/labels results into: user manual, troubleshooting
     guide, driver/software (link only), compatible accessories (batteries, ink, etc.) →
     returned to frontend as a checkbox list with source links.
   - `troubleshoot_item(item_id_or_text, query)` → RAG retrieval from Chroma (optionally
     scoped to the item's indexed docs) + LLM answer with citations back to source doc.
4. **Selection & storage**: user checks desired docs → `POST /documents/select` → for
   non-driver docs: download file, extract text, chunk, embed, upsert to Chroma, mark
   `indexed`; for driver docs: save the URL only, mark `link_only`.
5. **Troubleshooting chat**: reuses `troubleshoot_item` RAG flow; answers grounded in
   indexed manuals with citations.

## Phases

### Phase 0 — Scaffolding
- Initialize backend (FastAPI + SQLAlchemy, simple `create_all` for v1 — no Alembic yet)
  and frontend (Next.js + Tailwind) project skeletons.
- Set up `.env` handling, config module, `requirements.txt` / `package.json`.
- Wire up empty SQLite DB with `Category` seed data (Electronics, Appliances, Furniture,
  Tools, Other).

### Phase 1 — Catalog core (depends on Phase 0)
- Item/Category CRUD API + basic manual add-item form.
- Dashboard UI: scorecards with counts, category → item list, item detail page (docs
  section empty for now).

### Phase 2 — Web search & doc discovery (depends on Phase 1)
- Implement `search_provider.py` (Tavily wrapper + DuckDuckGo fallback, common result
  shape: title, url, snippet, source).
- Implement `llm.py` tool-calling orchestration for `search_product_docs`.
- Chat endpoint (`POST /chat`) routes intent (add/search vs troubleshoot) and returns
  structured doc suggestions.
- Frontend `ChatBox` + `DocumentPicker` (checkbox list grouped by type: Manual /
  Troubleshooting / Driver-Software / Accessories).

### Phase 3 — Selection, storage & RAG ingestion (depends on Phase 2)
- `POST /documents/select` endpoint: persists selected `Document` rows.
- `ingestion.py`: download PDFs/pages, extract text (pypdf/pdfplumber, or trafilatura for
  HTML pages), chunk (~500 tokens w/ overlap), embed via OpenAI, upsert into Chroma with
  metadata (item_id, doc_id, source_url, page).
- Drivers: skip download, store URL only + mark `link_only`.
- Background execution via FastAPI `BackgroundTasks` for v1 (no separate worker needed yet).

### Phase 4 — RAG troubleshooting chat (depends on Phase 3)
- `rag.py` retrieval: query Chroma (optionally filtered by item_id/category), build
  context, call OpenAI chat with citations.
- Extend chat endpoint/UI to show grounded answers with links back to source manual/page.

### Phase 5 — OCR / barcode add-item (parallel with Phase 2-4, depends on Phase 1)
- `ocr.py`: pytesseract for receipt/label text extraction, pyzbar for barcode decoding.
- Upload endpoint + frontend photo upload widget → prefill add-item form → user
  confirms/edits → proceeds to Phase 2 search flow.

### Phase 6 — Dockerization & polish (depends on Phases 1-5)
- `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml` with volumes for
  `data/uploads`, `data/chroma`, `data/app.db`.
- README/readme.txt with setup/run instructions (local dev + docker-compose).
- Basic tests: service-layer unit tests (mock Tavily/DDG/OpenAI), one end-to-end manual
  test script (add item → search → select → ingest → troubleshoot chat).

## Verification
1. Backend: `pytest` unit tests for `search_provider`, `ingestion`, `rag` (mocked external calls).
2. Manual E2E: add "Canon GX1020" printer via chat → verify suggested manual/driver/ink
   list appears with checkboxes → select manual → verify file downloaded to
   `data/uploads` and appears in the Chroma collection → ask a troubleshooting question
   in chat → verify grounded answer with citation.
3. Dashboard: verify category counts update after adding items across categories.
4. Docker: `docker compose up` builds and serves both frontend and backend; data persists
   across container restarts (volume-mounted).

## Scope Boundaries (explicit)
- **Included**: dashboard, manual/chat/OCR item add, web-search doc discovery with
  checkbox selection, RAG-indexed manuals/troubleshooting guides/accessory info, driver
  links (not hosted/not indexed), troubleshooting chatbot, Dockerization.
- **Excluded (v1)**: user auth/accounts, multi-household support, mobile app,
  Celery/queue-based background workers (using simple `BackgroundTasks` instead), cloud
  deployment automation (Docker image only, manual deploy).

## Open Considerations
1. Chat history persistence — default: persist minimal history tied to item for context
   continuity (vs. fully ephemeral).
2. Duplicate item detection on re-adding a matching model number — default: warn but
   allow duplicates.
