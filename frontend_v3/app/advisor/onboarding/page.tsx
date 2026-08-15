"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Link2, Sparkles, UserRound } from "lucide-react";
import { advisorApi, type ConnectionCategory, type OnboardingResult } from "@/services/advisorApi";

const STEPS = [
  "Welcome",
  "Agent profile",
  "Customer management",
  "Connect data sources",
  "Import / sync customers",
  "Initial result"
];

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [connections, setConnections] = useState<ConnectionCategory[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([advisorApi.getOnboardingResult(), advisorApi.listConnections()])
      .then(([resultData, connectionData]) => {
        setResult(resultData);
        setConnections(connectionData);
      })
      .catch((e) => setError(e.message));
  }, []);

  const progress = useMemo(() => Math.round(((step + 1) / STEPS.length) * 100), [step]);

  function finish() {
    localStorage.setItem("advisor_onboarding_complete", "true");
  }

  function skip() {
    localStorage.setItem("advisor_onboarding_complete", "skipped");
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href="/advisor" className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
          <ArrowLeft size={14} /> Back to My Day
        </Link>
        <Link href="/advisor" onClick={skip} className="text-xs font-bold uppercase tracking-wide text-gray-400 hover:text-v3-violet">
          Skip and complete later
        </Link>
      </div>

      <section className="rounded-lg border border-gray-100 bg-white shadow-card">
        <div className="border-b border-gray-100 p-5">
          <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Onboarding</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">{STEPS[step]}</h1>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-gray-100">
            <div className="h-full bg-v3-teal transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>

        <div className="min-h-[340px] p-5">
          {error && <p className="text-sm text-v3-rose">{error}</p>}
          {step === 0 && <WelcomeStep />}
          {step === 1 && <ProfileStep />}
          {step === 2 && <ManagementStep />}
          {step === 3 && <ConnectionStep connections={connections} />}
          {step === 4 && <ImportStep />}
          {step === 5 && <ResultStep result={result} />}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 p-5">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-600 hover:border-v3-violet hover:text-v3-violet disabled:opacity-40"
          >
            <ArrowLeft size={15} /> Back
          </button>
          {step < STEPS.length - 1 ? (
            <button onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))} className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2 text-sm font-bold text-white hover:bg-v3-violetDark">
              Continue <ArrowRight size={15} />
            </button>
          ) : (
            <Link href="/advisor" onClick={finish} className="inline-flex items-center gap-2 rounded-lg bg-v3-teal px-4 py-2 text-sm font-bold text-white hover:bg-teal-700">
              Finish setup <Check size={15} />
            </Link>
          )}
        </div>
      </section>
    </div>
  );
}

function WelcomeStep() {
  return (
    <div className="grid gap-6 md:grid-cols-[0.8fr_1.2fr] md:items-center">
      <div className="flex h-40 items-center justify-center rounded-lg bg-v3-violet/10">
        <Sparkles size={42} className="text-v3-violet" />
      </div>
      <div>
        <h2 className="text-xl font-bold text-gray-900">Know every customer. Prepare for every conversation. Never forget what matters.</h2>
        <p className="mt-3 text-sm leading-6 text-gray-600">This setup creates an advisor-facing workflow for daily attention, customer intelligence, meeting preparation, and memory review.</p>
      </div>
    </div>
  );
}

function ProfileStep() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <UserRound size={28} className="text-v3-violet" />
        <div>
          <h2 className="font-bold text-gray-900">Agent profile</h2>
          <p className="text-sm text-gray-500">Stage 1 captures the product shape. Persistent profile editing can attach here later.</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <ReadonlyField label="Role" value="Insurance / financial advisor" />
        <ReadonlyField label="Primary workflow" value="Relationship intelligence and meeting prep" />
      </div>
    </div>
  );
}

function ManagementStep() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {["By upcoming meetings", "By recent life events", "By stale customer information"].map((item) => (
        <div key={item} className="rounded-lg border border-gray-100 p-4">
          <p className="font-semibold text-gray-900">{item}</p>
          <p className="mt-1 text-sm text-gray-500">Used to shape My Day and follow-up priority.</p>
        </div>
      ))}
    </div>
  );
}

function ConnectionStep({ connections }: { connections: ConnectionCategory[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {connections.map((group) => (
        <div key={group.category} className="rounded-lg border border-gray-100 p-4">
          <div className="mb-2 flex items-center gap-2">
            <Link2 size={16} className="text-v3-teal" />
            <p className="font-semibold text-gray-900">{group.category}</p>
          </div>
          <p className="text-sm text-gray-500">{group.providers.map((p) => p.provider).join(", ")}</p>
          <p className="mt-2 text-xs font-bold uppercase text-gray-400">Not connected</p>
        </div>
      ))}
    </div>
  );
}

function ImportStep() {
  return (
    <div className="rounded-lg border border-gray-100 p-5">
      <h2 className="font-bold text-gray-900">Import and sync framework</h2>
      <p className="mt-2 text-sm leading-6 text-gray-600">Stage 1 does not perform third-party sync. Existing seeded customers remain available so the advisor can complete the workflow and inspect the app experience.</p>
    </div>
  );
}

function ResultStep({ result }: { result: OnboardingResult | null }) {
  return (
    <div className="rounded-lg border border-v3-teal/20 bg-v3-teal/5 p-6">
      <p className="text-sm font-bold uppercase tracking-wide text-v3-teal">Initial result</p>
      <h2 className="mt-2 text-2xl font-bold text-gray-900">{result ? result.message : "Loading customer result..."}</h2>
      <p className="mt-2 text-sm text-gray-600">Open My Day next to review attention signals, find a customer, prepare a meeting, and view available connections.</p>
    </div>
  );
}

function ReadonlyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-100 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900">{value}</p>
    </div>
  );
}
