"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, HelpCircle, MessageSquareQuote, RefreshCw, ShieldCheck, Sparkles, Users } from "lucide-react";
import { advisorApi, money, type Briefing } from "@/services/advisorApi";

const PRIORITY_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-600"
};

export default function MeetingBriefingPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    advisorApi.prepareMeeting(customerId).then(setBriefing).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }

  useEffect(load, [customerId]);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <Link href={`/advisor/customers/${customerId}`} className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to Customer 360
      </Link>

      {loading && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-gray-100 bg-white p-16 shadow-card">
          <Sparkles size={28} className="animate-pulse text-v3-violet" />
          <p className="text-sm font-semibold text-gray-600">Preparing your meeting briefing...</p>
          <p className="text-xs text-gray-400">Retrieving graph relationships, semantic memory, and portfolio, then reasoning with Gemini.</p>
        </div>
      )}

      {error && !loading && (
        <div className="rounded-lg border border-v3-rose/20 bg-v3-rose/5 p-5 text-sm text-v3-rose">
          {error}
          <button onClick={load} className="ml-3 inline-flex items-center gap-1 font-bold underline">
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      )}

      {briefing && !loading && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Prepare for Meeting</p>
              <h1 className="mt-1 text-2xl font-bold text-gray-900">{briefing.name}</h1>
            </div>
            <button onClick={load} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-500 hover:border-v3-violet hover:text-v3-violet">
              <RefreshCw size={12} /> Regenerate
            </button>
          </div>

          {briefing.gemini_error && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              AI reasoning was unavailable ({briefing.gemini_error}). Grounded customer facts are still shown.
            </div>
          )}

          <Section title="Who Is This Customer?" icon={<Users size={16} className="text-v3-violet" />}>
            <p className="text-sm leading-6 text-gray-700">{briefing.who_is_customer.value || "Not available."}</p>
            <Evidence text={briefing.who_is_customer.based_on} />
          </Section>

          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="What Changed?" icon={<AlertTriangle size={16} className="text-amber-500" />}>
              {briefing.what_changed.length === 0 ? (
                <p className="text-sm text-gray-400">No significant changes identified.</p>
              ) : (
                <div className="space-y-3">
                  {briefing.what_changed.map((change, i) => (
                    <div key={i} className="rounded-lg border border-gray-100 p-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_TONE[change.priority]}`}>{change.priority}</span>
                      <p className="mt-2 text-sm text-gray-800">{change.description}</p>
                      <Evidence text={change.based_on} />
                    </div>
                  ))}
                </div>
              )}
            </Section>

            <Section title="What Matters To Them?">
              <p className="mb-1 text-xs font-bold uppercase text-gray-400">Goals</p>
              <BulletList items={briefing.what_matters.goals.map((g) => `${g.description} (${g.source})`)} />
              <p className="mb-1 mt-4 text-xs font-bold uppercase text-gray-400">Needs</p>
              <BulletList items={briefing.what_matters.needs.map((n) => `${n.description} (${n.source})`)} />
            </Section>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="Previous Concerns And Preferences" icon={<MessageSquareQuote size={16} className="text-v3-teal" />}>
              <p className="mb-1 text-xs font-bold uppercase text-gray-400">Concerns</p>
              <BulletList items={briefing.what_to_remember.concerns.map((c) => `${c.topic} (${c.source})`)} />
              <p className="mb-1 mt-4 text-xs font-bold uppercase text-gray-400">Past meetings</p>
              <BulletList items={briefing.what_to_remember.past_meetings.map((m) => `${m.date}: ${m.summary}`)} />
            </Section>

            <Section title="Existing Portfolio" icon={<ShieldCheck size={16} className="text-v3-teal" />}>
              <div className="space-y-2">
                {briefing.portfolio.map((policy) => (
                  <div key={policy.policy_id} className="flex items-start justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2 text-sm">
                    <div>
                      <p className="font-semibold text-gray-900">{policy.product_name}</p>
                      <p className="text-xs text-gray-500">{policy.line_of_business} | {policy.policy_status}</p>
                    </div>
                    <p className="font-bold text-gray-900">{money(policy.annual_premium)}</p>
                  </div>
                ))}
                {briefing.portfolio.length === 0 && <p className="text-sm text-gray-400">No policies recorded.</p>}
              </div>
            </Section>
          </div>

          <Section title="Recent Conversations" icon={<MessageSquareQuote size={16} className="text-v3-teal" />}>
            {briefing.what_they_said.length === 0 ? (
              <p className="text-sm text-gray-400">No relevant conversation notes found.</p>
            ) : (
              <div className="space-y-3">
                {briefing.what_they_said.map((q, i) => (
                  <blockquote key={i} className="border-l-2 border-v3-teal/40 pl-3 text-sm italic text-gray-700">
                    {q.text}
                  </blockquote>
                ))}
              </div>
            )}
          </Section>

          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="Questions To Ask" icon={<HelpCircle size={16} className="text-v3-violet" />}>
              <Numbered items={briefing.suggested_questions.map((q) => ({ text: q.question, evidence: q.based_on }))} empty="No suggested questions generated." />
            </Section>

            <Section title="Potential Discussion Areas" icon={<AlertTriangle size={16} className="text-amber-500" />}>
              <p className="mb-3 text-xs text-gray-400">Areas to explore with the customer, not product recommendations.</p>
              <Numbered items={briefing.potential_discussion_areas.map((d) => ({ text: `${d.area}: ${d.why}`, evidence: d.based_on }))} empty="No discussion areas generated." />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-card">
      <div className="mb-3 flex items-center gap-2">
        {icon}
        <h2 className="text-base font-bold text-gray-900">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Evidence({ text }: { text: string }) {
  return <p className="mt-1 text-[11px] text-gray-400">Source: {text}</p>;
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) return <p className="text-sm text-gray-400">None recorded.</p>;
  return (
    <ul className="space-y-2 text-sm text-gray-700">
      {items.map((it, i) => <li key={i} className="rounded-lg bg-gray-50 px-3 py-2">{it}</li>)}
    </ul>
  );
}

function Numbered({ items, empty }: { items: { text: string; evidence: string }[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-gray-400">{empty}</p>;
  return (
    <ol className="space-y-3">
      {items.map((item, i) => (
        <li key={i} className="text-sm">
          <p className="font-semibold text-gray-800">{i + 1}. {item.text}</p>
          <Evidence text={item.evidence} />
        </li>
      ))}
    </ol>
  );
}
