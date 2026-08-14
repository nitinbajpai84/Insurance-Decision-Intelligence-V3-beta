/**
 * apiBase — single source of truth for the V3 backend URL.
 * Same resolution pattern as V2's frontend_v2/services/apiBase.ts.
 */
const LOCAL_API = "http://127.0.0.1:3011";
const HOSTED_API = "https://meridian-v3-backend-786480520780.asia-southeast1.run.app";

function resolveApiBase(): string {
  const fromEnv = typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_V3_URL;
  if (fromEnv) return fromEnv;
  if (typeof window === "undefined") return LOCAL_API;
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "::1";
  return isLocal ? LOCAL_API : HOSTED_API;
}

export const API_BASE: string = resolveApiBase();
