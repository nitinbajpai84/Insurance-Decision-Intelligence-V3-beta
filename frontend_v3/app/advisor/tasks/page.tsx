"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CalendarClock, CheckSquare, Circle } from "lucide-react";
import { advisorApi, type AdvisorTask } from "@/services/advisorApi";

const PRIORITY_TONE: Record<string, string> = {
  high: "bg-v3-rose/10 text-v3-rose",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-gray-100 text-gray-600"
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<AdvisorTask[] | null>(null);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("open");

  useEffect(() => {
    advisorApi.listTasks().then(setTasks).catch((e) => setError(e.message));
  }, []);

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
      {!tasks && !error && <p className="text-sm text-gray-400">Loading...</p>}

      {tasks && (
        <section className="rounded-lg border border-gray-100 bg-white shadow-card">
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
