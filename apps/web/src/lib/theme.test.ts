import { describe, expect, it } from "vitest";
import { parseTheme, resolveDark } from "./theme";

describe("theme", () => {
  it("defaults unknown values to system", () => {
    expect(parseTheme(null)).toBe("system");
    expect(parseTheme("blue")).toBe("system");
    expect(parseTheme("dark")).toBe("dark");
  });
  it("resolves dark", () => {
    expect(resolveDark("system", true)).toBe(true);
    expect(resolveDark("light", true)).toBe(false);
    expect(resolveDark("dark", false)).toBe(true);
  });
});
