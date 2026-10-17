import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const config = JSON.parse(readFileSync('/workspace/opencode.json', 'utf8'));
assert.deepEqual(config.mcp.servers.context7, {
  type: 'remote', url: 'https://mcp.context7.com/mcp',
});
assert.equal(process.env.CONTEXT7_API_KEY, undefined);

const result = spawnSync('opencode', [
  'run', '--server', 'http://127.0.0.1:4096', '--format', 'json', '--auto',
  'Use Context7 MCP to resolve the React library ID, then query its documentation for useEffect cleanup. Context7 can be behind Code Mode: use execute and search({query:"context7"}) to discover its tools first. Return and read the resolve result before selecting a library ID for query-docs. Do not substitute remembered docs, web search, or shell calls. Summarize when cleanup runs and cite the returned library ID. Do not modify files.',
], { cwd: '/workspace', encoding: 'utf8', timeout: 150000, maxBuffer: 10 * 1024 * 1024 });
if (result.error) throw result.error;
assert.equal(result.status, 0, 'OpenCode live request must exit successfully');
const events = result.stdout.trim().split('\n').map((line) => JSON.parse(line));
assert.equal(events.some((event) => event.type === 'error'), false);
const completed = events.filter((event) => event.type === 'tool_use' && event.part.state.status === 'completed');
const calls = completed.flatMap((event) => event.part.state.metadata?.metadata?.toolCalls ?? []);
for (const name of ['resolve-library-id', 'query-docs']) {
  const found = calls.some((call) => call.tool === `context7.${name}` && call.status === 'completed')
    || completed.some((event) => event.part.tool === `context7_${name}`);
  assert.ok(found, `Missing successful Context7 ${name} call`);
}
const outputs = completed.map((event) => event.part.state.output).join('\n');
assert.match(outputs, /Source: https:\/\//);
assert.match(outputs, /cleanup/i);
const answer = events.filter((event) => event.type === 'text').map((event) => event.part.text).join('\n');
assert.match(answer, /cleanup/i);
assert.match(answer, /unmount|removed/i);
assert.match(answer, /dependencies/i);
assert.match(answer, /\/(?:reactjs|react|websites)\//);

const headers = { Authorization: `Basic ${Buffer.from(`opencode:${process.env.OPENCODE_SERVER_PASSWORD}`).toString('base64')}` };
const response = await fetch('http://127.0.0.1:4096/api/mcp?location%5Bdirectory%5D=%2Fworkspace', {
  headers, signal: AbortSignal.timeout(45000),
});
assert.equal(response.status, 200);
const status = await response.json();
assert.ok(status.data.some((server) => server.name === 'context7' && server.status.status === 'connected'));
console.log('Context7 connected without API key; resolve-library-id and query-docs completed via OpenCode.');
console.log(answer);
