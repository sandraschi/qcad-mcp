import { expect, test } from "@playwright/test";

test.describe("QCAD MCP Webapp Smoke Tests", () => {
	test("Dashboard loads correctly", async ({ page }) => {
		await page.goto("/");
		await expect(page).toHaveTitle(/QCAD MCP|Vite/i);
		await expect(page.locator("h1")).toBeVisible();
	});

	test("Navigation to Viewer Page works", async ({ page }) => {
		await page.goto("/viewer");
		await expect(page.locator("h1")).toContainText(/Viewer/i);
	});

	test("Navigation to Extrude Page works", async ({ page }) => {
		await page.goto("/extrude");
		await expect(page.locator("h1")).toContainText(/Extrus/i);
	});

	test("Navigation to Analyse Page works", async ({ page }) => {
		await page.goto("/analyse");
		await expect(page.locator("h1")).toContainText(/Analyse/i);
	});

	test("Navigation to Depot Page works", async ({ page }) => {
		await page.goto("/depot");
		await expect(page.locator("h1")).toContainText(/Depot|File/i);
	});

	test("Navigation to Settings Page works", async ({ page }) => {
		await page.goto("/settings");
		await expect(page.locator("h1")).toContainText(/Setting/i);
	});
});
