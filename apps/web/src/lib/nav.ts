export const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
  { href: "/lab", label: "Inference Lab", icon: "lab" },
  { href: "/populations", label: "Populations", icon: "populations" },
  { href: "/experiments", label: "Experiments", icon: "experiments" },
  { href: "/runs", label: "Runs", icon: "runs" },
  { href: "/reports", label: "Reports", icon: "reports" },
  { href: "/settings", label: "Settings", icon: "settings" },
] as const;

export type NavIcon = (typeof NAV_ITEMS)[number]["icon"];

export function isActive(pathname: string, href: string): boolean {
  const path = pathname.replace(/\/$/, "") || "/";
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
}
