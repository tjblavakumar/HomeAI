import ChatBox from "@/components/ChatBox";
import { getDocumentsForItem, getItem } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending: "Downloading…",
  downloaded: "Extracting…",
  indexed: "Ready for troubleshooting chat",
  failed: "Failed to index (check backend logs / API key)",
  link_only: "Link saved (not downloaded/indexed)",
};

export default async function ItemDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const item = await getItem(Number(id));
  const documents = await getDocumentsForItem(Number(id));

  const fields: [string, string | null][] = [
    ["Brand", item.brand],
    ["Model number", item.model_number],
    ["Purchased from", item.purchase_store],
    ["Purchase date", item.purchase_date],
    ["Notes", item.notes],
  ];

  return (
    <div className="flex flex-col flex-1 min-h-screen" style={{ backgroundColor: '#0a1628' }}>
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <a href={`/categories/${item.category_id}`} className="text-sm text-slate-400 hover:underline">
          ← Back to items
        </a>
        <h1 className="mt-2 text-2xl font-semibold text-white">
          {item.name}
        </h1>

        <dl className="mt-6 divide-y divide-blue-200/30 rounded-lg border border-blue-200/40 bg-blue-100/20">
          {fields.map(([label, value]) => (
            <div key={label} className="flex justify-between px-4 py-3">
              <dt className="text-sm text-slate-300">{label}</dt>
              <dd className="text-sm font-medium text-white">
                {value || "—"}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-8">
          <h2 className="text-lg font-semibold text-white">
            Manuals & documents
          </h2>
          {documents.length === 0 ? (
            <div className="mt-3 rounded-lg border border-dashed border-blue-200/30 p-6 text-center text-slate-400">
              No documents saved yet — use the chat box below to find and save some.
            </div>
          ) : (
            <ul className="mt-3 divide-y divide-blue-200/30 rounded-lg border border-blue-200/40 bg-blue-100/20">
              {documents.map((doc) => (
                <li key={doc.id} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <a
                        href={doc.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-blue-300 hover:underline"
                      >
                        {doc.title}
                      </a>
                      <p className="text-xs text-slate-400">{doc.doc_type}</p>
                    </div>
                    <span className={`text-xs font-medium ${
                      doc.indexed_status === "indexed" ? "text-emerald-300" :
                      doc.indexed_status === "failed" ? "text-red-300" :
                      doc.indexed_status === "link_only" ? "text-purple-300" :
                      "text-slate-400"
                    }`}>
                      {STATUS_LABELS[doc.indexed_status] ?? doc.indexed_status}
                    </span>
                  </div>
                  {doc.local_path && (
                    <p className="mt-1 text-xs text-slate-500">
                      File: <code className="bg-blue-950/40 px-1 rounded">{doc.local_path}</code>
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <ChatBox itemId={item.id} />
      </main>
    </div>
  );
}
