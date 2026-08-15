import type { Metadata, Viewport } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";

export const metadata: Metadata = {
  title: "Advisor Intelligence",
  description: "AI relationship intelligence for insurance and financial advisors."
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen bg-gray-100 text-gray-900">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex items-center justify-between gap-3 border-b border-gray-200 bg-white px-4 py-3 sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <MobileNav />
                <div className="min-w-0">
                  <p className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Advisor Intelligence</p>
                  <p className="truncate text-sm font-bold text-gray-900">
                    <span className="sm:hidden">Know every customer.</span>
                    <span className="hidden sm:inline">Know every customer. Prepare for every conversation.</span>
                  </p>
                </div>
              </div>
              <span className="shrink-0 rounded-full bg-v3-teal/10 px-3 py-1 text-xs font-bold text-v3-teal">STAGE 1</span>
            </header>
            <main className="flex-1">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
