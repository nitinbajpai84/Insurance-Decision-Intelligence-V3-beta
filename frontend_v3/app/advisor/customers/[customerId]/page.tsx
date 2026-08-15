"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Brain, CalendarClock, Clock, FileText, ShieldCheck, Sparkles, Upload, Users } from "lucide-react";
import { advisorApi, money, type Customer360 } from "@/services/advisorApi";

const PRIORITY_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-600"
};

export default function CustomerProfilePage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [customer, setCustomer] = useState<Customer360 | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    advisorApi.getCustomer(customerId).then(setCustomer).catch((e) => setError(e.message));
  }, [customerId]);

  if (error) return <div className="p-8 text-sm text-v3-rose">{error}</div>;
  if (!customer) return <div className="p-8 text-sm text-gray-400">Loading...</div>;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <section className="rounded-lg bg-v3-hero p-6 text-white shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-v3-teal">Customer 360</p>
            <h1 className="mt-1 text-2xl font-bold">{customer.name}</h1>
            <p className="mt-2 text-sm text-gray-300">
              {customer.life_stage} | Last contact: {customer.last_contact_date || "No contact recorded"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`/advisor/customers/${customerId}/conversations/new`} className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-2.5 text-sm font-bold text-white hover:bg-white/20">
              <Upload size={16} /> Capture
            </Link>
            <Link href={`/advisor/customers/${customerId}/memory`} className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-2.5 text-sm font-bold text-white hover:bg-white/20">
              <Clock size={16} /> Memory
            </Link>
            <Link href={`/advisor/customers/${customerId}/briefing`} className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2.5 text-sm font-bold text-white shadow-glow hover:bg-v3-violetDark">
              <Sparkles size={16} /> Prepare for Meeting <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
        <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-card">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-v3-violet" />
            <h2 className="text-base font-bold text-gray-900">Profile</h2>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <Fact label="Life stage" value={customer.life_stage} />
            <Fact label="Advisor" value={customer.advisor_name || "Not assigned"} />
            <Fact label="Open concerns" value={`${customer.open_concerns_count}`} />
          </dl>
          <h3 className="mt-5 text-xs font-bold uppercase tracking-wide text-gray-400">Family</h3>
          <div className="mt-2 space-y-2">
            {customer.family.map((f, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm">
                <span className="font-semibold text-gray-900">{f.name}</span>
                <span className="text-xs text-gray-500">{f.relationship}</span>
              </div>
            ))}
            {customer.family.length === 0 && <p className="text-sm text-gray-400">No family members recorded.</p>}
          </div>
        </section>

        <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-card">
          <div className="flex items-center gap-2">
            <Brain size={16} className="text-v3-teal" />
            <h2 className="text-base font-bold text-gray-900">AI Insights</h2>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Insight label="Priority" value={customer.priority} tone={PRIORITY_TONE[customer.priority]} />
            <Insight label="Information freshness" value={customer.is_stale ? "Stale" : "Current"} tone={customer.is_stale ? "bg-amber-50 text-amber-700" : "bg-green-50 text-green-700"} />
            <Insight label="Recent event" value={customer.most_recent_life_event_days_ago === null ? "None" : `${customer.most_recent_life_event_days_ago} days ago`} tone="bg-gray-100 text-gray-600" />
          </div>
          <p className="mt-4 text-xs leading-5 text-gray-500">Insights are derived from graph facts and conversation memory. AI-synthesized suggestions appear in meeting preparation and cite their evidence.</p>
        </section>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Goals">
          <BulletList items={customer.goals.map((g) => `${g.description} (${g.source})`)} empty="No goals recorded." />
        </Card>
        <Card title="Needs">
          <BulletList items={customer.needs.map((n) => `${n.description} (${n.source})`)} empty="No needs recorded." />
        </Card>
      </div>

      <Card title={`Policies (${customer.portfolio.length})`} icon={<ShieldCheck size={16} className="text-v3-teal" />}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs font-bold uppercase tracking-wide text-gray-400">
              <tr>
                <th className="py-2 pr-3">Product</th>
                <th className="py-2 pr-3">Line</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 text-right">Annual premium</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {customer.portfolio.map((p) => (
                <tr key={p.policy_id}>
                  <td className="py-2 pr-3 font-medium text-gray-800">{p.product_name}</td>
                  <td className="py-2 pr-3 text-gray-600">{p.line_of_business}</td>
                  <td className="py-2 pr-3 text-gray-600">{p.policy_status}</td>
                  <td className="py-2 text-right font-semibold text-gray-900">{money(p.annual_premium)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Recent Events" icon={<AlertTriangle size={16} className="text-amber-500" />}>
          <Timeline items={customer.life_events.map((e) => ({ date: e.date, text: `${e.description} (${e.source})` }))} empty="No life events recorded." />
        </Card>
        <Card title="Conversation History" icon={<CalendarClock size={16} className="text-v3-violet" />}>
          <Timeline items={customer.meetings.map((m) => ({ date: m.date, text: m.summary }))} empty="No meeting history recorded." />
        </Card>
      </div>

      <Card title="Customer Memory" icon={<Brain size={16} className="text-v3-teal" />}>
        <BulletList items={customer.relevant_conversations.map((c) => c.text)} empty="No semantic conversation memory found." />
      </Card>

      <Card title={`Claims (${customer.claims.length})`} icon={<FileText size={16} className="text-v3-teal" />}>
        {customer.claims.length === 0 ? (
          <p className="text-sm text-gray-400">No claims on file for this customer.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs font-bold uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="py-2 pr-3">Claim</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Loss cause</th>
                  <th className="py-2 text-right">Paid</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {customer.claims.map((c) => (
                  <tr key={c.claim_id}>
                    <td className="py-2 pr-3">
                      <Link href={`/claims/${c.claim_id}`} className="font-semibold text-v3-violet hover:underline">{c.claim_number}</Link>
                    </td>
                    <td className="py-2 pr-3 text-gray-600">{c.claim_status}</td>
                    <td className="py-2 pr-3 text-gray-600">{c.loss_cause || "Not recorded"}</td>
                    <td className="py-2 text-right font-semibold text-gray-900">{money(c.paid_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-right font-semibold text-gray-900">{value}</dd>
    </div>
  );
}

function Insight({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-lg border border-gray-100 p-3">
      <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
      <span className={`mt-2 inline-flex rounded-full px-2 py-0.5 text-xs font-bold uppercase ${tone}`}>{value}</span>
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
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

function BulletList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-gray-400">{empty}</p>;
  return (
    <ul className="space-y-2 text-sm text-gray-700">
      {items.map((it, i) => (
        <li key={i} className="rounded-lg bg-gray-50 px-3 py-2">{it}</li>
      ))}
    </ul>
  );
}

function Timeline({ items, empty }: { items: { date: string; text: string }[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-gray-400">{empty}</p>;
  return (
    <ul className="space-y-3 text-sm">
      {items.map((item, i) => (
        <li key={i} className="border-l-2 border-v3-violet/30 pl-3">
          <p className="text-xs font-bold text-gray-500">{item.date}</p>
          <p className="text-gray-700">{item.text}</p>
        </li>
      ))}
    </ul>
  );
}
