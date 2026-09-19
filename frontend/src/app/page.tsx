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
    <div className="flex flex-col flex-1 min-h-screen bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
              HomeAI — Household Knowledge Base
            </h1>
            <p className="mt-1 text-zinc-600 dark:text-zinc-400">
              Your household&apos;s items, manuals, and troubleshooting assistant.
            </p>
          </div>
          <a
            href="/items/new"
            className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium whitespace-nowrap text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
          >
            + Add item
          </a>
        </div>

        {error && (
          <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
          {categories.map((category) => (
            <a
              key={category.id}
              href={`/categories/${category.id}`}
              className="flex flex-col items-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-6 text-center shadow-sm transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
            >
              <span className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
                {category.item_count}
              </span>
              <span className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
                {category.name}
              </span>
            </a>
          ))}
        </div>

        <ChatBox />
      </main>
    </div>
  );
}

