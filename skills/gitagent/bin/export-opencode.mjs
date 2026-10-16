import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { mcpConfig } from './mcp-config.mjs';

const dir = resolve(process.argv[2] ?? process.cwd());
const root = process.env.OPENGAP_ROOT ?? '/usr/local/lib/node_modules/@open-gitagent/opengap';
const adapter = await import(`${root}/dist/adapters/opencode.js`);
const loader = await import(`${root}/dist/utils/loader.js`);
const manifest = loader.loadAgentManifest(dir);
const preferred = manifest.model?.preferred;
if (typeof preferred !== 'string' || !/^[^:\s]+:.+$/.test(preferred)) {
  throw new Error('agent.yaml requires model.preferred in provider:model format');
}
const separator = preferred.indexOf(':');
const provider = preferred.slice(0, separator);
const model = preferred.slice(separator + 1);
const exported = adapter.exportToOpenCode(dir);
const navigation = join(dir, 'knowledge/index.md');
const content = existsSync(navigation) ? readFileSync(navigation, 'utf8') : '';
const instructions = content && !exported.instructions.includes(content)
  ? `${exported.instructions}\n## OKF navigation\n\n${content}`
  : exported.instructions;
const entry = { name: model, modelID: model };
if (provider === 'openai' && model === 'gpt-6-luna') {
  entry.package = '@opencode/ai/providers/openai/responses';
}
// Retain upstream instructions and translate model/MCP settings into native V2.
const config = {
  $schema: 'https://opencode.ai/config.json',
  model: `${provider}/${model}`,
  providers: { [provider]: { models: { [model]: entry } } },
  mcp: { servers: mcpConfig(exported.config.mcpServers) },
};
writeFileSync(join(dir, 'AGENTS.md'), instructions);
writeFileSync(join(dir, 'opencode.json'), `${JSON.stringify(config, null, 2)}\n`);
console.log(`Exported agent instructions and V2 configuration for ${provider}/${model}`);
