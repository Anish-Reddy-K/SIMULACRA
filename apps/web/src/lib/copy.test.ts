import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? files(p) : [p];
  });
}

describe("UI copy rules", () => {
  it("never uses em dashes in source (project rule: hyphens only)", () => {
    const offenders = files(join(__dirname, ".."))
      .filter((f) => /\.(tsx?|css)$/.test(f) && !f.endsWith("copy.test.ts"))
      .filter((f) => readFileSync(f, "utf8").includes("—"));
    expect(offenders).toEqual([]);
  });
});
