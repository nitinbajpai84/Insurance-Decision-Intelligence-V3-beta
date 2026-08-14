"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, Clock, Sparkles } from "lucide-react";
import { advisorApi, type CustomerListItem } from "@/services/advisorApi";

const PRIORITY_DOT: Record<string, string> = { high: "bg-v3-rose", medium: "bg-amber-500", low: "bg-gray-300" };
const PRIORITY_LABEL: Record<string, string> = { high: "🔴 High", medium: "🟠 Medium", low: "⚪ Low" };

export default function AgentHomePage() {
  const [customers, setCustomers] = useState<CustomerListItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    advisorApi.listCustomers().then(setCustomers).catch((e) => setError(e.message));
  }, []);

  const stale = useMemo(() => customers?.filter((c) => c.is_stale) || [], [customers]);
  const recentEvents = useMemo(
    () => customers?.filter((c) => c.most_recent_life_event_days_ago !== null && c.most_recent_life_event_days_ago <= 90) || [],
    [customers]
  );
  const highPriority = useMemo(() => customers?.filter((c) => c.priority === "high") || [], [customers]);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">My Day</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Agent Home</h1>
        <p className="mt-1 text-sm text-gray-500">Customers requiring attention, sorted by priority.</p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!customers && !error && <p className="text-sm text-gray-400">Loading…</p>}

      {customers && (
        <>
          <section className="grid gap-4 sm:grid-cols-3">
            <StatCard label="High priority" value={highPriority.length} icon={<AlertTriangle size={16} className="text-v3-rose" />} />
            <StatCard label="New life events (90d)" value={recentEvents.length} icon={<Sparkles size={16} className="text-v3-violet" />} />
            <StatCard label="Stale (180d+ no contact)" value={stale.length} icon={<Clock size={16} className="text-amber-500" />} />
          </section>

          <section className="rounded-xl border border-gray-100 bg-white shadow-card">
            <div className="border-b border-gray-100 px-5 py-3">
              <h2 className="text-base font-bold text-gray-900">Customers</h2>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-5 py-3">Customer</th>
                  <th className="px-5 py-3">Priority</th>
                  <th className="px-5 py-3">Last contact</th>
                  <th className="px-5 py-3">Recent life event</th>
                  <th className="px-5 py-3">AI Prep</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {customers.map((c) => (
                  <tr key={c.customer_id} className="hover:bg-v3-violet/5">
                    <td className="px-5 py-3">
                      <Link href={`/advisor/customers/${c.customer_id}`} className="font-semibold text-v3-violet hover:underline">
                        {c.name}
                      </Link>
                      <p className="text-xs text-gray-400">{c.life_stage}</p>
                    </td>
                    <td className="px-5 py-3">
                      <span className="inline-flex items-center gap-1.5 text-xs font-bold">
                        <span className={`h-2 w-2 rounded-full ${PRIORITY_DOT[c.priority]}`} /> {PRIORITY_LABEL[c.priority]}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-600">
                      {c.last_contact_date || "—"}
                      {c.is_stale && <span className="ml-1.5 text-[10px] font-bold uppercase text-amber-600">stale</span>}
                    </td>
                    <td className="px-5 py-3 max-w-xs truncate text-gray-600">{c.most_recent_life_event || "—"}</td>
                    <td className="px-5 py-3">
                      <Link
                        href={`/advisor/customers/${c.customer_id}/briefing`}
                        className="inline-flex items-center gap-1 rounded-full bg-v3-violet px-3 py-1 text-xs font-bold text-white hover:bg-v3-violetDark"
                      >
                        <Sparkles size={12} /> Prepare <ArrowRight size={12} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
        {icon}
      </div>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
