import NetworkScan from "@/components/NetworkScan";

export default function NetworkPage() {
  return (
    <div className="flex flex-col flex-1 min-h-screen" style={{ backgroundColor: "#0a1628" }}>
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <h1 className="text-2xl font-semibold text-white">Network Devices</h1>
        <p className="mt-1 text-slate-300">
          Scan your local network to find connected devices, add their manuals to your
          knowledge base, and download drivers or software to the server.
        </p>

        <div className="mt-8">
          <NetworkScan />
        </div>
      </main>
    </div>
  );
}
