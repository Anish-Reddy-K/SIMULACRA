import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const MOCK = /mock \/ mock-model/;

async function pickMockAndStart(page: Page, stage: RegExp, soakMinutes?: string) {
  await page.goto("/lab/benchmark/");
  await page.getByRole("checkbox", { name: MOCK }).check();
  await page.getByRole("radio", { name: stage }).check();
  if (soakMinutes) await page.getByLabel("Duration (minutes)").fill(soakMinutes);
  await page.getByRole("button", { name: /Start benchmark/ }).click();
  await expect(page).toHaveURL(/\/lab\/benchmark\/\?id=\d+/);
}

test.describe("inference lab overview", () => {
  test("shows real hardware, runtimes and honest empty recommendations", async ({ page }) => {
    await page.goto("/lab/");
    await expect(page.getByRole("heading", { level: 1, name: "Inference Lab" })).toBeVisible();
    await expect(page.getByText("This machine")).toBeVisible();
    await expect(page.getByText("Memory", { exact: true })).toBeVisible();
    await expect(page.getByText(/\d+(\.\d)? GB total/)).toBeVisible();
    await expect(page.getByText("Installed runtimes")).toBeVisible();
    for (const goal of ["Fastest", "Best balanced", "Highest local quality", "Overnight large-scale", "Low memory", "Privacy-first"]) {
      await expect(page.getByRole("heading", { name: goal })).toBeVisible();
    }
    await expect(page.getByText("Nothing recommended yet.").first()).toBeVisible();
  });

  test("a failed API call shows an error with retry, not a blank page", async ({ page }) => {
    await page.route("**/api/v1/lab/hardware", (route) => route.abort());
    await page.goto("/lab/");
    await expect(page.getByRole("alert").filter({ hasText: "Could not load this section" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });
});

test.describe("benchmark flow (synthetic mock backend)", () => {
  test("setup, live progress, results, evidence, and no recommendation from mock data", async ({ page }) => {
    await page.goto("/lab/benchmark/");
    await expect(page.getByRole("button", { name: /Start benchmark/ })).toBeDisabled();
    await pickMockAndStart(page, /Quick benchmark/);

    await expect(page.getByTestId("run-status")).toHaveText(/running|completed/);
    await expect(page.getByTestId("run-status")).toHaveText("completed", { timeout: 60_000 });
    await expect(page.getByText("Benchmark completed")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/lab-progress-done.png", fullPage: true });

    await page.getByRole("link", { name: "View results and evidence" }).click();
    await expect(page.getByRole("heading", { name: /Benchmark #\d+/ })).toBeVisible();
    await expect(page.getByText("Valid trials per minute (higher is better)")).toBeVisible();
    await expect(page.getByText(/Evidence: Quick \(indicative\)/).first()).toBeVisible();
    await expect(page.getByText(/Consistency diagnostics/)).toBeVisible();

    await page.getByRole("button", { name: "Inspect trials" }).first().click();
    await expect(page.getByRole("table", { name: /Raw trials/ })).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/lab-results.png", fullPage: true });

    await page.goto("/lab/");
    await expect(page.getByText("Nothing recommended yet.").first()).toBeVisible();
  });

  test("progress survives a page refresh and the run can be cancelled", async ({ page }) => {
    await pickMockAndStart(page, /Sustained run/, "1");
    await expect(page.getByTestId("run-status")).toHaveText("running");
    await expect(page.getByTestId("current-op")).toContainText("soak");
    await page.reload();
    await expect(page.getByTestId("run-status")).toHaveText("running");
    await expect(page.getByRole("progressbar")).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByTestId("run-status")).toHaveText("cancelled", { timeout: 20_000 });
    await expect(page.getByRole("link", { name: "View results and evidence" })).toBeVisible();
  });

  test("history lists runs and opens one", async ({ page }) => {
    await page.goto("/lab/history/");
    await expect(page.getByRole("heading", { level: 1, name: "Benchmark history" })).toBeVisible();
    await expect(page.getByRole("table", { name: /history/ })).toBeVisible();
    await page.getByRole("link", { name: "Open" }).first().click();
    await expect(page.getByRole("heading", { name: /Benchmark #\d+/ })).toBeVisible();
  });
});

test.describe("accessibility and layout", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`axe: lab pages have no serious violations (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      for (const [path, heading] of [
        ["/lab/", "Inference Lab"],
        ["/lab/benchmark/", "Run a benchmark"],
        ["/lab/history/", "Benchmark history"],
      ] as const) {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        await expect(page.getByText(/Loading/)).toHaveCount(0, { timeout: 10_000 });
        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
        expect(bad.map((v) => `${path}: ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
      }
    });
  }

  for (const vp of [{ n: "mobile", w: 375, h: 812 }, { n: "tablet", w: 768, h: 1024 }, { n: "desktop", w: 1280, h: 900 }]) {
    test(`lab overview fits ${vp.n}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h });
      await page.goto("/lab/");
      await expect(page.getByText(/GB total/)).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      await page.screenshot({ path: `e2e/screenshots/lab-${vp.n}.png`, fullPage: true });
    });
  }
});
