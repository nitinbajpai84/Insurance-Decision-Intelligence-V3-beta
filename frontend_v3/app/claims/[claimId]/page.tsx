"use client";

import { use, useEffect, useRef, useState } from "react";
import { AlertTriangle, FileUp, Loader2, Users } from "lucide-react";
import { api, money, type ClaimDetail } from "@/services/api";

export default function ClaimDetailPage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId } = use(params);
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => api.getClaim(claimId).then(setClaim).catch((e) => setError(e.message));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claimId]);

  async function onUpload(file: File) {
    setUploading(true);
    setUploadError("");
    try {
      await api.uploadDocument(claimId, file);
      await load();
    } catch (e: any) {
      setUploadError(e.message || "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (error) return <div className="p-8 text-sm text-v3-rose">{error}</div>;
  if (!claim) return <div className="p-8 text-sm text-gray-400">Loading…</div>;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Claim</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">{claim.claim_number}</h1>
        <p className="mt-1 text-sm text-gray-500">{claim.customer_name} · {claim.customer_email}</p>
      </div>

      <section className="grid gap-4 sm:grid-cols-3">
        <Stat label="Status" value={claim.claim_status} />
        <Stat label="Paid" value={money(claim.paid_amount)} />
        <Stat label="Reserve" value={money(claim.reserve_amount)} />
      </section>

      <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-2 text-base font-bold text-gray-900">Loss details</h2>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-gray-400">Loss date</dt><dd className="font-semibold text-gray-800">{claim.loss_date}</dd></div>
          <div><dt className="text-gray-400">Report date</dt><dd className="font-semibold text-gray-800">{claim.report_date}</dd></div>
          <div><dt className="text-gray-400">Loss cause</dt><dd className="font-semibold text-gray-800">{claim.loss_cause || "—"}</dd></div>
          <div><dt className="text-gray-400">Policy</dt><dd className="font-semibold text-gray-800">{claim.policy_id}</dd></div>
        </dl>
        {claim.loss_description && <p className="mt-3 text-sm text-gray-600">{claim.loss_description}</p>}
      </section>

      {claim.fraud_indicators.length > 0 && (
        <section className="rounded-xl border border-v3-rose/20 bg-v3-rose/5 p-5">
          <h2 className="mb-2 flex items-center gap-1.5 text-base font-bold text-v3-rose"><AlertTriangle size={16} /> Fraud indicators (structured)</h2>
          <ul className="space-y-1 text-sm text-gray-700">
            {claim.fraud_indicators.map((f: any) => (
              <li key={f.claim_fraud_indicator_id}>{f.indicator_type} — {f.severity} ({f.indicator_date})</li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900">Ingested documents (Neo4j + Qdrant)</h2>
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-v3-violet px-3 py-1.5 text-xs font-bold text-white hover:bg-v3-violetDark">
            {uploading ? <Loader2 size={14} className="animate-spin" /> : <FileUp size={14} />}
            {uploading ? "Processing…" : "Upload document"}
            <input
              ref={fileRef}
              type="file"
              accept="image/*,application/pdf"
              className="hidden"
              disabled={uploading}
              onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
            />
          </label>
        </div>
        {uploadError && <p className="mb-2 text-xs text-v3-rose">{uploadError}</p>}
        {claim.ingested_documents.length === 0 ? (
          <p className="text-sm text-gray-400">No documents ingested yet for this claim. Upload a scan, photo, or PDF — Gemini will OCR and extract entities into the graph.</p>
        ) : (
          <div className="space-y-3">
            {claim.ingested_documents.map((d) => (
              <div key={d.doc_id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wide text-v3-violet">{d.doc_type}</span>
                  <span className="text-xs text-gray-400">{Math.round((d.confidence || 0) * 100)}% confidence</span>
                </div>
                {d.parties.length > 0 && (
                  <p className="mt-1 flex items-center gap-1 text-sm text-gray-700"><Users size={13} /> {d.parties.join(", ")}</p>
                )}
                {d.flags.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {d.flags.map((f, i) => (
                      <li key={i} className="flex items-start gap-1 text-xs font-semibold text-v3-rose"><AlertTriangle size={12} className="mt-0.5 shrink-0" /> {f}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-card">
      <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
