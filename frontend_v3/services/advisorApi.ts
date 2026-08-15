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

export interface CalendarMeeting {
  meeting_id: string;
  title: string;
  starts_at: string | null;
  ends_at: string | null;
  time_label: string;
  date: string | null;
  meeting_link: string | null;
  location: string | null;
  status: string;
  attendees: string[];
  organizer: string | null;
  source_system: string | null;
  source_label: string;
  customer_id: string | null;
  customer_name: string | null;
  match_status: "matched" | "match_required";
  matched_on: string | null;
  match_label: string;
}

export interface TodayMeetings {
  date: string;
  total: number;
  matched: number;
  unmatched: number;
  message: string;
  meetings: CalendarMeeting[];
}

export interface FollowUp {
  followup_id: string;
  customer_id: string;
  customer_name: string;
  title: string;
  evidence: string | null;
  confidence: number;
  due_date: string;
  assigned_to: string;
  status: "open" | "completed";
  source: string;
  created_at: string;
  completed_at: string | null;
}

export interface PendingMemoryReview {
  memory_id: string;
  customer_id: string;
  customer_name: string;
  memory_type: string;
  value: string;
  category: string | null;
  evidence: string;
  confidence: number;
  created_at: string;
  has_conflict: boolean;
  conflict_with: string | null;
}

export interface MeetingHistoryEntry {
  conversation_id: string;
  date: string;
  summary: string;
  interaction_type: string;
  source_system: string | null;
  insights: { memory_id: string; memory_type: string; value: string; evidence: string; confidence: number }[];
  memory_changes: { memory_id: string; memory_type: string; value: string; status: string }[];
  pending_review_count: number;
  follow_ups: { followup_id: string; title: string; due_date: string; assigned_to: string; status: string }[];
}

export interface MyDay {
  today: string;
  meetings_message: string;
  calendar_meetings_today: CalendarMeeting[];
  unmatched_meetings: CalendarMeeting[];
  meetings_requiring_preparation: CalendarMeeting[];
  meetings_awaiting_processing: CalendarMeeting[];
  memory_updates_awaiting_approval: PendingMemoryReview[];
  overdue_followups: FollowUp[];
  summary: {
    customers: number;
    meetings_today: number;
    customer_meetings_today: number;
    unmatched_meetings: number;
    upcoming_meetings: number;
    customers_requiring_attention: number;
    pending_followups: number;
    new_customer_events: number;
    stale_customer_information: number;
    high_priority_customers: number;
    meetings_requiring_preparation: number;
    meetings_awaiting_processing: number;
    memory_updates_awaiting_approval: number;
    overdue_followups: number;
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

export interface ConnectionRow {
  provider: string;
  name: string;
  category: string;
  implementation: "live" | "credentialed" | "architecture";
  auth: string;
  scopes: string[];
  produces: string[];
  notes: string;
  missing_config: string[];
  can_connect: boolean;
  status: "connected" | "not_connected" | "error";
  account: string | null;
  last_sync: string | null;
  sync_status: string;
  data_synchronized: Record<string, number>;
  last_error: string | null;
  connected: boolean;
  blocked_reason: string;
  actions: { connect: boolean; disconnect: boolean; sync_now: boolean; upload: boolean };
}

export interface ConnectionCenterCategory {
  category: string;
  providers: ConnectionRow[];
}

export interface ImportPreview {
  dataset: string;
  headers: string[];
  valid_count: number;
  error_count: number;
  duplicate_count: number;
  existing_count: number;
  new_count: number;
  errors: { row: number; message: string }[];
  duplicates: { row: number; message: string }[];
  existing: Record<string, unknown>[];
  preview: Record<string, string>[];
  committed: boolean;
  imported?: Record<string, number>;
  import_errors?: string[];
  reason?: string;
}

export interface CalendarImportResult {
  counts: Record<string, number>;
  errors: string[];
  meetings: { meeting_id: string; customer_id: string | null; match_status: string; matched_on: string }[];
  unmatched_meetings: { meeting_id: string }[];
}

export interface AuditEvent {
  event_type: string;
  actor: string;
  subject_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

async function postEmpty<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers: { Accept: "application/json" } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `POST ${path} -> HTTP ${res.status}`);
  return body as T;
}

async function postFile<T>(path: string, file: File, fields: Record<string, string> = {}): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  Object.entries(fields).forEach(([key, value]) => form.append(key, value));
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `POST ${path} -> HTTP ${res.status}`);
  return body as T;
}

export interface CredentialField {
  key: string;
  label: string;
  help_text: string;
  secret: boolean;
  optional: boolean;
  default: string;
}

export interface AccountCapability {
  provider: string;
  name: string;
  category: string;
  implementation: string;
  scopes: string[];
}

export interface AccountProvider {
  account: string;
  name: string;
  auth_kind: string;
  console_url: string;
  console_name: string;
  docs_url: string;
  setup_steps: string[];
  notes: string;
  redirect_uri: string;
  capabilities: AccountCapability[];
  credential_fields: CredentialField[];
  credentials_configured: boolean;
  credentials_source: string;
  missing_credentials: string[];
}

export interface CrmVendor {
  provider: string;
  vendor: string;
  name: string;
  access: "self_serve_oauth" | "partner_gated";
  auth_kind: string;
  docs_url: string;
  notes: string;
  csv_export_hint: string;
  credential_fields: { key: string; label: string; secret: boolean }[];
  credentials_configured: boolean;
  hints: Record<string, string>;
  status: string;
  account: string | null;
  last_sync: string | null;
  data_synchronized: Record<string, number>;
  connected: boolean;
}

