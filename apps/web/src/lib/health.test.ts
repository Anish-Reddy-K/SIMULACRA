import { describe, expect, it } from "vitest";
import { describeHealth, type Health } from "./health";

const base: Health = {
  status: "ok",
  version: "0.1.0",
  database: { ok: true, journal_mode: "wal" },
  worker: { status: "not_running" },
};

describe("describeHealth", () => {
  it("reports loading before a response", () => {
    expect(describeHealth(null, false)).toEqual({ label: "Checking API...", ok: false });
  });
  it("reports unreachable on failure", () => {
    expect(describeHealth(null, true).ok).toBe(false);
  });
  it("reports ok with version", () => {
    expect(describeHealth(base, false)).toEqual({ label: "API ok (v0.1.0)", ok: true });
  });
  it("reports degraded", () => {
    const view = describeHealth({ ...base, status: "degraded" }, false);
    expect(view.ok).toBe(false);
    expect(view.label).toContain("degraded");
  });
});
