import { API_BASE } from "./apiBase";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface TriageReason {
  signal: string;
  points: number;
  text: string;
}

export interface TriagedClaim {
  claim_id: string;
  claim_number: string;
  customer_id: string;
  customer_name: string | null;
  policy_id: string | null;
  policy_number: string | null;
  product_name: string | null;
  line_of_business: string | null;
  loss_cause: string | null;
  loss_date: string | null;
  report_date: string | null;
  days_open: number | null;
  policy_duration_months: number | null;
  paid_amount: number | null;
  reserve_amount: number | null;
  litigation_flag: boolean;
  catastrophe_flag: boolean;
  open_fraud_indicators: number;
  underwriting: {
    application_id: string | null;
    rule_key: string | null;
    rule_version: number | null;
    auto_decided: boolean | null;
    risk_score: number | null;
    decision_status: string | null;
  } | null;
  score: number;
  tier: "high" | "medium" | "low";
  escalated_by: string | null;
  reasons: TriageReason[];
}

export interface TriageSummary {
  open_claims: number;
  needs_attention: number;
  by_tier: { high: number; medium: number; low: number };
  signal_counts: Record<string, number>;
  total_reserve: number;
  weights: Record<string, number>;
}

export function fetchTriage(limit = 100) {
  return getJSON<{ summary: TriageSummary; claims: TriagedClaim[] }>(
    `/api/v3/claims/triage?limit=${limit}`
  );
}
