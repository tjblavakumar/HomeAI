"use client";

import { useState } from "react";

import { selectDocuments, sendChatMessage, type Citation, type DocumentSuggestion } from "@/lib/api";

const DOC_TYPE_LABELS: Record<string, string> = {
  manual: "User Manual",
  troubleshooting: "Troubleshooting Guide",
  driver: "Driver / Software (link only)",
  accessory: "Compatible Accessories",
};

function groupByType(documents: DocumentSuggestion[]) {
  const groups: Record<string, DocumentSuggestion[]> = {};
  for (const doc of documents) {
    (groups[doc.doc_type] ??= []).push(doc);
  }
  return groups;
}

export default function ChatBox({ itemId }: { itemId?: number }) {
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentSuggestion[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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
    try {
      const response = await sendChatMessage(message, itemId);
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
      await selectDocuments(itemId, toSave);
      setSaved(true);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save documents.");
    } finally {
      setSaving(false);
    }
  }

  const grouped = groupByType(documents);

  return (
    <div className="mt-10 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
        Ask HomeAI
      </h2>
      <p className="mt-1 text-sm text-zinc-500">
        {itemId
          ? 'e.g. "why won\'t this turn on?" (answers come from this item\'s saved manuals)'
          : 'e.g. "find the user manual for the Ninja CAFE Luxe3 I bought from Costco"'}
      </p>

      <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="What do you want to find or fix?"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-zinc-900 px-4 py-2 font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {error && (
        <p className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {reply && <p className="mt-4 text-sm text-zinc-700 dark:text-zinc-300">{reply}</p>}

      {citations.length > 0 && (
        <div className="mt-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Sources
          </h3>
          <ul className="mt-1 flex flex-col gap-1">
            {citations.map((citation) => (
              <li key={citation.source_url}>
                <a
                  href={citation.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-700 hover:underline dark:text-blue-400"
                >
                  {citation.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {documents.length > 0 && (
        <div className="mt-4 flex flex-col gap-4">
          {Object.entries(grouped).map(([docType, docs]) => (
            <div key={docType}>
              <h3 className="text-sm font-semibold text-zinc-600 dark:text-zinc-400">
                {DOC_TYPE_LABELS[docType] ?? docType}
              </h3>
              <ul className="mt-2 flex flex-col gap-1">
                {docs.map((doc) => (
                  <li key={doc.source_url} className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={selected.has(doc.source_url)}
                      disabled={docType === "driver"}
                      onChange={() => toggle(doc.source_url)}
                    />
                    <a
                      href={doc.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-700 hover:underline dark:text-blue-400"
                    >
                      {doc.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          <button
            type="button"
            onClick={handleSave}
            disabled={!itemId || saving || selected.size === 0}
            title={itemId ? undefined : "Open this chat from an item's page to save documents to it"}
            className="mt-2 w-fit rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {saving ? "Saving…" : `Save selected (${selected.size})`}
          </button>
          {saved && (
            <p className="text-sm text-emerald-600 dark:text-emerald-400">
              Saved — manuals will be indexed in the background; refresh to see status.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
