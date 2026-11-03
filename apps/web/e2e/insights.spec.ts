import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";

async function completedRun(request: APIRequestContext, name: string) {
  const preset = await (await request.get("/api/v1/populations/presets")).json();
  const pop = await (await request.post("/api/v1/populations", { data: { spec: { ...preset, size: 60, seed: 3, name: `${name} pop` } } })).json();
  const exp = await (await request.post("/api/v1/experiments", {
    data: {
      name, research_question: "Which segments like it?", population_version_id: pop.id,
      scenario: { product_name: "WarmMug", description: "A self-heating mug that keeps drinks hot for hours.", price_usd: 79 },
    },
  })).json();
  const started = await (await request.post(`/api/v1/experiments/${exp.id}/start`, {
    data: { target: { base_url: "mock://", model: "mock-model" }, batch_size: 12 },
  })).json();
  await expect
    .poll(async () => (await (await request.get(`/api/v1/runs/${started.run_id}`)).json()).state, { timeout: 60_000 })
    .toBe("completed");
  return started.run_id as number;
}

test.describe("explore, evidence and comparison", () => {
  test("findings are verified and link to source trials", async ({ page, request }) => {
    const run = await completedRun(request, "Insights run");
    await page.goto(`/experiments/explore/?run=${run}`);
    await expect(page.getByRole("heading", { name: "Key findings with evidence" })).toBeVisible();
    await expect(page.getByText("verified against stored trials").first()).toBeVisible();
    await expect(page.getByText("not verified")).toHaveCount(0);
    await page.getByRole("button", { name: /Open source trial \d+/ }).first().click();
    await expect(page.getByText("Prompt sent to the model")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Themes in the free-text reasons" })).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/explore.png", fullPage: true });
  });

  test("structured question is computed and shows evidence; invalid input is explained", async ({ page, request }) => {
    const run = await completedRun(request, "Query run");
    await page.goto(`/experiments/explore/?run=${run}`);
    await page.getByLabel("Break down by").selectOption("region");
    await page.getByRole("button", { name: "Compute answer" }).click();
    await expect(page.getByText(/top2 share by region/i)).toBeVisible();
    await expect(page.getByText(/evidence:/).first()).toBeVisible();
    await page.getByLabel("What to measure").selectOption("objection_share");
    await page.getByLabel("Objection").selectOption("price");
    await page.getByLabel("Only people where").selectOption("region");
    await page.getByLabel("equals").fill("west");
    await page.getByRole("button", { name: "Compute answer" }).click();
    await expect(page.getByText(/objection share by region/i)).toBeVisible();
  });

  test("two runs can be compared for agreement", async ({ page, request }) => {
    const a = await completedRun(request, "Compare A");
    const b = await completedRun(request, "Compare B");
    await page.goto(`/experiments/compare/?a=${a}&b=${b}`);
    await expect(page.getByText(/Cohen's kappa/)).toBeVisible();
    await expect(page.getByText(/Matched trials/)).toBeVisible();
    await page.goto("/experiments/compare/?a=999999&b=999998");
    await expect(page.getByRole("alert").filter({ hasText: "Could not load this section" })).toBeVisible();
  });

  test("trials export as CSV", async ({ page, request }) => {
    const run = await completedRun(request, "CSV run");
    await page.goto(`/experiments/explore/?run=${run}`);
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Export trials (CSV)" }).click()]);
    expect(dl.suggestedFilename()).toMatch(/trials-\d+\.csv/);
  });

  for (const scheme of ["light", "dark"] as const) {
    test(`axe: explore page (${scheme})`, async ({ page, request }) => {
      await page.emulateMedia({ colorScheme: scheme });
      const run = await completedRun(request, `Axe ${scheme}`);
      await page.goto(`/experiments/explore/?run=${run}`);
      await expect(page.getByText(/Loading/)).toHaveCount(0, { timeout: 10_000 });
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    });
  }
});
