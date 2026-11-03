import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function generate(page: Page, name: string, size: string, seed = "1") {
  await page.goto("/populations/");
  await page.getByLabel("Name").first().fill(name);
  await page.getByLabel(/Number of personas/).fill(size);
  await page.getByLabel("Seed").fill(seed);
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page).toHaveURL(/\/populations\/view\/\?id=\d+/);
}

test.describe("population explorer", () => {
  test("generate, inspect diagnostics and personas, search and page", async ({ page }) => {
    await generate(page, "E2E population", "120");
    await expect(page.getByTestId("pop-status")).toHaveText("ready");
    await expect(page.getByText("Synthetic people")).toBeVisible();
    await expect(page.getByText("Fidelity to the assumed distribution")).toBeVisible();
    await expect(page.getByText("target 17% - realized 17%").first()).toBeVisible();
    await expect(page.getByText(/Rejection sampling discarded/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Correlations" })).toBeVisible();

    const table = page.getByRole("table", { name: "Personas in this population" });
    await expect(table.getByRole("row")).toHaveCount(26); // header + 25
    await expect(page.getByRole("status").filter({ hasText: "1 to 25 of 120" })).toBeVisible();
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.getByRole("status").filter({ hasText: "26 to 50 of 120" })).toBeVisible();

    await page.getByRole("button", { name: "Details" }).first().click();
    await expect(page.getByText(/Bio source: template/)).toBeVisible();

    await page.getByLabel("Search name, id or biography").fill("zzzz-no-such-persona");
    await expect(page.getByText("No personas match")).toBeVisible();
    await page.screenshot({ path: "e2e/screenshots/population-detail.png", fullPage: true });
  });

  test("export and re-import round trip", async ({ page }) => {
    await generate(page, "Round trip source", "30", "9");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: "Export JSONL" }).click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/population-\d+\.jsonl/);
    const path = await download.path();

    await page.goto("/populations/");
    await page.getByLabel("File (.jsonl exported from Simulacra)").setInputFiles(path);
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await expect(page).toHaveURL(/\/populations\/view\/\?id=\d+/);
    await expect(page.getByText("30 personas")).toBeVisible();
    await expect(page.getByText(/imported/).first()).toBeVisible();
  });

  test("rejects a bad import file with a clear message", async ({ page }) => {
    await page.goto("/populations/");
    await page.getByLabel("File (.jsonl exported from Simulacra)").setInputFiles({
      name: "bad.jsonl",
      mimeType: "application/x-ndjson",
      buffer: Buffer.from("this is not json"),
    });
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "not valid JSON" })).toBeVisible();
  });

  test("biographies from a model show live progress then finish (mock backend)", async ({ page }) => {
    await page.goto("/populations/");
    await page.getByLabel("Name").first().fill("Enriched");
    await page.getByLabel(/Number of personas/).fill("20");
    await page.getByLabel(/Write biographies with a local model/).selectOption({ label: "mock / mock-model" });
    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page).toHaveURL(/\/populations\/view\/\?id=\d+/);
    await expect(page.getByTestId("pop-status")).toHaveText("ready", { timeout: 30_000 });
    await page.getByRole("button", { name: "Details" }).first().click();
    await expect(page.getByText(/Bio source: llm/)).toBeVisible();
  });

  test("list shows created populations", async ({ page }) => {
    await generate(page, "Listed population", "10");
    await page.goto("/populations/");
    const table = page.getByRole("table", { name: /Populations, newest first/ });
    await expect(table.getByText("Listed population")).toBeVisible();
    await table.getByRole("link", { name: "Open" }).first().click();
    await expect(page.getByTestId("pop-status")).toBeVisible();
  });

  test("a failing API shows an error state", async ({ page }) => {
    await page.route("**/api/v1/populations", (route) => route.abort());
    await page.goto("/populations/");
    await expect(page.getByRole("alert").filter({ hasText: "Could not load this section" })).toBeVisible();
  });
});

test.describe("accessibility and layout", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`axe: population pages have no serious violations (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await generate(page, `A11y ${scheme}`, "30");
      await expect(page.getByTestId("pop-status")).toHaveText("ready");
      await expect(page.getByText(/Loading/)).toHaveCount(0, { timeout: 10_000 });
      for (const path of [page.url(), "/populations/"]) {
        await page.goto(path);
        await expect(page.getByText(/Loading/)).toHaveCount(0, { timeout: 10_000 });
        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
        expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
      }
    });
  }

  for (const vp of [{ n: "mobile", w: 375, h: 812 }, { n: "desktop", w: 1280, h: 900 }]) {
    test(`population detail fits ${vp.n}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.w, height: vp.h });
      await generate(page, `Layout ${vp.n}`, "40");
      await expect(page.getByTestId("pop-status")).toHaveText("ready");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      await page.screenshot({ path: `e2e/screenshots/population-${vp.n}.png`, fullPage: true });
    });
  }
});
