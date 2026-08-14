"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ArrowLeft, MessageSquare } from "lucide-react";
import { advisorApi, type ConversationRecord, type MemoryTimelineEntry } from "@/services/advisorApi";

const STATUS_TONE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700",
  accepted: "bg-green-50 text-green-700",
  edited: "bg-v3-teal/10 text-v3-teal",
  rejected: "bg-gray-100 text-gray-500",
};

export default function MemoryTimelinePage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [timeline, setTimeline] = useState<MemoryTimelineEntry[] | null>(null);
  const [conversations, setConversations] = useState<ConversationRecord[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([advisorApi.getMemoryTimeline(customerId), advisorApi.listConversations(customerId)])
      .then(([t, c]) => {
        setTimeline(t);
        setConversations(c);
      })
      .catch((e) => setError(e.message));
  }, [customerId]);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <Link href={`/advisor/customers/${customerId}`} className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to profile
      </Link>

      {error && <p className="text-sm text-v3-rose">{error}</p>}

      <section>
        <h1 className="text-xl font-bold text-gray-900">Customer Memory Timeline</h1>
        <p className="mt-1 text-sm text-gray-500">Every fact ever proposed about this customer, and what happened to it.</p>
        {!timeline && !error && <p className="mt-3 text-sm text-gray-400">Loading…</p>}
        {timeline && timeline.length === 0 && <p className="mt-3 text-sm text-gray-400">No memory events yet — upload a conversation to start building this timeline.</p>}
        {timeline && timeline.length > 0 && (
          <div className="mt-3 space-y-2">
            {timeline.map((m) => (
              <div key={m.memory_id} className="rounded-lg border border-gray-100 bg-white p-3 shadow-card">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-gray-900">{m.value}</p>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_TONE[m.status] || "bg-gray-100 text-gray-500"}`}>{m.status}</span>
                </div>
                <p className="mt-1 text-xs text-gray-400">
                  {m.memory_type} · {Math.round(m.confidence * 100)}% confidence · {new Date(m.created_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="flex items-center gap-1.5 text-lg font-bold text-gray-900"><MessageSquare size={18} className="text-v3-violet" /> Conversation History</h2>
        {!conversations && !error && <p className="mt-3 text-sm text-gray-400">Loading…</p>}
        {conversations && conversations.length === 0 && <p className="mt-3 text-sm text-gray-400">No conversations uploaded yet.</p>}
        {conversations && conversations.length > 0 && (
          <div className="mt-3 space-y-3">
            {conversations.map((c) => (
              <div key={c.conversation_id} className="rounded-lg border border-gray-100 bg-white p-4 shadow-card">
                <p className="text-xs font-bold text-gray-500">{c.date}</p>
                <p className="mt-1 text-sm text-gray-800">{c.summary}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
