import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";

async function demoRun(request: APIRequestContext, units: number, sleep_s: number, batch_size = 5) {
  const res = await request.post("/api/v1/runs/demo", {
    data: { name: `E2E demo ${units}`, units, batch_size, config: { sleep_s } },
  });
  expect(res.status()).toBe(201);
  return (await res.json()) as { id: number };
}

test.describe("run monitor (real worker process)", () => {
  test("shows live progress and completes", async ({ page, request }) => {
    const run = await demoRun(request, 60, 0.02);
    await page.goto(`/runs/view/?id=${run.id}`);
    await expect(page.getByRole("heading", { name: /E2E demo 60/ })).toBeVisible();
    await expect(page.getByTestId("run-state")).toHaveText("completed", { timeout: 60_000 });
    await expect(page.getByTestId("run-progress-text")).toContainText("60 of 60 units complete (100%)");
    await expect(page.getByText("Run started")).toBeVisible();
    await expect(page.getByText(/Run completed/)).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/run-completed.png", fullPage: true });
  });

  test("pause, resume and cancel from the UI", async ({ page, request }) => {
    const run = await demoRun(request, 400, 0.05, 2);
    await page.goto(`/runs/view/?id=${run.id}`);
    await expect(page.getByTestId("run-state")).toHaveText("running", { timeout: 20_000 });
    await page.getByRole("button", { name: "Pause" }).click();
    await expect(page.getByTestId("run-state")).toHaveText("paused", { timeout: 20_000 });
    const frozen = await page.getByTestId("run-progress-text").textContent();
    await page.waitForTimeout(1500);
    await expect(page.getByTestId("run-progress-text")).toHaveText(frozen ?? "");
    await expect(page.getByRole("button", { name: "Resume" })).toBeVisible();

    await page.getByRole("button", { name: "Resume" }).click();
    await expect(page.getByTestId("run-state")).toHaveText("running", { timeout: 20_000 });
    await page.getByRole("button", { name: "Cancel run" }).click();
    await expect(page.getByTestId("run-state")).toHaveText("cancelled", { timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Pause" })).toHaveCount(0);
  });

  test("refresh mid-run reconnects without losing history", async ({ page, request }) => {
    const run = await demoRun(request, 300, 0.04, 3);
    await page.goto(`/runs/view/?id=${run.id}`);
    await expect(page.getByText("Run started")).toBeVisible({ timeout: 20_000 });
    await page.reload();
    await expect(page.getByText("Run started")).toBeVisible();
    await expect(page.getByTestId("run-state")).toHaveText("running");
    const first = Number((await page.getByTestId("run-progress-text").textContent())?.match(/^(\d+)/)?.[1]);
    await expect
      .poll(async () => Number((await page.getByTestId("run-progress-text").textContent())?.match(/^(\d+)/)?.[1]))
      .toBeGreaterThan(first);
    await request.post(`/api/v1/runs/${run.id}/cancel`);
    await expect(page.getByTestId("run-state")).toHaveText("cancelled", { timeout: 30_000 });
  });

  test("the time estimate is indeterminate until a rate exists", async ({ page, request }) => {
    const run = await demoRun(request, 500, 0.05, 4);
    await page.goto(`/runs/view/?id=${run.id}`);
    await expect(page.getByText("Time remaining").locator("xpath=..")).toContainText(/estimating|about|under a minute/, { timeout: 20_000 });
    await expect(page.getByText("estimating...")).toBeVisible();
    await expect(page.getByText(/about \d|under a minute/)).toBeVisible({ timeout: 30_000 });
    await request.post(`/api/v1/runs/${run.id}/cancel`);
  });

  test("runs list links to the monitor; unknown run shows an error", async ({ page, request }) => {
    const run = await demoRun(request, 5, 0);
    await page.goto("/runs/");
    const table = page.getByRole("table", { name: /Runs, newest first/ });
    await expect(table).toBeVisible();
    await expect(table.getByText(`#${run.id}`)).toBeVisible();
    await table.getByRole("row", { name: new RegExp(`#${run.id}`) }).getByRole("link").click();
    await expect(page.getByTestId("run-state")).toBeVisible();

    await page.goto("/runs/view/?id=999999");
    await expect(page.getByRole("alert").filter({ hasText: "Could not load this section" })).toBeVisible();
  });

  test("health shows the worker is running", async ({ request }) => {
    await expect
      .poll(async () => ((await (await request.get("/api/v1/health")).json()) as { worker: { status: string } }).worker.status)
      .toBe("running");
  });
});

test.describe("accessibility", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`axe: runs pages (${scheme})`, async ({ page, request }) => {
      await page.emulateMedia({ colorScheme: scheme });
      const run = await demoRun(request, 5, 0);
      for (const path of ["/runs/", `/runs/view/?id=${run.id}`]) {
        await page.goto(path);
        await expect(page.getByText(/Loading/)).toHaveCount(0, { timeout: 10_000 });
        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
        expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
      }
    });
  }
});
