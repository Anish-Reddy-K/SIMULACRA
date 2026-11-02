import { describe, expect, it } from "vitest";
import { formatBytes, formatDuration, formatMb, formatNumber, formatPercent } from "./format";

describe("format", () => {
  it("never invents values for missing data", () => {
    expect(formatMb(null)).toBe("not measured");
    expect(formatNumber(undefined)).toBe("not measured");
    expect(formatPercent(null)).toBe("not measured");
    expect(formatBytes(null)).toBe("unknown");
  });
  it("formats sizes", () => {
    expect(formatMb(512)).toBe("512 MB");
    expect(formatMb(2048)).toBe("2.0 GB");
    expect(formatBytes(1929903008)).toBe("1.8 GB");
  });
  it("formats percent, numbers and durations", () => {
    expect(formatPercent(0.916)).toBe("92%");
    expect(formatNumber(24.56, 1, "/min")).toBe("24.6/min");
    expect(formatDuration(45)).toBe("45s");
    expect(formatDuration(185)).toBe("3m 5s");
  });
});
