"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/services/api";

export default function OverviewPage() {
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(e.message));
  }, []);

  const services = health
    ? [
        { name: "DuckDB (structured business data)", ok: health.duckdb?.status === "ok", detail: health.duckdb?.table_count ? `${health.duckdb.table_count} tables` : health.duckdb?.detail },
        { name: "Neo4j (context graph)", ok: health.neo4j?.status === "ok", detail: health.neo4j?.node_count !== undefined ? `${health.neo4j.node_count} nodes` : health.neo4j?.detail },
        { name: "Qdrant (vector search)", ok: health.qdrant?.status === "ok", detail: (health.qdrant?.collections || []).join(", ") || health.qdrant?.detail },
        { name: "Gemini (OCR + extraction)", ok: !!health.gemini?.api_key_present, detail: health.gemini?.api_key_present ? "key present" : "not configured" }
      ]
    : [];

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Experimental workspace</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Meridian V3 (beta)</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          Forked from the production Meridian platform to rebuild the context layer on a real graph database
          (Neo4j) and vector database (Qdrant), and to add ingestion for unstructured claim documents.
        </p>
      </div>

      <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-3 text-base font-bold text-gray-900">Stack status</h2>
        {error && <p className="text-sm text-v3-rose">Could not reach backend_v3: {error}</p>}
        {!health && !error && <p className="text-sm text-gray-400">Checking…</p>}
        <div className="space-y-2">
          {services.map((s) => (
            <div key={s.name} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2">
              <span className="text-sm font-medium text-gray-700">{s.name}</span>
              <span className="flex items-center gap-1.5 text-xs font-semibold">
                {s.ok ? <CheckCircle2 size={14} className="text-green-600" /> : <XCircle size={14} className="text-v3-rose" />}
                <span className={s.ok ? "text-green-700" : "text-v3-rose"}>{s.detail || (s.ok ? "ok" : "error")}</span>
              </span>
            </div>
          ))}
        </div>
      </section>

      <Link
        href="/claims"
        className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2.5 text-sm font-bold text-white shadow-glow hover:bg-v3-violetDark"
      >
        Browse claims <ArrowRight size={16} />
      </Link>
    </div>
  );
}
