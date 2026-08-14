"use client";

import Link from "next/link";
import { use, useState } from "react";
import { AlertTriangle, ArrowLeft, Check, FileText, Loader2, Pencil, Sparkles, X } from "lucide-react";
import { advisorApi, type IngestConversationResult, type ProposedMemory } from "@/services/advisorApi";

const TYPE_LABEL: Record<string, string> = {
  life_event: "Life event", goal: "Goal", need: "Need", concern: "Concern",
  preference: "Preference", objection: "Objection", commitment: "Commitment", follow_up: "Follow-up",
};

export default function NewConversationPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [transcript, setTranscript] = useState("");
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<IngestConversationResult | null>(null);
  const [memories, setMemories] = useState<ProposedMemory[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  async function submit() {
    setProcessing(true);
    setError("");
    try {
      const res = await advisorApi.uploadConversation(customerId, transcript);
      setResult(res);
      setMemories(res.proposed_memories);
    } catch (e: any) {
      setError(e.message || "Processing failed");
    } finally {
      setProcessing(false);
    }
  }

  async function accept(m: ProposedMemory, edited?: string) {
    await advisorApi.approveMemory(m.memory_id, edited);
    setMemories((prev) => prev.map((x) => (x.memory_id === m.memory_id ? { ...x, status: edited ? "edited" : "accepted", value: edited || x.value } : x)));
    setEditingId(null);
  }

  async function reject(m: ProposedMemory) {
    await advisorApi.rejectMemory(m.memory_id);
    setMemories((prev) => prev.map((x) => (x.memory_id === m.memory_id ? { ...x, status: "rejected" } : x)));
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <Link href={`/advisor/customers/${customerId}`} className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to profile
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Conversation capture</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Upload meeting transcript</h1>
      </div>

      {!result && (
        <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="Paste the meeting transcript here…"
            rows={14}
            className="w-full rounded-lg border border-gray-200 p-3 text-sm outline-none focus:border-v3-violet focus:ring-2 focus:ring-v3-violet/20"
          />
          {error && <p className="mt-2 text-sm text-v3-rose">{error}</p>}
          <button
            onClick={submit}
            disabled={processing || !transcript.trim()}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2.5 text-sm font-bold text-white shadow-glow hover:bg-v3-violetDark disabled:opacity-50"
          >
            {processing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {processing ? "Processing conversation…" : "Analyze conversation"}
          </button>
          {processing && (
            <p className="mt-2 text-xs text-gray-400">Embedding into semantic memory and extracting new information with Gemini — usually a few seconds.</p>
          )}
        </section>
      )}

      {result && (
        <>
          <section className="rounded-xl border border-v3-violet/20 bg-v3-violet/5 p-5">
            <p className="flex items-center gap-1.5 text-xs font-bold uppercase text-v3-violet"><FileText size={14} /> AI summary</p>
            <p className="mt-1 text-sm text-gray-700">{result.summary}</p>
            <p className="mt-2 text-xs text-gray-400">{result.chunks_stored} transcript chunk(s) stored in semantic memory.</p>
          </section>

          <section>
            <p className="mb-2 text-sm font-bold text-gray-900">
              AI identified {memories.length} piece{memories.length === 1 ? "" : "s"} of new information
            </p>
            <div className="space-y-3">
              {memories.map((m) => (
                <MemoryCard
                  key={m.memory_id}
                  memory={m}
                  editing={editingId === m.memory_id}
                  editValue={editValue}
                  onStartEdit={() => { setEditingId(m.memory_id); setEditValue(m.value); }}
                  onEditChange={setEditValue}
                  onAccept={() => accept(m)}
                  onAcceptEdit={() => accept(m, editValue)}
                  onReject={() => reject(m)}
                  onCancelEdit={() => setEditingId(null)}
                />
              ))}
            </div>
          </section>

          <Link href={`/advisor/customers/${customerId}`} className="inline-flex items-center gap-1 text-sm font-semibold text-v3-violet hover:underline">
            Done — back to customer profile
          </Link>
        </>
      )}
    </div>
  );
}

function MemoryCard({
  memory, editing, editValue, onStartEdit, onEditChange, onAccept, onAcceptEdit, onReject, onCancelEdit,
}: {
  memory: ProposedMemory;
  editing: boolean;
  editValue: string;
  onStartEdit: () => void;
  onEditChange: (v: string) => void;
  onAccept: () => void;
  onAcceptEdit: () => void;
  onReject: () => void;
  onCancelEdit: () => void;
}) {
  const decided = memory.status !== "pending";
  return (
    <div className={`rounded-lg border p-4 ${memory.has_conflict ? "border-amber-300 bg-amber-50" : "border-gray-100 bg-white"} shadow-card`}>
      <div className="flex items-start justify-between gap-2">
        <span className="rounded-full bg-v3-violet/10 px-2 py-0.5 text-[10px] font-bold uppercase text-v3-violet">{TYPE_LABEL[memory.memory_type]}</span>
        {decided && (
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${memory.status === "rejected" ? "bg-gray-100 text-gray-500" : "bg-green-50 text-green-700"}`}>
            {memory.status}
          </span>
        )}
      </div>

      {memory.has_conflict && (
        <p className="mt-2 flex items-start gap-1 text-xs font-semibold text-amber-700">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" /> Possible conflict with existing record: &ldquo;{memory.conflict_with}&rdquo;
        </p>
      )}

      {editing ? (
        <textarea
          value={editValue}
          onChange={(e) => onEditChange(e.target.value)}
          rows={2}
          className="mt-2 w-full rounded-lg border border-gray-200 p-2 text-sm outline-none focus:border-v3-violet"
        />
      ) : (
        <p className="mt-2 text-sm font-medium text-gray-900">{memory.value}</p>
      )}

      <p className="mt-2 text-xs italic text-gray-500">Evidence: &ldquo;{memory.evidence}&rdquo;</p>
      <p className="mt-0.5 text-[11px] text-gray-400">Confidence: {Math.round(memory.confidence * 100)}%</p>

      {!decided && (
        <div className="mt-3 flex gap-2">
          {editing ? (
            <>
              <button onClick={onAcceptEdit} className="inline-flex items-center gap-1 rounded-lg bg-v3-violet px-3 py-1.5 text-xs font-bold text-white hover:bg-v3-violetDark">
                <Check size={13} /> Save & Accept
              </button>
              <button onClick={onCancelEdit} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50">Cancel</button>
            </>
          ) : (
            <>
              <button onClick={onAccept} className="inline-flex items-center gap-1 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-green-700">
                <Check size={13} /> Accept
              </button>
              <button onClick={onStartEdit} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50">
                <Pencil size={13} /> Edit
              </button>
              <button onClick={onReject} className="inline-flex items-center gap-1 rounded-lg border border-v3-rose/30 px-3 py-1.5 text-xs font-semibold text-v3-rose hover:bg-v3-rose/5">
                <X size={13} /> Reject
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
