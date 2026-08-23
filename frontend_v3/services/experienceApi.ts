import { API_BASE } from "./apiBase";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface ExperienceBasis {
  method: string;
  description: string;
  limitation: string;
  baseline_loss_ratio: number | null;
  earned_premium: number;
  incurred_claims: number;
  claim_count: number;
  window_from: string | null;
  window_to: string | null;
  min_claims_to_flag: number;
  divergence_threshold: number;
}

export interface ExperienceCell {
  cell: string;
  earned_premium: number;
  incurred_claims: number;
  claim_count: number;
  loss_ratio: number;
  actual_vs_expected: number | null;
  credibility: number;
  credible: boolean;
  diverging: boolean;
  direction: "adverse" | "favourable" | null;
}

export interface ExperienceDimension {
  dimension: string;
  label: string;
  derivation: "emergent" | "calibrated";
  derivation_note: string;
  basis: ExperienceBasis;
  cells: ExperienceCell[];
}

export interface FlaggedCell extends ExperienceCell {
  dimension: string;
  dimension_label: string;
}

export function fetchExperienceOverview() {
  return getJSON<{
    basis: ExperienceBasis;
    dimensions: ExperienceDimension[];
    diverging: FlaggedCell[];
  }>("/api/v3/experience/overview");
}
