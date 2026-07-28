# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: e2e.spec.ts >> E2E Suite >> App loads successfully and redirects to sign-in
- Location: tests\e2e.spec.ts:4:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.goto: Test timeout of 30000ms exceeded.
Call log:
  - navigating to "http://localhost:3000/", waiting until "load"

```

# Page snapshot

```yaml
- generic [active]:
  - alert [ref=e1]
  - dialog [ref=e4]:
    - generic [ref=e5]:
      - generic [ref=e6]:
        - navigation [ref=e8]:
          - button "previous" [disabled] [ref=e9]:
            - img "previous" [ref=e10]
          - button "next" [disabled] [ref=e12]:
            - img "next" [ref=e13]
          - generic [ref=e15]: 1 of 1 error
          - generic [ref=e16]:
            - text: Next.js (14.2.35) is outdated
            - link "(learn more)" [ref=e18] [cursor=pointer]:
              - /url: https://nextjs.org/docs/messages/version-staleness
        - heading "Server Error" [level=1] [ref=e19]
        - paragraph [ref=e20]: "Error: Publishable key not valid."
        - generic [ref=e21]: This error happened while generating the page. Any console logs will be displayed in the terminal window.
      - generic [ref=e22]:
        - heading "Call Stack" [level=2] [ref=e23]
        - generic [ref=e24]:
          - heading "parsePublishableKey" [level=3] [ref=e25]
          - generic [ref=e26]: node_modules\@clerk\shared\dist\keys.mjs (84:1)
        - generic [ref=e28]:
          - heading "assertValidPublishableKey" [level=3] [ref=e29]
          - generic [ref=e30]: node_modules\@clerk\backend\dist\chunk-QJHUZO3A.mjs (475:22)
        - generic [ref=e32]:
          - heading "AuthenticateContext.initPublishableKeyValues" [level=3] [ref=e33]
          - generic [ref=e34]: node_modules\@clerk\backend\dist\chunk-QJHUZO3A.mjs (619:1)
        - generic [ref=e36]:
          - heading "new AuthenticateContext" [level=3] [ref=e37]
          - generic [ref=e38]: node_modules\@clerk\backend\dist\chunk-QJHUZO3A.mjs (512:1)
        - generic [ref=e40]:
          - heading "createAuthenticateContext" [level=3] [ref=e41]
          - generic [ref=e42]: node_modules\@clerk\backend\dist\chunk-QJHUZO3A.mjs (718:1)
        - generic [ref=e44]:
          - heading "async authenticateRequest" [level=3] [ref=e45]
          - generic [ref=e46]: node_modules\@clerk\backend\dist\chunk-QJHUZO3A.mjs (6943:1)
        - generic [ref=e48]:
          - heading "async eval" [level=3] [ref=e49]
          - generic [ref=e50]: node_modules\@clerk\nextjs\dist\esm\server\clerkMiddleware.js (114:1)
        - group [ref=e52]:
          - generic "Next.js" [ref=e53] [cursor=pointer]
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('E2E Suite', () => {
  4  |   test('App loads successfully and redirects to sign-in', async ({ page }) => {
> 5  |     await page.goto('/');
     |                ^ Error: page.goto: Test timeout of 30000ms exceeded.
  6  |     // Since we don't have Clerk testing tokens, we expect to be redirected to Clerk sign-in
  7  |     await expect(page).toHaveURL(/.*sign-in.*/);
  8  |   });
  9  | });
  10 | 
```