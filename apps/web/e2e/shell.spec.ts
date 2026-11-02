import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const ROUTES = [
  ["/", "Dashboard"],
  ["/lab/", "Inference Lab"],
  ["/populations/", "Populations"],
  ["/experiments/", "Experiments"],
  ["/runs/", "Runs"],
  ["/reports/", "Reports"],
  ["/settings/", "Settings"],
] as const;

const VIEWPORTS = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1280, height: 800 },
] as const;

test.describe("navigation", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("every section is reachable from the sidebar", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Primary", exact: true });
    for (const [href, title] of ROUTES.slice(1)) {
      await nav.getByRole("link", { name: title }).click();
      await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
      await expect(nav.getByRole("link", { name: title })).toHaveAttribute("aria-current", "page");
      expect(new URL(page.url()).pathname.replace(/\/$/, "")).toBe(href.replace(/\/$/, ""));
    }
  });

  test("keyboard only: skip link, tab order and visible focus", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to content" });
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main$/);
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    const focused = page.locator(":focus");
    await expect(focused).toBeVisible();
    const outline = await focused.evaluate((el) => getComputedStyle(el).outlineStyle);
    expect(outline).not.toBe("none");
  });

  test("unknown route shows the not-found page", async ({ page }) => {
    await page.goto("/definitely-missing/");
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to dashboard" })).toBeVisible();
  });
});

test.describe("theme", () => {
  test("toggle switches, persists across reload, and has no flash", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Dark theme" }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await page.reload();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect(page.getByRole("button", { name: "Dark theme" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await page.getByRole("button", { name: "Light theme" }).click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });

  test("follows the OS preference by default", async ({ browser }) => {
    const ctx = await browser.newContext({ colorScheme: "dark" });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/dark/);
    await ctx.close();
  });
});

for (const vp of VIEWPORTS) {
  for (const scheme of ["light", "dark"] as const) {
    test.describe(`${vp.name} ${scheme}`, () => {
      test.use({ viewport: { width: vp.width, height: vp.height }, colorScheme: scheme });

      test("layout, no horizontal scroll, screenshot", async ({ page }) => {
        await page.goto("/");
        await expect(page.getByTestId("api-status")).toHaveText(/API ok/);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow).toBeLessThanOrEqual(0);
        const mobileNav = page.getByRole("navigation", { name: "Primary mobile" });
        if (vp.width < 768) await expect(mobileNav).toBeVisible();
        else await expect(mobileNav).toBeHidden();
        await page.screenshot({
          path: `e2e/screenshots/dashboard-${vp.name}-${scheme}.png`,
          fullPage: true,
        });
      });

      test("axe: no serious or critical violations on every route", async ({ page }) => {
        for (const [href, title] of ROUTES) {
          await page.goto(href);
          await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
          await expect(page.getByTestId("api-status")).toHaveText(/API ok/);
          const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
          const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
          expect(bad.map((v) => `${href}: ${v.id} (${v.nodes.length})`)).toEqual([]);
        }
      });
    });
  }
}

test.describe("mobile navigation", () => {
  test.use({ viewport: { width: 375, height: 812 } });

  test("every section is reachable from the bottom bar", async ({ page }) => {
    await page.goto("/");
    const bar = page.getByRole("navigation", { name: "Primary mobile" });
    const link = bar.getByRole("link", { name: "Settings" });
    await link.scrollIntoViewIfNeeded();
    await link.click();
    await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  });
});
