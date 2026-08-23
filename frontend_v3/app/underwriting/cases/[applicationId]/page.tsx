"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { ArrowLeft, Check, CircleSlash, Minus, TriangleAlert } from "lucide-react";
import {
  fetchCase,
  submitDecision,
  type UwCaseDetail
} from "@/services/underwritingApi";

const DECISIONS = [
  { value: "approved_standard", label: "Approve — standard" },
  { value: "approved_rated", label: "Approve — rated" },
  { value: "approved_exclusion", label: "Approve — with exclusion" },
  { value: "postponed", label: "Postpone" },
  { value: "declined", label: "Decline" }
];

const RECOMMENDATION_TONE: Record<string, string> = {
  approved_standard: "border-green-200 bg-green-50 text-green-800",
  declined: "border-v3-rose/30 bg-v3-rose/10 text-v3-rose",
  refer: "border-amber-200 bg-amber-50 text-amber-800"
};

export default function UnderwritingCasePage({
  params
}: {
  params: Promise<{ applicationId: string }>;
}) {
  const { applicationId } = use(params);
  const [data, setData] = useState<UwCaseDetail | null>(null);
  const [error, setError] = useState("");
  const [decision, setDecision] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<string>("");

  const load = useCallback(() => {
    fetchCase(applicationId).then(setData).catch((e) => setError(e.message));
  }, [applicationId]);

  useEffect(load, [load]);

  const recommended = data?.assessment?.recommendation;
  // Selecting anything other than what the rules recommended is an override, and
  // an override has to be explained. "refer" is a request for judgement, not a
  // recommendation to contradict.
  const isOverride = Boolean(
    decision && recommended && recommended !== "refer" && recommended !== decision
  );

  async function onSubmit() {
    setSaving(true);
    setError("");
    try {
      const r = await submitDecision(applicationId, decision, "underwriter", reason || undefined);
      setResult(
        r.was_override
          ? `Recorded as an override of "${r.recommended}" — logged with your reason.`
          : "Decision recorded."
      );
      setDecision("");
      setReason("");
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (error && !data) return <Shell><p className="text-sm text-v3-rose">{error}</p></Shell>;
  if (!data) return <Shell><p className="text-sm text-gray-400">Loading…</p></Shell>;

  const a = data.assessment;

  return (
    <Shell>
      <Link
        href="/underwriting"
        className="inline-flex items-center gap-1 text-sm font-semibold text-v3-violet hover:underline"
      >
        <ArrowLeft size={15} /> Back to queue
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">
          Risk chain · Underwriting case
        </p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">{data.application_number}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {data.customer_name} · {data.product_name} · {data.line_of_business}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Risk score" value={data.risk_score?.toFixed(3) ?? "—"} mono />
        <Field label="Risk class" value={(data.risk_class ?? "—").replace("_", " ")} />
        <Field
          label="Sum assured"
          value={data.requested_sum_assured ? `S$${Math.round(data.requested_sum_assured).toLocaleString()}` : "—"}
          mono
        />
        <Field
          label="Premium"
          value={data.requested_premium ? `S$${Math.round(data.requested_premium).toLocaleString()}` : "—"}
          mono
        />
      </div>

      {a && (
        <section className="space-y-3">
          <div className={`rounded-xl border p-4 ${RECOMMENDATION_TONE[a.recommendation] ?? "border-gray-200 bg-gray-50 text-gray-800"}`}>
            <p className="text-xs font-bold uppercase tracking-wide opacity-70">Recommendation</p>
            <p className="mt-1 text-xl font-bold">{a.recommendation.replace("_", " ")}</p>
            <p className="mt-1 text-sm opacity-80">
              Governed by {a.governing_rule ?? "no rule"} · evaluated against the rules in force on{" "}
              {a.evaluated_on}
            </p>
          </div>

          <div className="rounded-xl border border-gray-100 bg-white shadow-card">
            <div className="border-b border-gray-100 px-4 py-3">
              <h2 className="text-sm font-bold text-gray-900">Rule trace</h2>
              <p className="text-xs text-gray-500">
                Every rule considered, including those that did not fire. &ldquo;No rule mentioned it&rdquo;
                and &ldquo;a rule considered it and declined to act&rdquo; are different statements.
              </p>
            </div>
            <ul className="divide-y divide-gray-100">
              {a.trace.map((t) => (
                <li key={t.rule_id} className="flex items-start gap-3 px-4 py-3">
                  <span className="mt-0.5 shrink-0">
                    {t.fired ? (
                      <Check size={16} className="text-green-600" />
                    ) : t.in_force ? (
                      <Minus size={16} className="text-gray-300" />
                    ) : (
                      <CircleSlash size={16} className="text-gray-300" />
                    )}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900">
                      {t.rule_key} <span className="font-mono text-xs text-gray-400">v{t.version}</span>
                      {!t.in_force && (
                        <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-gray-500">
                          not in force
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-gray-500">{t.name}</p>
                    <p className="mt-1 text-sm text-gray-600">{t.why}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {data.decision_status === "pending_review" ? (
        <section className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
          <h2 className="text-sm font-bold text-gray-900">Record your decision</h2>
          <p className="mt-1 text-xs text-gray-500">
            You hold the authority. The recommendation is advisory and your decision is logged either way.
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {DECISIONS.map((d) => (
              <button
                key={d.value}
                type="button"
                onClick={() => setDecision(d.value)}
                className={`rounded-lg border px-3 py-2 text-sm font-semibold transition-colors ${
                  decision === d.value
                    ? "border-v3-violet bg-v3-violet text-white"
                    : "border-gray-200 text-gray-700 hover:border-v3-violet hover:text-v3-violet"
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>

          {isOverride && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="flex items-center gap-2 text-sm font-bold text-amber-800">
                <TriangleAlert size={15} /> This overrides the recommendation
              </p>
              <p className="mt-1 text-xs text-amber-700">
                The rules recommended <strong>{recommended?.replace("_", " ")}</strong>. Recording a
                different outcome needs a reason — that disagreement is how the rules learn they are wrong.
              </p>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                placeholder="Why does this case warrant a different decision?"
                className="mt-2 w-full rounded-lg border border-amber-200 px-3 py-2 text-sm focus:border-amber-400 focus:outline-none"
              />
            </div>
          )}

          <button
            type="button"
            disabled={!decision || saving || (isOverride && !reason.trim())}
            onClick={onSubmit}
            className="mt-3 rounded-lg bg-v3-teal px-4 py-2 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? "Recording…" : "Record decision"}
          </button>

          {result && <p className="mt-2 text-sm font-semibold text-v3-teal">{result}</p>}
          {error && <p className="mt-2 text-sm text-v3-rose">{error}</p>}
        </section>
      ) : (
        <section className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
          <p className="text-xs font-bold uppercase tracking-wide text-gray-400">Decision</p>
          <p className="mt-1 text-lg font-bold text-gray-900">
            {data.decision_status.replace(/_/g, " ")}
          </p>
          <p className="mt-1 text-sm text-gray-500">{data.underwriting_reason}</p>
        </section>
      )}

      <section className="rounded-xl border border-gray-100 bg-white shadow-card">
        <div className="border-b border-gray-100 px-4 py-3">
          <h2 className="text-sm font-bold text-gray-900">Decision trail</h2>
          <p className="text-xs text-gray-500">
            Append-only. Nothing here is edited, so the sequence reconstructs how the decision was reached.
          </p>
        </div>
        <ol className="divide-y divide-gray-100">
          {data.trail.map((e) => (
            <li key={e.log_id} className="flex items-start gap-3 px-4 py-3">
              <span className="mt-0.5 font-mono text-xs text-gray-300">{e.event_seq}</span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-900">
                  {e.event_type.replace(/_/g, " ")}
                  {e.is_override && (
                    <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-700">
                      override
                    </span>
                  )}
                </p>
                <p className="text-xs text-gray-500">
                  {e.actor} · {e.actor_type} · {e.decided_at?.slice(0, 19).replace("T", " ")}
                  {e.decision ? ` · ${e.decision.replace(/_/g, " ")}` : ""}
                </p>
                {e.override_reason && (
                  <p className="mt-1 text-sm italic text-gray-600">&ldquo;{e.override_reason}&rdquo;</p>
                )}
              </div>
            </li>
          ))}
        </ol>
      </section>

      {data.policy && (
        <section className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
          <p className="text-xs font-bold uppercase tracking-wide text-gray-400">Issued policy</p>
          <p className="mt-1 text-sm text-gray-900">
            {data.policy.policy_number} · {data.policy.policy_status} · effective{" "}
            {data.policy.effective_date}
          </p>
          {data.policy.claim_count > 0 && (
            <p className="mt-1 text-sm font-semibold text-v3-rose">
              {data.policy.claim_count} claim{data.policy.claim_count === 1 ? "" : "s"} on this policy
            </p>
          )}
        </section>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">{children}</div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-3 shadow-card">
      <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1 text-lg font-bold text-gray-900 ${mono ? "font-mono tabular-nums" : ""}`}>
        {value}
      </p>
    </div>
  );
}
