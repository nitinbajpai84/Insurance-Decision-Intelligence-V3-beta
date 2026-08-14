"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
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
  const [priorityFilter, setPriorityFilter] = useState<string>("all");

  useEffect(() => {
    advisorApi.listCustomers().then(setCustomers).catch((e) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    if (!customers) return [];
    return customers.filter((c) => {
      const matchesQuery = !query || c.name.toLowerCase().includes(query.toLowerCase()) || c.life_stage.toLowerCase().includes(query.toLowerCase());
      const matchesPriority = priorityFilter === "all" || c.priority === priorityFilter;
      return matchesQuery && matchesPriority;
    });
  }, [customers, query, priorityFilter]);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Advisor workspace</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Customers</h1>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or life stage…"
            className="h-10 w-full rounded-lg border border-gray-200 pl-9 pr-3 text-sm outline-none focus:border-v3-violet focus:ring-2 focus:ring-v3-violet/20"
          />
        </div>
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold outline-none focus:border-v3-violet"
        >
          <option value="all">All priorities</option>
          <option value="high">High priority</option>
          <option value="medium">Medium priority</option>
          <option value="low">Low priority</option>
        </select>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!customers && !error && <p className="text-sm text-gray-400">Loading…</p>}

      {customers && (
        <div className="grid gap-3 sm:grid-cols-2">
          {filtered.map((c) => (
            <Link
              key={c.customer_id}
              href={`/advisor/customers/${c.customer_id}`}
              className="rounded-xl border border-gray-100 bg-white p-4 shadow-card transition-all hover:-translate-y-0.5 hover:border-v3-violet/30"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="font-bold text-gray-900">{c.name}</p>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_TONE[c.priority]}`}>{c.priority}</span>
              </div>
              <p className="mt-1 text-xs text-gray-500">{c.life_stage}</p>
              <p className="mt-2 text-xs text-gray-400">Last contact: {c.last_contact_date || "—"}</p>
            </Link>
          ))}
          {filtered.length === 0 && <p className="col-span-2 text-sm text-gray-400">No customers match your search.</p>}
        </div>
      )}
    </div>
  );
}
