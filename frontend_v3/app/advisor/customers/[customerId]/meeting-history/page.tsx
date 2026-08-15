"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ArrowLeft, CalendarClock, CheckSquare, Lightbulb, ListChecks } from "lucide-react";
import { advisorApi, type MeetingHistoryEntry } from "@/services/advisorApi";

const MEMORY_STATUS_TONE: Record<string, string> = {
  accepted: "bg-green-50 text-green-700",
  edited: "bg-v3-teal/10 text-v3-teal",
  rejected: "bg-gray-100 text-gray-500"
};

export default function MeetingHistoryPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [timeline, setTimeline] = useState<MeetingHistoryEntry[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    advisorApi.getMeetingHistory(customerId).then(setTimeline).catch((e) => setError(e.message));
  }, [customerId]);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <Link href={`/advisor/customers/${customerId}`} className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to profile
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Meeting History</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Every meeting, what it produced</h1>
        <p className="mt-1 text-sm text-gray-500">Summary, insights extracted, what happened to each, and follow-ups.</p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {!timeline && !error && <p className="text-sm text-gray-400">Loading...</p>}
      {timeline && timeline.length === 0 && (
        <p className="rounded-lg border border-gray-100 bg-white p-5 text-sm text-gray-400 shadow-card">
          No meetings captured yet — upload a transcript or notes to start this timeline.
        </p>
      )}

      {timeline?.map((entry) => (
        <section key={entry.conversation_id} className="rounded-lg border border-gray-100 bg-white shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-5 py-4">
            <div>
              <span className="rounded-full bg-v3-violet/10 px-2 py-0.5 text-[10px] font-bold uppercase text-v3-violet">
                {entry.interaction_type}
              </span>
              <p className="mt-1 text-sm text-gray-500">{entry.date}{entry.source_system ? ` · ${entry.source_system}` : ""}</p>
            </div>
            {entry.pending_review_count > 0 && (
              <Link
                href={`/advisor/customers/${customerId}/conversations/new`}
                className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700 hover:underline"
              >
                {entry.pending_review_count} pending review
              </Link>
            )}
          </div>

          <div className="space-y-4 p-5">
            <p className="text-sm leading-6 text-gray-800">{entry.summary}</p>

            {entry.insights.length > 0 && (
              <div>
                <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-gray-500">
                  <Lightbulb size={13} /> Insights extracted
                </p>
                <ul className="mt-2 space-y-1.5">
                  {entry.insights.map((insight) => (
                    <li key={insight.memory_id} className="text-sm text-gray-700">
                      <span className="mr-1.5 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-gray-500">
                        {insight.memory_type}
                      </span>
                      {insight.value}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {entry.memory_changes.length > 0 && (
              <div>
                <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-gray-500">
                  <CheckSquare size={13} /> Memory changes
                </p>
                <ul className="mt-2 space-y-1.5">
                  {entry.memory_changes.map((change) => (
                    <li key={change.memory_id} className="flex items-center gap-2 text-sm text-gray-700">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${MEMORY_STATUS_TONE[change.status] || "bg-gray-100 text-gray-500"}`}>
                        {change.status}
                      </span>
                      {change.value}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {entry.follow_ups.length > 0 && (
              <div>
                <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-gray-500">
                  <ListChecks size={13} /> Follow-ups
                </p>
                <ul className="mt-2 space-y-1.5">
                  {entry.follow_ups.map((followup) => (
                    <li key={followup.followup_id} className="flex items-center justify-between gap-2 text-sm text-gray-700">
                      <span>{followup.title}</span>
                      <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                        <CalendarClock size={12} /> {followup.due_date}
                        <span className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${followup.status === "completed" ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                          {followup.status}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
