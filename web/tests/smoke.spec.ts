import { expect, test } from "@playwright/test";

test("overview page renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Scanner health and review queue")).toBeVisible();
  await expect(page.getByText("Current Watchlist")).toBeVisible();
});

test("markets page renders", async ({ page }) => {
  await page.goto("/markets");
  await expect(page.getByText("Scanner-scope market explorer")).toBeVisible();
  await expect(page.getByText("Valorant: Dragon Ranger Gaming vs Wolves Esports (BO3)")).toBeVisible();
});

test("watchlist page renders", async ({ page }) => {
  await page.goto("/watchlist");
  await expect(page.getByText("Persisted watchlist candidates")).toBeVisible();
  await expect(page.getByText("History-ready")).toBeVisible();
});

test("alerts page handles empty state", async ({ page }) => {
  await page.goto("/alerts");
  await expect(page.getByText("No alerts fired yet")).toBeVisible();
});

test("research page handles empty state", async ({ page }) => {
  await page.goto("/research");
  await expect(page.getByText("Backtest feedback loop")).toBeVisible();
  await expect(page.getByText("No scored outcomes yet")).toBeVisible();
});

test("system page renders job history", async ({ page }) => {
  await page.goto("/system");
  await expect(page.getByText("Operational diagnostics and job history")).toBeVisible();
  await expect(page.getByText("snapshot")).toBeVisible();
});

test("market detail page renders without alerts", async ({ page }) => {
  await page.goto("/markets/0x7335fb4a2d4a63565d1cc79a0b3ed4d8170ed6c4c2465c46fd59892e20a31a01");
  await expect(page.getByText("Latest Holders")).toBeVisible();
  await expect(page.getByText("No related alerts")).toBeVisible();
});
