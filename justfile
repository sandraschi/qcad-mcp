
# ── Playwright E2E ─────────────────────────────────────────────────────

# Install Playwright browsers (one-time)
e2e-install:
    cd {{REPO}}\webapp
    npx playwright install chromium

# Run Playwright E2E smoke tests (start backend first: just serve)
e2e:
    cd {{REPO}}\webapp
    npx playwright test

