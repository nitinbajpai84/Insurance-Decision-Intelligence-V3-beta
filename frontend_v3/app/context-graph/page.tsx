"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api, type GraphLink, type GraphNode } from "@/services/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const TYPE_COLOR: Record<string, string> = {
  Claim: "#7C3AED",
  Document: "#0D9488",
  Party: "#D97706",
  Flag: "#DC2626"
};

export default function ContextGraphPage() {
  const [data, setData] = useState<{ nodes: GraphNode[]; links: GraphLink[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.graph().then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col">
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <p className="text-xs font-bold uppercase tracking-wide text-v3-violet">Neo4j · live graph</p>
        <h1 className="mt-1 text-xl font-bold text-gray-900">Context Graph</h1>
        <div className="mt-2 flex gap-3 text-xs">
          {Object.entries(TYPE_COLOR).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1 font-semibold text-gray-600">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} /> {type}
            </span>
          ))}
        </div>
      </div>
      <div className="flex-1 bg-gray-50">
        {error && <p className="p-6 text-sm text-v3-rose">{error}</p>}
        {!data && !error && <p className="p-6 text-sm text-gray-400">Loading graph…</p>}
        {data && data.nodes.length === 0 && (
          <p className="p-6 text-sm text-gray-400">No nodes yet — upload a claim document to populate the graph.</p>
        )}
        {data && data.nodes.length > 0 && (
          <ForceGraph2D
            graphData={data}
            nodeLabel={(n: any) => `${n.type}: ${n.label}`}
            nodeColor={(n: any) => TYPE_COLOR[n.type] || "#9CA3AF"}
            linkLabel={(l: any) => l.type}
            linkColor={() => "#D1CFE0"}
            nodeRelSize={5}
          />
        )}
      </div>
    </div>
  );
}
