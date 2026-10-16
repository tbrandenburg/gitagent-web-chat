// Translate OpenGAP's MCP export into native OpenCode V2 configuration.
const expand = (value) => value.replace(/\$\{([A-Za-z_][A-Za-z0-9_]*)\}/g, '{env:$1}');
const variables = (values) => Object.fromEntries(
  Object.entries(values).map(([name, value]) => [name, expand(value)]),
);

export function mcpConfig(servers = {}) {
  return Object.fromEntries(Object.entries(servers).map(([name, server]) => {
    const remote = typeof server.url === 'string' && server.url.length > 0;
    const local = typeof server.command === 'string' && server.command.length > 0;
    if (remote === local) {
      throw new Error(`MCP server ${name} requires exactly one of url or command`);
    }
    if (remote) {
      const config = { type: 'remote', url: expand(server.url) };
      if (server.headers) config.headers = variables(server.headers);
      return [name, config];
    }
    const config = { type: 'local', command: [server.command, ...(server.args ?? [])].map(expand) };
    if (server.env) config.environment = variables(server.env);
    return [name, config];
  }));
}
