import { getCategories } from "@/lib/api";

import AddItemForm from "./AddItemForm";
import ChatBox from "@/components/ChatBox";

export default async function NewItemPage({
  searchParams,
}: {
  searchParams: Promise<{ category_id?: string }>;
}) {
  const { category_id } = await searchParams;
  const categories = await getCategories();

  return (
    <div className="flex flex-col flex-1 min-h-screen" style={{ backgroundColor: '#0a1628' }}>
      <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12">
        <a href="/" className="text-sm text-slate-400 hover:underline">
          ← Back to dashboard
        </a>
        <h1 className="mt-2 text-2xl font-semibold text-white">
          Add an item
        </h1>
        <AddItemForm
          categories={categories}
          defaultCategoryId={category_id ? Number(category_id) : undefined}
        />

        <div className="mt-10 border-t border-blue-200/20 pt-8">
          <h2 className="text-lg font-semibold text-white">
            Find manuals & documents
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Search the web for manuals, drivers, and accessories. You can save them
            to a new item or to an existing item from its detail page.
          </p>
          <ChatBox mode="discovery" />
        </div>
      </main>
    </div>
  );
}
