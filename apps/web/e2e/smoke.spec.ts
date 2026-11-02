import { expect, test } from "@playwright/test";

test("shell shows live API status", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByTestId("api-status")).toHaveText(/API ok \(v\d+\.\d+\.\d+\)/);
});

test("shows an unreachable state when the API call fails", async ({ page }) => {
  await page.route("**/api/v1/health", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API unreachable");
});
