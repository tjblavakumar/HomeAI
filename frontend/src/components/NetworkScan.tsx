"use client";

import { useEffect, useRef, useState } from "react";

import {
  addDeviceManuals,
  downloadDeviceDrivers,
  getDeviceDownloads,
  getDevices,
  scanNetwork,
  suggestDeviceDocs,
  updateDevice,
  type Device,
  type DeviceSuggestion,
  type DriverDownload,
} from "@/lib/api";

const DEVICE_ICONS: Record<string, string> = {
  printer: "🖨️",
  router: "📶",
  nas: "🗄️",
  computer: "💻",
  phone: "📱",
  tv: "📺",
  speaker: "🔊",
  camera: "📷",
  iot: "🔆",
  generic: "🔌",
};

const DOC_TYPE_LABELS: Record<string, string> = {
  manual: "User Manuals",
  troubleshooting: "Troubleshooting Guides",
  driver: "Drivers / Software",
  accessory: "Compatible Accessories",
};

const DOWNLOAD_STATUS_LABELS: Record<string, string> = {
  pending: "Downloading…",
  downloaded: "Saved to server",
  failed: "Failed",
};

function deviceTitle(device: Device): string {
  if (device.label) return device.label;
  if (device.vendor) return `${device.vendor} device`;
  if (device.hostname) return device.hostname.replace(/\.(local|lan|home)\.?$/i, "");
  return `Unknown device (${device.ip})`;
}

function isManualType(t: string) {
  return t === "manual" || t === "troubleshooting";
}

// ── Per-device card ──────────────────────────────────────────────────

