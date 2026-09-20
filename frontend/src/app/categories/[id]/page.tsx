import { getItemsForCategory } from "@/lib/api";

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const items = await getItemsForCategory(Number(id));

  return (
    <div className="flex flex-col flex-1 min-h-screen" style={{ backgroundColor: '#0a1628' }}>
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <a href="/" className="text-sm text-slate-400 hover:underline">
          ← Back to dashboard
        </a>
        <div className="mt-2 flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-white">
            Items
          </h1>
          <a
            href={`/items/new?category_id=${id}`}
            className="rounded-md bg-purple-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-purple-600"
          >
            + Add item
          </a>
        </div>

        {items.length === 0 ? (
          <p className="mt-6 text-slate-400">No items in this category yet.</p>
        ) : (
          <ul className="mt-6 divide-y divide-blue-200/20">
            {items.map((item) => (
              <li key={item.id} className="py-4">
                <a href={`/items/${item.id}`} className="block hover:underline">
                  <p className="font-medium text-white">
                    {item.name}
                  </p>
                  <p className="text-sm text-slate-400">
                    {[item.brand, item.model_number].filter(Boolean).join(" · ") || "No brand/model on file"}
                  </p>
                </a>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
