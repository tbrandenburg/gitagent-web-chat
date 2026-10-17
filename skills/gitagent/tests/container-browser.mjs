// Optional real Chromium smoke check. No model prompt, mocked response, or terminal.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ?? 'playwright');

const runtime = process.env.FEASIBILITY_RUNTIME;
const base = process.env.FEASIBILITY_BASE;
assert.ok(['gitagent', 'opencode'].includes(runtime));
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
const browser = await chromium.launch({ headless: true });
const failures = [];
const httpFailures = [];
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const authorization = 'Basic ' + Buffer.from('opencode:' + process.env.OPENCODE_SERVER_PASSWORD).toString('base64');
  // Keep browser probes offline except for the isolated server. No canned responses.
  await context.route('**/*', route => {
    if (!route.request().url().startsWith(base + '/')) return route.abort();
    const headers = route.request().headers();
    return route.continue({ headers: runtime === 'opencode' ? { ...headers, authorization } : headers });
  });
  const page = await context.newPage();
  const events = [];
  page.on('pageerror', error => failures.push(error.message));
  page.on('response', response => {
    if (response.status() >= 400) httpFailures.push(`${response.status()} ${new URL(response.url()).pathname}`);
  });
  page.on('websocket', socket => socket.on('framereceived', frame => {
    try { events.push(JSON.parse(frame.payload.toString()).type); }
    catch { events.push('non-json'); }
  }));
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
  if (runtime === 'gitagent') {
    await page.getByPlaceholder('Username', { exact: true }).fill('feasibility');
    await page.getByPlaceholder('Password', { exact: true }).fill('incorrect');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.getByText('Incorrect username or password', { exact: true }).waitFor();
    await page.getByPlaceholder('Password', { exact: true }).fill(process.env.GITAGENT_PASSWORD);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('#pw'));
    await page.getByText('Text chat ready.', { exact: false }).first().waitFor({ timeout: 20000 });
    assert.ok(events.includes('transcript'));
  } else {
    await page.waitForFunction(() => document.body.innerText.trim().length > 0, { timeout: 30000 });
    await page.locator('button').first().waitFor();
    assert.match(await page.title(), /OpenCode/);
    await page.getByText('Add project', { exact: true }).click();
    const picker = page.getByRole('dialog');
    await picker.waitFor();
    assert.equal(await picker.locator('input').inputValue(), '/tmp/workspace');
    await picker.getByRole('button', { name: 'Select folder', exact: true }).click();
    await picker.waitFor({ state: 'hidden' });
    await page.getByText('workspace', { exact: true }).first().waitFor();
  }
  await mkdir('.playwright-mcp', { recursive: true });
  await page.screenshot({ path: `.playwright-mcp/${runtime}-feasibility.png`, fullPage: true });
  console.log(`${runtime}: real Chromium upstream UI rendered; page errors=${failures.length}; no model prompt submitted`);
  assert.equal(failures.length, 0, 'Browser page errors');
} catch (error) {
  console.error(`${runtime}: browser page errors=${failures.length}; HTTP errors=${JSON.stringify(httpFailures)}`);
  const pages = browser.contexts().flatMap(context => context.pages());
  await mkdir('.playwright-mcp', { recursive: true });
  for (const page of pages) {
    await page.screenshot({ path: `.playwright-mcp/${runtime}-feasibility-failed.png`, fullPage: true });
    console.error(`${runtime}: browser diagnostic title=${await page.title()}; body length=${(await page.locator('body').innerText()).length}`);
  }
  throw error;
} finally {
  await browser.close();
}
