"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Lightbulb, ListChecks, MessageSquareWarning, Sparkles } from "lucide-react";
import { intelligenceApi, type InsightsView } from "@/services/advisorApi";

const PRIORITY_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-600"
};

export default function InsightsPage() {
  const [data, setData] = useState<InsightsView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    intelligenceApi.getInsights().then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Insights</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">What needs your attention, across the whole book</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          A rolling view rather than just today — the same transparent signals My Day and priority scoring use.
        </p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!data && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {data && (
        <>
          <section className="rounded-lg border border-gray-100 bg-white shadow-card">
            <PanelHeader
              icon={<Sparkles size={16} className="text-v3-violet" />}
              title="Top Priority Customers"
              subtitle="Transparent scoring — every customer's score is a sum of stated reasons, never a black box."
            />
            <div className="divide-y divide-gray-100">
              {data.top_priority_customers.slice(0, 8).map((c) => (
                <div key={c.customer_id} className="p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Link href={`/advisor/customers/${c.customer_id}`} className="font-semibold text-v3-violet hover:underline">
                      {c.name}
                    </Link>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_TONE[c.priority]}`}>
                      {c.priority} · {c.score}
                    </span>
                  </div>
                  <ul className="mt-2 space-y-0.5">
                    {c.reasons.slice(0, 3).map((r) => (
                      <li key={r.label} className="text-xs text-gray-600">• {r.label}</li>
                    ))}
                  </ul>
                </div>
              ))}
              {data.top_priority_customers.length === 0 && <Empty text="No customers scored yet." />}
            </div>
          </section>

          <div className="grid gap-5 lg:grid-cols-2">
            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader icon={<AlertTriangle size={16} className="text-v3-rose" />} title="Customers Requiring Attention" />
              <div className="divide-y divide-gray-100">
                {data.customers_requiring_attention.map((c) => (
                  <Link key={c.customer_id} href={`/advisor/customers/${c.customer_id}`} className="block p-4 hover:bg-gray-50">
                    <p className="font-semibold text-gray-900">{c.name}</p>
                    <p className="mt-0.5 text-xs text-gray-500">{c.life_stage}</p>
                  </Link>
                ))}
                {data.customers_requiring_attention.length === 0 && <Empty text="Nobody urgent right now." />}
              </div>
            </section>

            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader icon={<Lightbulb size={16} className="text-amber-600" />} title="New Life Events" />
              <div className="divide-y divide-gray-100">
                {data.new_life_events.map((e, i) => (
                  <Link key={i} href={`/advisor/customers/${e.customer_id}`} className="block p-4 hover:bg-gray-50">
                    <p className="font-semibold text-gray-900">{e.customer_name}</p>
                    <p className="mt-0.5 text-xs text-gray-500">{e.description} ({e.days_ago}d ago)</p>
                  </Link>
                ))}
                {data.new_life_events.length === 0 && <Empty text="No recent life events." />}
              </div>
            </section>

            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader icon={<ListChecks size={16} className="text-v3-teal" />} title="Emerging Needs" />
              <div className="divide-y divide-gray-100">
                {data.emerging_needs.map((n) => (
                  <Link key={n.memory_id} href={`/advisor/customers/${n.customer_id}/memory`} className="block p-4 hover:bg-gray-50">
                    <p className="text-sm text-gray-900">{n.value}</p>
                    <p className="mt-0.5 text-xs text-v3-violet">{n.customer_name}</p>
                  </Link>
                ))}
                {data.emerging_needs.length === 0 && <Empty text="No emerging needs pending review." />}
              </div>
            </section>

            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader icon={<MessageSquareWarning size={16} className="text-v3-violet" />} title="Unresolved Conversations" />
              <div className="divide-y divide-gray-100">
                {data.unresolved_conversations.map((n) => (
                  <Link key={n.memory_id} href={`/advisor/customers/${n.customer_id}/memory`} className="block p-4 hover:bg-gray-50">
                    <p className="text-sm text-gray-900">{n.value}</p>
                    <p className="mt-0.5 text-xs text-v3-violet">
                      {n.customer_name} <ArrowRight size={11} className="inline" />
                    </p>
                  </Link>
                ))}
                {data.unresolved_conversations.length === 0 && <Empty text="Nothing awaiting a decision." />}
              </div>
            </section>
          </div>

          <section className="rounded-lg border border-gray-100 bg-white shadow-card">
            <PanelHeader icon={<ListChecks size={16} className="text-v3-teal" />} title="Follow-Up Opportunities" />
            <div className="divide-y divide-gray-100">
              {data.followup_opportunities.map((f) => (
                <Link key={f.followup_id} href={`/advisor/customers/${f.customer_id}`} className="flex items-center justify-between gap-2 p-4 hover:bg-gray-50">
                  <span>
                    <span className="block text-sm text-gray-900">{f.title}</span>
                    <span className="mt-0.5 block text-xs text-v3-violet">{f.customer_name}</span>
                  </span>
                  <span className="text-xs font-semibold text-gray-500">Due {f.due_date}</span>
                </Link>
              ))}
              {data.followup_opportunities.length === 0 && <Empty text="No open follow-ups." />}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function PanelHeader({ icon, title, subtitle }: { icon: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="border-b border-gray-100 px-4 py-3">
      <h2 className="inline-flex items-center gap-1.5 text-sm font-bold text-gray-900">
        {icon} {title}
      </h2>
      {subtitle && <p className="mt-1 text-xs text-gray-500">{subtitle}</p>}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="p-4 text-sm text-gray-400">{text}</p>;
}
