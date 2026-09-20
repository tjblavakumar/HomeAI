"use client";

import { useEffect, useState } from "react";

import {
  createItem,
  getCategories,
  getDocumentsForItem,
  selectDocuments,
  sendChatMessage,
  type Category,
  type Citation,
  type Document,
  type DocumentSuggestion,
  type Item,
} from "@/lib/api";

const DOC_TYPE_LABELS: Record<string, string> = {
  manual: "User Manual",
  troubleshooting: "Troubleshooting Guide",
  driver: "Driver / Software (link only)",
  accessory: "Compatible Accessories",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Downloading…",
  downloaded: "Extracting & indexing…",
  indexed: "Ready",
  failed: "Failed",
  link_only: "Saved (link only)",
};

function groupByType(documents: DocumentSuggestion[]) {
  const groups: Record<string, DocumentSuggestion[]> = {};
  for (const doc of documents) {
    (groups[doc.doc_type] ??= []).push(doc);
  }
  return groups;
}

// ── Lightweight markdown renderer (no external deps) ─────────────
// Handles: **bold**, *italic*, `code`, [1] citation chips, paragraphs,
// ## headings, numbered lists, and bullet lists — enough for LLM replies.

const INLINE_TOKEN_RE = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[\d+(?:,\s*\d+)*\])/g;

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const tokens: React.ReactNode[] = [];
  let lastIndex = 0;
  let i = 0;
  let match: RegExpExecArray | null;
  INLINE_TOKEN_RE.lastIndex = 0;
  while ((match = INLINE_TOKEN_RE.exec(text)) !== null) {
    if (match.index > lastIndex) tokens.push(text.slice(lastIndex, match.index));
    const token = match[0];
    const key = `${keyPrefix}-${i++}`;
    if (token.startsWith("**")) {
      tokens.push(
        <strong key={key} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("`")) {
      tokens.push(
        <code
          key={key}
          className="rounded bg-purple-950/70 px-1.5 py-0.5 font-mono text-[0.85em] text-purple-200"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith("[")) {
      tokens.push(
        <sup
          key={key}
          className="ml-0.5 rounded bg-purple-500/25 px-1.5 py-[1px] align-super text-[0.65rem] font-semibold leading-none text-purple-200"
        >
          {token.slice(1, -1)}
        </sup>
      );
    } else {
      tokens.push(<em key={key} className="text-purple-50">{token.slice(1, -1)}</em>);
    }
    lastIndex = INLINE_TOKEN_RE.lastIndex;
  }
  if (lastIndex < text.length) tokens.push(text.slice(lastIndex));
  return tokens;
}

function MarkdownText({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let listBuffer: { ordered: boolean; items: string[]; startNum?: number } | null = null;

  const flushList = (key: string) => {
    if (!listBuffer) return;
    const { ordered, items, startNum } = listBuffer;
    listBuffer = null;
    const children = items.map((item, idx) => (
      <li key={idx} className="pl-1">
        {renderInline(item, `${key}-li${idx}`)}
      </li>
    ));
    blocks.push(
      ordered ? (
        <ol
          key={key}
          start={startNum ?? 1}
          className="ml-5 list-decimal space-y-1.5 marker:font-semibold marker:text-purple-400"
        >
          {children}
        </ol>
      ) : (
        <ul key={key} className="ml-5 list-disc space-y-1 marker:text-purple-400">
          {children}
        </ul>
      )
    );
  };

  const paraBuffer: string[] = [];
  const flushPara = (key: string) => {
    if (paraBuffer.length === 0) return;
    const joined = paraBuffer.join("\n").trim();
    paraBuffer.length = 0;
    if (!joined) return;
    blocks.push(
      <p key={key} className="leading-relaxed text-purple-100">
        {renderInline(joined, key)}
      </p>
    );
  };

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const trimmed = line.trim();

    // Blank line → flush any open paragraph/list
    if (!trimmed) {
      flushList(`bl-${idx}`);
      flushPara(`bp-${idx}`);
      return;
    }

    // Heading (## / ###)
    const headingMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
    if (headingMatch) {
      flushList(`hl-${idx}`);
      flushPara(`hp-${idx}`);
      blocks.push(
        <h3 key={idx} className="mt-2 text-sm font-semibold text-white">
          {renderInline(headingMatch[2], `h-${idx}`)}
        </h3>
      );
      return;
    }

    // Numbered list item: "1. text" / "1) text"
    const olMatch = trimmed.match(/^(\d+)[.)]\s+(.*)$/);
    if (olMatch) {
      flushPara(`op-${idx}`);
      if (!listBuffer || !listBuffer.ordered) {
        flushList(`ol-${idx}`);
        listBuffer = { ordered: true, items: [], startNum: parseInt(olMatch[1], 10) };
      }
      listBuffer.items.push(olMatch[2]);
      return;
    }

    // Bullet item: "- text" / "* text" / "• text"
    const ulMatch = trimmed.match(/^[-*•]\s+(.*)$/);
    if (ulMatch) {
      flushPara(`up-${idx}`);
      if (!listBuffer || listBuffer.ordered) {
        flushList(`ul-${idx}`);
        listBuffer = { ordered: false, items: [] };
      }
      listBuffer.items.push(ulMatch[1]);
      return;
    }

    // Regular text line → paragraph (flush any open list first)
    flushList(`pl-${idx}`);
    paraBuffer.push(trimmed);
  });

  flushList("fl-end");
  flushPara("fp-end");

  return <div className="space-y-2.5 text-sm">{blocks}</div>;
}

