import {
  BarChart3,
  CalendarDays,
  CheckSquare,
  FileText,
  GitBranch,
  LayoutDashboard,
  Lightbulb,
  Link2,
  MessageSquareText,
  Scale,
  Settings,
  ShieldCheck,
  Stethoscope,
  Users
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
}

// Grouped by where each screen sits in the life & health value chain, not by
// when it was built. Distribution was the original product; the risk chain is
// the same warehouse pointed at underwriting, pricing and claims decisions.
export const NAV_SECTIONS: { title: string | null; items: NavItem[] }[] = [
  {
    title: "Distribution",
    items: [
      { href: "/advisor", label: "My Day", icon: CalendarDays },
      { href: "/advisor/insights", label: "Insights", icon: Lightbulb },
      { href: "/advisor/customers", label: "Customers", icon: Users },
      { href: "/advisor/conversations", label: "Conversations", icon: MessageSquareText },
      { href: "/advisor/tasks", label: "Tasks", icon: CheckSquare }
    ]
  },
  {
    title: "Risk chain",
    items: [
      { href: "/underwriting", label: "Underwriting", icon: Stethoscope },
      { href: "/claims/triage", label: "Claims", icon: FileText }
    ]
  },
  {
    title: "Governance",
    items: [
      { href: "/underwriting/rules", label: "Rules & Versions", icon: Scale },
      { href: "/advisor/audit", label: "AI Auditability", icon: ShieldCheck },
      { href: "/context-graph", label: "Context Graph", icon: GitBranch }
    ]
  },
  {
    title: "Platform",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard },
      { href: "/advisor/kpis", label: "KPI Dashboard", icon: BarChart3 },
      { href: "/advisor/connections", label: "Connections", icon: Link2 },
      { href: "/advisor/settings", label: "Profile / Settings", icon: Settings }
    ]
  }
];

export function isNavItemActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/advisor") return pathname === "/advisor";
  // "Underwriting" must not light up while the reader is on the Rules screen,
  // which lives beneath it but is a separate destination in the nav.
  if (href === "/underwriting") return pathname === "/underwriting" || pathname.startsWith("/underwriting/cases");
  // Claims points at the triage queue, but the register and claim detail sit at
  // /claims/* and should still keep the nav item lit rather than orphaning it.
  if (href === "/claims/triage") return pathname.startsWith("/claims");
  return pathname.startsWith(href);
}
