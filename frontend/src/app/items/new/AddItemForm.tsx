"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createItem, scanItemPhoto, type Category } from "@/lib/api";

export default function AddItemForm({
  categories,
  defaultCategoryId,
}: {
  categories: Category[];
  defaultCategoryId?: number;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [barcodes, setBarcodes] = useState<string[]>([]);

  async function handleScan(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanning(true);
    setScanError(null);
    try {
      const result = await scanItemPhoto(file);
      if (result.guessed_name) setName(result.guessed_name);
      if (result.raw_text) setNotes(result.raw_text);
      setBarcodes(result.barcodes);
    } catch (err) {
      setScanError(err instanceof Error ? err.message : "Could not scan photo.");
    } finally {
      setScanning(false);
      e.target.value = "";
    }
  }

  async function handleSubmit(formData: FormData) {
    setSubmitting(true);
    setError(null);
    try {
      const item = await createItem({
        name: String(formData.get("name")),
        brand: String(formData.get("brand") || "") || undefined,
        model_number: String(formData.get("model_number") || "") || undefined,
        category_id: Number(formData.get("category_id")),
        purchase_store: String(formData.get("purchase_store") || "") || undefined,
        purchase_date: String(formData.get("purchase_date") || "") || undefined,
        notes: String(formData.get("notes") || "") || undefined,
      });
      router.push(`/items/${item.id}`);
      router.refresh();
    } catch {
      setError("Could not save item. Please check the backend is running and try again.");
      setSubmitting(false);
    }
  }

  return (
    <form action={handleSubmit} className="mt-6 flex flex-col gap-4">
      <div className="rounded-md border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Scan a label, receipt, or barcode (optional)
        </span>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleScan}
          disabled={scanning}
          className="mt-2 block text-sm text-zinc-600 dark:text-zinc-400"
        />
        {scanning && <p className="mt-2 text-sm text-zinc-500">Scanning…</p>}
        {scanError && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{scanError}</p>}
        {barcodes.length > 0 && (
          <p className="mt-2 text-sm text-zinc-500">Barcode(s) found: {barcodes.join(", ")}</p>
        )}
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Name *</span>
        <input
          name="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Ninja CAFE Luxe3"
          className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Category *</span>
        <select
          name="category_id"
          required
          defaultValue={defaultCategoryId}
          className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
        >
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Brand</span>
          <input
            name="brand"
            placeholder="e.g. Ninja"
            className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Model number</span>
          <input
            name="model_number"
            placeholder="e.g. CAFE Luxe3"
            className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Purchased from</span>
          <input
            name="purchase_store"
            placeholder="e.g. Costco"
            className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Purchase date</span>
          <input
            type="date"
            name="purchase_date"
            className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Notes</span>
        <textarea
          name="notes"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="mt-2 rounded-md bg-zinc-900 px-4 py-2 font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {submitting ? "Saving…" : "Save item"}
      </button>
    </form>
  );
}
