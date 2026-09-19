HomeAI - Local Setup & Run Guide (Linux)
==========================================

This guide covers running HomeAI on a local Linux development box.
Docker instructions will be added in Phase 6 once the app is containerized.

PREREQUISITES
--------------
- Python 3.11+
- Node.js 20+ and npm
- An OpenAI API key (https://platform.openai.com/api-keys)
- A Tavily API key (https://tavily.com - free tier)
- Tesseract OCR installed on the system (for photo/label scanning, Phase 5):
    sudo apt-get install tesseract-ocr
- zbar library installed (for barcode scanning, Phase 5):
    sudo apt-get install libzbar0

Like the API keys, these two system packages are optional to start the app:
without tesseract-ocr, the "Scan a label/receipt" upload on the Add Item page
returns a clear "not installed" error instead of crashing; without libzbar0,
barcode decoding is silently skipped (OCR text extraction still works).

PROJECT LAYOUT
--------------
backend/    FastAPI application (API, services, models)
frontend/   Next.js application (UI)
data/       Local data: uploads/ (manuals, photos), chroma/ (vector store), app.db (SQLite)
docker/     Dockerfiles and docker-compose.yml (added in Phase 6)

1. CONFIGURE ENVIRONMENT VARIABLES
-----------------------------------
Copy the example env file and fill in your API keys:

    cp .env.example .env

Edit .env and set:
    OPENAI_API_KEY=sk-...
    TAVILY_API_KEY=tvly-...

Both keys are optional to start the app and can be added at any time later:
- Without TAVILY_API_KEY, web search automatically falls back to the free,
  key-less DuckDuckGo provider.
- Without OPENAI_API_KEY, the dashboard/catalog work fully, but the chat box
  returns a clear "not configured yet" message instead of an answer. Add the
  key to .env and restart the backend to enable chat.

You can also change which OpenAI models are used, directly in .env:
    OPENAI_CHAT_MODEL=gpt-4o-mini
    OPENAI_EMBEDDING_MODEL=text-embedding-3-small
Restart the backend after changing either value.

2. BACKEND SETUP
-----------------
    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Run the API server (from the backend/ directory, venv active):

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

The API will be available at http://localhost:8000
Interactive API docs (Swagger UI) at http://localhost:8000/docs

On first run, the backend creates the SQLite database at ../data/app.db and
seeds the starter categories (Electronics, Appliances, Furniture, Tools, Other).

3. FRONTEND SETUP
------------------
In a separate terminal:

    cd frontend
    npm install
    npm run dev

The web UI will be available at http://localhost:3000
It expects the backend API at http://localhost:8000 (configurable via
frontend/.env.local, e.g. NEXT_PUBLIC_API_URL=http://localhost:8000).

4. USING THE APP
------------------
- Open http://localhost:3000 in a browser on any device on your local network
  (use the machine's LAN IP instead of localhost to access from other devices).
- The dashboard shows category scorecards with item counts.
- Add items via the form, the chat box, or by uploading a photo/barcode.
- Use the chat box to ask things like:
    "find the user manual for the Ninja CAFE Luxe3 I bought from Costco"
    "what ink does my Canon GX1020 use?"
- Review the suggested documents (manual, troubleshooting guide, driver links,
  compatible accessories), check the ones you want saved, and confirm.
- Once a manual is indexed, ask troubleshooting questions directly in the chat box.

5. DATA STORAGE
------------------
All local data lives under data/ at the repo root:
    data/app.db      SQLite database (items, categories, document metadata)
    data/chroma/     Persisted vector store for RAG search
    data/uploads/    Downloaded manuals and uploaded item photos

Back up the data/ directory to preserve your household's knowledge base.

6. RUNNING TESTS
------------------
    cd backend
    source .venv/bin/activate
    pytest

NOTES
------------------
- v1 has no authentication; it is intended for use on a trusted home network only.
- Software drivers/installers are stored as links only, never downloaded or indexed.
- Docker packaging (docker-compose up) will be documented here once Phase 6 is complete.
