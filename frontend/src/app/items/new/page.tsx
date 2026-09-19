import { getCategories } from "@/lib/api";

import AddItemForm from "./AddItemForm";

export default async function NewItemPage({
  searchParams,
}: {
  searchParams: Promise<{ category_id?: string }>;
}) {
  const { category_id } = await searchParams;
  const categories = await getCategories();

  return (
    <div className="flex flex-col flex-1 min-h-screen bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12">
        <a href="/" className="text-sm text-zinc-500 hover:underline">
          ← Back to dashboard
        </a>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Add an item
        </h1>
        <AddItemForm
          categories={categories}
          defaultCategoryId={category_id ? Number(category_id) : undefined}
        />
      </main>
    </div>
  );
}