async function putJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body)
  });
  const parsed = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(parsed.detail || `PUT ${path} -> HTTP ${res.status}`);
  return parsed as T;
}

export const accountApi = {
  list: () => getJSON<AccountProvider[]>("/api/v3/integrations/accounts"),
  get: (account: string) => getJSON<AccountProvider>(`/api/v3/integrations/accounts/${encodeURIComponent(account)}`),
  saveCredentials: (account: string, values: Record<string, string>) =>
    putJSON<Record<string, unknown>>(`/api/v3/integrations/accounts/${encodeURIComponent(account)}/credentials`, { values }),
  connect: (account: string, capabilities?: string[]) =>
    postRaw<{ mode: string; authorization_url?: string; webhook_url?: string; verified_name?: string }>(
      `/api/v3/integrations/accounts/${encodeURIComponent(account)}/connect`,
      { capabilities: capabilities ?? null }
    ),
  disconnect: (account: string) =>
    postRaw<Record<string, unknown>>(`/api/v3/integrations/accounts/${encodeURIComponent(account)}/disconnect`, {}),
  listCrm: () => getJSON<CrmVendor[]>("/api/v3/integrations/crm"),
  saveCrmCredentials: (vendor: string, values: Record<string, string>) =>
    putJSON<Record<string, unknown>>(`/api/v3/integrations/crm/${encodeURIComponent(vendor)}/credentials`, { values }),
  connectCrm: (vendor: string) =>
    postRaw<{ mode: string; authorization_url?: string; connected?: boolean; next?: string }>(
      `/api/v3/integrations/crm/${encodeURIComponent(vendor)}/connect`,
      {}
    )
};

export const integrationApi = {
  connectionCenter: () => getJSON<ConnectionCenterCategory[]>("/api/v3/integrations"),
  connect: (provider: string) =>
    postEmpty<{ provider: string; mode: string; authorization_url?: string; message?: string }>(
      `/api/v3/integrations/${encodeURIComponent(provider)}/connect`
    ),
  disconnect: (provider: string) => postEmpty<Record<string, unknown>>(`/api/v3/integrations/${encodeURIComponent(provider)}/disconnect`),
  syncNow: (provider: string) => postEmpty<Record<string, unknown>>(`/api/v3/integrations/${encodeURIComponent(provider)}/sync`),
  auditLog: (subjectId?: string) =>
    getJSON<AuditEvent[]>(`/api/v3/integrations/audit${subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : ""}`),
  previewCsv: (file: File, dataset: string) => postFile<ImportPreview>("/api/v3/import/csv/preview", file, { dataset }),
  commitCsv: (file: File, dataset: string) => postFile<ImportPreview>("/api/v3/import/csv/commit", file, { dataset }),
  importIcs: (file: File) => postFile<CalendarImportResult>("/api/v3/import/calendar/ics", file),
  matchMeeting: (meetingId: string, customerId: string) =>
    postRaw<{ meeting_id: string; customer_id: string; customer_name: string; identities_learned: string[] }>(
      "/api/v3/import/meetings/match",
      { meeting_id: meetingId, customer_id: customerId }
    ),
};

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
  uploadConversation: (customerId: string, transcript: string, interactionType: "transcript" | "notes" = "transcript") =>
    postRaw<IngestConversationResult>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/conversations`, {
      transcript,
      interaction_type: interactionType
    }),
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
  getTodayMeetings: () => getJSON<TodayMeetings>("/api/v3/advisor/meetings/today"),
  listUnmatchedMeetings: () => getJSON<CalendarMeeting[]>("/api/v3/advisor/meetings/unmatched"),
  listConnections: () => getJSON<ConnectionCategory[]>("/api/v3/advisor/connections"),
  getOnboardingResult: () => getJSON<OnboardingResult>("/api/v3/advisor/onboarding/result"),
  listFollowUps: (opts?: { status?: string; overdue?: boolean }) => {
    const params = new URLSearchParams();
    if (opts?.status) params.set("status", opts.status);
    if (opts?.overdue) params.set("overdue", "true");
    const qs = params.toString();
    return getJSON<FollowUp[]>(`/api/v3/advisor/follow-ups${qs ? `?${qs}` : ""}`);
  },
  listCustomerFollowUps: (customerId: string) =>
    getJSON<FollowUp[]>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/follow-ups`),
  updateFollowUp: (followupId: string, changes: { title?: string; due_date?: string; assigned_to?: string }) =>
    patchJSON<FollowUp>(`/api/v3/advisor/follow-ups/${encodeURIComponent(followupId)}`, changes),
  completeFollowUp: (followupId: string) =>
    postRaw<FollowUp>(`/api/v3/advisor/follow-ups/${encodeURIComponent(followupId)}/complete`, {}),
  reopenFollowUp: (followupId: string) =>
    postRaw<FollowUp>(`/api/v3/advisor/follow-ups/${encodeURIComponent(followupId)}/reopen`, {}),
  getMeetingHistory: (customerId: string) =>
    getJSON<MeetingHistoryEntry[]>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/meeting-history`),
};

async function patchJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body)
  });
  const parsed = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(parsed.detail || `PATCH ${path} -> HTTP ${res.status}`);
  return parsed as T;
}

export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `S$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
