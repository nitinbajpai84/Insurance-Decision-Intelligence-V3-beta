import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Meridian V3 (beta) — Neo4j + Qdrant context layer",
  description: "Experimental rebuild of the context layer on Neo4j + Qdrant, with unstructured document ingestion."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen bg-gray-100 text-gray-900">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex items-center justify-between gap-3 border-b border-gray-200 bg-white px-4 py-3 sm:px-6">
              <div className="min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Experimental workspace</p>
                <p className="truncate text-sm font-bold text-gray-900">Meridian V3 — Graph + Vector Beta</p>
              </div>
              <span className="rounded-full bg-v3-amber/10 px-3 py-1 text-xs font-bold text-v3-amber">BETA</span>
            </header>
            <main className="flex-1">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
