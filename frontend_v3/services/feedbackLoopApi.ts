import { API_BASE } from "./apiBase";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface LoopMethod {
  measure: string;
  early_window_months: number;
  minimum_exposure_months: number;
  material_lift: number;
  why_exposure_matched: string;
  caveat: string;
}

export interface CohortRate {
  policies: number;
  early_claims: number;
  per_1000: number;
}

export interface LeakageFinding {
  detected: boolean;
  lift?: number;
  leaked_cohort?: CohortRate;
  comparison_cohort?: CohortRate;
  headline?: string;
  implication?: string;
  reason?: string;
}

export interface LeakCase {
  claim_id: string;
  claim_number: string;
  policy_duration_months: number | null;
  incurred: number | null;
  loss_cause: string | null;
  claim_status: string | null;
  policy_number: string | null;
  product_name: string | null;
  application_id: string | null;
  risk_score: number | null;
  decision_status: string | null;
  customer_name: string | null;
}

export interface LoopReport {
  method: LoopMethod;
  finding: LeakageFinding;
  by_rule_version: { rule: string; policies: number; early_claims: number; per_1000: number }[];
  by_score_band: { band: string; policies: number; early_claims: number; per_1000: number }[];
  cases: LeakCase[];
}

export function fetchLoopReport() {
  return getJSON<LoopReport>("/api/v3/feedback-loop/report");
}
