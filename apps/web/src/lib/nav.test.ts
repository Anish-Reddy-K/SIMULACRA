import { describe, expect, it } from "vitest";
import { isActive } from "./nav";

describe("isActive", () => {
  it("matches the dashboard only on the root", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/lab", "/")).toBe(false);
  });
  it("matches nested routes and trailing slashes", () => {
    expect(isActive("/lab/", "/lab")).toBe(true);
    expect(isActive("/lab/history", "/lab")).toBe(true);
    expect(isActive("/labs", "/lab")).toBe(false);
  });
});
