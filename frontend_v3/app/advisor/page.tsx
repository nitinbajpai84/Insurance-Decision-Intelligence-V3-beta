"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock,
  FileUp,
  Link as LinkIcon,
  RefreshCw,
  Sparkles,
  UserRoundCheck
} from "lucide-react";
import { advisorApi, type CalendarMeeting, type CustomerListItem, type MyDay } from "@/services/advisorApi";

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
          {day.calendar_meetings_today.length > 0 && (
            <section className="rounded-lg border border-v3-teal/20 bg-v3-teal/5 px-5 py-4">
              <p className="text-lg font-bold text-gray-900">{day.meetings_message}</p>
              {day.summary.unmatched_meetings > 0 && (
                <p className="mt-1 text-sm text-amber-700">
                  {day.summary.unmatched_meetings} calendar entr
                  {day.summary.unmatched_meetings === 1 ? "y needs" : "ies need"} a customer match.{" "}
                  <Link href="/advisor/meetings/match" className="font-bold underline">
                    Resolve now
                  </Link>
                </p>
              )}
            </section>
          )}

          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Customer meetings today" value={day.summary.customer_meetings_today} icon={<CalendarDays size={17} className="text-v3-teal" />} />
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
              <PanelHeader
                title="Today's Meetings"
                subtitle={
                  day.calendar_meetings_today.length > 0
                    ? day.meetings_message
                    : "Connect a calendar or import an .ics file to see today's schedule."
                }
              />
              <div className="divide-y divide-gray-100">
                {day.calendar_meetings_today.map((meeting) => (
                  <MeetingRow key={meeting.meeting_id} meeting={meeting} />
                ))}
                {day.calendar_meetings_today.length === 0 && (
                  <div className="p-4">
                    <p className="text-sm text-gray-400">No calendar meetings for today.</p>
                    <Link
                      href="/advisor/connections"
                      className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline"
                    >
                      Open Connection Center <ArrowRight size={13} />
                    </Link>
                  </div>
                )}
              </div>
            </section>
          </div>

          {(day.meetings_requiring_preparation.length > 0 ||
            day.meetings_awaiting_processing.length > 0 ||
            day.memory_updates_awaiting_approval.length > 0 ||
            day.overdue_followups.length > 0) && (
            <section>
              <h2 className="text-base font-bold text-gray-900">Meeting lifecycle</h2>
              <p className="mt-1 text-sm text-gray-500">Before, during, and after — what still needs your attention.</p>
              <div className="mt-3 grid gap-5 lg:grid-cols-2 xl:grid-cols-4">
                <LifecyclePanel
                  title="Requiring Preparation"
                  count={day.summary.meetings_requiring_preparation}
                  icon={<Sparkles size={15} className="text-v3-violet" />}
                >
                  {day.meetings_requiring_preparation.map((m) => (
                    <div key={m.meeting_id} className="p-3">
                      <Link href={`/advisor/customers/${m.customer_id}`} className="text-sm font-semibold text-v3-violet hover:underline">
                        {m.customer_name}
                      </Link>
                      <p className="mt-0.5 text-xs text-gray-500">{m.date} · {m.time_label}</p>
                      <Link
                        href={`/advisor/customers/${m.customer_id}/briefing`}
                        className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline"
                      >
                        Prepare <ArrowRight size={12} />
                      </Link>
                    </div>
                  ))}
                  {day.meetings_requiring_preparation.length === 0 && <EmptyState text="Everything is prepared." />}
                </LifecyclePanel>

                <LifecyclePanel
                  title="Awaiting Processing"
                  count={day.summary.meetings_awaiting_processing}
                  icon={<FileUp size={15} className="text-amber-600" />}
                >
                  {day.meetings_awaiting_processing.map((m) => (
                    <div key={m.meeting_id} className="p-3">
                      <Link href={`/advisor/customers/${m.customer_id}`} className="text-sm font-semibold text-v3-violet hover:underline">
                        {m.customer_name}
                      </Link>
                      <p className="mt-0.5 text-xs text-gray-500">Met {m.date}</p>
                      <Link
                        href={`/advisor/customers/${m.customer_id}/conversations/new`}
                        className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-amber-700 hover:underline"
                      >
                        Upload transcript or notes <ArrowRight size={12} />
                      </Link>
                    </div>
                  ))}
                  {day.meetings_awaiting_processing.length === 0 && <EmptyState text="Nothing waiting on you." />}
                </LifecyclePanel>

                <LifecyclePanel
                  title="Memory Updates Pending"
                  count={day.summary.memory_updates_awaiting_approval}
                  icon={<CheckCircle2 size={15} className="text-v3-teal" />}
                >
                  {day.memory_updates_awaiting_approval.map((m) => (
                    <div key={m.memory_id} className="p-3">
                      <p className="text-sm text-gray-900">{m.value}</p>
                      <Link
                        href={`/advisor/customers/${m.customer_id}/memory`}
                        className="mt-1 inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline"
                      >
                        {m.customer_name} <ArrowRight size={12} />
                      </Link>
                      {m.has_conflict && <p className="mt-1 text-[11px] font-bold uppercase text-amber-700">Conflict</p>}
                    </div>
                  ))}
                  {day.memory_updates_awaiting_approval.length === 0 && <EmptyState text="No proposals waiting." />}
                </LifecyclePanel>

                <LifecyclePanel
                  title="Overdue Follow-Ups"
                  count={day.summary.overdue_followups}
                  icon={<Clock size={15} className="text-v3-rose" />}
                >
                  {day.overdue_followups.map((f) => (
                    <div key={f.followup_id} className="p-3">
                      <p className="text-sm text-gray-900">{f.title}</p>
                      <div className="mt-1 flex items-center justify-between gap-2">
                        <Link href={`/advisor/customers/${f.customer_id}`} className="text-xs font-bold text-v3-violet hover:underline">
                          {f.customer_name}
                        </Link>
                        <span className="text-[11px] font-bold text-v3-rose">Due {f.due_date}</span>
                      </div>
                    </div>
                  ))}
                  {day.overdue_followups.length === 0 && <EmptyState text="Nothing overdue." />}
                </LifecyclePanel>
              </div>
            </section>
          )}

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

