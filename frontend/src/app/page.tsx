import ChatBox from "@/components/ChatBox";
import { getCategories, type Category } from "@/lib/api";

export default async function Home() {
  let categories: Category[];
  let error: string | null = null;
  try {
    categories = await getCategories();
  } catch {
    categories = [];
    error = "Could not reach the HomeAI backend. Is it running on port 8000?";
  }

  return (
    <div className="flex flex-col flex-1 min-h-screen" style={{ backgroundColor: '#0a1628' }}>
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              HomeAI — Household Knowledge Base
            </h1>
            <p className="mt-1 text-slate-300">
              Ask questions about your household items, or browse categories below.
            </p>
          </div>
          <a
            href="/items/new"
            className="rounded-md bg-purple-700 px-3 py-1.5 text-sm font-medium whitespace-nowrap text-white hover:bg-purple-600"
          >
            + Add item
          </a>
        </div>

        {error && (
          <p className="mt-6 rounded-md bg-red-900/60 px-4 py-3 text-red-200">
            {error}
          </p>
        )}

        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
          {categories.map((category) => (
            <a
              key={category.id}
              href={`/categories/${category.id}`}
              className="flex flex-col items-center gap-2 rounded-lg border border-blue-200 bg-blue-100 px-4 py-6 text-center shadow-sm transition hover:shadow-md"
            >
              <span className="text-3xl font-bold text-slate-800">
                {category.item_count}
              </span>
              <span className="text-sm font-medium text-slate-700">
                {category.name}
              </span>
            </a>
          ))}
        </div>

        <ChatBox mode="rag" />
      </main>
    </div>
  );
}

