import { defineConfig } from '@playwright/test';
export default defineConfig({
    testDir: './e2e', timeout: 60000, retries: 1,
    use: { baseURL: 'http://localhost:10967', headless: true, screenshot: 'only-on-failure' },
    webServer: {
        command: 'uv run python -m qcad_mcp.server --port 10966',
        port: 10966, timeout: 30000, reuseExistingServer: false
    }
});
