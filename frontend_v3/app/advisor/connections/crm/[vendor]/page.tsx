"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Check, ExternalLink, FileSpreadsheet, KeyRound, ShieldCheck } from "lucide-react";
import { accountApi, integrationApi, type CrmVendor } from "@/services/advisorApi";

export default function CrmSetupPage() {
  const params = useParams<{ vendor: string }>();
  const vendorKey = params.vendor;

  const [vendor, setVendor] = useState<CrmVendor | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    accountApi
      .listCrm()
      .then((rows) => {
        const found = rows.find((r) => r.vendor === vendorKey) || null;
        setVendor(found);
        if (!found) setError(`Unknown CRM '${vendorKey}'`);
      })
      .catch((e) => setError(e.message));
  }, [vendorKey]);

  useEffect(load, [load]);

  async function save() {
    setBusy("save");
    setError("");
    setNotice("");
    try {
      await accountApi.saveCrmCredentials(vendorKey, values);
      setNotice("Credentials saved and encrypted.");
      setValues((prev) => {
        const next = { ...prev };
        vendor?.credential_fields.forEach((field) => {
          if (field.secret) next[field.key] = "";
        });
        return next;
      });
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function connect() {
    setBusy("connect");
    setError("");
    setNotice("");
    try {
      const result = await accountApi.connectCrm(vendorKey);
      if (result.authorization_url) {
        window.location.href = result.authorization_url;
        return;
      }
      setNotice(
        result.connected
          ? "Connected. Run a sync to pull customers."
          : "Credentials stored. Run a sync — that is what confirms API access for this vendor."
      );
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function syncNow() {
    if (!vendor) return;
    setBusy("sync");
    setError("");
    setNotice("");
    try {
      const result = await integrationApi.syncNow(vendor.provider);
      const counts = (result.counts as Record<string, number>) || {};
      const summary = Object.entries(counts)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => `${v} ${k}`)
        .join(", ");
      setNotice(`Sync complete: ${summary || "nothing new"}.`);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  if (!vendor) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 lg:px-8">
        {error ? <p className="text-sm text-v3-rose">{error}</p> : <p className="text-sm text-gray-400">Loading...</p>}
      </div>
    );
  }

  const partnerGated = vendor.access === "partner_gated";

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <Link href="/advisor/connections" className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to Connection Center
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">CRM setup</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Connect {vendor.name}</h1>
        <p className="mt-1 text-sm text-gray-500">{vendor.notes}</p>
      </div>

      {notice && (
        <p className="inline-flex items-center gap-2 rounded-lg border border-v3-teal/30 bg-v3-teal/5 px-4 py-3 text-sm text-teal-800">
          <Check size={15} /> {notice}
        </p>
      )}
      {error && <p className="rounded-lg border border-v3-rose/30 bg-v3-rose/5 px-4 py-3 text-sm text-v3-rose">{error}</p>}

      {partnerGated && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-start gap-3">
            <FileSpreadsheet size={18} className="mt-0.5 shrink-0 text-amber-700" />
            <div>
              <h2 className="text-sm font-bold text-amber-900">{vendor.name} gates its API behind a partner agreement</h2>
              <p className="mt-1 text-sm leading-6 text-amber-900">
                They issue endpoint documentation together with your credentials, so the base URL below comes from
                them rather than being built in. Guessing it would produce a connector that fails on first call.
              </p>
              <p className="mt-2 text-sm leading-6 text-amber-900">
                Meanwhile the CSV importer already handles {vendor.name} exports today, with validation and duplicate
                detection — {vendor.csv_export_hint}
              </p>
              <Link
                href="/advisor/connections/import"
                className="mt-3 inline-flex rounded-lg bg-amber-700 px-3 py-2 text-xs font-bold text-white hover:bg-amber-800"
              >
                Import a CSV export instead
              </Link>
            </div>
          </div>
        </section>
      )}

      <section className="rounded-lg border border-gray-100 bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <h2 className="font-bold text-gray-900">Credentials</h2>
          <p className="mt-1 inline-flex items-start gap-2 text-sm text-gray-500">
            <ShieldCheck size={15} className="mt-0.5 shrink-0 text-v3-teal" />
            Stored encrypted. Secrets are never returned by the API — only a masked hint.
          </p>
        </div>
        <div className="space-y-4 p-5">
          {vendor.credential_fields.map((field) => (
            <div key={field.key}>
              <label className="block text-sm font-semibold text-gray-800">{field.label}</label>
              {vendor.hints[field.key] && (
                <p className="mt-0.5 font-mono text-xs text-gray-400">Stored: {vendor.hints[field.key]}</p>
              )}
              <input
                type={field.secret ? "password" : "text"}
                autoComplete="off"
                value={values[field.key] ?? ""}
                onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                placeholder={field.secret ? "••••••••" : ""}
                className="mt-1 h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-v3-violet focus:ring-2 focus:ring-v3-violet/20"
              />
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={save}
              disabled={busy !== ""}
              className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2 text-sm font-bold text-white hover:bg-v3-violetDark disabled:opacity-50"
            >
              <KeyRound size={15} /> {busy === "save" ? "Saving..." : "Save credentials"}
            </button>
            <button
              onClick={connect}
              disabled={busy !== "" || !vendor.credentials_configured}
              className="rounded-lg bg-v3-teal px-4 py-2 text-sm font-bold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500"
            >
              {busy === "connect" ? "Connecting..." : "Connect"}
            </button>
            <button
              onClick={syncNow}
              disabled={busy !== "" || !vendor.credentials_configured}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-bold text-gray-700 hover:border-v3-violet hover:text-v3-violet disabled:cursor-not-allowed disabled:text-gray-300"
            >
              {busy === "sync" ? "Syncing..." : "Sync now"}
            </button>
            <a
              href={vendor.docs_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-bold text-v3-violet hover:underline"
            >
              {vendor.name} docs <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
