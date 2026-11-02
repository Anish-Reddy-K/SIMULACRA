"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ApiStatus } from "@/components/shell/api-status";
import { NavGlyph } from "@/components/shell/nav-icon";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { isActive, NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";

function NavLinks({ orientation }: { orientation: "rail" | "bar" }) {
  const pathname = usePathname();
  return (
    <ul className={cn("flex gap-1", orientation === "rail" ? "flex-col" : "overflow-x-auto")}>
      {NAV_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <li key={item.href} className={orientation === "bar" ? "min-w-[4.75rem] flex-1" : undefined}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-11 items-center rounded-lg border text-sm font-medium transition-colors duration-150",
                orientation === "rail"
                  ? "gap-3 px-3"
                  : "flex-col justify-center gap-0.5 px-1 py-1 text-[0.7rem]",
                active
                  ? "border-primary bg-accent text-accent-foreground neu-inset"
                  : "border-transparent text-foreground hover:bg-muted",
              )}
            >
              <NavGlyph name={item.icon} />
              <span className={orientation === "bar" ? "max-w-full truncate" : undefined}>
                {item.label}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-lg focus:border focus:border-primary focus:bg-card focus:px-4 focus:py-2"
      >
        Skip to content
      </a>
      <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r border-hairline bg-sidebar p-4 md:flex">
        <div className="px-3 pt-2">
          <p className="text-lg font-semibold tracking-tight">Simulacra</p>
          <p className="text-xs text-muted-foreground">Local synthetic research lab</p>
        </div>
        <nav aria-label="Primary">
          <NavLinks orientation="rail" />
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-3 md:px-8">
          <p className="text-base font-semibold tracking-tight md:hidden">Simulacra</p>
          <div className="ml-auto flex items-center gap-3">
            <ApiStatus />
            <ThemeToggle />
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 pb-28 md:px-8 md:pb-10">
          {children}
        </main>
      </div>
      <nav
        aria-label="Primary mobile"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-hairline bg-sidebar p-2 md:hidden"
      >
        <NavLinks orientation="bar" />
      </nav>
    </div>
  );
}