function LifecyclePanel({
  title,
  count,
  icon,
  children
}: {
  title: string;
  count: number;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-gray-100 bg-white shadow-card">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-gray-900">
          {icon} {title}
        </span>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-bold text-gray-600">{count}</span>
      </div>
      <div className="max-h-72 divide-y divide-gray-100 overflow-y-auto">{children}</div>
    </section>
  );
}

function MeetingRow({ meeting }: { meeting: CalendarMeeting }) {
  const matched = meeting.match_status === "matched";
  return (
    <div className="p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        {matched && meeting.customer_id ? (
          <Link href={`/advisor/customers/${meeting.customer_id}`} className="font-semibold text-v3-violet hover:underline">
            {meeting.customer_name}
          </Link>
        ) : (
          <span className="font-semibold text-gray-900">{meeting.title}</span>
        )}
        <span className="text-sm font-bold text-gray-700">{meeting.time_label}</span>
      </div>

      <p className="mt-1 text-xs text-gray-500">{meeting.source_label}</p>
      <p className={`mt-1 text-xs font-semibold ${matched ? "text-v3-teal" : "text-amber-700"}`}>
        {meeting.match_label}
      </p>
      {matched && <p className="mt-1 text-sm text-gray-600">{meeting.title}</p>}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {matched && meeting.customer_id ? (
          // Preparation stays an explicit action — opening My Day never
          // generates a briefing on its own.
          <Link
            href={`/advisor/customers/${meeting.customer_id}/briefing`}
            className="inline-flex items-center gap-1 rounded-lg bg-v3-violet px-3 py-1.5 text-xs font-bold text-white hover:bg-v3-violetDark"
          >
            <Sparkles size={13} /> Prepare for meeting
          </Link>
        ) : (
          <Link
            href="/advisor/meetings/match"
            className="inline-flex items-center gap-1 rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-bold text-amber-700 hover:bg-amber-50"
          >
            <UserRoundCheck size={13} /> Match customer
          </Link>
        )}
        {meeting.meeting_link && (
          <a
            href={meeting.meeting_link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline"
          >
            <LinkIcon size={12} /> Join
          </a>
        )}
        {meeting.location && <span className="text-xs text-gray-500">{meeting.location}</span>}
      </div>
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
