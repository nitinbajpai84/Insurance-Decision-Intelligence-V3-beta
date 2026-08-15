"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, UserRoundCheck } from "lucide-react";
import {
  advisorApi,
  integrationApi,
  type CalendarMeeting,
  type CustomerListItem
} from "@/services/advisorApi";

export default function MeetingMatchPage() {
  const [meetings, setMeetings] = useState<CalendarMeeting[] | null>(null);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    Promise.all([advisorApi.listUnmatchedMeetings(), advisorApi.listCustomers()])
      .then(([meetingRows, customerRows]) => {
        setMeetings(meetingRows);
        setCustomers(customerRows);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function confirm(meeting: CalendarMeeting) {
    const customerId = choice[meeting.meeting_id];
    if (!customerId) {
      setError("Choose a customer for this meeting first.");
      return;
    }
    setBusy(meeting.meeting_id);
    setError("");
    setNotice("");
    try {
      const result = await integrationApi.matchMeeting(meeting.meeting_id, customerId);
      setNotice(
        result.identities_learned.length > 0
          ? `Matched to ${result.customer_name}. Future meetings with ${result.identities_learned.join(", ")} will match automatically.`
          : `Matched to ${result.customer_name}.`
      );
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <Link href="/advisor" className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to My Day
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Meetings</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Customer match required</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">
          These calendar entries could not be matched to a customer from their attendees. Confirming a match
          also teaches the system that attendee address, so it resolves automatically next time.
        </p>
      </div>

      {notice && (
        <p className="inline-flex items-center gap-2 rounded-lg border border-v3-teal/30 bg-v3-teal/5 px-4 py-3 text-sm text-teal-800">
          <CheckCircle2 size={15} /> {notice}
        </p>
      )}
      {error && <p className="rounded-lg border border-v3-rose/30 bg-v3-rose/5 px-4 py-3 text-sm text-v3-rose">{error}</p>}
      {!meetings && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {meetings?.length === 0 && (
        <section className="rounded-lg border border-gray-100 bg-white p-6 text-center shadow-card">
          <UserRoundCheck size={26} className="mx-auto text-v3-teal" />
          <p className="mt-2 font-bold text-gray-900">Every meeting is matched.</p>
          <p className="mt-1 text-sm text-gray-500">Nothing needs your attention here.</p>
        </section>
      )}

      {meetings?.map((meeting) => (
        <section key={meeting.meeting_id} className="rounded-lg border border-gray-100 bg-white p-5 shadow-card">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-bold text-gray-900">{meeting.title}</h2>
            <span className="text-sm font-bold text-gray-700">
              {meeting.date} · {meeting.time_label}
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-500">{meeting.source_label}</p>

          {meeting.attendees.length > 0 && (
            <p className="mt-2 text-sm text-gray-600">
              <span className="font-semibold text-gray-700">Attendees:</span> {meeting.attendees.join(", ")}
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <select
              value={choice[meeting.meeting_id] || ""}
              onChange={(e) => setChoice((prev) => ({ ...prev, [meeting.meeting_id]: e.target.value }))}
              className="h-10 min-w-[16rem] rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-v3-violet"
            >
              <option value="">Select a customer...</option>
              {customers.map((customer) => (
                <option key={customer.customer_id} value={customer.customer_id}>
                  {customer.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => confirm(meeting)}
              disabled={busy !== "" || !choice[meeting.meeting_id]}
              className="rounded-lg bg-v3-violet px-4 py-2 text-sm font-bold text-white hover:bg-v3-violetDark disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500"
            >
              {busy === meeting.meeting_id ? "Matching..." : "Confirm match"}
            </button>
          </div>
        </section>
      ))}
    </div>
  );
}
