import { defineConfig } from "@playwright/test";
export default defineConfig({
	testDir: "./e2e",
	timeout: 60000,
	retries: 1,
	use: {
		baseURL: "http://localhost:11967",
		headless: true,
		screenshot: "only-on-failure",
	},
	webServer: [
		{
			command: "uv run python -m qcad_mcp.server --mode http --port 11966",
			port: 11966,
			timeout: 60000,
			reuseExistingServer: false,
		},
		{
			// BUN_EXE override for machines where bun is off-PATH (fleet standard
			// location: %USERPROFILE%\.bun\bin\bun.exe). CI provides bun on PATH.
			command: `${process.env.BUN_EXE ?? "bun"} run preview -- --port 11967 --strictPort --host 127.0.0.1`,
			port: 11967,
			timeout: 60000,
			reuseExistingServer: false,
		},
	],
});
