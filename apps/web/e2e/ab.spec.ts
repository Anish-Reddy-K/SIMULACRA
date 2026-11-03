import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

async function makePopulation(request: APIRequestContext, size: number, name: string) {
  const preset = await (await request.get("/api/v1/populations/presets")).json();
  const res = await request.post("/api/v1/populations", { data: { spec: { ...preset, size, seed: 9, name } } });
  expect(res.status()).toBe(201);
}

async function stepsToOffer(page: Page, popName: string, template: string) {
  await page.goto("/experiments/new/");
  await page.getByLabel("Research question").fill("Which option performs best with simulated shoppers?");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Population").selectOption({ label: `${popName} v1 (60 personas)` });
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Product name").fill("WarmMug");
  await page.getByLabel("Description").fill("A self-heating mug that keeps drinks hot for hours.");
  await page.getByRole("radio", { name: new RegExp(template) }).check();
}

test.describe("A/B and pricing through the UI", () => {
  test("pricing test: arms validated, comparison and demand curve shown", async ({ page, request }) => {
    await makePopulation(request, 60, "Pricing pop");
    await stepsToOffer(page, "Pricing pop", "Pricing");
    const next = page.getByRole("button", { name: "Next" });
    await expect(next).toBeDisabled();
    await page.getByLabel(/Prices to compare/).fill("49, 49");
    await expect(next).toBeDisabled(); // duplicate prices rejected
    await page.getByLabel(/Prices to compare/).fill("49, 79, 129");
    await expect(next).toBeEnabled();
    await next.click();
    await page.getByLabel("Model and runtime").selectOption({ label: "mock / mock-model" });
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Start experiment" }).click();

    await expect(page).toHaveURL(/\/runs\/view\/\?id=\d+/);
    await expect(page.getByTestId("run-state")).toHaveText("completed", { timeout: 60_000 });
    await page.getByRole("link", { name: "View results" }).click();
    await expect(page.getByRole("heading", { name: "Treatment comparison" })).toBeVisible();
    const table = page.getByRole("table", { name: /Treatments compared with the baseline/ });
    await expect(table.getByRole("row")).toHaveCount(3); // header + 2 vs baseline
    await expect(page.getByText("Simulated purchase interest by price (top-2-box)")).toBeVisible();
    await expect(page.getByText(/Randomization balance/)).toBeVisible();
    await expect(page.getByText(/not real demand/i)).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/pricing-results.png", fullPage: true });

    await page.getByRole("button", { name: "Create report" }).click();
    await expect(page).toHaveURL(/\/reports\/view\/\?id=\d+/);
    await expect(page.getByText(/versus \$49/).first()).toBeVisible();
  });

  test("ad comparison needs at least two headlines", async ({ page, request }) => {
    await makePopulation(request, 60, "Ad pop");
    await stepsToOffer(page, "Ad pop", "Ad comparison");
    const next = page.getByRole("button", { name: "Next" });
    await page.getByLabel(/Headlines to compare/).fill("Only one headline");
    await expect(next).toBeDisabled();
    await page.getByLabel(/Headlines to compare/).fill("Save an hour a day\nKeep your coffee hot");
    await expect(next).toBeEnabled();
  });

  test("axe on the wizard offer step with a template", async ({ page, request }) => {
    await makePopulation(request, 60, "Axe pop");
    await stepsToOffer(page, "Axe pop", "Ad comparison");
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  });
});
