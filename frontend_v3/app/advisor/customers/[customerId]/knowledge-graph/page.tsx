"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { use, useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { intelligenceApi, type CustomerKnowledgeGraph, type KnowledgeGraphNode } from "@/services/advisorApi";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const TYPE_COLOR: Record<string, string> = {
  Customer: "#7C3AED",
  FamilyMember: "#D97706",
  LifeEvent: "#DC2626",
  Goal: "#0D9488",
  Need: "#2563EB",
  Policy: "#059669",
  Conversation: "#9333EA",
  Topic: "#EA580C"
};

export default function CustomerKnowledgeGraphPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = use(params);
  const [data, setData] = useState<CustomerKnowledgeGraph | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<KnowledgeGraphNode | null>(null);

  useEffect(() => {
    intelligenceApi
      .getKnowledgeGraph(customerId)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [customerId]);

  const handleNodeClick = useCallback((node: unknown) => {
    setSelected(node as KnowledgeGraphNode);
  }, []);

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col">
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <Link href={`/advisor/customers/${customerId}`} className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-v3-violet">
          <ArrowLeft size={14} /> Back to profile
        </Link>
        <p className="mt-2 text-xs font-bold uppercase tracking-wide text-v3-violet">Knowledge Graph</p>
        <h1 className="mt-1 text-xl font-bold text-gray-900">{data ? data.nodes.find((n) => n.type === "Customer")?.label : "Loading..."}</h1>
        <div className="mt-2 flex flex-wrap gap-3 text-xs">
          {Object.entries(TYPE_COLOR).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1 font-semibold text-gray-600">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} /> {type}
            </span>
          ))}
        </div>
      </div>

      <div className="relative flex-1 bg-gray-50">
        {error && <p className="p-6 text-sm text-v3-rose">{error}</p>}
        {!data && !error && <p className="p-6 text-sm text-gray-400">Loading graph...</p>}

        {data && (
          <ForceGraph2D
            graphData={data}
            nodeId="id"
            nodeLabel="label"
            nodeColor={(node: any) => TYPE_COLOR[node.type] || "#94A3B8"}
            linkLabel="type"
            linkDirectionalArrowLength={4}
            linkColor={() => "#CBD5E1"}
            onNodeClick={handleNodeClick}
            nodeCanvasObjectMode={() => "after"}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
              const fontSize = 11 / scale;
              ctx.font = `${fontSize}px sans-serif`;
              ctx.fillStyle = "#334155";
              ctx.textAlign = "center";
              ctx.fillText(node.label, node.x, node.y + 10 / scale);
            }}
          />
        )}

        {selected && (
          <div className="absolute right-4 top-4 w-80 rounded-lg border border-gray-200 bg-white p-4 shadow-lg">
            <div className="flex items-start justify-between gap-2">
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase text-white"
                style={{ background: TYPE_COLOR[selected.type] || "#94A3B8" }}
              >
                {selected.type}
              </span>
              <button onClick={() => setSelected(null)} className="text-xs font-semibold text-gray-400 hover:text-gray-600">
                Close
              </button>
            </div>
            <p className="mt-2 text-sm font-semibold text-gray-900">{String(selected.value)}</p>
            <dl className="mt-3 space-y-1.5 text-xs">
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Source</dt>
                <dd className="text-right font-semibold text-gray-800">{selected.source || "—"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Confidence</dt>
                <dd className="text-right font-semibold text-gray-800">
                  {selected.confidence === null ? "—" : `${Math.round(Number(selected.confidence) * 100)}%`}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Last verified</dt>
                <dd className="text-right font-semibold text-gray-800">
                  {selected.last_verified_at ? new Date(selected.last_verified_at).toLocaleDateString() : "—"}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </div>
    </div>
  );
}
