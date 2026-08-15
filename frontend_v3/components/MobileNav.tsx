"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu, Sparkles, X } from "lucide-react";
import { NAV_SECTIONS, isNavItemActive } from "./navSections";

export default function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // A route change is the advisor tapping a link — close the drawer so
  // it never sits open over the page they just navigated to.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation menu"
        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-gray-200 text-gray-600 lg:hidden"
      >
        <Menu size={20} />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-black/40"
          />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-v3-sidebar text-white shadow-xl">
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-v3-violet shadow-glow">
                  <Sparkles size={18} />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-v3-teal">Advisor</p>
                  <h1 className="text-base font-bold leading-tight">Intelligence</h1>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation menu"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-300 hover:bg-white/10 hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-5">
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
                        className={`flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-semibold transition-colors ${
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
          </div>
        </div>
      )}
    </>
  );
}
