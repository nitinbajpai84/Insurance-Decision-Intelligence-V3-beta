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
  Settings,
  ShieldCheck,
  Users
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
}

// Shared by the desktop Sidebar and the mobile nav drawer so the two
// surfaces can never drift into showing a different set of pages.
export const NAV_SECTIONS: { title: string | null; items: NavItem[] }[] = [
  {
    title: "Advisor workspace",
    items: [
      { href: "/advisor", label: "My Day", icon: CalendarDays },
      { href: "/advisor/insights", label: "Insights", icon: Lightbulb },
      { href: "/advisor/customers", label: "Customers", icon: Users },
      { href: "/advisor/conversations", label: "Conversations", icon: MessageSquareText },
      { href: "/advisor/tasks", label: "Tasks", icon: CheckSquare },
      { href: "/advisor/connections", label: "Connections", icon: Link2 },
      { href: "/advisor/kpis", label: "KPI Dashboard", icon: BarChart3 },
      { href: "/advisor/audit", label: "AI Auditability", icon: ShieldCheck },
      { href: "/advisor/settings", label: "Profile / Settings", icon: Settings }
    ]
  },
  {
    title: "Platform",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard },
      { href: "/context-graph", label: "Context Graph", icon: GitBranch },
      { href: "/claims", label: "Claims", icon: FileText }
    ]
  }
];

export function isNavItemActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/advisor") return pathname === "/advisor";
  return pathname.startsWith(href);
}
