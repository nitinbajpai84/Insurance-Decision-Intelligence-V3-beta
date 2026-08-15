"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import { NAV_SECTIONS, isNavItemActive } from "./navSections";

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 flex-col bg-v3-sidebar text-white lg:flex">
      <div className="border-b border-white/10 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-v3-violet shadow-glow">
            <Sparkles size={22} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-v3-teal">Advisor</p>
            <h1 className="text-lg font-bold leading-tight">Intelligence</h1>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-5 thin-scroll">
        {NAV_SECTIONS.map((section, i) => (
          <div key={section.title || `section-${i}`} className={i > 0 ? "pt-4" : ""}>
            {section.title && (
              <p className="px-3 pb-1 text-[10px] font-bold uppercase tracking-[0.16em] text-gray-500">{section.title}</p>
            )}
            {section.items.map((item) => {
              const active = isNavItemActive(pathname, item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
                    active ? "bg-v3-violet text-white" : "text-gray-300 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <Icon size={18} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 p-5">
        <div className="rounded-lg border border-v3-teal/30 bg-v3-teal/10 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-v3-teal">Memory model</p>
          <p className="mt-1 text-sm text-gray-200">AI proposes. Approved customer information becomes truth.</p>
        </div>
      </div>
    </aside>
  );
}
