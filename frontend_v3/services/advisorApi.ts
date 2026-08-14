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

export const advisorApi = {
  listCustomers: () => getJSON<CustomerListItem[]>("/api/v3/advisor/customers"),
  getCustomer: (customerId: string) => getJSON<Customer360>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}`),
  prepareMeeting: (customerId: string) => postJSON<Briefing>(`/api/v3/advisor/customers/${encodeURIComponent(customerId)}/briefing`),
};

export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `S$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
