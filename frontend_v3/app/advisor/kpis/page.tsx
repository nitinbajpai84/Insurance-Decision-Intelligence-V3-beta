"use client";

import { useEffect, useState } from "react";
import { intelligenceApi, type KpiDashboard } from "@/services/advisorApi";

function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return key.includes("percent") ? `${value}%` : value.toLocaleString();
  }
  return String(value);
}

function label(key: string): string {
  return key
    .replace(/_percent$/, "")
    .replace(/_reason$/, "")
    .replace(/_note$/, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function CategorySection({ title, data, accent }: { title: string; data: Record<string, unknown>; accent: string }) {
  const entries = Object.entries(data).filter(([key]) => !key.endsWith("_reason") && !key.endsWith("_note"));
  return (
    <section className="rounded-lg border border-gray-100 bg-white shadow-card">
      <div className="border-b border-gray-100 px-5 py-4">
        <h2 className="text-sm font-bold text-gray-900">{title}</h2>
      </div>
      <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([key, value]) => {
          const reasonKey = `${key.replace(/_percent$/, "")}_reason`;
          const noteKey = `${key.replace(/_percent$/, "")}_note`;
          const reason = (data[reasonKey] || data[noteKey]) as string | undefined;
          const isNull = value === null;
          return (
            <div key={key} className="rounded-lg border border-gray-100 p-3">
              <p className="text-[11px] font-bold uppercase tracking-wide text-gray-400">{label(key)}</p>
              <p className={`mt-1 text-xl font-bold ${isNull ? "text-gray-300" : accent}`}>{formatValue(key, value)}</p>
              {isNull && reason && <p className="mt-1 text-[11px] leading-4 text-gray-400">{reason}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function KpiDashboardPage() {
  const [data, setData] = useState<KpiDashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    intelligenceApi.getKpis().then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Business KPIs</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Operating dashboard</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          Every figure here is computed from real data at request time. Where this product cannot measure something
          yet, it says so instead of showing a plausible-looking number.
        </p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!data && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {data && (
        <>
          <CategorySection title="Agent" data={data.agent} accent="text-v3-violet" />
          <CategorySection title="Customer" data={data.customer} accent="text-v3-teal" />
          <CategorySection title="AI" data={data.ai} accent="text-v3-violet" />
          <CategorySection title="Business" data={data.business} accent="text-v3-teal" />
          <CategorySection title="Guardrails" data={data.guardrails} accent="text-v3-rose" />
        </>
      )}
    </div>
  );
}
