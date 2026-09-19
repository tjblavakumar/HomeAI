// On the server (SSR), calls stay on localhost since the backend runs on the same
// machine. In the browser, default to the page's own hostname so devices on the LAN
// reach the backend on this machine instead of trying "localhost" on themselves.
function resolveApiUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export const API_URL = resolveApiUrl();

export type Category = {
  id: number;
  name: string;
  icon: string;
  is_custom: boolean;
  item_count: number;
};

export type Item = {
  id: number;
  name: string;
  brand: string | null;
  model_number: string | null;
  category_id: number;
  purchase_store: string | null;
  purchase_date: string | null;
  photo_path: string | null;
  notes: string | null;
  created_at: string;
};

export type ItemCreate = {
  name: string;
  brand?: string;
  model_number?: string;
  category_id: number;
  purchase_store?: string;
  purchase_date?: string;
  notes?: string;
};

export type DocumentSuggestion = {
  doc_type: "manual" | "troubleshooting" | "driver" | "accessory" | string;
  title: string;
  source_url: string;
  reason?: string | null;
};

export type Citation = {
  title: string;
  source_url: string;
};

export type ChatResponse = {
  reply: string;
  intent: string;
  documents: DocumentSuggestion[];
  citations: Citation[];
};

export async function sendChatMessage(message: string, itemId?: number): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, item_id: itemId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Chat request failed");
  }
  return res.json();
}

export async function getCategories(): Promise<Category[]> {
  const res = await fetch(`${API_URL}/categories`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load categories");
  return res.json();
}

export async function getItemsForCategory(categoryId: number): Promise<Item[]> {
  const res = await fetch(`${API_URL}/categories/${categoryId}/items`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load items");
  return res.json();
}

export async function getItem(itemId: number): Promise<Item> {
  const res = await fetch(`${API_URL}/items/${itemId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load item");
  return res.json();
}

export async function createItem(payload: ItemCreate): Promise<Item> {
  const res = await fetch(`${API_URL}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create item");
  return res.json();
}

export type Document = {
  id: number;
  item_id: number;
  doc_type: string;
  title: string;
  source_url: string;
  local_path: string | null;
  indexed_status: "pending" | "downloaded" | "indexed" | "failed" | "link_only" | string;
  selected_at: string;
};

export async function getDocumentsForItem(itemId: number): Promise<Document[]> {
  const res = await fetch(`${API_URL}/items/${itemId}/documents`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load documents");
  return res.json();
}

export async function selectDocuments(
  itemId: number,
  documents: DocumentSuggestion[]
): Promise<Document[]> {
  const res = await fetch(`${API_URL}/documents/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      item_id: itemId,
      documents: documents.map((d) => ({
        doc_type: d.doc_type,
        title: d.title,
        source_url: d.source_url,
      })),
    }),
  });
  if (!res.ok) throw new Error("Failed to save selected documents");
  return res.json();
}

export type ScanResult = {
  raw_text: string;
  barcodes: string[];
  guessed_name: string | null;
};

export async function scanItemPhoto(file: File): Promise<ScanResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/items/scan`, { method: "POST", body: formData });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "Failed to scan photo");
  }
  return res.json();
}
