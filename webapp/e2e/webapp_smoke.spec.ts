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
		await expect(page.locator("h1")).toContainText(/Analy/i);
	});

	test("Navigation to Depot Page works", async ({ page }) => {
		await page.goto("/depot");
		await expect(page.locator("h1")).toContainText(/Depot|File/i);
	});

	test("Navigation to Settings Page works", async ({ page }) => {
		await page.goto("/settings");
		await expect(page.locator("h1")).toContainText(/Setting/i);
	});

	test("Navigation to Chat Page works", async ({ page }) => {
		await page.goto("/chat");
		await expect(page.locator('[data-testid="chat-page"]')).toBeVisible();
		await expect(page.locator('[data-testid="chat-input"]')).toBeVisible();
	});

	test("Navigation to Skills Page works", async ({ page }) => {
		await page.goto("/skills");
		await expect(page.locator('[data-testid="skills-page"]')).toBeVisible();
	});

	test("Navigation to Tools Page works", async ({ page }) => {
		await page.goto("/tools");
		await expect(page.locator('[data-testid="tools-page"]')).toBeVisible();
		await expect(page.locator('[data-testid="tools-count"]')).toContainText(/tools/i);
	});

	test("Navigation to Inbox Page works", async ({ page }) => {
		await page.goto("/inbox");
		await expect(page.locator('[data-testid="inbox-page"]')).toBeVisible();
	});
});
