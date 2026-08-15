"use client";

import Link from "next/link";
import { Bell, ShieldCheck, SlidersHorizontal, UserCircle } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Profile / Settings</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Advisor profile</h1>
        <p className="mt-1 text-sm text-gray-500">Lightweight Stage 1 settings for the advisor-facing workflow.</p>
      </div>

      <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-card">
        <div className="flex items-center gap-3">
          <UserCircle size={34} className="text-v3-violet" />
          <div>
            <p className="font-bold text-gray-900">Advisor workspace</p>
            <p className="text-sm text-gray-500">Insurance and financial relationship intelligence</p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-3">
        <SettingCard icon={<SlidersHorizontal size={18} className="text-v3-violet" />} title="Customer Management" text="Book review, follow-up cadence, and attention signals." />
        <SettingCard icon={<Bell size={18} className="text-v3-teal" />} title="Notifications" text="Daily reminders and meeting preparation prompts." />
        <SettingCard icon={<ShieldCheck size={18} className="text-v3-violet" />} title="Governance" text="AI proposals require advisor approval before becoming customer truth." />
      </div>

      <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="text-base font-bold text-gray-900">Setup</h2>
        <p className="mt-1 text-sm text-gray-500">Onboarding can be revisited any time to update profile choices and review data source readiness.</p>
        <Link href="/advisor/onboarding" className="mt-4 inline-flex rounded-lg bg-v3-violet px-4 py-2 text-sm font-bold text-white hover:bg-v3-violetDark">
          Open onboarding
        </Link>
      </section>
    </div>
  );
}

function SettingCard({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <section className="rounded-lg border border-gray-100 bg-white p-4 shadow-card">
      {icon}
      <h2 className="mt-3 text-sm font-bold text-gray-900">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-gray-500">{text}</p>
    </section>
  );
}
