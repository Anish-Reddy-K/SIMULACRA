import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(__dirname, "../app/globals.css"), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  const body = css.slice(start, css.indexOf("\n}", start));
  const vars: Record<string, string> = {};
  for (const m of body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})\s*;/gi)) vars[m[1]] = m[2];
  return vars;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const themes = { light: block(":root"), dark: block(".dark") };

describe.each(Object.entries(themes))("%s theme contrast", (_name, t) => {
  const textPairs: [string, string][] = [
    ["foreground", "background"],
    ["foreground", "surface"],
    ["muted-foreground", "background"],
    ["muted-foreground", "surface"],
    ["muted-foreground", "muted"],
    ["primary", "background"],
    ["primary", "surface"],
    ["primary-foreground", "primary"],
    ["accent-foreground", "accent"],
    ["destructive", "surface"],
    ["destructive", "background"],
    ["warning", "warning-soft"],
    ["warning", "background"],
    ["success", "surface"],
  ];
  it.each(textPairs)("text %s on %s is at least 4.5:1", (fg, bg) => {
    expect(t[fg], `missing --${fg}`).toBeDefined();
    expect(t[bg], `missing --${bg}`).toBeDefined();
    expect(ratio(t[fg], t[bg])).toBeGreaterThanOrEqual(4.5);
  });

  const uiPairs: [string, string][] = [
    ["border", "background"],
    ["border", "surface"],
    ["border", "muted"],
    ["ring", "background"],
    ["ring", "surface"],
  ];
  it.each(uiPairs)("control %s against %s is at least 3:1", (fg, bg) => {
    expect(ratio(t[fg], t[bg])).toBeGreaterThanOrEqual(3);
  });
});
