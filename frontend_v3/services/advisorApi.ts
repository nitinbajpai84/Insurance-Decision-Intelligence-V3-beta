import { API_BASE } from "./apiBase";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers: { Accept: "application/json" } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `POST ${path} -> HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export interface CustomerListItem {
  customer_id: string;
  name: string;
  life_stage: string;
  priority: "high" | "medium" | "low";
  days_since_contact: number | null;
  last_contact_date: string | null;
  is_stale: boolean;
  most_recent_life_event: string | null;
  most_recent_life_event_days_ago: number | null;
  open_concerns_count: number;
}

export interface Sourced<T = string> {
  source: string;
  confidence?: number;
  [key: string]: unknown;
}

export interface Customer360 extends CustomerListItem {
  advisor_name: string;
  family: { name: string; relationship: string; source: string; confidence: number }[];
  goals: { description: string; category: string; source: string; confidence: number }[];
  needs: { description: string; category: string; source: string; confidence: number }[];
  life_events: { description: string; date: string; category: string; source: string; confidence: number }[];
  meetings: { date: string; summary: string; source: string; confidence: number }[];
  concerns: { topic: string; source: string; confidence: number }[];
  discussed_topics: { topic: string; source: string; confidence: number }[];
  portfolio: { policy_id: string; product_name: string; line_of_business: string; annual_premium: number; policy_status: string }[];
  relevant_conversations: { text: string; score: number; confidence: number }[];
  claims: { claim_id: string; claim_number: string; claim_status: string; loss_date: string; report_date: string; loss_cause: string; paid_amount: number; reserve_amount: number }[];
}

export interface Briefing {
  customer_id: string;
  name: string;
  life_stage: { value: string; source: string; confidence: number };
  who_is_customer: { value: string | null; source: string; based_on: string };
  what_changed: { description: string; priority: "high" | "medium" | "low"; based_on: string; source: string }[];
  what_matters: {
    goals: { description: string; category: string; source: string; confidence: number }[];
    needs: { description: string; category: string; source: string; confidence: number }[];
  };
  what_they_said: { text: string; score: number; source: string; confidence: number }[];
  what_to_remember: {
    concerns: { topic: string; source: string; confidence: number }[];
    past_meetings: { date: string; summary: string; source: string; confidence: number }[];
  };
  suggested_questions: { question: string; based_on: string; source: string }[];
  potential_discussion_areas: { area: string; why: string; based_on: string; source: string }[];
  portfolio: { policy_id: string; product_name: string; line_of_business: string; annual_premium: number; policy_status: string }[];
  family: { name: string; relationship: string; source: string; confidence: number }[];
  gemini_error: string | null;
}

export interface ProposedMemory {
  memory_id: string;
  customer_id: string;
  memory_type: "life_event" | "goal" | "need" | "concern" | "preference" | "objection" | "commitment" | "follow_up";
  value: string;
  category: string | null;
  evidence: string;
  confidence: number;
  status: "pending" | "accepted" | "rejected" | "edited";
  has_conflict: boolean;
  conflict_with: string | null;
}

export interface IngestConversationResult {
  conversation_id: string;
  customer_id: string;
  summary: string;
  chunks_stored: number;
  proposed_memories: ProposedMemory[];
}

export interface ConversationRecord {
  conversation_id: string;
  date: string;
  summary: string;
  transcript_excerpt: string;
}

export interface MemoryTimelineEntry {
  memory_id: string;
  memory_type: string;
  value: string;
  status: string;
  confidence: number;
  created_at: string;
  last_verified_at: string;
  source: string;
}

export interface AdvisorTask {
  task_id: string;
  customer_id: string;
  customer_name: string;
  title: string;
  due_date: string;
  due_label?: string;
  status: "open" | "done";
  priority: "high" | "medium" | "low";
  source: string;
  type?: string;
}

export interface MyDay {
  today: string;
  summary: {
    customers: number;
    meetings_today: number;
    upcoming_meetings: number;
    customers_requiring_attention: number;
    pending_followups: number;
    new_customer_events: number;
    stale_customer_information: number;
    high_priority_customers: number;
  };
  meetings_today: { customer_id: string; customer_name: string; date: string; summary: string }[];
  upcoming_meetings: { customer_id: string; customer_name: string; date: string; summary: string }[];
  customers_requiring_attention: CustomerListItem[];
  pending_followups: AdvisorTask[];
  new_customer_events: CustomerListItem[];
  stale_customer_information: CustomerListItem[];
  high_priority_customers: CustomerListItem[];
}

export interface ConnectionProvider {
  provider: string;
  status: "connected" | "not_connected";
  sync_status: "synced" | "syncing" | "error" | "not_configured";
  last_sync: string | null;
}

export interface ConnectionCategory {
  category: string;
  providers: ConnectionProvider[];
}

export interface OnboardingResult {
  customers: number;
  upcoming_meetings: number;
  message: string;
}

async function postRaw<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `POST ${path} -> HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export const advisorApi = {
  getMyDay: () => getJSON<MyDay>("/api/v3/advisor/my-day"),
  listCustomers: () => getJSON<CustomerListItem[]>("/api/v3/advisor/customers"),
  getCustomer: (customerId: string) => getJSON<Customer360>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}`),
  uploadConversation: (customerId: string, transcript: string) =>
    postRaw<IngestConversationResult>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/conversations`, { transcript }),
  listConversations: (customerId: string) => getJSON<ConversationRecord[]>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/conversations`),
  listPendingMemories: (customerId: string, status = "pending") =>
    getJSON<ProposedMemory[]>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/pending-memories?status=${status}`),
  getMemoryTimeline: (customerId: string) => getJSON<MemoryTimelineEntry[]>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/memory-timeline`),
  approveMemory: (memoryId: string, editedValue?: string) =>
    postRaw<{ memory_id: string; status: string; value: string; promoted: boolean }>(`/api/v3/advisor/memories/${encodeURIComponent(memoryId)}/approve`, { edited_value: editedValue || null }),
  rejectMemory: (memoryId: string) =>
    postRaw<{ memory_id: string; status: string }>(`/api/v3/advisor/memories/${encodeURIComponent(memoryId)}/reject`, {}),
  prepareMeeting: (customerId: string) => postJSON<Briefing>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/briefing`),
  listTasks: () => getJSON<AdvisorTask[]>("/api/v3/advisor/tasks"),
  listConnections: () => getJSON<ConnectionCategory[]>("/api/v3/advisor/connections"),
  getOnboardingResult: () => getJSON<OnboardingResult>("/api/v3/advisor/onboarding/result"),
};

export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `S$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
