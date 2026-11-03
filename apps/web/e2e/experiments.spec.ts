import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

async function makePopulation(request: APIRequestContext, size = 40) {
  const preset = await (await request.get("/api/v1/populations/presets")).json();
  const res = await request.post("/api/v1/populations", { data: { spec: { ...preset, size, seed: 5, name: "Wizard pop" } } });
  expect(res.status()).toBe(201);
  return (await res.json()) as { id: number };
}

async function runWizard(page: Page, popLabel: string) {
  await page.goto("/experiments/new/");
  await page.getByLabel("Research question").fill("Would busy people buy a self-heating mug?");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Population").selectOption({ label: popLabel });
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Product name").fill("WarmMug");
  await page.getByLabel("Description").fill("A self-heating mug that keeps drinks hot for hours.");
  await page.getByLabel(/Price in USD/).fill("79");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Model and runtime").selectOption({ label: "mock / mock-model" });
  await page.getByRole("button", { name: "Next" }).click();
}

test.describe("experiment flow (mock backend, real worker)", () => {
  test("wizard to run to results to report to export", async ({ page, request }) => {
    await makePopulation(request, 40);
    await runWizard(page, "Wizard pop v1 (40 personas)");
    await expect(page.getByText("Trials", { exact: true })).toBeVisible();
    await expect(page.getByText("40", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/unknown - no benchmark/)).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/experiment-review.png", fullPage: true });
    await page.getByRole("button", { name: "Start experiment" }).click();

    await expect(page).toHaveURL(/\/runs\/view\/\?id=\d+/);
    await expect(page.getByTestId("run-state")).toHaveText("completed", { timeout: 60_000 });
    await expect(page.getByTestId("run-progress-text")).toContainText("40 of 40");

    await page.getByRole("link", { name: "View results" }).click();
    await expect(page.getByRole("heading", { name: "Results", level: 1 })).toBeVisible();
    await expect(page.getByText("Simulated results").first()).toBeVisible();
    await expect(page.getByText("Top-2-box:").first()).toBeVisible();
    await expect(page.getByText(/Not uncertainty about real people/).first()).toBeVisible();
    await page.getByRole("button", { name: /Source trial #\d+/ }).first().click();
    await expect(page.getByText("Prompt sent to the model")).toBeVisible();
    await expect(page.getByText(/WarmMug/).first()).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/experiment-results.png", fullPage: true });

    await page.getByRole("button", { name: "Create report" }).click();
    await expect(page).toHaveURL(/\/reports\/view\/\?id=\d+/);
    await expect(page.getByRole("heading", { name: "Executive summary" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Limitations" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Reproducibility metadata" })).toBeVisible();

    const [dl] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: "Export Markdown" }).click(),
    ]);
    expect(dl.suggestedFilename()).toMatch(/report-\d+\.md/);
    await page.screenshot({ path: "e2e/screenshots/experiment-report.png", fullPage: true });

    await page.goto("/reports/");
    await expect(page.getByRole("table", { name: /Reports, newest first/ })).toBeVisible();
  });

  test("wizard validates each step before moving on", async ({ page }) => {
    await page.goto("/experiments/new/");
    await expect(page.getByRole("button", { name: "Next" })).toBeDisabled();
    await page.getByLabel("Research question").fill("A real question?");
    await expect(page.getByRole("button", { name: "Next" })).toBeEnabled();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByRole("button", { name: "Next" })).toBeDisabled(); // no population chosen
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByLabel("Research question")).toHaveValue("A real question?");
  });

  test("experiments list and error states", async ({ page }) => {
    await page.goto("/experiments/");
    await expect(page.getByRole("link", { name: "New experiment" })).toBeVisible();
    await page.goto("/experiments/results/?run=999999");
    await expect(page.getByRole("alert").filter({ hasText: "Could not load this section" })).toBeVisible();
    await page.goto("/reports/view/?id=999999");
    await expect(page.getByRole("alert").filter({ hasText: "Could not load this section" })).toBeVisible();
  });
});

test.describe("accessibility", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`axe: experiment pages (${scheme})`, async ({ page, request }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await makePopulation(request, 30);
      const exp = await (await request.post("/api/v1/experiments", {
        data: {
          name: `A11y ${scheme}`, research_question: "A real question?", population_version_id: (await (await request.get("/api/v1/populations")).json())[0].id,
          scenario: { product_name: "P", description: "A product description here." },
        },
      })).json();
      const started = await (await request.post(`/api/v1/experiments/${exp.id}/start`, {
        data: { target: { base_url: "mock://", model: "mock-model" } },
      })).json();
      await expect.poll(async () => (await (await request.get(`/api/v1/runs/${started.run_id}`)).json()).state, { timeout: 60_000 }).toBe("completed");
      const rep = await (await request.post(`/api/v1/runs/${started.run_id}/reports`)).json();
      for (const path of ["/experiments/", "/experiments/new/", `/experiments/results/?run=${started.run_id}`, `/reports/view/?id=${rep.id}`, "/reports/"]) {
        await page.goto(path);
        await expect(page.getByText(/Loading/)).toHaveCount(0, { timeout: 10_000 });
        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
        expect(bad.map((v) => `${path}: ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
      }
    });
  }
});
