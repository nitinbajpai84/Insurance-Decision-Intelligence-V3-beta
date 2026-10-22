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
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,700&display=swap"
        />
      </head>
      <body>
        <div className="flex min-h-screen bg-[#F3F5F6] text-[#14232B]">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex items-center justify-between gap-3 border-b border-gray-200 bg-white px-4 py-3 sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <MobileNav />
                <div className="min-w-0">
                  <p className="eyebrow">Advisor Intelligence</p>
                  <p className="truncate text-sm font-bold text-gray-900">
                    <span className="sm:hidden">Know every customer.</span>
                    <span className="hidden sm:inline">Know every customer. Prepare for every conversation.</span>
                  </p>
                </div>
              </div>
              <span className="shrink-0 rounded-full bg-[#D9EEF0] px-3 py-1 text-xs font-bold text-[#0F6B6B]">STAGE 1</span>
            </header>
            <main className="flex-1">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
