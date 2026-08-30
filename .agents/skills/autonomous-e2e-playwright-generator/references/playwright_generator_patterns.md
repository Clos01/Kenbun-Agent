# Playwright Test Generation Patterns & Fixtures

This guide provides test harnesses, authentication state re-use, and execution commands for generated Playwright suites.

---

## 1. Multi-Tenant Auth State Fixture

To avoid logging in before every single test:

```typescript
import { test as base, expect } from '@playwright/test';

export const test = base.extend({
  authenticatedPage: async ({ page }, use) => {
    // 1. Set auth session cookie / local storage
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('carlos@test.com');
    await page.getByLabel(/password/i).fill('TestPassword123!');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL(/.*dashboard/);

    // 2. Use authenticated page across tests
    await use(page);
  },
});
```

---

## 2. Running & Debugging Playwright Suites

```bash
# Run all E2E tests headless
npx playwright test

# Run in UI mode with time-travel debugger
npx playwright test --ui

# View failed trace artifacts
npx playwright show-trace test-results/trace.zip
```
