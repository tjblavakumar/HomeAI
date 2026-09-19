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
    <div className="flex flex-col flex-1 min-h-screen bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <a href={`/categories/${item.category_id}`} className="text-sm text-zinc-500 hover:underline">
          ← Back to items
        </a>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          {item.name}
        </h1>

        <dl className="mt-6 divide-y divide-zinc-200 rounded-lg border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
          {fields.map(([label, value]) => (
            <div key={label} className="flex justify-between px-4 py-3">
              <dt className="text-sm text-zinc-500">{label}</dt>
              <dd className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                {value || "—"}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-8">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            Manuals & documents
          </h2>
          {documents.length === 0 ? (
            <div className="mt-3 rounded-lg border border-dashed border-zinc-300 p-6 text-center text-zinc-500 dark:border-zinc-700">
              No documents saved yet — use the chat box below to find and save some.
            </div>
          ) : (
            <ul className="mt-3 divide-y divide-zinc-200 rounded-lg border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <a
                      href={doc.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-blue-700 hover:underline dark:text-blue-400"
                    >
                      {doc.title}
                    </a>
                    <p className="text-xs text-zinc-500">{doc.doc_type}</p>
                  </div>
                  <span className="text-xs text-zinc-500">
                    {STATUS_LABELS[doc.indexed_status] ?? doc.indexed_status}
                  </span>
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
