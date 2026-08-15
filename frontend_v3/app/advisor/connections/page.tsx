"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Check,
  Cloud,
  Database,
  Mail,
  MessageCircle,
  RefreshCw,
  Upload,
  Video
} from "lucide-react";
import {
  integrationApi,
  type ConnectionCenterCategory,
  type ConnectionRow
} from "@/services/advisorApi";

const CATEGORY_ICON: Record<string, React.ReactNode> = {
  "Customer Data": <Database size={17} className="text-v3-violet" />,
  Calendar: <CalendarDays size={17} className="text-v3-teal" />,
  Meetings: <Video size={17} className="text-v3-teal" />,
  Communication: <Mail size={17} className="text-v3-violet" />,
  Files: <Cloud size={17} className="text-v3-violet" />
};

const IMPLEMENTATION_LABEL: Record<string, { label: string; tone: string }> = {
  live: { label: "Available now", tone: "bg-green-50 text-green-700" },
  credentialed: { label: "Needs credentials", tone: "bg-amber-50 text-amber-700" },
  architecture: { label: "Architecture only", tone: "bg-gray-100 text-gray-600" }
};

function formatSync(value: string | null): string {
  if (!value) return "Never";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatSynchronized(data: Record<string, number>): string {
  const entries = Object.entries(data).filter(([, count]) => count > 0);
  if (entries.length === 0) return "—";
  return entries.map(([key, count]) => `${count} ${key}`).join(", ");
}

export default function ConnectionsPage() {
  const [categories, setCategories] = useState<ConnectionCenterCategory[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    integrationApi
      .connectionCenter()
      .then((data) => {
        setCategories(data);
        setError("");
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function act(provider: ConnectionRow, action: "connect" | "disconnect" | "sync") {
    setBusy(`${provider.provider}:${action}`);
    setNotice("");
    setError("");
    try {
      if (action === "connect") {
        const result = await integrationApi.connect(provider.provider);
        if (result.authorization_url) {
          window.location.href = result.authorization_url;
          return;
        }
        setNotice(result.message || `${provider.name} connects by uploading a file.`);
      } else if (action === "disconnect") {
        await integrationApi.disconnect(provider.provider);
        setNotice(`${provider.name} disconnected and stored credentials destroyed.`);
      } else {
        const result = await integrationApi.syncNow(provider.provider);
        const counts = (result.counts as Record<string, number>) || {};
        setNotice(`${provider.name} sync complete: ${formatSynchronized(counts)}.`);
      }
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Connections</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Connection Center</h1>
          <p className="mt-1 max-w-3xl text-sm text-gray-500">
            Connect the systems you already use. Status reflects real connection state — a provider reads
            connected only once a credential-backed connection exists.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/advisor/connections/import"
            className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-3 py-2 text-sm font-bold text-white hover:bg-v3-violetDark"
          >
            <Upload size={15} /> Import data
          </Link>
          <button
            onClick={load}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:border-v3-violet hover:text-v3-violet"
          >
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </div>

      {notice && (
        <p className="rounded-lg border border-v3-teal/30 bg-v3-teal/5 px-4 py-3 text-sm text-teal-800">{notice}</p>
      )}
      {error && (
        <p className="rounded-lg border border-v3-rose/30 bg-v3-rose/5 px-4 py-3 text-sm text-v3-rose">{error}</p>
      )}
      {!categories && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {categories?.map((group) => (
        <section key={group.category} className="rounded-lg border border-gray-100 bg-white shadow-card">
          <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
            {CATEGORY_ICON[group.category]}
            <h2 className="font-bold text-gray-900">{group.category}</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-sm">
              <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-5 py-3">Integration</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Account</th>
                  <th className="px-5 py-3">Last sync</th>
                  {/* Reports the most recent sync. Writes are idempotent
                      merges, so a lifetime total would overstate reality. */}
                  <th className="px-5 py-3">Data synchronized</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {group.providers.map((provider) => {
                  const impl = IMPLEMENTATION_LABEL[provider.implementation];
                  return (
                    <tr key={provider.provider} className="align-top">
                      <td className="px-5 py-4">
                        <p className="font-semibold text-gray-900">{provider.name}</p>
                        <p className="mt-1 max-w-md text-xs leading-5 text-gray-500">{provider.notes}</p>
                        {provider.blocked_reason && (
                          <p className="mt-1 inline-flex items-start gap-1 text-xs text-amber-700">
                            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                            {provider.blocked_reason}
                          </p>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                            provider.connected ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {provider.connected && <Check size={11} />}
                          {provider.connected ? "Connected" : "Not connected"}
                        </span>
                        <span className={`mt-1 block w-fit rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${impl.tone}`}>
                          {impl.label}
                        </span>
                        {provider.last_error && (
                          <p className="mt-1 max-w-xs text-xs text-v3-rose">{provider.last_error}</p>
                        )}
                      </td>
                      <td className="px-5 py-4 text-gray-700">{provider.account || "—"}</td>
                      <td className="px-5 py-4 text-gray-700">{formatSync(provider.last_sync)}</td>
                      <td className="px-5 py-4 text-gray-700">{formatSynchronized(provider.data_synchronized)}</td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap justify-end gap-2">
                          {provider.actions.upload ? (
                            <Link
                              href="/advisor/connections/import"
                              className="rounded-lg bg-v3-violet px-3 py-1.5 text-xs font-bold text-white hover:bg-v3-violetDark"
                            >
                              Upload file
                            </Link>
                          ) : (
                            <button
                              disabled={!provider.actions.connect || busy !== ""}
                              onClick={() => act(provider, "connect")}
                              className="rounded-lg bg-v3-violet px-3 py-1.5 text-xs font-bold text-white hover:bg-v3-violetDark disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500"
                              title={provider.blocked_reason || "Start the OAuth flow"}
                            >
                              Connect
                            </button>
                          )}
                          <button
                            disabled={!provider.actions.sync_now || busy !== ""}
                            onClick={() => act(provider, "sync")}
                            className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-700 hover:border-v3-violet hover:text-v3-violet disabled:cursor-not-allowed disabled:text-gray-300"
                          >
                            {busy === `${provider.provider}:sync` ? "Syncing..." : "Sync now"}
                          </button>
                          <button
                            disabled={!provider.actions.disconnect || busy !== ""}
                            onClick={() => act(provider, "disconnect")}
                            className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-700 hover:border-v3-rose hover:text-v3-rose disabled:cursor-not-allowed disabled:text-gray-300"
                          >
                            Disconnect
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-card">
        <div className="flex items-start gap-3">
          <MessageCircle size={17} className="mt-0.5 shrink-0 text-v3-teal" />
          <div>
            <h2 className="text-sm font-bold text-gray-900">How connection state is decided</h2>
            <p className="mt-1 text-sm leading-6 text-gray-600">
              <span className="font-semibold">Available now</span> sources ingest today. <span className="font-semibold">Needs credentials</span>{" "}
              sources have working ingestion code that activates once OAuth credentials are configured.{" "}
              <span className="font-semibold">Architecture only</span> sources have a defined connector contract and
              permission model, but no ingestion yet — so they cannot report a connection.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
