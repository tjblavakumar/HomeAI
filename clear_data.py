#!/usr/bin/env python3
"""Force-delete all items, documents, and chroma data."""
import sqlite3, shutil
from pathlib import Path

root = Path(__file__).resolve().parent
db = root / "data" / "app.db"

if db.exists():
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=OFF")
    r1 = conn.execute("DELETE FROM documents").rowcount
    r2 = conn.execute("DELETE FROM items").rowcount
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    conn.close()
    print(f"DB: deleted {r1} docs, {r2} items")
else:
    print("DB: not found")

chroma = root / "data" / "chroma"
if chroma.exists():
    shutil.rmtree(str(chroma))
    print("Chroma: cleared")
else:
    print("Chroma: not found")

print("All clear.")