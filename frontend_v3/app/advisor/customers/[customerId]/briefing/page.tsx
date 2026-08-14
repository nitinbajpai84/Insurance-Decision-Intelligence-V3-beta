"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, HelpCircle, MessageSquareQuote, RefreshCw, Sparkles } from "lucide-react";
import { advisorApi, type Briefing } from "@/services/advisorApi";

const PRIORITY_DOT: Record<string, string> = { high: "🔴", medium: "🟠", low: "⚪" };

export default function MeetingBriefingPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    advisorApi
      .prepareMeeting(customerId)
      .then(setBriefing)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [customerId]);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <Link href={`/advisor/customers/${customerId}`} className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to profile
      </Link>

      {loading && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-gray-100 bg-white p-16 shadow-card">
          <Sparkles size={28} className="animate-pulse text-v3-violet" />
          <p className="text-sm font-semibold text-gray-600">Preparing your meeting briefing…</p>
          <p className="text-xs text-gray-400">Retrieving graph relationships, semantic memory, and portfolio, then reasoning with Gemini.</p>
        </div>
      )}

      {error && !loading && (
        <div className="rounded-xl border border-v3-rose/20 bg-v3-rose/5 p-5 text-sm text-v3-rose">
          {error}
          <button onClick={load} className="ml-3 inline-flex items-center gap-1 font-bold underline">
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      )}

      {briefing && !loading && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Meeting Briefing</p>
            <button onClick={load} className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
              <RefreshCw size={12} /> Regenerate
            </button>
          </div>

          {briefing.gemini_error && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              AI reasoning was unavailable ({briefing.gemini_error}) — showing grounded facts only, without executive summary or suggestions.
            </div>
          )}

          <Section title={`WHO IS ${briefing.name.split(" ")[0].toUpperCase()}?`}>
            <p className="text-sm leading-6 text-gray-700">{briefing.who_is_customer.value || "Not available."}</p>
          </Section>

          <Section title="WHAT CHANGED?">
            {briefing.what_changed.length === 0 ? (
              <p className="text-sm text-gray-400">No significant changes identified.</p>
            ) : (
              <ul className="space-y-2">
                {briefing.what_changed.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span>{PRIORITY_DOT[c.priority]}</span>
                    <div>
                      <span className="text-gray-800">{c.description}</span>
                      <EvidenceLine text={c.based_on} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title={`WHAT MATTERS TO ${briefing.name.split(" ")[0].toUpperCase()}?`}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1 text-xs font-bold uppercase text-gray-400">Goals</p>
                <BulletList items={briefing.what_matters.goals.map((g) => g.description)} />
              </div>
              <div>
                <p className="mb-1 text-xs font-bold uppercase text-gray-400">Needs</p>
                <BulletList items={briefing.what_matters.needs.map((n) => n.description)} />
              </div>
            </div>
          </Section>

          <Section title={`WHAT DID ${briefing.name.split(" ")[0].toUpperCase()} SAY?`} icon={<MessageSquareQuote size={16} className="text-v3-teal" />}>
            {briefing.what_they_said.length === 0 ? (
              <p className="text-sm text-gray-400">No relevant conversation notes found.</p>
            ) : (
              <div className="space-y-3">
                {briefing.what_they_said.map((q, i) => (
                  <blockquote key={i} className="border-l-2 border-v3-teal/40 pl-3 text-sm italic text-gray-700">
                    &ldquo;{q.text}&rdquo;
                  </blockquote>
                ))}
              </div>
            )}
          </Section>

          <Section title="WHAT SHOULD I ASK?" icon={<HelpCircle size={16} className="text-v3-violet" />}>
            {briefing.suggested_questions.length === 0 ? (
              <p className="text-sm text-gray-400">No suggested questions generated.</p>
            ) : (
              <ol className="space-y-2.5">
                {briefing.suggested_questions.map((q, i) => (
                  <li key={i} className="text-sm">
                    <span className="font-semibold text-gray-800">{i + 1}. {q.question}</span>
                    <EvidenceLine text={q.based_on} />
                  </li>
                ))}
              </ol>
            )}
          </Section>

          <Section title="WHAT SHOULD I REMEMBER?">
            <p className="mb-1 text-xs font-bold uppercase text-gray-400">Previous concerns</p>
            <BulletList items={briefing.what_to_remember.concerns.map((c) => c.topic)} />
            <p className="mb-1 mt-3 text-xs font-bold uppercase text-gray-400">Past meetings</p>
            <ul className="space-y-1.5 text-sm text-gray-700">
              {briefing.what_to_remember.past_meetings.map((m, i) => (
                <li key={i}><span className="text-xs text-gray-400">{m.date}:</span> {m.summary}</li>
              ))}
            </ul>
          </Section>

          <Section title="POTENTIAL DISCUSSION AREAS" icon={<AlertTriangle size={16} className="text-amber-500" />}>
            <p className="mb-3 text-xs text-gray-400">These are areas to explore with the customer — not product recommendations.</p>
            {briefing.potential_discussion_areas.length === 0 ? (
              <p className="text-sm text-gray-400">No discussion areas generated.</p>
            ) : (
              <div className="space-y-3">
                {briefing.potential_discussion_areas.map((d, i) => (
                  <div key={i} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                    <p className="font-semibold text-gray-900">{d.area}</p>
                    <p className="mt-0.5 text-sm text-gray-600">{d.why}</p>
                    <EvidenceLine text={d.based_on} />
                  </div>
                ))}
              </div>
            )}
          </Section>
        </>
      )}
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
      <div className="mb-3 flex items-center gap-2">
        {icon}
        <h2 className="text-sm font-bold tracking-wide text-gray-900">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function EvidenceLine({ text }: { text: string }) {
  return <p className="mt-0.5 text-[11px] text-gray-400">Source: {text}</p>;
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) return <p className="text-sm text-gray-400">None recorded.</p>;
  return (
    <ul className="list-disc space-y-1 pl-4 text-sm text-gray-700">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}
