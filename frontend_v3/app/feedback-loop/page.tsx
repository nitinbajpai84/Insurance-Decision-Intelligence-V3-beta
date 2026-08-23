"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Info, TriangleAlert } from "lucide-react";
import { fetchLoopReport, type LoopReport } from "@/services/feedbackLoopApi";

const money = (v: number | null) =>
  v == null ? "—" : v >= 1_000_000 ? `S$${(v / 1_000_000).toFixed(1)}M` : `S$${Math.round(v).toLocaleString()}`;

export default function FeedbackLoopPage() {
  const [r, setR] = useState<LoopReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchLoopReport().then(setR).catch((e) => setError(e.message));
  }, []);

  if (error) return <Shell><p className="text-sm text-v3-rose">{error}</p></Shell>;
  if (!r) return <Shell><p className="text-sm text-gray-400">Loading…</p></Shell>;

  const f = r.finding;
  // The rule-version cut is the one that understates the problem; showing it
  // beside the band cut is the whole argument, so both are always rendered.
  const maxBand = Math.max(...r.by_score_band.map((b) => b.per_1000), 1);

  return (
    <Shell>
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">
          Risk chain · Claims → Underwriting
        </p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Is a rule leaking?</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          Early claims traced back to the underwriting rule that accepted the risk. Claims triage
          asks this one case at a time; this asks it of the rule.
        </p>
      </div>

      {f.detected && (
        <section className="rounded-xl border border-v3-rose/30 bg-v3-rose/5 p-5">
          <div className="flex items-start gap-3">
            <TriangleAlert size={20} className="mt-0.5 shrink-0 text-v3-rose" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-3">
                <span className="font-mono text-4xl font-bold tabular-nums text-v3-rose">
                  {f.lift?.toFixed(2)}x
                </span>
                <span className="text-sm font-bold uppercase tracking-wide text-v3-rose">
                  early-claim lift
                </span>
              </div>
              <p className="mt-2 text-sm text-gray-800">{f.headline}</p>
              <p className="mt-2 text-sm font-semibold text-gray-900">{f.implication}</p>
            </div>
          </div>
        </section>
      )}

      {/* Method sits above the numbers, not in a footnote. */}
      <section className="rounded-xl border border-gray-200 bg-gray-50 p-4">
        <div className="flex items-start gap-2">
          <Info size={16} className="mt-0.5 shrink-0 text-gray-500" />
          <div>
            <h2 className="text-sm font-bold text-gray-900">
              How this is measured: {r.method.measure}
            </h2>
            <p className="mt-1 text-sm text-gray-700">{r.method.why_exposure_matched}</p>
            <p className="mt-2 text-xs text-gray-500">{r.method.caveat}</p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="By rule version"
          note="On its own this understates the problem — both versions contain a mix of bands."
        >
          {r.by_rule_version.map((x) => (
            <Row key={x.rule} label={x.rule} policies={x.policies} early={x.early_claims} rate={x.per_1000} max={maxBand} />
          ))}
        </Panel>

        <Panel
          title="By score band"
          note="The middle band is the one whose treatment changed between versions. This is where the leak is."
          accent
        >
          {r.by_score_band.map((x) => (
            <Row
              key={x.band}
              label={x.band}
              policies={x.policies}
              early={x.early_claims}
              rate={x.per_1000}
              max={maxBand}
              highlight={x.band.includes("0.42-0.55")}
            />
          ))}
        </Panel>
      </div>

      <section className="rounded-xl border border-gray-100 bg-white shadow-card">
        <div className="border-b border-gray-100 px-4 py-3">
          <h2 className="text-sm font-bold text-gray-900">The claims behind the finding</h2>
          <p className="text-xs text-gray-500">
            An aggregate you cannot open is hard to trust. Each row links to the underwriting case
            that accepted the risk.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-2.5">Claim</th>
                <th className="px-4 py-2.5">Customer</th>
                <th className="px-4 py-2.5">Product</th>
                <th className="px-4 py-2.5 text-right">Month</th>
                <th className="px-4 py-2.5 text-right">Incurred</th>
                <th className="px-4 py-2.5 text-right">Score</th>
                <th className="px-4 py-2.5">Underwriting</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {r.cases.map((c) => (
                <tr key={c.claim_id} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <Link href={`/claims/${c.claim_id}`} className="font-semibold text-v3-violet hover:underline">
                      {c.claim_number}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-gray-900">{c.customer_name ?? "—"}</td>
                  <td className="px-4 py-2.5 text-gray-600">{c.product_name ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-gray-900">
                    {c.policy_duration_months ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-gray-600">
                    {money(c.incurred)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-gray-600">
                    {c.risk_score?.toFixed(2) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    {c.application_id ? (
                      <Link
                        href={`/underwriting/cases/${c.application_id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-v3-violet hover:underline"
                      >
                        view case <ArrowRight size={12} />
                      </Link>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">{children}</div>;
}

function Panel({
  title,
  note,
  accent,
  children
}: {
  title: string;
  note: string;
  accent?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className={`rounded-xl border bg-white shadow-card ${
        accent ? "border-v3-violet/30" : "border-gray-100"
      }`}
    >
      <div className="border-b border-gray-100 px-4 py-3">
        <h2 className="text-sm font-bold text-gray-900">{title}</h2>
        <p className="mt-0.5 text-xs text-gray-500">{note}</p>
      </div>
      <div className="space-y-3 p-4">{children}</div>
    </section>
  );
}

function Row({
  label,
  policies,
  early,
  rate,
  max,
  highlight
}: {
  label: string;
  policies: number;
  early: number;
  rate: number;
  max: number;
  highlight?: boolean;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className={`text-sm ${highlight ? "font-bold text-gray-900" : "text-gray-700"}`}>{label}</p>
        <p className={`font-mono text-sm font-bold tabular-nums ${highlight ? "text-v3-rose" : "text-gray-900"}`}>
          {rate}
          <span className="ml-1 text-xs font-normal text-gray-400">/1,000</span>
        </p>
      </div>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          className={`h-full rounded-full ${highlight ? "bg-v3-rose" : "bg-gray-300"}`}
          style={{ width: `${Math.min(100, (rate / max) * 100)}%` }}
        />
      </div>
      <p className="mt-1 text-xs text-gray-400">
        {policies.toLocaleString()} policies · {early} early claims
      </p>
    </div>
  );
}
