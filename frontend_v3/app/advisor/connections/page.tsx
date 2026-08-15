"use client";

import { useEffect, useState } from "react";
import { Cloud, Database, FileSpreadsheet, Link2, Mail, MessageCircle, Video } from "lucide-react";
import { advisorApi, type ConnectionCategory, type ConnectionProvider } from "@/services/advisorApi";

const CATEGORY_ICON: Record<string, React.ReactNode> = {
  "Customer Data": <Database size={18} className="text-v3-violet" />,
  Calendar: <Link2 size={18} className="text-v3-teal" />,
  Communication: <Mail size={18} className="text-v3-violet" />,
  Meetings: <Video size={18} className="text-v3-teal" />,
  Files: <Cloud size={18} className="text-v3-violet" />
};

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<ConnectionCategory[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    advisorApi.listConnections().then(setConnections).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Connections</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Data source connections</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">Stage 1 builds the connection framework and sync status UX. Providers are not connected until real integrations are implemented.</p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!connections && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {connections && (
        <div className="grid gap-5 lg:grid-cols-2">
          {connections.map((group) => (
            <section key={group.category} className="rounded-lg border border-gray-100 bg-white shadow-card">
              <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
                {CATEGORY_ICON[group.category] || <FileSpreadsheet size={18} className="text-v3-violet" />}
                <h2 className="font-bold text-gray-900">{group.category}</h2>
              </div>
              <div className="divide-y divide-gray-100">
                {group.providers.map((provider) => (
                  <ConnectionRow key={provider.provider} provider={provider} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function ConnectionRow({ provider }: { provider: ConnectionProvider }) {
  const Icon = provider.provider.includes("WhatsApp") ? MessageCircle : provider.provider.includes("CSV") ? FileSpreadsheet : Link2;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500">
          <Icon size={17} />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-gray-900">{provider.provider}</p>
          <p className="mt-0.5 text-xs text-gray-500">Sync status: {provider.sync_status.replaceAll("_", " ")}</p>
        </div>
      </div>
      <button
        type="button"
        className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-500"
        title="Integration not implemented in Stage 1"
      >
        Not connected
      </button>
    </div>
  );
}
