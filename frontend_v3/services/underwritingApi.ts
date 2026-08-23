import { API_BASE } from "./apiBase";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || `POST ${path} -> HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export interface UwCase {
  application_id: string;
  application_number: string;
  application_date: string | null;
  application_status: string;
  requested_premium: number | null;
  requested_sum_assured: number | null;
  medical_required: boolean | null;
  customer_id: string;
  customer_name: string | null;
  customer_segment: string | null;
  risk_tier: string | null;
  product_name: string | null;
  line_of_business: string | null;
  decision_status: string;
  risk_score: number | null;
  risk_class: string | null;
  rating_factor: number | null;
  exclusion_applied: boolean | null;
  auto_decided: boolean | null;
  rule_id_applied: string | null;
  decision_date: string | null;
  underwriting_reason: string | null;
}

export interface RuleTraceEntry {
  rule_id: string;
  rule_key: string;
  version: number;
  name: string;
  action: string;
  threshold: number | null;
  in_force: boolean;
  fired: boolean;
  why: string;
}

export interface Assessment {
  risk_score: number;
  recommendation: string;
  requires_underwriter: boolean;
  governing_rule: string | null;
  governing_rule_id: string | null;
  evaluated_on: string;
  trace: RuleTraceEntry[];
}

export interface DecisionEvent {
  log_id: string;
  event_seq: number;
  event_type: string;
  decided_at: string | null;
  decision: string | null;
  risk_score: number | null;
  rules_fired: string[];
  actor: string;
  actor_type: string;
  is_override: boolean;
  override_reason: string | null;
}

export interface UwCaseDetail extends UwCase {
  assessment?: Assessment;
  trail: DecisionEvent[];
  policy: {
    policy_id: string;
    policy_number: string;
    policy_status: string;
    effective_date: string | null;
    annual_premium: number | null;
    claim_count: number;
  } | null;
}

export interface QueueSummary {
  awaiting_review: number;
  auto_decided: number;
  total_cases: number;
  straight_through_rate: number | null;
  average_risk_score: number | null;
}

export interface UwRule {
  rule_id: string;
  rule_key: string;
  version: number;
  name: string;
  description: string | null;
  action: string;
  effective_from: string | null;
  effective_to: string | null;
  status: string;
  condition: Record<string, unknown> | null;
}

export function fetchQueue(awaitingOnly = true, limit = 50) {
  return getJSON<{ summary: QueueSummary; cases: UwCase[] }>(
    `/api/v3/underwriting/queue?awaiting_only=${awaitingOnly}&limit=${limit}`
  );
}

export function fetchCase(applicationId: string) {
  return getJSON<UwCaseDetail>(`/api/v3/underwriting/cases/${applicationId}`);
}

export function submitDecision(
  applicationId: string,
  decision: string,
  actor: string,
  reason?: string
) {
  return postJSON<{
    application_id: string;
    decision: string;
    recommended: string | null;
    was_override: boolean;
  }>(`/api/v3/underwriting/cases/${applicationId}/decision`, { decision, actor, reason });
}

export function fetchRules(activeOnly = false) {
  return getJSON<{ rules: UwRule[] }>(`/api/v3/underwriting/rules?active_only=${activeOnly}`);
}

export function fetchGovernance() {
  return getJSON<{
    applications: number;
    auto_approved: number;
    referred: number;
    underwriter_decisions: number;
    overrides: number;
    straight_through_rate: number | null;
    override_rate: number | null;
  }>("/api/v3/underwriting/governance");
}
