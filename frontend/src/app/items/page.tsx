"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import {
  getCategories,
  getDocumentsForItem,
  getItems,
  deleteItem,
  reindexDocument,
  type Category,
  type Document,
  type Item,
} from "@/lib/api";

export default function ItemsPage() {
  const [items, setItems] = useState<(Item & { documents?: Document[] })[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [filterCategory, setFilterCategory] = useState<number | undefined>(undefined);
  const [filterDocType, setFilterDocType] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState<Set<number>>(new Set());

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [allItems, allCats] = await Promise.all([
        getItems(filterCategory, filterDocType || undefined),
        getCategories(),
      ]);
      const withDocs = await Promise.all(
        allItems.map(async (item) => {
          try {
            const docs = await getDocumentsForItem(item.id);
            return { ...item, documents: docs };
          } catch {
            return { ...item, documents: [] };
          }
        })
      );
      setItems(withDocs);
      setCategories(allCats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load items");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filterCategory, filterDocType]);

  async function handleDelete(itemId: number) {
    if (!confirm("Delete this item and all its documents?")) return;
    try {
      await deleteItem(itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function handleReindex(documentId: number, itemId: number) {
    try {
      setReindexing((prev) => new Set(prev).add(documentId));
      await reindexDocument(documentId);
      // Poll until the document reaches a terminal status
      await pollUntilResolved(documentId, itemId);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Re-index failed");
    } finally {
      setReindexing((prev) => {
        const next = new Set(prev);
        next.delete(documentId);
        return next;
      });
      load();
    }
  }

  async function pollUntilResolved(documentId: number, itemId: number) {
    for (let attempt = 0; attempt < 60; attempt++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const docs = await getDocumentsForItem(itemId).catch(() => []);
        const target = docs.find((d) => d.id === documentId);
        if (target && ["indexed", "failed", "link_only"].includes(target.indexed_status)) {
          return;
        }
      } catch {
        // keep polling
      }
    }
  }

  return (
    <div className="flex flex-col flex-1 min-h-screen" style={{ backgroundColor: '#0a1628' }}>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
<div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold text-white">Items</h1>
          <Link
            href="/items/new"
            className="rounded-md bg-purple-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-purple-600"
          >
            + Add item
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-6">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Category</label>
            <select
              value={filterCategory ?? ""}
              onChange={(e) => setFilterCategory(e.target.value ? Number(e.target.value) : undefined)}
              className="rounded-md border border-blue-200/30 bg-blue-950/40 px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="" className="bg-[#0a1628] text-white">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id} className="bg-[#0a1628] text-white">{c.name}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Document type</label>
            <select
              value={filterDocType}
              onChange={(e) => setFilterDocType(e.target.value)}
              className="rounded-md border border-blue-200/30 bg-blue-950/40 px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="" className="bg-[#0a1628] text-white">All types</option>
              <option value="manual" className="bg-[#0a1628] text-white">Manual</option>
              <option value="troubleshooting" className="bg-[#0a1628] text-white">Troubleshooting</option>
              <option value="driver" className="bg-[#0a1628] text-white">Driver</option>
              <option value="accessory" className="bg-[#0a1628] text-white">Accessory</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-900/60 px-4 py-3 text-sm text-red-200">{error}</div>
        )}

        {loading ? (
          <div className="text-center text-slate-400 py-12">Loading items…</div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-blue-200/30 p-12 text-center text-slate-500">
            No items found.
            {!filterCategory && !filterDocType && (
              <div className="mt-2">
                <Link href="/items/new" className="text-blue-300 hover:underline">Add your first item</Link>
              </div>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-blue-200/30 bg-blue-100/5">
<table className="w-full text-sm">
              <thead>
                <tr className="border-b border-blue-200/20 text-left text-slate-400">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Brand</th>
                  <th className="px-4 py-3 font-medium">Category</th>
                  <th className="px-4 py-3 font-medium">Documents</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-blue-200/10">
                {items.map((item) => (
                  <tr key={item.id} className="text-white hover:bg-blue-100/5">
                    <td className="px-4 py-3">
                      <Link href={`/items/${item.id}`} className="text-blue-300 hover:underline font-medium">
                        {item.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{item.brand || "—"}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {categories.find((c) => c.id === item.category_id)?.name || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        {(item.documents ?? []).length === 0 ? (
                          <span className="text-xs text-slate-500">None</span>
                        ) : (
                          (item.documents ?? []).map((doc) => (
                            <div key={doc.id} className="flex items-center gap-2">
                              {reindexing.has(doc.id) ? (
                                <span className="text-xs text-purple-300 animate-pulse">
                                  ↻ re-indexing…
                                </span>
                              ) : (
                                <span className={`text-xs ${
                                  doc.indexed_status === "indexed" ? "text-emerald-300" :
                                  doc.indexed_status === "failed" ? "text-red-300" :
                                  "text-slate-400"
                                }`}>
                                  {doc.doc_type}
                                  {doc.indexed_status === "indexed" ? " ✓" :
                                   doc.indexed_status === "failed" ? " ✗" :
                                   " …"}
                                </span>
                              )}
                              {doc.doc_type !== "driver" && !reindexing.has(doc.id) && (
                                <button
                                  onClick={() => handleReindex(doc.id, item.id)}
                                  title={`Re-index: ${doc.title}`}
                                  className="text-xs text-purple-300 hover:text-purple-200 hover:underline"
                                >
                                  re-index
                                </button>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="text-xs text-red-300 hover:text-red-200 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-4 text-xs text-slate-500">
          {items.length} item{items.length !== 1 ? "s" : ""} — 
          {loading ? "refreshing…" : `filtered by category${filterDocType ? ` + doc type "${filterDocType}"` : ""}`}
        </p>
      </main>
    </div>
  );
}