"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Search, SlidersHorizontal } from "lucide-react";
import { advisorApi, type CustomerListItem } from "@/services/advisorApi";

const PRIORITY_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-600"
};

export default function CustomerListPage() {
  const [customers, setCustomers] = useState<CustomerListItem[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [signalFilter, setSignalFilter] = useState("all");

  useEffect(() => {
    advisorApi.listCustomers().then(setCustomers).catch((e) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    if (!customers) return [];
    return customers.filter((c) => {
      const q = query.toLowerCase();
      const matchesQuery = !q || c.name.toLowerCase().includes(q) || c.life_stage.toLowerCase().includes(q);
      const matchesPriority = priorityFilter === "all" || c.priority === priorityFilter;
      const matchesSignal =
        signalFilter === "all" ||
        (signalFilter === "stale" && c.is_stale) ||
        (signalFilter === "events" && c.most_recent_life_event_days_ago !== null && c.most_recent_life_event_days_ago <= 90) ||
        (signalFilter === "concerns" && c.open_concerns_count > 0);
      return matchesQuery && matchesPriority && matchesSignal;
    });
  }, [customers, query, priorityFilter, signalFilter]);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Customers</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Customer intelligence</h1>
        <p className="mt-1 text-sm text-gray-500">Search the book, inspect priority signals, and open Customer 360.</p>
      </div>

      <section className="rounded-lg border border-gray-100 bg-white p-4 shadow-card">
        <div className="flex flex-wrap gap-3">
          <div className="relative min-w-[260px] flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name or life stage..."
              className="h-10 w-full rounded-lg border border-gray-200 pl-9 pr-3 text-sm outline-none focus:border-v3-violet focus:ring-2 focus:ring-v3-violet/20"
            />
          </div>
          <Select value={priorityFilter} onChange={setPriorityFilter} options={[
            ["all", "All priorities"],
            ["high", "High priority"],
            ["medium", "Medium priority"],
            ["low", "Low priority"]
          ]} />
          <Select value={signalFilter} onChange={setSignalFilter} options={[
            ["all", "All signals"],
            ["stale", "Stale information"],
            ["events", "Recent events"],
            ["concerns", "Open concerns"]
          ]} icon={<SlidersHorizontal size={15} />} />
        </div>
      </section>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!customers && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {customers && (
        <section className="rounded-lg border border-gray-100 bg-white shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs font-bold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-5 py-3">Customer</th>
                  <th className="px-5 py-3">Priority</th>
                  <th className="px-5 py-3">Last contact</th>
                  <th className="px-5 py-3">Signal</th>
                  <th className="px-5 py-3 text-right">Customer 360</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((c) => (
                  <tr key={c.customer_id} className="hover:bg-v3-violet/5">
                    <td className="px-5 py-3">
                      <Link href={`/advisor/customers/${c.customer_id}`} className="font-semibold text-v3-violet hover:underline">
                        {c.name}
                      </Link>
                      <p className="text-xs text-gray-500">{c.life_stage}</p>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_TONE[c.priority]}`}>{c.priority}</span>
                    </td>
                    <td className="px-5 py-3 text-gray-600">
                      {c.last_contact_date || "No contact recorded"}
                      {c.is_stale && <span className="ml-2 text-[10px] font-bold uppercase text-amber-600">stale</span>}
                    </td>
                    <td className="max-w-xs px-5 py-3 text-gray-600">{c.most_recent_life_event || `${c.open_concerns_count} open concern(s)`}</td>
                    <td className="px-5 py-3 text-right">
                      <Link href={`/advisor/customers/${c.customer_id}`} className="inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline">
                        Open <ArrowRight size={13} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 && <p className="p-5 text-sm text-gray-400">No customers match your filters.</p>}
        </section>
      )}
    </div>
  );
}

function Select({ value, onChange, options, icon }: { value: string; onChange: (value: string) => void; options: string[][]; icon?: React.ReactNode }) {
  return (
    <label className="inline-flex h-10 items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-700 focus-within:border-v3-violet">
      {icon}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="bg-transparent outline-none">
        {options.map(([optionValue, label]) => (
          <option key={optionValue} value={optionValue}>{label}</option>
        ))}
      </select>
    </label>
  );
}
