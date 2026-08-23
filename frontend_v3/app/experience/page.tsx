"use client";

import { useEffect, useState } from "react";
import { Info, TrendingDown, TrendingUp, TriangleAlert } from "lucide-react";
import {
  fetchExperienceOverview,
  type ExperienceBasis,
  type ExperienceDimension,
  type FlaggedCell
} from "@/services/experienceApi";

const money = (v: number) =>
  v >= 1_000_000 ? `S$${(v / 1_000_000).toFixed(1)}M` : `S$${Math.round(v).toLocaleString()}`;

function aeTone(ae: number | null, diverging: boolean) {
  if (ae == null) return "text-gray-400";
  if (!diverging) return "text-gray-900";
  return ae > 1 ? "text-v3-rose" : "text-green-700";
}

export default function ExperiencePage() {
  const [basis, setBasis] = useState<ExperienceBasis | null>(null);
  const [dims, setDims] = useState<ExperienceDimension[] | null>(null);
  const [flagged, setFlagged] = useState<FlaggedCell[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchExperienceOverview()
      .then((r) => {
        setBasis(r.basis);
        setDims(r.dimensions);
        setFlagged(r.diverging);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Risk chain · Pricing</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Experience monitor</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          Actual versus expected across the book. Every figure is relative to a stated basis — an
          A/E number without its denominator on the page is not interpretable.
        </p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!basis && !error && <p className="text-sm text-gray-400">Loading…</p>}

      {/* The basis, stated before any number that depends on it. */}
      {basis && (
        <section className="rounded-xl border border-v3-violet/25 bg-v3-violet/5 p-4">
          <div className="flex items-start gap-2">
            <Info size={16} className="mt-0.5 shrink-0 text-v3-violet" />
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-gray-900">What &ldquo;expected&rdquo; means here</h2>
              <p className="mt-1 text-sm text-gray-700">{basis.description}</p>
              <p className="mt-2 text-sm text-gray-700">
                <strong>What it cannot tell you:</strong> {basis.limitation}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Fact label="Baseline loss ratio" value={`${((basis.baseline_loss_ratio ?? 0) * 100).toFixed(1)}%`} />
                <Fact label="Earned premium" value={money(basis.earned_premium)} />
                <Fact label="Incurred claims" value={money(basis.incurred_claims)} />
                <Fact label="Observation window" value={`${basis.window_from} → ${basis.window_to}`} small />
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Cells with fewer than {basis.min_claims_to_flag} claims are shown but never flagged.
                Divergence is flagged beyond ±{(basis.divergence_threshold * 100).toFixed(0)}%.
              </p>
            </div>
          </div>
        </section>
      )}

      {flagged.length > 0 && (
        <section className="rounded-xl border border-gray-100 bg-white shadow-card">
          <div className="border-b border-gray-100 px-4 py-3">
            <h2 className="text-sm font-bold text-gray-900">Diverging from the baseline</h2>
            <p className="text-xs text-gray-500">
              Ordered by distance from A/E 1.00, credible cells only.
            </p>
          </div>
          <ul className="divide-y divide-gray-100">
            {flagged.map((c) => (
              <li key={`${c.dimension}-${c.cell}`} className="flex items-center gap-3 px-4 py-3">
                {c.direction === "adverse" ? (
                  <TrendingUp size={16} className="shrink-0 text-v3-rose" />
                ) : (
                  <TrendingDown size={16} className="shrink-0 text-green-700" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-gray-900">
                    {c.cell}{" "}
                    <span className="font-normal text-gray-400">· {c.dimension_label}</span>
                  </p>
                  <p className="text-xs text-gray-500">
                    {c.claim_count.toLocaleString()} claims · {money(c.earned_premium)} earned · loss
                    ratio {(c.loss_ratio * 100).toFixed(1)}%
                    {c.credibility < 1 && ` · credibility ${c.credibility.toFixed(2)}`}
                  </p>
                </div>
                <span className={`font-mono text-xl font-bold tabular-nums ${aeTone(c.actual_vs_expected, true)}`}>
                  {c.actual_vs_expected?.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {dims?.map((d) => (
        <section key={d.dimension} className="rounded-xl border border-gray-100 bg-white shadow-card">
          <div className="border-b border-gray-100 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-bold text-gray-900">{d.label}</h2>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                  d.derivation === "calibrated"
                    ? "bg-amber-50 text-amber-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {d.derivation}
              </span>
            </div>
            {d.derivation === "calibrated" && (
              <p className="mt-1 flex items-start gap-1.5 text-xs text-amber-700">
                <TriangleAlert size={13} className="mt-0.5 shrink-0" />
                {d.derivation_note}
              </p>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-2.5">Segment</th>
                  <th className="px-4 py-2.5 text-right">Earned</th>
                  <th className="px-4 py-2.5 text-right">Claims</th>
                  <th className="px-4 py-2.5 text-right">Loss ratio</th>
                  <th className="px-4 py-2.5 text-right">A/E</th>
                  <th className="px-4 py-2.5 text-right">Credibility</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {d.cells.map((c) => (
                  <tr key={c.cell} className={c.diverging ? "bg-gray-50/60" : ""}>
                    <td className="px-4 py-2.5 font-medium text-gray-900">
                      {c.cell}
                      {!c.credible && (
                        <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-gray-500">
                          thin
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-gray-600">
                      {money(c.earned_premium)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-gray-600">
                      {c.claim_count.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-gray-600">
                      {(c.loss_ratio * 100).toFixed(1)}%
                    </td>
                    <td
                      className={`px-4 py-2.5 text-right font-mono font-bold tabular-nums ${aeTone(
                        c.actual_vs_expected,
                        c.diverging
                      )}`}
                    >
                      {c.actual_vs_expected?.toFixed(2) ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-gray-400">
                      {c.credibility.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}

function Fact({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`font-bold text-gray-900 ${small ? "text-xs" : "text-lg"}`}>{value}</p>
    </div>
  );
}
