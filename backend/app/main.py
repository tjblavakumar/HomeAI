from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import categories, chat, documents, items
from app.db import Base, SessionLocal, engine
from app.seed import seed_categories


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_categories(db)
    yield


app = FastAPI(title="HomeAI", lifespan=lifespan)

# Local-network only app (no auth in v1); allow the Next.js dev server origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(categories.router)
app.include_router(items.router)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
