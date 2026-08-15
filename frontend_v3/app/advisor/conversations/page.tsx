"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, MessageSquareText, Sparkles } from "lucide-react";
import { advisorApi, type ConversationRecord, type CustomerListItem, type MemoryTimelineEntry } from "@/services/advisorApi";

interface ConversationWithCustomer extends ConversationRecord {
  customer_id: string;
  customer_name: string;
}

interface MemoryWithCustomer extends MemoryTimelineEntry {
  customer_id: string;
  customer_name: string;
}

export default function ConversationsPage() {
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [conversations, setConversations] = useState<ConversationWithCustomer[]>([]);
  const [memories, setMemories] = useState<MemoryWithCustomer[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const customerRows = await advisorApi.listCustomers();
        setCustomers(customerRows);
        const conversationRows = await Promise.all(
          customerRows.map(async (customer) => {
            const rows = await advisorApi.listConversations(customer.customer_id).catch(() => []);
            return rows.map((row) => ({ ...row, customer_id: customer.customer_id, customer_name: customer.name }));
          })
        );
        const memoryRows = await Promise.all(
          customerRows.map(async (customer) => {
            const rows = await advisorApi.getMemoryTimeline(customer.customer_id).catch(() => []);
            return rows.map((row) => ({ ...row, customer_id: customer.customer_id, customer_name: customer.name }));
          })
        );
        setConversations(conversationRows.flat().sort((a, b) => b.date.localeCompare(a.date)).slice(0, 12));
        setMemories(memoryRows.flat().slice(0, 12));
      } catch (e: any) {
        setError(e.message || "Could not load conversations");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const customersWithConversationActions = useMemo(() => customers.slice(0, 6), [customers]);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Conversations</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Capture and remember customer conversations</h1>
        <p className="mt-1 text-sm text-gray-500">Meeting summaries, transcript uploads, and AI-proposed customer memory updates.</p>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}
      {loading && <p className="text-sm text-gray-400">Loading...</p>}

      {!loading && (
        <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-lg border border-gray-100 bg-white shadow-card">
            <PanelHeader title="Recent Conversations" subtitle="Uploaded and seeded meeting summaries from the customer graph." />
            <div className="divide-y divide-gray-100">
              {conversations.map((conversation) => (
                <div key={conversation.conversation_id} className="p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Link href={`/advisor/customers/${conversation.customer_id}`} className="font-semibold text-v3-violet hover:underline">
                      {conversation.customer_name}
                    </Link>
                    <span className="text-xs font-semibold text-gray-400">{conversation.date}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-gray-700">{conversation.summary}</p>
                  <Link href={`/advisor/customers/${conversation.customer_id}/briefing`} className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline">
                    Prepare next meeting <ArrowRight size={13} />
                  </Link>
                </div>
              ))}
              {conversations.length === 0 && <Empty text="No uploaded conversations yet. Seeded meeting history still appears inside each Customer 360." />}
            </div>
          </section>

          <div className="space-y-5">
            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader title="Customer Memory Updates" subtitle="AI proposals remain reviewable until the advisor accepts or rejects them." />
              <div className="divide-y divide-gray-100">
                {memories.map((memory) => (
                  <div key={memory.memory_id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{memory.value}</p>
                        <Link href={`/advisor/customers/${memory.customer_id}/memory`} className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-v3-violet hover:underline">
                          {memory.customer_name} <ArrowRight size={12} />
                        </Link>
                      </div>
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-bold uppercase text-gray-600">{memory.status}</span>
                    </div>
                  </div>
                ))}
                {memories.length === 0 && <Empty text="No proposed memory updates yet." />}
              </div>
            </section>

            <section className="rounded-lg border border-gray-100 bg-white shadow-card">
              <PanelHeader title="Capture Conversation" subtitle="Upload a transcript against a specific customer." />
              <div className="grid gap-2 p-4 sm:grid-cols-2 xl:grid-cols-1">
                {customersWithConversationActions.map((customer) => (
                  <Link key={customer.customer_id} href={`/advisor/customers/${customer.customer_id}/conversations/new`} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2 text-sm font-semibold text-gray-800 hover:border-v3-violet hover:text-v3-violet">
                    <span className="inline-flex min-w-0 items-center gap-2">
                      <MessageSquareText size={15} className="shrink-0 text-v3-teal" />
                      <span className="truncate">{customer.name}</span>
                    </span>
                    <Sparkles size={14} />
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}
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

function Empty({ text }: { text: string }) {
  return <p className="p-4 text-sm text-gray-400">{text}</p>;
}