export default function ChatBox({ itemId, mode }: { itemId?: number; mode?: string }) {
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentSuggestion[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // When saving from the dashboard we "adopt" the newly created item so
  // subsequent messages (troubleshoot, find_docs) carry the right item_id.
  const [localItemId, setLocalItemId] = useState<number | undefined>(undefined);
  const effectiveItemId = itemId ?? localItemId;

  // ── Inline "create item & save" form (dashboard chat) ──────────
  const [showItemForm, setShowItemForm] = useState(false);
  const [itemFormName, setItemFormName] = useState("");
  const [itemFormCategoryId, setItemFormCategoryId] = useState<number>(0);
  const [categoriesList, setCategoriesList] = useState<Category[]>([]);
  const [savingNewItem, setSavingNewItem] = useState(false);
  const [newItem, setNewItem] = useState<Item | null>(null);

  // ── Polling for document indexing progress ───────────────────────
  const [polling, setPolling] = useState(false);
  const [docStatuses, setDocStatuses] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!polling || !effectiveItemId) return;
    const interval = setInterval(async () => {
      try {
        const docs: Document[] = await getDocumentsForItem(effectiveItemId);
        const statuses: Record<number, string> = {};
        let allDone = true;
        for (const doc of docs) {
          statuses[doc.id] = doc.indexed_status;
          if (doc.indexed_status === "pending" || doc.indexed_status === "downloaded") {
            allDone = false;
          }
        }
        setDocStatuses(statuses);
        if (allDone) {
          setPolling(false);
        }
      } catch {
        // Network errors shouldn't stop polling; just wait for next tick.
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, effectiveItemId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim()) return;
    setLoading(true);
    setError(null);
    setReply(null);
    setDocuments([]);
    setCitations([]);
    setSelected(new Set());
    setSaved(false);
    setPolling(false);
    setDocStatuses({});
    setShowItemForm(false);
    setNewItem(null);
    setCategoriesList([]);
    setLocalItemId(undefined);
    try {
      const response = await sendChatMessage(message, effectiveItemId, mode);
      setReply(response.reply);
      setDocuments(response.documents);
      setCitations(response.citations);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function toggle(url: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

  async function handleSave() {
    if (!itemId) return;
    setSaving(true);
    setError(null);
    try {
      const toSave = documents.filter((d) => selected.has(d.source_url));
      const savedDocs = await selectDocuments(itemId, toSave);
      setSaved(true);
      setSelected(new Set());

      // Start polling for indexing progress on the just-saved documents
      const initial: Record<number, string> = {};
      for (const doc of savedDocs) {
        initial[doc.id] = doc.indexed_status;
      }
      setDocStatuses(initial);
      setPolling(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save documents.");
    } finally {
      setSaving(false);
    }
  }
// ── Helpers & handlers for "Save to new item" (dashboard) ──────
  function guessProductName(): string {
    // Try extracting from reply: "Here's what I found for XXX."
    const match = reply?.match(/found for (.+?)\./);
    if (match) return match[1].trim();
    // Fallback: first doc title
    if (documents.length > 0) {
      const title = documents[0].title;
      const cleaned = title
        .replace(/ (Owner'?s Manual|User Manual|Manual|Troubleshooting|Guide|PDF|Download).*/i, "")
        .trim();
      if (cleaned) return cleaned;
    }
    return "";
  }

  async function handleOpenItemForm() {
    setShowItemForm(true);
    setItemFormName(guessProductName());
    try {
      const cats = await getCategories();
      setCategoriesList(cats);
      // Default to first category or "Other" (id 5 from seed)
      const other = cats.find((c) => c.name === "Other");
      setItemFormCategoryId(other?.id ?? cats[0]?.id ?? 0);
    } catch {
      // Offline — categories will stay empty
    }
  }

  async function handleSaveToNewItem() {
    if (!itemFormName.trim() || !itemFormCategoryId) return;
    setSavingNewItem(true);
    setError(null);
    try {
      const item = await createItem({
        name: itemFormName.trim(),
        category_id: itemFormCategoryId,
      });
      // Adopt the newly created item so subsequent chat uses its ID
      setLocalItemId(item.id);
      const toSave = documents.filter((d) => selected.has(d.source_url));
      const savedDocs = await selectDocuments(item.id, toSave);
      setNewItem(item);
      setSaved(true);
      setSelected(new Set());
      setShowItemForm(false);

      // Start polling for indexing progress
      const initial: Record<number, string> = {};
      for (const doc of savedDocs) {
        initial[doc.id] = doc.indexed_status;
      }
      setDocStatuses(initial);
      setPolling(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setSavingNewItem(false);
    }
  }

  const grouped = groupByType(documents);
  const isPolling = polling && Object.keys(docStatuses).length > 0;
  const statusEntries = Object.entries(docStatuses);

  return (
    <div className="mt-10 rounded-lg border border-purple-400/30 p-6" style={{ backgroundColor: '#2d1b4e' }}>
      <h2 className="text-lg font-semibold text-white">
        {mode === "rag" ? "Ask HomeAI — Your Local Knowledge Base" : "Ask HomeAI"}
      </h2>
      <p className="mt-1 text-sm text-purple-200">
        {mode === "rag"
          ? "Ask questions about your household items — answers come from your saved and indexed manuals only."
          : mode === "discovery"
          ? 'Search the web for manuals, drivers, and accessories for your items.'
          : itemId
          ? 'e.g. "why won\'t this turn on?" (answers come from this item\'s saved manuals)'
          : 'e.g. "find the user manual for the Ninja CAFE Luxe3 I bought from Costco"'}
      </p>

      <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={
              mode === "rag"
                ? "Ask a question about your saved manuals…"
                : mode === "discovery"
                ? "Find manuals, drivers, or accessories…"
                : "What do you want to find or fix?"
            }
          className="flex-1 rounded-md border border-purple-300/30 bg-purple-950/40 px-3 py-2 text-white placeholder-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-400"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-purple-600 px-4 py-2 font-medium text-white hover:bg-purple-500 disabled:opacity-50"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {error && (
        <p className="mt-4 rounded-md bg-red-900/60 px-4 py-3 text-sm text-red-200">
          {error}
        </p>
      )}

      {reply && (
        <div className="mt-4 rounded-md border border-purple-400/20 bg-purple-950/40 p-4">
          <MarkdownText text={reply} />
        </div>
      )}

      {citations.length > 0 && mode !== "discovery" && (
        <div className="mt-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-purple-300">
            Sources
          </h3>
          <ul className="mt-1 flex flex-col gap-1">
            {citations.map((citation) => (
              <li key={citation.source_url}>
                <a
                  href={citation.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-300 hover:underline"
                >
                  {citation.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Documents to select ───────────────────────────────── */}
      {documents.length > 0 && mode !== "rag" && (
        <div className="mt-4 flex flex-col gap-4">
          {Object.entries(grouped).map(([docType, docs]) => (
            <div key={docType}>
              <h3 className="text-sm font-semibold text-purple-200">
                {DOC_TYPE_LABELS[docType] ?? docType}
              </h3>
              <ul className="mt-2 flex flex-col gap-1">
                {docs.map((doc) => (
                  <li key={doc.source_url} className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-1 accent-purple-500"
                      checked={selected.has(doc.source_url)}
                      disabled={docType === "driver"}
                      onChange={() => toggle(doc.source_url)}
                    />
                    <a
                      href={doc.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-300 hover:underline"
                    >
                      {doc.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {itemId ? (
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || selected.size === 0}
              className="mt-2 w-fit rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50"
            >
              {saving ? "Saving…" : `Save selected (${selected.size})`}
            </button>
          ) : !showItemForm ? (
            <button
              type="button"
              onClick={handleOpenItemForm}
              disabled={selected.size === 0}
              className="mt-2 w-fit rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50"
            >
              Save selected ({selected.size}) to a new item…
            </button>
          ) : (
            <div className="mt-2 flex flex-col gap-3 rounded-md border border-purple-400/30 bg-purple-950/40 p-3">
              <h4 className="text-sm font-semibold text-purple-200">
                Create item & save documents
              </h4>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-purple-300">Item name</span>
                <input
                  value={itemFormName}
                  onChange={(e) => setItemFormName(e.target.value)}
                  className="rounded-md border border-purple-300/30 bg-purple-950/60 px-2 py-1.5 text-sm text-white placeholder-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-400"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-purple-300">Category</span>
                <select
                  value={itemFormCategoryId}
                  onChange={(e) => setItemFormCategoryId(Number(e.target.value))}
                  className="rounded-md border border-purple-300/30 bg-purple-950/60 px-2 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-400"
                >
                  {categoriesList.map((c) => (
                    <option key={c.id} value={c.id} className="bg-[#2d1b4e] text-white">
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowItemForm(false)}
                  disabled={savingNewItem}
                  className="rounded-md border border-purple-400/40 px-3 py-1.5 text-sm text-purple-200 hover:bg-purple-950/60 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveToNewItem}
                  disabled={savingNewItem || !itemFormName.trim()}
                  className="rounded-md bg-purple-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50"
                >
                  {savingNewItem ? "Creating & saving…" : "Create & Save"}
                </button>
              </div>
            </div>
          )}

          {saved && !isPolling && (
            <div className="text-sm text-emerald-300">
              {newItem ? (
                <p>
                  ✅ <span className="font-medium">{newItem.name}</span> created
                  with documents saved and indexing.
                  <br />
                  <a
                    href={`/items/${newItem.id}`}
                    className="font-medium underline hover:text-emerald-200"
                  >
                    View item page
                  </a>{" "}
                  — or just ask a question here (it will target this item).
                </p>
              ) : (
                <p>Saved — documents are being indexed in the background.</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Progress bars for indexing ────────────────────────── */}
      {isPolling && statusEntries.length > 0 && (
        <div className="mt-4 space-y-2">
          <h3 className="text-sm font-semibold text-purple-200">
            Indexing progress
          </h3>
          {statusEntries.map(([id, status]) => {
            const isActive = status === "pending" || status === "downloaded";
            return (
              <div key={id}>
                <div className="flex items-center justify-between text-xs text-purple-300">
                  <span>Document #{id}</span>
                  <span>{STATUS_LABELS[status] ?? status}</span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-purple-950/60">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      status === "indexed"
                        ? "w-full bg-emerald-500"
                        : status === "failed"
                        ? "w-full bg-red-500"
                        : "w-2/3 animate-pulse bg-purple-400"
                    }`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
