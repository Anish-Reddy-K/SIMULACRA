export type ThemeChoice = "light" | "dark" | "system";
export const THEME_KEY = "simulacra-theme";

export function resolveDark(choice: ThemeChoice, prefersDark: boolean): boolean {
  return choice === "dark" || (choice === "system" && prefersDark);
}

export function parseTheme(raw: string | null): ThemeChoice {
  return raw === "light" || raw === "dark" ? raw : "system";
}

// Runs before first paint (inline in <head>) so there is no flash of the wrong theme.
export const THEME_INIT_SCRIPT = `try{var c=localStorage.getItem("${THEME_KEY}");var d=c==="dark"||(c!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){}`;
