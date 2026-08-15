"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { intelligenceApi, type AiAuditRow } from "@/services/advisorApi";

const DECISION_TONE: Record<string, string> = {
  accepted: "bg-green-50 text-green-700",
  edited: "bg-v3-teal/10 text-v3-teal",
  rejected: "bg-gray-100 text-gray-500",
  pending: "bg-amber-50 text-amber-700",
  viewed: "bg-gray-100 text-gray-600"
};

export default function AiAuditPage() {
  const [rows, setRows] = useState<AiAuditRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    intelligenceApi.getAiAudit().then(setRows).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-v3-violet">
          <ShieldCheck size={14} /> AI Auditability
        </p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Every AI insight, on the record</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          Customer, agent, timestamp, source, model, output, confidence, and the human decision — for every
          extracted memory, suggested action, and generated briefing.
        </p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!rows && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {rows && (
        <section className="rounded-lg border border-gray-100 bg-white shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[64rem] text-sm">
              <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Agent</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Output</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Model</th>
                  <th className="px-4 py-3">Confidence</th>
                  <th className="px-4 py-3">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((row) => (
                  <tr key={`${row.kind}-${row.record_id}`}>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {row.timestamp ? new Date(row.timestamp).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/advisor/customers/${row.customer_id}`} className="font-semibold text-v3-violet hover:underline">
                        {row.customer_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{row.agent || "—"}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-bold uppercase text-gray-600">
                        {row.insight_type}
                      </span>
                    </td>
                    <td className="max-w-sm truncate px-4 py-3 text-gray-800" title={row.output}>
                      {row.output}
                    </td>
                    <td className="max-w-xs truncate px-4 py-3 text-xs text-gray-500" title={row.source}>
                      {row.source}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{row.model}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {row.confidence === null || row.confidence === undefined ? "—" : `${Math.round(Number(row.confidence) <= 1 ? Number(row.confidence) * 100 : Number(row.confidence))}%`}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${DECISION_TONE[row.human_decision] || "bg-gray-100 text-gray-500"}`}>
                        {row.human_decision}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="p-5 text-sm text-gray-400">No AI activity recorded yet.</p>}
          </div>
        </section>
      )}
    </div>
  );
}
