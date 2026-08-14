"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Clock, Sparkles, Upload, Users } from "lucide-react";
import { advisorApi, money, type Customer360 } from "@/services/advisorApi";

const PRIORITY_LABEL: Record<string, string> = { high: "🔴 High priority", medium: "🟠 Medium priority", low: "⚪ Low priority" };

export default function CustomerProfilePage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [customer, setCustomer] = useState<Customer360 | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    advisorApi.getCustomer(customerId).then(setCustomer).catch((e) => setError(e.message));
  }, [customerId]);

  if (error) return <div className="p-8 text-sm text-v3-rose">{error}</div>;
  if (!customer) return <div className="p-8 text-sm text-gray-400">Loading…</div>;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <section className="rounded-xl bg-v3-hero p-6 text-white shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">{customer.name}</h1>
            <p className="mt-1 text-sm text-gray-300">
              {customer.life_stage} · {PRIORITY_LABEL[customer.priority]} · Last contact: {customer.last_contact_date || "—"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/advisor/customers/${customerId}/conversations/new`}
              className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-2.5 text-sm font-bold text-white hover:bg-white/20"
            >
              <Upload size={16} /> Upload Conversation
            </Link>
            <Link
              href={`/advisor/customers/${customerId}/memory`}
              className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-2.5 text-sm font-bold text-white hover:bg-white/20"
            >
              <Clock size={16} /> Memory Timeline
            </Link>
            <Link
              href={`/advisor/customers/${customerId}/briefing`}
              className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2.5 text-sm font-bold text-white shadow-glow hover:bg-v3-violetDark"
            >
              <Sparkles size={16} /> Prepare for Meeting <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </section>

      {/* Profile / Family */}
      <Card title="Profile & Family" icon={<Users size={16} className="text-v3-violet" />}>
        {customer.family.length === 0 ? (
          <p className="text-sm text-gray-400">No family members recorded.</p>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {customer.family.map((f, i) => (
              <li key={i} className="flex items-center justify-between">
                <span className="font-medium text-gray-800">{f.name}</span>
                <span className="text-xs text-gray-500">{f.relationship}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Goals + Needs */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card title="Goals">
          <BulletList items={customer.goals.map((g) => g.description)} empty="No goals recorded." />
        </Card>
        <Card title="Needs">
          <BulletList items={customer.needs.map((n) => n.description)} empty="No needs recorded." />
        </Card>
      </div>

      {/* Portfolio */}
      <Card title={`Portfolio (${customer.portfolio.length} policies)`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs font-bold uppercase tracking-wide text-gray-400">
              <tr>
                <th className="py-1.5 pr-3">Product</th>
                <th className="py-1.5 pr-3">Line</th>
                <th className="py-1.5 pr-3">Status</th>
                <th className="py-1.5 text-right">Annual premium</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {customer.portfolio.map((p) => (
                <tr key={p.policy_id}>
                  <td className="py-1.5 pr-3 font-medium text-gray-800">{p.product_name}</td>
                  <td className="py-1.5 pr-3 text-gray-600">{p.line_of_business}</td>
                  <td className="py-1.5 pr-3 text-gray-600">{p.policy_status}</td>
                  <td className="py-1.5 text-right font-semibold text-gray-900">{money(p.annual_premium)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Recent events */}
      <Card title="Recent Events" icon={customer.life_events.length > 0 ? <AlertTriangle size={16} className="text-amber-500" /> : undefined}>
        {customer.life_events.length === 0 ? (
          <p className="text-sm text-gray-400">No life events recorded.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {customer.life_events.map((e, i) => (
              <li key={i} className="flex items-start justify-between gap-3">
                <span className="text-gray-800">{e.description}</span>
                <span className="shrink-0 text-xs text-gray-400">{e.date}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Conversations / meeting timeline */}
      <Card title="Conversations">
        {customer.meetings.length === 0 ? (
          <p className="text-sm text-gray-400">No meeting history recorded.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {customer.meetings.map((m, i) => (
              <li key={i} className="border-l-2 border-v3-violet/30 pl-3">
                <p className="text-xs font-bold text-gray-500">{m.date}</p>
                <p className="text-gray-700">{m.summary}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
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
    <ul className="list-disc space-y-1 pl-4 text-sm text-gray-700">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}
