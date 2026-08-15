"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, CalendarDays, CheckCircle2, FileSpreadsheet, TriangleAlert, Upload } from "lucide-react";
import {
  integrationApi,
  type CalendarImportResult,
  type ImportPreview
} from "@/services/advisorApi";

const DATASETS = [
  ["customers", "Customers", "external_id, full_name, email, phone, life_stage, advisor_name"],
  ["family", "Family", "customer_external_id, full_name, relationship, email, phone"],
  ["policies", "Policies", "customer_external_id, policy_id, product_name, line_of_business, annual_premium, policy_status"],
  ["interactions", "Interactions", "customer_external_id, occurred_at, summary, interaction_type, body"]
];

export default function ImportPage() {
  const [dataset, setDataset] = useState("customers");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportPreview | null>(null);
  const [calendar, setCalendar] = useState<CalendarImportResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function run(mode: "preview" | "commit") {
    if (!file) {
      setError("Choose a file first.");
      return;
    }
    setBusy(mode);
    setError("");
    try {
      const data =
        mode === "preview"
          ? await integrationApi.previewCsv(file, dataset)
          : await integrationApi.commitCsv(file, dataset);
      setResult(data);
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setBusy("");
    }
  }

  async function importCalendar(icsFile: File) {
    setBusy("calendar");
    setError("");
    try {
      setCalendar(await integrationApi.importIcs(icsFile));
    } catch (e) {
      setError((e as Error).message);
      setCalendar(null);
    } finally {
      setBusy("");
    }
  }

  const selected = DATASETS.find(([key]) => key === dataset);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <Link href="/advisor/connections" className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to Connection Center
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Import</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Import customer data</h1>
        <p className="mt-1 max-w-3xl text-sm text-gray-500">
          Preview validates the file and detects duplicates without writing anything. Nothing enters the
          customer graph until you choose to import.
        </p>
      </div>

      {error && <p className="rounded-lg border border-v3-rose/30 bg-v3-rose/5 px-4 py-3 text-sm text-v3-rose">{error}</p>}

      <section className="rounded-lg border border-gray-100 bg-white shadow-card">
        <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
          <FileSpreadsheet size={17} className="text-v3-violet" />
          <h2 className="font-bold text-gray-900">CSV / Excel</h2>
        </div>
        <div className="space-y-4 p-5">
          <div className="flex flex-wrap gap-3">
            {DATASETS.map(([key, label]) => (
              <button
                key={key}
                onClick={() => {
                  setDataset(key);
                  setResult(null);
                }}
                className={`rounded-lg border px-3 py-1.5 text-sm font-semibold ${
                  dataset === key
                    ? "border-v3-violet bg-v3-violet/10 text-v3-violet"
                    : "border-gray-200 text-gray-600 hover:border-v3-violet"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <p className="text-xs text-gray-500">
            Expected columns: <span className="font-mono text-gray-700">{selected?.[2]}</span>
          </p>

          <input
            type="file"
            accept=".csv,.xlsx,.xlsm,text/csv"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setResult(null);
            }}
            className="block w-full text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-v3-violet/10 file:px-3 file:py-2 file:text-sm file:font-bold file:text-v3-violet"
          />

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => run("preview")}
              disabled={busy !== ""}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2 text-sm font-bold text-gray-700 hover:border-v3-violet hover:text-v3-violet disabled:opacity-50"
            >
              {busy === "preview" ? "Validating..." : "Preview"}
            </button>
            <button
              onClick={() => run("commit")}
              disabled={busy !== "" || !result || result.valid_count === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2 text-sm font-bold text-white hover:bg-v3-violetDark disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500"
              title={!result ? "Preview the file first" : ""}
            >
              <Upload size={15} /> {busy === "commit" ? "Importing..." : "Import"}
            </button>
          </div>

          {result && (
            <div className="space-y-4 rounded-lg border border-gray-100 bg-gray-50 p-4">
              {result.committed ? (
                <p className="inline-flex items-center gap-2 text-sm font-bold text-green-700">
                  <CheckCircle2 size={16} /> Imported{" "}
                  {Object.entries(result.imported || {})
                    .filter(([, v]) => v > 0)
                    .map(([k, v]) => `${v} ${k}`)
                    .join(", ") || "nothing"}
                  .
                </p>
              ) : (
                <p className="text-sm font-bold text-gray-900">Preview — nothing has been written yet.</p>
              )}

              <div className="grid gap-3 sm:grid-cols-4">
                <Stat label="Valid rows" value={result.valid_count} tone="text-green-700" />
                <Stat label="New" value={result.new_count} tone="text-v3-violet" />
                <Stat label="Already in system" value={result.existing_count} tone="text-amber-700" />
                <Stat label="Errors" value={result.error_count + result.duplicate_count} tone="text-v3-rose" />
              </div>

              {result.errors.length > 0 && (
                <IssueList title="Validation errors" items={result.errors} tone="text-v3-rose" />
              )}
              {result.duplicates.length > 0 && (
                <IssueList title="Duplicates within the file" items={result.duplicates} tone="text-amber-700" />
              )}
              {(result.import_errors?.length || 0) > 0 && (
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-v3-rose">Import errors</p>
                  <ul className="mt-1 space-y-1 text-sm text-gray-700">
                    {result.import_errors?.map((message) => (
                      <li key={message}>{message}</li>
                    ))}
                  </ul>
                </div>
              )}

              {result.preview.length > 0 && (
                <div className="overflow-x-auto">
                  <p className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-500">
                    First {result.preview.length} valid row(s)
                  </p>
                  <table className="w-full text-xs">
                    <thead className="bg-white text-left font-bold uppercase text-gray-500">
                      <tr>
                        {Object.keys(result.preview[0])
                          .filter((k) => k !== "_row")
                          .map((key) => (
                            <th key={key} className="px-3 py-2">
                              {key}
                            </th>
                          ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                      {result.preview.map((row, i) => (
                        <tr key={i}>
                          {Object.entries(row)
                            .filter(([k]) => k !== "_row")
                            .map(([key, value]) => (
                              <td key={key} className="px-3 py-2 text-gray-700">
                                {String(value)}
                              </td>
                            ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-gray-100 bg-white shadow-card">
        <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
          <CalendarDays size={17} className="text-v3-teal" />
          <h2 className="font-bold text-gray-900">Calendar file (.ics)</h2>
        </div>
        <div className="space-y-4 p-5">
          <p className="text-sm text-gray-600">
            Export an .ics file from Google Calendar or Outlook and upload it here. Attendees are matched to
            customers by email; anything unmatched is flagged rather than guessed.
          </p>
          <input
            type="file"
            accept=".ics,text/calendar"
            onChange={(e) => {
              const chosen = e.target.files?.[0];
              if (chosen) importCalendar(chosen);
            }}
            className="block w-full text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-v3-teal/10 file:px-3 file:py-2 file:text-sm file:font-bold file:text-v3-teal"
          />
          {busy === "calendar" && <p className="text-sm text-gray-400">Importing calendar...</p>}

          {calendar && (
            <div className="space-y-3 rounded-lg border border-gray-100 bg-gray-50 p-4">
              <p className="text-sm font-bold text-gray-900">
                Imported {calendar.counts.meetings || 0} meeting(s).
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Stat
                  label="Matched to a customer"
                  value={calendar.meetings.filter((m) => m.match_status === "matched").length}
                  tone="text-green-700"
                />
                <Stat
                  label="Customer match required"
                  value={calendar.meetings.filter((m) => m.match_status !== "matched").length}
                  tone="text-amber-700"
                />
              </div>
              {calendar.meetings.some((m) => m.match_status !== "matched") && (
                <p className="inline-flex items-start gap-2 text-sm text-amber-700">
                  <TriangleAlert size={15} className="mt-0.5 shrink-0" />
                  Unmatched meetings appear in My Day so you can assign the right customer.
                </p>
              )}
              {calendar.errors.length > 0 && (
                <ul className="text-sm text-v3-rose">
                  {calendar.errors.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              )}
              <Link href="/advisor" className="inline-flex text-sm font-bold text-v3-violet hover:underline">
                Open My Day
              </Link>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-white p-3">
      <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1 text-xl font-bold ${tone}`}>{value}</p>
    </div>
  );
}

function IssueList({ title, items, tone }: { title: string; items: { row: number; message: string }[]; tone: string }) {
  return (
    <div>
      <p className={`text-xs font-bold uppercase tracking-wide ${tone}`}>{title}</p>
      <ul className="mt-1 space-y-1 text-sm text-gray-700">
        {items.map((item) => (
          <li key={`${item.row}-${item.message}`}>
            Row {item.row}: {item.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
