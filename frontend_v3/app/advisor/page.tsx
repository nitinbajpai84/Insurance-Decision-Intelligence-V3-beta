"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, Clock, RefreshCw, Sparkles, UserRoundCheck } from "lucide-react";
import { advisorApi, type CustomerListItem, type MyDay } from "@/services/advisorApi";

const PRIORITY_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-600"
};

export default function MyDayPage() {
  const [day, setDay] = useState<MyDay | null>(null);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const [error, setError] = useState("");

  function load() {
    setError("");
    advisorApi.getMyDay().then(setDay).catch((e) => setError(e.message));
  }

  useEffect(() => {
    const onboardingState = localStorage.getItem("advisor_onboarding_complete");
    setOnboardingComplete(onboardingState === "true" || onboardingState === "skipped");
    load();
  }, []);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">My Day</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Today&apos;s advisor workspace</h1>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">Onboard, connect, prepare, meet, capture, remember, and act from one daily view.</p>
        </div>
        <button onClick={load} className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:border-v3-violet hover:text-v3-violet">
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {!onboardingComplete && (
        <section className="rounded-lg border border-v3-teal/20 bg-white p-4 shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-gray-900">Finish your advisor setup</p>
              <p className="mt-1 text-sm text-gray-500">Set your profile, choose data sources, and review the initial customer import result.</p>
            </div>
            <Link href="/advisor/onboarding" className="inline-flex items-center gap-2 rounded-lg bg-v3-teal px-3 py-2 text-sm font-bold text-white hover:bg-teal-700">
              Continue onboarding <ArrowRight size={15} />
            </Link>
          </div>
        </section>
      )}

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!day && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {day && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Meetings today" value={day.summary.meetings_today} icon={<CalendarDays size={17} className="text-v3-teal" />} />
            <StatCard label="Need attention" value={day.summary.customers_requiring_attention} icon={<AlertTriangle size={17} className="text-v3-rose" />} />
            <StatCard label="Pending follow-ups" value={day.summary.pending_followups} icon={<CheckCircle2 size={17} className="text-v3-violet" />} />
            <StatCard label="Stale info" value={day.summary.stale_customer_information} icon={<Clock size={17} className="text-amber-600" />} />
          </section>

          <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader title="Customers Requiring Attention" subtitle="Sorted by deterministic priority signals from the customer graph." />
              <div className="divide-y divide-gray-100">
                {day.customers_requiring_attention.map((customer) => (
                  <CustomerRow key={customer.customer_id} customer={customer} />
                ))}
                {day.customers_requiring_attention.length === 0 && <EmptyState text="No customers require attention today." />}
              </div>
            </section>

            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader title="Today's Meetings" subtitle="Calendar integrations are not connected yet." />
              <div className="divide-y divide-gray-100">
                {day.meetings_today.map((meeting) => (
                  <div key={`${meeting.customer_id}-${meeting.date}`} className="p-4">
                    <Link href={`/advisor/customers/${meeting.customer_id}`} className="font-semibold text-v3-violet hover:underline">
                      {meeting.customer_name}
                    </Link>
                    <p className="mt-1 text-sm text-gray-600">{meeting.summary}</p>
                    <Link href={`/advisor/customers/${meeting.customer_id}/briefing`} className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline">
                      Prepare briefing <ArrowRight size={13} />
                    </Link>
                  </div>
                ))}
                {day.meetings_today.length === 0 && <EmptyState text="No meetings are scheduled for today." />}
              </div>
            </section>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <MiniPanel title="New Customer Events" items={day.new_customer_events} empty="No recent life events." />
            <MiniPanel title="High-Priority Customers" items={day.high_priority_customers} empty="No high-priority customers." />
            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader title="Pending Follow-Ups" subtitle="Derived from stale data, open concerns, and recent changes." />
              <div className="divide-y divide-gray-100">
                {day.pending_followups.map((task) => (
                  <div key={task.task_id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{task.title}</p>
                        <Link href={`/advisor/customers/${task.customer_id}`} className="text-xs font-semibold text-v3-violet hover:underline">
                          {task.customer_name}
                        </Link>
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_TONE[task.priority]}`}>{task.priority}</span>
                    </div>
                  </div>
                ))}
                {day.pending_followups.length === 0 && <EmptyState text="No pending follow-ups." />}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 shadow-card">
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
        {icon}
      </div>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

function PanelHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-gray-100 px-5 py-4">
      <h2 className="text-base font-bold text-gray-900">{title}</h2>
      {subtitle && <p className="mt-1 text-xs text-gray-500">{subtitle}</p>}
    </div>
  );
}

function CustomerRow({ customer }: { customer: CustomerListItem }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div>
        <Link href={`/advisor/customers/${customer.customer_id}`} className="font-semibold text-v3-violet hover:underline">
          {customer.name}
        </Link>
        <p className="mt-0.5 text-xs text-gray-500">{customer.life_stage}</p>
        {customer.most_recent_life_event && <p className="mt-1 text-xs text-gray-500">{customer.most_recent_life_event}</p>}
      </div>
      <div className="flex items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_TONE[customer.priority]}`}>{customer.priority}</span>
        <Link href={`/advisor/customers/${customer.customer_id}/briefing`} className="inline-flex items-center gap-1 rounded-lg bg-v3-violet px-3 py-1.5 text-xs font-bold text-white hover:bg-v3-violetDark">
          <Sparkles size={13} /> Prepare
        </Link>
      </div>
    </div>
  );
}

function MiniPanel({ title, items, empty }: { title: string; items: CustomerListItem[]; empty: string }) {
  return (
    <section className="rounded-lg border border-gray-100 bg-white shadow-card">
      <PanelHeader title={title} />
      <div className="divide-y divide-gray-100">
        {items.map((customer) => (
          <div key={customer.customer_id} className="p-4">
            <div className="flex items-start gap-2">
              <UserRoundCheck size={15} className="mt-0.5 shrink-0 text-v3-teal" />
              <div>
                <Link href={`/advisor/customers/${customer.customer_id}`} className="text-sm font-semibold text-gray-900 hover:text-v3-violet">
                  {customer.name}
                </Link>
                <p className="mt-1 text-xs text-gray-500">{customer.most_recent_life_event || customer.life_stage}</p>
              </div>
            </div>
          </div>
        ))}
        {items.length === 0 && <EmptyState text={empty} />}
      </div>
    </section>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="p-4 text-sm text-gray-400">{text}</p>;
}