function DeviceCard({
  device,
  onChanged,
}: {
  device: Device;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [loadingSuggest, setLoadingSuggest] = useState(false);
  const [suggestions, setSuggestions] = useState<DeviceSuggestion[] | null>(null);
  const [suggestMessage, setSuggestMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedManuals, setSelectedManuals] = useState<Set<string>>(new Set());
  const [selectedDrivers, setSelectedDrivers] = useState<Set<string>>(new Set());

  const [addingManuals, setAddingManuals] = useState(false);
  const [manualsResult, setManualsResult] = useState<{ itemId: number } | null>(null);

  const [downloading, setDownloading] = useState(false);
  const [downloads, setDownloads] = useState<DriverDownload[]>([]);
  const [pollingDownloads, setPollingDownloads] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll driver-download progress until every download leaves "pending".
  useEffect(() => {
    if (!pollingDownloads) return;
    const interval = setInterval(async () => {
      try {
        const rows = await getDeviceDownloads(device.id);
        setDownloads(rows);
        if (rows.every((r) => r.status !== "pending")) {
          setPollingDownloads(false);
        }
      } catch {
        // transient — keep polling
      }
    }, 2000);
    pollRef.current = interval;
    return () => clearInterval(interval);
  }, [pollingDownloads, device.id]);

  async function handleSuggest() {
    setExpanded(true);
    setLoadingSuggest(true);
    setError(null);
    setSuggestMessage(null);
    try {
      const res = await suggestDeviceDocs(device.id);
      setSuggestions(res.suggestions);
      setSuggestMessage(res.message ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to find suggestions");
    } finally {
      setLoadingSuggest(false);
    }
  }

  function toggle(set: Set<string>, url: string): Set<string> {
    const next = new Set(set);
    if (next.has(url)) next.delete(url);
    else next.add(url);
    return next;
  }

  async function handleAddManuals() {
    if (!suggestions) return;
    const manuals = suggestions.filter(
      (s) => isManualType(s.doc_type) && selectedManuals.has(s.source_url)
    );
    if (manuals.length === 0) return;
    setAddingManuals(true);
    setError(null);
    try {
      const res = await addDeviceManuals(device.id, manuals);
      setManualsResult({ itemId: res.item_id });
      setSelectedManuals(new Set());
      onChanged(); // refresh badges (device is now linked)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add manuals");
    } finally {
      setAddingManuals(false);
    }
  }

  async function handleDownloadDrivers() {
    if (!suggestions) return;
    const drivers = suggestions.filter(
      (s) => s.doc_type === "driver" && selectedDrivers.has(s.source_url)
    );
    if (drivers.length === 0) return;
    setDownloading(true);
    setError(null);
    try {
      const rows = await downloadDeviceDrivers(device.id, drivers);
      setDownloads(rows);
      setSelectedDrivers(new Set());
      setPollingDownloads(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download drivers");
    } finally {
      setDownloading(false);
    }
  }

  async function handleDismiss() {
    try {
      await updateDevice(device.id, { status: "dismissed" });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dismiss");
    }
  }

  const icon = DEVICE_ICONS[device.device_type ?? "generic"] ?? "🔌";
  const strongMatch = device.matches.find(
    (m) => m.confidence === "linked" || m.confidence === "strong"
  );
  const possibleMatch = device.matches.find((m) => m.confidence === "possible");

  const manualSuggestions = (suggestions ?? []).filter((s) => isManualType(s.doc_type));
  const driverSuggestions = (suggestions ?? []).filter((s) => s.doc_type === "driver");
  const otherSuggestions = (suggestions ?? []).filter(
    (s) => !isManualType(s.doc_type) && s.doc_type !== "driver"
  );

  return (
    <div className="rounded-lg border border-blue-200/20 bg-blue-950/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xl">{icon}</span>
            <h3 className="truncate font-medium text-white">{deviceTitle(device)}</h3>
            {strongMatch && (
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-300">
                In knowledge base
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-xs text-slate-400">
            {device.ip}
            {device.vendor ? ` · ${device.vendor}` : ""}
            {device.mac ? ` · ${device.mac}` : ""}
            {device.hostname ? ` · ${device.hostname}` : ""}
            {device.open_ports ? ` · ports ${device.open_ports}` : ""}
          </p>
          {!strongMatch && possibleMatch && (
            <p className="mt-1 text-xs text-amber-300">
              Possible match:{" "}
              <a href={`/items/${possibleMatch.item_id}`} className="underline hover:text-amber-200">
                {possibleMatch.item_name}
              </a>{" "}
              — check before adding to avoid duplicates.
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={handleSuggest}
            disabled={loadingSuggest}
            className="rounded-md bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-500 disabled:opacity-50"
          >
            {loadingSuggest ? "Searching…" : "Find manuals & drivers"}
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            className="rounded-md border border-slate-500/40 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-500/10"
          >
            Dismiss
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded-md bg-red-900/60 px-3 py-2 text-xs text-red-200">{error}</p>
      )}

      {expanded && (
        <div className="mt-4 border-t border-blue-200/10 pt-4">
          {loadingSuggest && (
            <p className="text-sm text-slate-400">Searching the web for this device…</p>
          )}

          {!loadingSuggest && suggestMessage && (
            <p className="text-sm text-slate-400">{suggestMessage}</p>
          )}

          {!loadingSuggest && suggestions && suggestions.length > 0 && (
            <div className="flex flex-col gap-4">
              {/* Manuals → RAG */}
              {manualSuggestions.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-purple-200">
                    {DOC_TYPE_LABELS.manual}
                  </h4>
                  <ul className="mt-2 flex flex-col gap-1">
                    {manualSuggestions.map((s) => (
                      <li key={s.source_url} className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          className="mt-1 accent-purple-500"
                          checked={selectedManuals.has(s.source_url)}
                          onChange={() =>
                            setSelectedManuals((prev) => toggle(prev, s.source_url))
                          }
                        />
                        <a
                          href={s.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-300 hover:underline"
                        >
                          {s.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={handleAddManuals}
                    disabled={addingManuals || selectedManuals.size === 0}
                    className="mt-2 rounded-md bg-purple-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-purple-500 disabled:opacity-50"
                  >
                    {addingManuals
                      ? "Adding…"
                      : `Add ${selectedManuals.size || ""} to knowledge base`}
                  </button>
                  {manualsResult && (
                    <p className="mt-2 text-sm text-emerald-300">
                      ✅ Added and indexing in the background.{" "}
                      <a
                        href={`/items/${manualsResult.itemId}`}
                        className="font-medium underline hover:text-emerald-200"
                      >
                        View item
                      </a>
                    </p>
                  )}
                </div>
              )}

              {/* Drivers → download to server */}
              {driverSuggestions.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-purple-200">
                    {DOC_TYPE_LABELS.driver}
                  </h4>
                  <ul className="mt-2 flex flex-col gap-1">
                    {driverSuggestions.map((s) => (
                      <li key={s.source_url} className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          className="mt-1 accent-purple-500"
                          checked={selectedDrivers.has(s.source_url)}
                          onChange={() =>
                            setSelectedDrivers((prev) => toggle(prev, s.source_url))
                          }
                        />
                        <a
                          href={s.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-300 hover:underline"
                        >
                          {s.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={handleDownloadDrivers}
                    disabled={downloading || selectedDrivers.size === 0}
                    className="mt-2 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                  >
                    {downloading
                      ? "Starting…"
                      : `Download ${selectedDrivers.size || ""} to server`}
                  </button>
                </div>
              )}

              {/* Accessories / other — informational links only */}
              {otherSuggestions.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-purple-200">
                    {DOC_TYPE_LABELS.accessory}
                  </h4>
                  <ul className="mt-2 flex flex-col gap-1">
                    {otherSuggestions.map((s) => (
                      <li key={s.source_url}>
                        <a
                          href={s.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-300 hover:underline"
                        >
                          {s.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Download progress */}
          {downloads.length > 0 && (
            <div className="mt-4 space-y-2">
              <h4 className="text-sm font-semibold text-purple-200">Driver downloads</h4>
              {downloads.map((d) => (
                <div key={d.id} className="text-xs">
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="truncate pr-2">{d.title}</span>
                    <span
                      className={
                        d.status === "downloaded"
                          ? "text-emerald-300"
                          : d.status === "failed"
                          ? "text-red-300"
                          : "text-purple-300"
                      }
                    >
                      {DOWNLOAD_STATUS_LABELS[d.status] ?? d.status}
                    </span>
                  </div>
                  {d.status === "downloaded" && d.local_path && (
                    <p className="mt-0.5 truncate font-mono text-[0.7rem] text-slate-500">
                      {d.local_path}
                    </p>
                  )}
                  {(d.error || (d.status === "downloaded" && !d.local_path)) && (
                    <p className="mt-0.5 text-[0.7rem] text-amber-300">{d.error}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page-level component ─────────────────────────────────────────────

export default function NetworkScan() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scannedOnce, setScannedOnce] = useState(false);

  async function refresh() {
    try {
      const list = await getDevices();
      setDevices(list);
    } catch {
      // ignore refresh errors; the scan button surfaces real errors
    }
  }

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const list = await getDevices();
        setDevices(list);
        if (list.length > 0) setScannedOnce(true);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Could not reach the backend. Is it running on port 8000?"
        );
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleScan() {
    setScanning(true);
    setError(null);
    try {
      const list = await scanNetwork();
      setDevices(list);
      setScannedOnce(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network scan failed");
    } finally {
      setScanning(false);
    }
  }

  const visible = devices.filter((d) => d.status !== "dismissed");

  return (
    <div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleScan}
          disabled={scanning}
          className="rounded-md bg-purple-700 px-4 py-2 text-sm font-medium text-white hover:bg-purple-600 disabled:opacity-50"
        >
          {scanning ? "📡 Scanning…" : "📡 Scan network"}
        </button>
        <span className="text-sm text-slate-400">
          {scanning
            ? "Reading the ARP table and probing the LAN…"
            : `${visible.length} device${visible.length === 1 ? "" : "s"} found`}
        </span>
      </div>

      {error && (
        <p className="mt-4 rounded-md bg-red-900/60 px-4 py-3 text-sm text-red-200">{error}</p>
      )}

      {!loading && !scanning && visible.length === 0 && (
        <p className="mt-8 text-slate-400">
          {scannedOnce
            ? "No devices found on your local network."
            : 'No devices yet. Click "Scan network" to discover devices on your LAN.'}
        </p>
      )}

      <div className="mt-6 flex flex-col gap-3">
        {visible.map((device) => (
          <DeviceCard key={device.id} device={device} onChanged={refresh} />
        ))}
      </div>
    </div>
  );
}
