import {
  Activity,
  FileText,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Settings,
  Users,
} from "lucide-react";
import type { NavIcon } from "@/lib/nav";

const ICONS = {
  dashboard: LayoutDashboard,
  lab: Gauge,
  populations: Users,
  experiments: FlaskConical,
  runs: Activity,
  reports: FileText,
  settings: Settings,
} as const;

export function NavGlyph({ name }: { name: NavIcon }) {
  const Icon = ICONS[name];
  return <Icon aria-hidden="true" className="size-5" />;
}
