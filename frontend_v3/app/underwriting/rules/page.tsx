"use client";

import { useEffect, useState } from "react";
import { fetchGovernance, fetchRules, type UwRule } from "@/services/underwritingApi";

function pct(v: number | null | undefined) {
  if (v == null) return "—";
  const p = v * 100;
  // A rate that rounds to 0.0% while a non-zero count sits beside it reads as a
  // bug. Say "under a tenth of a percent" instead of claiming zero.
  if (p > 0 && p < 0.1) return "<0.1%";
  return `${p.toFixed(1)}%`;
}

export default function RulesPage() {
  const [rules, setRules] = useState<UwRule[] | null>(null);
  const [gov, setGov] = useState<Awaited<ReturnType<typeof fetchGovernance>> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchRules(false).then((r) => setRules(r.rules)).catch((e) => setError(e.message));
    fetchGovernance().then(setGov).catch(() => undefined);
  }, []);

  // Group versions under their key so the history of a rule reads as one story.
  const byKey = (rules ?? []).reduce<Record<string, UwRule[]>>((acc, r) => {
    (acc[r.rule_key] ||= []).push(r);
    return acc;
  }, {});

  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Governance · Rules</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Underwriting rules & versions</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          A rule is not a row that gets edited — it is a series of versions, each with the window it
          was in force. A decision made in March 2024 has to be explainable against the rule text
          that applied in March 2024, not against whatever the rule says today.
        </p>
      </div>

      {gov && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Straight-through rate" value={pct(gov.straight_through_rate)} />
          <Stat label="Override rate" value={pct(gov.override_rate)} accent />
          <Stat label="Referred to a human" value={gov.referred.toLocaleString()} />
          <Stat label="Overrides recorded" value={gov.overrides.toLocaleString()} />
        </div>
      )}
      {gov && (
        <p className="text-xs text-gray-500">
          Straight-through rate is reported next to override rate deliberately. On its own, a high
          STP rate only says how often nobody looked.
        </p>
      )}

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!rules && !error && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="space-y-4">
        {Object.entries(byKey).map(([key, versions]) => (
          <div key={key} className="rounded-xl border border-gray-100 bg-white shadow-card">
            <div className="border-b border-gray-100 px-4 py-3">
              <h2 className="font-mono text-sm font-bold text-gray-900">{key}</h2>
              <p className="text-xs text-gray-500">
                {versions.length} version{versions.length === 1 ? "" : "s"}
              </p>
            </div>
            <ul className="divide-y divide-gray-100">
              {versions
                .slice()
                .sort((a, b) => a.version - b.version)
                .map((r) => (
                  <li key={r.rule_id} className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-gray-500">v{r.version}</span>
                      <span className="text-sm font-semibold text-gray-900">{r.name}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                          r.status === "active"
                            ? "bg-green-50 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {r.status}
                      </span>
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-[10px] font-bold uppercase text-gray-600">
                        {r.action.replace("_", " ")}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-600">{r.description}</p>
                    <p className="mt-1 font-mono text-xs text-gray-400">
                      in force {r.effective_from} → {r.effective_to ?? "present"}
                      {r.condition && typeof r.condition === "object"
                        ? ` · ${JSON.stringify(r.condition)}`
                        : ""}
                    </p>
                  </li>
                ))}
            </ul>
          </div>
        ))}
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
