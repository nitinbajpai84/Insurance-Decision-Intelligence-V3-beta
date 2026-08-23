"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, Gavel, Scale, ShieldAlert } from "lucide-react";
import {
  fetchTriage,
  type TriageSummary,
  type TriagedClaim
} from "@/services/claimsTriageApi";

const TIER_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-500"
};

const SIGNAL_LABEL: Record<string, string> = {
  unresolved_fraud: "Fraud flag",
  litigation: "Litigation",
  early_duration: "Early duration",
  stp_early_claim: "STP early claim",
  long_open: "Ageing",
  large_reserve: "Large reserve",
  contestable_period: "Contestable",
  catastrophe: "Catastrophe"
};

export default function ClaimsTriagePage() {
  const [claims, setClaims] = useState<TriagedClaim[] | null>(null);
  const [summary, setSummary] = useState<TriageSummary | null>(null);
  const [tier, setTier] = useState<"all" | "high" | "medium">("all");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchTriage(150)
      .then((r) => {
        setClaims(r.claims);
        setSummary(r.summary);
      })
      .catch((e) => setError(e.message));
  }, []);

  const shown = (claims ?? []).filter((c) => (tier === "all" ? true : c.tier === tier));

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Risk chain · Claims</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Claims needing attention</h1>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">
            Every open claim scored from signals already on its record. The score is a sum of stated
            reasons — you can disagree with a reason, which is the point.
          </p>
        </div>
        <Link
          href="/claims"
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700 hover:border-v3-violet hover:text-v3-violet"
        >
          Full claims register
        </Link>
      </div>

      {summary && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Open claims" value={summary.open_claims.toLocaleString()} />
            <Stat label="Needs attention" value={summary.needs_attention.toLocaleString()} accent />
            <Stat label="High priority" value={summary.by_tier.high.toLocaleString()} />
            <Stat
              label="Reserve at risk"
              value={`S$${(summary.total_reserve / 1_000_000).toFixed(1)}M`}
            />
          </div>

          <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
            <p className="text-xs font-bold uppercase tracking-wide text-gray-400">
              Signals firing across the open book
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(summary.signal_counts)
                .sort((a, b) => b[1] - a[1])
                .map(([sig, n]) => (
                  <span
                    key={sig}
                    className="inline-flex items-center gap-1.5 rounded-full bg-gray-50 px-2.5 py-1 text-xs text-gray-600"
                  >
                    <span className="font-semibold text-gray-900">{SIGNAL_LABEL[sig] ?? sig}</span>
                    <span className="font-mono tabular-nums">{n}</span>
                    <span className="text-gray-300">·</span>
                    <span className="font-mono text-gray-400">+{summary.weights[sig]}</span>
                  </span>
                ))}
            </div>
            <p className="mt-2 text-xs text-gray-500">
              A fraud indicator or an active litigation escalates a claim on its own, whatever the
              total — a referral is a decision, not an arithmetic outcome.
            </p>
          </div>
        </>
      )}

      <div className="flex gap-2">
        {(["all", "high", "medium"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTier(t)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-semibold capitalize transition-colors ${
              tier === t
                ? "border-v3-violet bg-v3-violet text-white"
                : "border-gray-200 text-gray-600 hover:border-v3-violet hover:text-v3-violet"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!claims && !error && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="space-y-3">
        {shown.map((c) => (
          <div key={c.claim_id} className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={`/claims/${c.claim_id}`}
                    className="font-semibold text-v3-violet hover:underline"
                  >
                    {c.claim_number}
                  </Link>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-bold uppercase ${TIER_TONE[c.tier]}`}
                  >
                    {c.tier}
                  </span>
                  {c.escalated_by && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-v3-rose/10 px-2 py-0.5 text-xs font-bold text-v3-rose">
                      {c.escalated_by === "litigation" ? <Gavel size={11} /> : <ShieldAlert size={11} />}
                      escalated
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm text-gray-900">
                  {c.customer_name} · {c.product_name} · {c.loss_cause}
                </p>
                <p className="text-xs text-gray-400">
                  Loss {c.loss_date} · open {c.days_open}d · reserve S$
                  {Math.round(c.reserve_amount ?? 0).toLocaleString()}
                </p>
              </div>
              <div className="text-right">
                <p className="font-mono text-2xl font-bold tabular-nums text-gray-900">{c.score}</p>
                <p className="text-xs text-gray-400">priority score</p>
              </div>
            </div>

            <ul className="mt-3 space-y-1.5 border-t border-gray-100 pt-3">
              {c.reasons.map((r) => (
                <li key={r.signal} className="flex items-start gap-2 text-sm">
                  <span className="mt-0.5 shrink-0 font-mono text-xs font-bold text-gray-400">
                    +{r.points}
                  </span>
                  <span className="text-gray-700">{r.text}</span>
                </li>
              ))}
            </ul>

            {c.underwriting?.application_id && (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
                <Scale size={14} className="text-gray-400" />
                <span className="text-xs text-gray-500">Underwritten as</span>
                <Link
                  href={`/underwriting/cases/${c.underwriting.application_id}`}
                  className="text-xs font-semibold text-v3-violet hover:underline"
                >
                  {c.underwriting.rule_key} v{c.underwriting.rule_version} ·{" "}
                  {c.underwriting.decision_status?.replace(/_/g, " ")}
                </Link>
              </div>
            )}
          </div>
        ))}
        {claims && shown.length === 0 && (
          <p className="rounded-xl border border-gray-100 bg-white p-6 text-sm text-gray-500 shadow-card">
            No claims in this tier.
          </p>
        )}
      </div>
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
