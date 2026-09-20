"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createItem, createItemFromUrl, scanItemPhoto, uploadItemPdf, type Category } from "@/lib/api";

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
  const [url, setUrl] = useState("");
  const [urlMode, setUrlMode] = useState(false);
  const [urlSubmitting, setUrlSubmitting] = useState(false);
  const [urlName, setUrlName] = useState("");
  const [urlBrand, setUrlBrand] = useState("");
  const [urlModel, setUrlModel] = useState("");
  const [urlCategoryId, setUrlCategoryId] = useState<number>(defaultCategoryId ?? categories[0]?.id ?? 0);
  const [uploadMode, setUploadMode] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [uploadBrand, setUploadBrand] = useState("");
  const [uploadModel, setUploadModel] = useState("");
  const [uploadCategoryId, setUploadCategoryId] = useState<number>(defaultCategoryId ?? categories[0]?.id ?? 0);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);

  function autoNameFromUrl(rawUrl: string) {
    try {
      const path = new URL(rawUrl).pathname;
      const file = path.split("/").filter(Boolean).pop() || "";
      const stem = file.replace(/\.(pdf|html?)$/i, "").replace(/[_-]/g, " ");
      const titled = stem.split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
      setUrlName(titled || "");
    } catch { /* invalid URL */ }
  }

  function autoNameFromFile(file: File | null) {
    if (!file) return;
    const stem = file.name.replace(/\.pdf$/i, "").replace(/[_-]/g, " ");
    const titled = stem.split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
    setUploadName(titled || "");
  }

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

  async function handleUrlSubmit() {
    if (!url.trim()) return;
    setUrlSubmitting(true);
    setError(null);
    try {
      const item = await createItemFromUrl({
        url: url.trim(), name: urlName.trim() || "Manual from URL",
        category_id: urlCategoryId, brand: urlBrand.trim() || undefined,
        model_number: urlModel.trim() || undefined,
      });
      router.push(`/items/${item.id}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add item from URL.");
      setUrlSubmitting(false);
    }
  }

  async function handleUploadSubmit() {
    if (!uploadFile) return;
    setUploadSubmitting(true);
    setError(null);
    try {
      const item = await uploadItemPdf({
        file: uploadFile, name: uploadName.trim() || uploadFile.name.replace(/\.pdf$/i, ""),
        category_id: uploadCategoryId, brand: uploadBrand.trim() || undefined,
        model_number: uploadModel.trim() || undefined,
      });
      router.push(`/items/${item.id}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload PDF.");
      setUploadSubmitting(false);
    }
  }

return (
    <form action={handleSubmit} className="mt-6 flex flex-col gap-4">
      <div className="rounded-md border border-dashed border-blue-200/30 bg-blue-100/10 p-4">
        <span className="text-sm font-medium text-slate-200">Scan a label, receipt, or barcode (optional)</span>
        <input type="file" accept="image/*" capture="environment" onChange={handleScan} disabled={scanning} className="mt-2 block text-sm text-slate-300" />
        {scanning && <p className="mt-2 text-sm text-slate-400">Scanning&hellip;</p>}
        {scanError && <p className="mt-2 text-sm text-red-300">{scanError}</p>}
        {barcodes.length > 0 && <p className="mt-2 text-sm text-slate-400">Barcode(s) found: {barcodes.join(", ")}</p>}
      </div>

      <div className="rounded-md border border-purple-200/30 bg-purple-100/10 p-4">
        <button type="button" onClick={() => setUrlMode(!urlMode)} className="text-sm font-medium text-purple-300 hover:text-purple-200">
          {urlMode ? "&minus; Hide" : "+ Add from URL"}
        </button>
        {urlMode && <div className="mt-3 flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-300">PDF / manual URL *</span>
            <input type="url" value={url} onChange={(e) => { setUrl(e.target.value); autoNameFromUrl(e.target.value); }} placeholder="https://example.com/manual.pdf" className="rounded-md border border-purple-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Item name</span>
              <input type="text" value={urlName} onChange={(e) => setUrlName(e.target.value)} placeholder="e.g. Tesla Model 3" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Category *</span>
              <select value={urlCategoryId} onChange={(e) => setUrlCategoryId(Number(e.target.value))} className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500">
                {categories.map((cat) => <option key={cat.id} value={cat.id} className="bg-[#0a1628] text-white">{cat.name}</option>)}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Brand</span>
              <input type="text" value={urlBrand} onChange={(e) => setUrlBrand(e.target.value)} placeholder="e.g. Tesla" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Model number</span>
              <input type="text" value={urlModel} onChange={(e) => setUrlModel(e.target.value)} placeholder="e.g. Model 3" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
            </label>
          </div>
          <button type="button" onClick={handleUrlSubmit} disabled={urlSubmitting || !url.trim()} className="self-start rounded-md bg-purple-700 px-4 py-2 text-sm font-medium text-white hover:bg-purple-600 disabled:opacity-50">
            {urlSubmitting ? "Downloading &amp; Indexing&hellip;" : "Add &amp; Index"}
          </button>
        </div>}
      </div>
<div className="rounded-md border border-emerald-200/30 bg-emerald-100/10 p-4">
        <button type="button" onClick={() => setUploadMode(!uploadMode)} className="text-sm font-medium text-emerald-300 hover:text-emerald-200">
          {uploadMode ? "&minus; Hide" : "+ Upload PDF file"}
        </button>
        {uploadMode && <div className="mt-3 flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-300">PDF file *</span>
            <input type="file" accept=".pdf,application/pdf" onChange={(e) => { const f = e.target.files?.[0] ?? null; setUploadFile(f); autoNameFromFile(f); }} className="mt-1 block text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-emerald-700 file:px-3 file:py-1 file:text-sm file:font-medium file:text-white hover:file:bg-emerald-600" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Item name</span>
              <input type="text" value={uploadName} onChange={(e) => setUploadName(e.target.value)} placeholder="e.g. Tesla Model 3" className="rounded-md border border-emerald-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Category *</span>
              <select value={uploadCategoryId} onChange={(e) => setUploadCategoryId(Number(e.target.value))} className="rounded-md border border-emerald-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500">
                {categories.map((cat) => <option key={cat.id} value={cat.id} className="bg-[#0a1628] text-white">{cat.name}</option>)}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Brand</span>
              <input type="text" value={uploadBrand} onChange={(e) => setUploadBrand(e.target.value)} placeholder="e.g. Tesla" className="rounded-md border border-emerald-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-slate-300">Model number</span>
              <input type="text" value={uploadModel} onChange={(e) => setUploadModel(e.target.value)} placeholder="e.g. Model 3" className="rounded-md border border-emerald-200/30 bg-blue-100/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500" />
            </label>
          </div>
          {uploadFile && <p className="text-xs text-slate-400">Selected: {uploadFile.name} ({(uploadFile.size / 1024).toFixed(0)} KB)</p>}
          <button type="button" onClick={handleUploadSubmit} disabled={uploadSubmitting || !uploadFile} className="self-start rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
            {uploadSubmitting ? "Uploading &amp; Indexing&hellip;" : "Upload &amp; Index"}
          </button>
        </div>}
      </div>
<label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-slate-200">Name *</span>
        <input name="name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ninja CAFE Luxe3" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-slate-200">Category *</span>
        <select name="category_id" required defaultValue={defaultCategoryId} className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500">
          {categories.map((cat) => <option key={cat.id} value={cat.id} className="bg-[#0a1628] text-white">{cat.name}</option>)}
        </select>
      </label>

      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-slate-200">Brand</span>
          <input name="brand" placeholder="e.g. Ninja" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-slate-200">Model number</span>
          <input name="model_number" placeholder="e.g. CAFE Luxe3" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-slate-200">Purchased from</span>
          <input name="purchase_store" placeholder="e.g. Costco" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-slate-200">Purchase date</span>
          <input type="date" name="purchase_date" className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500" />
        </label>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-slate-200">Notes</span>
        <textarea name="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className="rounded-md border border-blue-200/30 bg-blue-100/10 px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500" />
      </label>

      {error && <p className="text-sm text-red-300">{error}</p>}

      <button type="submit" disabled={submitting} className="mt-2 rounded-md bg-purple-700 px-4 py-2 font-medium text-white hover:bg-purple-600 disabled:opacity-50">
        {submitting ? "Saving&hellip;" : "Save item"}
      </button>
    </form>
  );
}