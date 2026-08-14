"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api, money, type ClaimSummary } from "@/services/api";

const STATUS_TONE: Record<string, string> = {
  paid: "bg-green-50 text-green-700",
  approved: "bg-green-50 text-green-700",
  denied: "bg-v3-rose/10 text-v3-rose",
  open: "bg-amber-50 text-amber-700",
  pending: "bg-amber-50 text-amber-700"
};

export default function ClaimsPage() {
  const [claims, setClaims] = useState<ClaimSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listClaims(50).then(setClaims).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Structured data · DuckDB</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Claims</h1>
        <p className="mt-1 text-sm text-gray-500">Click a claim to view its structured record and any ingested documents.</p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!claims && !error && <p className="text-sm text-gray-400">Loading…</p>}

      {claims && (
        <div className="overflow-x-auto rounded-xl border border-gray-100 bg-white shadow-card">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3">Claim</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Loss cause</th>
                <th className="px-4 py-3 text-right">Paid</th>
                <th className="px-4 py-3 text-right">Reserve</th>
                <th className="px-4 py-3">Fraud</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {claims.map((c) => (
                <tr key={c.claim_id} className="hover:bg-v3-violet/5">
                  <td className="px-4 py-3">
                    <Link href={`/claims/${c.claim_id}`} className="font-semibold text-v3-violet hover:underline">
                      {c.claim_number}
                    </Link>
                    <p className="text-xs text-gray-400">{c.report_date}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{c.customer_name || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${STATUS_TONE[c.claim_status] || "bg-gray-100 text-gray-600"}`}>
                      {c.claim_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{c.loss_cause || "—"}</td>
                  <td className="px-4 py-3 text-right font-semibold text-gray-900">{money(c.paid_amount)}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{money(c.reserve_amount)}</td>
                  <td className="px-4 py-3">
                    {c.open_fraud_indicators > 0 ? (
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-v3-rose">
                        <AlertTriangle size={12} /> {c.open_fraud_indicators}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-300">—</span>
                    )}
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
