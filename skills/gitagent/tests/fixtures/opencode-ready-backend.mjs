import { createServer } from 'node:http';
import { writeFileSync } from 'node:fs';

const mode = process.env.TEST_MODE;
const port = Number(process.argv.at(-1));
const started = Date.now();
const server = createServer((request, response) => {
  if (mode === 'hang') return;
  if (request.headers.authorization !== `Basic ${Buffer.from('opencode:synthetic-password').toString('base64')}`) {
    response.writeHead(401).end();
    return;
  }
  if (Date.now() - started < 250) {
    response.writeHead(503, { 'retry-after': '1' }).end('{"code":"service_starting"}');
    return;
  }
  if (request.url === '/api/info') return response.end(JSON.stringify({ version: 'synthetic', pid: process.pid }));
  if (request.url.startsWith('/api/integration')) return response.end('{"data":[]}');
  if (request.url.startsWith('/api/agent')) {
    const agents = mode === 'missing' ? [{ id: 'main' }] : [{ id: 'main' }, { id: 'child' }];
    return response.end(JSON.stringify({ data: agents }));
  }
  if (request.url === '/stream') {
    response.writeHead(200, { 'content-type': 'text/event-stream' });
    response.write('data: ready\n\n');
    request.once('close', () => writeFileSync('stream-closed', 'yes'));
    return;
  }
  if (request.url === '/large') return response.end(Buffer.alloc(4 * 1024 * 1024, 120));
  response.end(JSON.stringify({ url: request.url, host: request.headers.host,
    authorization: request.headers.authorization, body: 'unchanged' }));
});
server.on('upgrade', (request, socket, head) => {
  socket.write('HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: synthetic\r\n\r\n');
  if (head.length) socket.write(head);
  socket.pipe(socket);
});
const listen = () => server.listen(port, '127.0.0.1', () => writeFileSync('backend-pid', String(process.pid)));
if (mode === 'delayed') setTimeout(listen, 500);
if (mode !== 'delayed') listen();
if (mode === 'exit') setTimeout(() => process.exit(0), 100);
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => {
  writeFileSync('backend-signal', signal);
  if (mode !== 'stubborn') process.exit(0);
});
