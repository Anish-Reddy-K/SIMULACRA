import { describe, expect, it } from "vitest";
import { availableActions, describeEta, type Run } from "./runs-api";

const run = (over: Partial<Run>): Run => ({
  id: 1, kind: "demo", name: "r", state: "running", total_units: 100, done_units: 10, error_units: 0,
  batches_total: 4, batches_failed: 0, created_at: "", started_at: null, finished_at: null,
  elapsed_s: 5, rate_per_min: null, eta_s: null, error: null, ...over,
});

describe("runs helpers", () => {
  it("offers only valid controls per state", () => {
    expect(availableActions("running")).toEqual(["pause", "cancel"]);
    expect(availableActions("paused")).toEqual(["resume", "cancel"]);
    expect(availableActions("completed")).toEqual([]);
    expect(availableActions("cancelled")).toEqual([]);
  });
  it("never invents an ETA", () => {
    expect(describeEta(run({}))).toBe("estimating...");
    expect(describeEta(run({ rate_per_min: 30, eta_s: 180 }))).toBe("about 3 min");
    expect(describeEta(run({ rate_per_min: 30, eta_s: 20 }))).toBe("under a minute");
    expect(describeEta(run({ rate_per_min: 1, eta_s: 7200 }))).toBe("about 2.0 h");
    expect(describeEta(run({ state: "paused" }))).toBe("paused");
    expect(describeEta(run({ state: "completed" }))).toBe("finished");
  });
});
