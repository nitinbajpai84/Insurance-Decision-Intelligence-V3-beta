"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  Copy,
  ExternalLink,
  KeyRound,
  ShieldCheck,
  TriangleAlert
} from "lucide-react";
import { accountApi, type AccountProvider } from "@/services/advisorApi";

export default function AccountSetupPage() {
  const params = useParams<{ account: string }>();
  const accountKey = params.account;

  const [account, setAccount] = useState<AccountProvider | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    accountApi
      .get(accountKey)
      .then((data) => {
        setAccount(data);
        setValues((prev) => {
          const next = { ...prev };
          data.credential_fields.forEach((field) => {
            if (next[field.key] === undefined) next[field.key] = field.default || "";
          });
          return next;
        });
        setEnabled((prev) =>
          Object.keys(prev).length
            ? prev
            : Object.fromEntries(data.capabilities.map((c) => [c.provider, true]))
        );
      })
      .catch((e) => setError(e.message));
  }, [accountKey]);

  useEffect(load, [load]);

  async function saveCredentials() {
    setBusy("save");
    setError("");
    setNotice("");
    try {
      await accountApi.saveCredentials(accountKey, values);
      setNotice("Credentials saved and encrypted.");
      // Clear secrets from component state once stored — no reason to keep
      // them in memory, and it prevents an accidental re-render leak.
      setValues((prev) => {
        const next = { ...prev };
        account?.credential_fields.forEach((field) => {
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
      const selected = Object.entries(enabled)
        .filter(([, on]) => on)
        .map(([key]) => key);
      const result = await accountApi.connect(accountKey, selected);
      if (result.authorization_url) {
        window.location.href = result.authorization_url;
        return;
      }
      setNotice(
        result.verified_name
          ? `Connected as ${result.verified_name}. Webhook URL: ${result.webhook_url}`
          : "Connected."
      );
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  function copyRedirect() {
    if (!account) return;
    navigator.clipboard.writeText(account.redirect_uri).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (!account) {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
        {error ? <p className="text-sm text-v3-rose">{error}</p> : <p className="text-sm text-gray-400">Loading...</p>}
      </div>
    );
  }

  const isOAuth = account.auth_kind === "oauth2_authorization_code";

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <Link href="/advisor/connections" className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
        <ArrowLeft size={14} /> Back to Connection Center
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Set up</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">Connect {account.name}</h1>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">{account.notes}</p>
      </div>

      {notice && (
        <p className="inline-flex items-center gap-2 rounded-lg border border-v3-teal/30 bg-v3-teal/5 px-4 py-3 text-sm text-teal-800">
          <Check size={15} /> {notice}
        </p>
      )}
      {error && <p className="rounded-lg border border-v3-rose/30 bg-v3-rose/5 px-4 py-3 text-sm text-v3-rose">{error}</p>}

      <section className="rounded-lg border border-gray-100 bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <h2 className="font-bold text-gray-900">1. Register an app with {account.name}</h2>
          <p className="mt-1 text-sm text-gray-500">
            A one-time step. {account.name} issues the credentials — this application cannot create them for you.
          </p>
        </div>
        <div className="space-y-4 p-5">
          <ol className="space-y-2">
            {account.setup_steps.map((step, i) => (
              <li key={step} className="flex gap-3 text-sm text-gray-700">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-v3-violet/10 text-[11px] font-bold text-v3-violet">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>

          <div className="flex flex-wrap gap-2">
            <a
              href={account.console_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-3 py-2 text-sm font-bold text-white hover:bg-v3-violetDark"
            >
              Open {account.console_name} <ExternalLink size={14} />
            </a>
            {account.docs_url && (
              <a
                href={account.docs_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700 hover:border-v3-violet hover:text-v3-violet"
              >
                Provider docs <ExternalLink size={13} />
              </a>
            )}
          </div>

          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-gray-500">
              {isOAuth ? "Redirect URI to paste into the provider" : "Webhook callback URL"}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <code className="flex-1 break-all rounded bg-white px-3 py-2 text-xs text-gray-800">
                {isOAuth
                  ? account.redirect_uri
                  : account.redirect_uri.replace(/\/accounts\/meta\/callback$/, "/whatsapp/webhook")}
              </code>
              <button
                onClick={copyRedirect}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-bold text-gray-700 hover:border-v3-violet hover:text-v3-violet"
              >
                <Copy size={13} /> {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              This must match exactly, including the scheme and port. If you deploy the backend elsewhere, set
              OAUTH_REDIRECT_BASE to that public URL and re-copy this value.
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-gray-100 bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <h2 className="font-bold text-gray-900">2. Paste the credentials</h2>
          <p className="mt-1 inline-flex items-start gap-2 text-sm text-gray-500">
            <ShieldCheck size={15} className="mt-0.5 shrink-0 text-v3-teal" />
            Stored encrypted. Secrets are never shown again or returned by the API — only a masked hint.
          </p>
        </div>
        <div className="space-y-4 p-5">
          {account.credential_fields.map((field) => (
            <div key={field.key}>
              <label className="block text-sm font-semibold text-gray-800">
                {field.label}
                {field.optional && <span className="ml-1 text-xs font-normal text-gray-400">(optional)</span>}
              </label>
              <p className="mt-0.5 text-xs text-gray-500">{field.help_text}</p>
              <input
                type={field.secret ? "password" : "text"}
                autoComplete="off"
                value={values[field.key] ?? ""}
                onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                placeholder={field.secret ? "••••••••" : field.default || ""}
                className="mt-1 h-10 w-full rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-v3-violet focus:ring-2 focus:ring-v3-violet/20"
              />
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={saveCredentials}
              disabled={busy !== ""}
              className="inline-flex items-center gap-2 rounded-lg bg-v3-violet px-4 py-2 text-sm font-bold text-white hover:bg-v3-violetDark disabled:opacity-50"
            >
              <KeyRound size={15} /> {busy === "save" ? "Saving..." : "Save credentials"}
            </button>
            {account.credentials_configured ? (
              <span className="inline-flex items-center gap-1 text-sm font-semibold text-green-700">
                <Check size={15} /> Configured
                {account.credentials_source === "environment" && " (from environment)"}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-sm text-amber-700">
                <TriangleAlert size={15} /> Not configured yet
              </span>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-gray-100 bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <h2 className="font-bold text-gray-900">3. Choose what to enable, then authorize</h2>
          <p className="mt-1 text-sm text-gray-500">
            {isOAuth
              ? "One consent screen covers everything you tick. Only the scopes for those capabilities are requested."
              : "WhatsApp has no consent screen — the token is validated against Meta directly."}
          </p>
        </div>
        <div className="space-y-4 p-5">
          <div className="grid gap-2 sm:grid-cols-2">
            {account.capabilities.map((capability) => (
              <label
                key={capability.provider}
                className="flex cursor-pointer items-start gap-3 rounded-lg border border-gray-100 p-3 hover:border-v3-violet"
              >
                <input
                  type="checkbox"
                  checked={enabled[capability.provider] ?? true}
                  onChange={(e) =>
                    setEnabled((prev) => ({ ...prev, [capability.provider]: e.target.checked }))
                  }
                  className="mt-1"
                />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-gray-900">{capability.name}</span>
                  <span className="block text-xs text-gray-500">{capability.category}</span>
                  {capability.scopes.length > 0 && (
                    <span className="mt-1 block break-all font-mono text-[10px] text-gray-400">
                      {capability.scopes.join(" ")}
                    </span>
                  )}
                </span>
              </label>
            ))}
          </div>

          <button
            onClick={connect}
            disabled={busy !== "" || !account.credentials_configured}
            className="inline-flex items-center gap-2 rounded-lg bg-v3-teal px-4 py-2 text-sm font-bold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500"
            title={account.credentials_configured ? "" : "Save credentials first"}
          >
            {busy === "connect"
              ? "Connecting..."
              : isOAuth
                ? `Authorize with ${account.name}`
                : `Verify and connect ${account.name}`}
          </button>
        </div>
      </section>
    </div>
  );
}
