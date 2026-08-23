"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { fetchQueue, type QueueSummary, type UwCase } from "@/services/underwritingApi";

const RISK_TONE: Record<string, string> = {
  low: "bg-green-50 text-green-700",
  medium: "bg-amber-50 text-amber-700",
  high: "bg-orange-50 text-orange-700",
  very_high: "bg-v3-rose/10 text-v3-rose"
};

function pct(v: number | null | undefined) {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}

export default function UnderwritingQueuePage() {
  const [cases, setCases] = useState<UwCase[] | null>(null);
  const [summary, setSummary] = useState<QueueSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchQueue(true, 50)
      .then((r) => {
        setCases(r.cases);
        setSummary(r.summary);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Risk chain · Underwriting</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Cases awaiting a decision</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          Referred by the rules because no threshold could settle them. Ordered by risk score, not
          arrival — a queue sorted by age buries the cases that matter.
        </p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Awaiting review" value={summary.awaiting_review.toLocaleString()} accent />
          <Stat label="Straight-through rate" value={pct(summary.straight_through_rate)} />
          <Stat label="Auto-decided" value={summary.auto_decided.toLocaleString()} />
          <Stat label="Cases on file" value={summary.total_cases.toLocaleString()} />
        </div>
      )}

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!cases && !error && <p className="text-sm text-gray-400">Loading…</p>}

      {cases && cases.length === 0 && (
        <p className="rounded-xl border border-gray-100 bg-white p-6 text-sm text-gray-500 shadow-card">
          Nothing awaiting review.
        </p>
      )}

      {cases && cases.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-100 bg-white shadow-card">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3">Application</th>
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3 text-right">Score</th>
                <th className="px-4 py-3">Risk class</th>
                <th className="px-4 py-3 text-right">Sum assured</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {cases.map((c) => (
                <tr key={c.application_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      href={`/underwriting/cases/${c.application_id}`}
                      className="font-semibold text-v3-violet hover:underline"
                    >
                      {c.application_number}
                    </Link>
                    <p className="text-xs text-gray-400">{c.application_date ?? "—"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{c.customer_name ?? "—"}</p>
                    <p className="text-xs text-gray-400">{c.customer_segment ?? ""}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-gray-900">{c.product_name ?? "—"}</p>
                    <p className="text-xs text-gray-400">{c.line_of_business ?? ""}</p>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-gray-900">
                    {c.risk_score?.toFixed(3) ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-bold ${
                        RISK_TONE[c.risk_class ?? ""] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {c.risk_class === "very_high" && <ShieldAlert size={12} />}
                      {(c.risk_class ?? "unknown").replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-gray-600">
                    {c.requested_sum_assured
                      ? `S$${Math.round(c.requested_sum_assured).toLocaleString()}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
      <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent ? "text-v3-violet" : "text-gray-900"}`}>{value}</p>
    </div>
  );
}
