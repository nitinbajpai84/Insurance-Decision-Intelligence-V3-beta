"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, CalendarClock, Check, CheckSquare, Circle, RotateCcw } from "lucide-react";
import { advisorApi, type AdvisorTask, type FollowUp } from "@/services/advisorApi";

const PRIORITY_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-600"
};

function isOverdue(followup: FollowUp): boolean {
  return followup.status === "open" && followup.due_date < new Date().toISOString().slice(0, 10);
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<AdvisorTask[] | null>(null);
  const [followups, setFollowups] = useState<FollowUp[] | null>(null);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("open");
  const [editing, setEditing] = useState<string | null>(null);
  const [editDueDate, setEditDueDate] = useState("");
  const [editAssignee, setEditAssignee] = useState("");

  const load = useCallback(() => {
    advisorApi.listTasks().then(setTasks).catch((e) => setError(e.message));
    advisorApi
      .listFollowUps(statusFilter === "all" ? undefined : { status: statusFilter })
      .then(setFollowups)
      .catch((e) => setError(e.message));
  }, [statusFilter]);

  useEffect(load, [load]);

  async function complete(followup: FollowUp) {
    await advisorApi.completeFollowUp(followup.followup_id);
    load();
  }

  async function reopen(followup: FollowUp) {
    await advisorApi.reopenFollowUp(followup.followup_id);
    load();
  }

  function startEdit(followup: FollowUp) {
    setEditing(followup.followup_id);
    setEditDueDate(followup.due_date);
    setEditAssignee(followup.assigned_to);
  }

  async function saveEdit(followupId: string) {
    await advisorApi.updateFollowUp(followupId, { due_date: editDueDate, assigned_to: editAssignee });
    setEditing(null);
    load();
  }

  const visible = (tasks || []).filter((task) => statusFilter === "all" || task.status === statusFilter);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Tasks</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Follow-ups and due dates</h1>
          <p className="mt-1 text-sm text-gray-500">A focused queue of customer actions derived from customer signals.</p>
        </div>
        <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1">
          {["open", "all"].map((value) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              className={`rounded-md px-3 py-1.5 text-xs font-bold uppercase ${statusFilter === value ? "bg-v3-violet text-white" : "text-gray-500 hover:text-v3-violet"}`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-v3-rose">{error}</p>}

      {followups && followups.length > 0 && (
        <section className="rounded-lg border border-gray-100 bg-white shadow-card">
          <div className="border-b border-gray-100 px-4 py-3">
            <h2 className="text-sm font-bold text-gray-900">Follow-ups from conversations</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              Extracted from meetings and approved by you — assign, date, and complete them here.
            </p>
          </div>
          <div className="divide-y divide-gray-100">
            {followups.map((followup) => (
              <div key={followup.followup_id} className="grid gap-3 p-4 sm:grid-cols-[1fr_auto] sm:items-center">
                <div className="flex items-start gap-3">
                  {followup.status === "open" ? (
                    <Circle size={18} className={`mt-0.5 ${isOverdue(followup) ? "text-v3-rose" : "text-gray-300"}`} />
                  ) : (
                    <CheckSquare size={18} className="mt-0.5 text-v3-teal" />
                  )}
                  <div className="min-w-0">
                    <p className="font-semibold text-gray-900">{followup.title}</p>
                    <Link href={`/advisor/customers/${followup.customer_id}`} className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-v3-violet hover:underline">
                      {followup.customer_name} <ArrowRight size={13} />
                    </Link>
                    {followup.evidence && <p className="mt-1 text-xs italic text-gray-400">&ldquo;{followup.evidence}&rdquo;</p>}

                    {editing === followup.followup_id ? (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <input
                          type="date"
                          value={editDueDate}
                          onChange={(e) => setEditDueDate(e.target.value)}
                          className="h-8 rounded-lg border border-gray-200 px-2 text-xs outline-none focus:border-v3-violet"
                        />
                        <input
                          type="text"
                          value={editAssignee}
                          onChange={(e) => setEditAssignee(e.target.value)}
                          placeholder="Assigned to"
                          className="h-8 w-32 rounded-lg border border-gray-200 px-2 text-xs outline-none focus:border-v3-violet"
                        />
                        <button
                          onClick={() => saveEdit(followup.followup_id)}
                          className="rounded-lg bg-v3-violet px-2.5 py-1.5 text-xs font-bold text-white hover:bg-v3-violetDark"
                        >
                          Save
                        </button>
                        <button onClick={() => setEditing(null)} className="text-xs font-semibold text-gray-500 hover:text-gray-700">
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => startEdit(followup)}
                        className={`mt-1 inline-flex items-center gap-1 text-xs font-semibold ${isOverdue(followup) ? "text-v3-rose" : "text-gray-500"} hover:underline`}
                      >
                        <CalendarClock size={13} /> Due {followup.due_date} · {followup.assigned_to}
                        {isOverdue(followup) && " · overdue"}
                      </button>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {followup.status === "open" ? (
                    <button
                      onClick={() => complete(followup)}
                      className="inline-flex items-center gap-1 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-green-700"
                    >
                      <Check size={13} /> Complete
                    </button>
                  ) : (
                    <button
                      onClick={() => reopen(followup)}
                      className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50"
                    >
                      <RotateCcw size={13} /> Reopen
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {!tasks && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {tasks && (
        <section className="rounded-lg border border-gray-100 bg-white shadow-card">
          <div className="border-b border-gray-100 px-4 py-3">
            <h2 className="text-sm font-bold text-gray-900">Computed reminders</h2>
            <p className="mt-0.5 text-xs text-gray-500">Derived automatically from stale data and open concerns.</p>
          </div>
          <div className="divide-y divide-gray-100">
            {visible.map((task) => (
              <div key={task.task_id} className="grid gap-3 p-4 sm:grid-cols-[1fr_auto] sm:items-center">
                <div className="flex items-start gap-3">
                  {task.status === "open" ? <Circle size={18} className="mt-0.5 text-gray-300" /> : <CheckSquare size={18} className="mt-0.5 text-v3-teal" />}
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-gray-900">{task.title}</p>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${PRIORITY_TONE[task.priority]}`}>{task.priority}</span>
                    </div>
                    <Link href={`/advisor/customers/${task.customer_id}`} className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-v3-violet hover:underline">
                      {task.customer_name} <ArrowRight size={13} />
                    </Link>
                    <p className="mt-1 text-xs text-gray-400">Source: {task.source.replaceAll("_", " ")}</p>
                  </div>
                </div>
                <div className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600">
                  <CalendarClock size={16} className="text-v3-teal" />
                  {task.due_label || task.due_date}
                </div>
              </div>
            ))}
            {visible.length === 0 && <p className="p-5 text-sm text-gray-400">No tasks in this view.</p>}
          </div>
        </section>
      )}
    </div>
  );
}
