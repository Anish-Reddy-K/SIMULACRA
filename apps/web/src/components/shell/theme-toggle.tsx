"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { parseTheme, resolveDark, THEME_KEY, type ThemeChoice } from "@/lib/theme";

const OPTIONS = [
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "system", label: "System theme", Icon: Monitor },
  { value: "dark", label: "Dark theme", Icon: Moon },
] as const;

function apply(choice: ThemeChoice) {
  const prefersDark = matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", resolveDark(choice, prefersDark));
}

const CHANGE_EVENT = "simulacra-theme-change";

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function ThemeToggle() {
  const choice = useSyncExternalStore<ThemeChoice>(
    subscribe,
    () => parseTheme(localStorage.getItem(THEME_KEY)),
    () => "system",
  );

  function select(next: ThemeChoice) {
    localStorage.setItem(THEME_KEY, next);
    apply(next);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }

  return (
    <div role="group" aria-label="Theme" className="flex gap-1">
      {OPTIONS.map(({ value, label, Icon }) => (
        <Button
          key={value}
          type="button"
          variant="outline"
          size="icon-sm"
          aria-label={label}
          aria-pressed={choice === value}
          onClick={() => select(value)}
        >
          <Icon aria-hidden="true" />
        </Button>
      ))}
    </div>
  );
}
