import { API_BASE } from "./apiBase";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface ClaimSummary {
  claim_id: string;
  claim_number: string;
  claim_status: string;
  loss_date: string;
  report_date: string;
  loss_cause: string;
  paid_amount: number;
  reserve_amount: number;
  litigation_flag: boolean;
  customer_name: string | null;
  open_fraud_indicators: number;
}

export interface IngestedDocument {
  doc_id: string;
  doc_type: string;
  confidence: number;
  parties: string[];
  flags: string[];
}

export interface ClaimDetail extends ClaimSummary {
  close_date: string | null;
  loss_description: string | null;
  customer_email: string | null;
  policy_id: string;
  assigned_agent_id: string;
  fraud_indicators: Record<string, unknown>[];
  ingested_documents: IngestedDocument[];
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
}
export interface GraphLink {
  source: string;
  target: string;
  type: string;
}

export const api = {
  health: () => getJSON<Record<string, unknown>>("/api/v3/health"),
  listClaims: (limit = 50) => getJSON<ClaimSummary[]>(`/api/v3/claims?limit=${limit}`),
  getClaim: (claimId: string) => getJSON<ClaimDetail>(`/api/v3/claims/${encodeURIComponent(claimId)}`),
  graph: () => getJSON<{ nodes: GraphNode[]; links: GraphLink[] }>("/api/v3/graph"),
  async uploadDocument(claimId: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/v3/claims/${encodeURIComponent(claimId)}/documents`, {
      method: "POST",
      body: form
    });
    if (!res.ok) throw new Error(`upload failed: HTTP ${res.status}`);
    return res.json();
  }
};

export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `S$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
