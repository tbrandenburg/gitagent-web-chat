"""No-inference admission check shared by private bootstrap and HTTPS verification."""
import base64
import http.client
import os
import re
import time
import urllib.parse


def verify(origin: str, wait: bool = False) -> None:
    url = urllib.parse.urlsplit(origin)
    if (url.scheme not in {'http', 'https'} or not url.hostname or url.username
            or url.password or url.path or url.query or url.fragment):
        raise ValueError('Invalid gateway origin')
    password = os.environ['OPENCODE_SERVER_PASSWORD']
    authorization = 'Basic ' + base64.b64encode(('opencode:' + password).encode()).decode()

    def request(path: str, auth: str | None = None) -> tuple[int, bytes]:
        connection = (http.client.HTTPSConnection if url.scheme == 'https'
                      else http.client.HTTPConnection)(url.hostname, url.port, timeout=3)
        try:
            connection.request('GET', path, headers={'Authorization': auth} if auth else {})
            response = connection.getresponse()
            return response.status, response.read(2_000_000)
        finally:
            connection.close()

    deadline = time.monotonic() + (95 if wait else 0)
    while True:
        try:
            status, _ = request('/')
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeError('Gateway did not become ready') from None
            time.sleep(0.2)
    if status != 401:
        raise RuntimeError('Gateway root is not protected')
    status, html = request('/', authorization)
    if status != 200:
        raise RuntimeError('Gateway rejected selected credentials')
    assets = re.findall(rb'(?:src|href)="(/[^"<>]+\.(?:js|css))"', html)
    if not assets:
        raise RuntimeError('No native UI assets discovered')
    paths = ['/', assets[0].decode(), '/api/info', '/api/event', '/api/pty', '/api/pty/test/connect?ticket=fixture']
    wrong = 'Basic ' + base64.b64encode(b'opencode:incorrect-fixture').decode()
    for path in paths:
        if request(path)[0] != 401 or request(path, wrong)[0] != 401:
            raise RuntimeError('Unauthenticated gateway path admitted')
    if request('/api/info', authorization)[0] != 200 or request(assets[0].decode(), authorization)[0] != 200:
        raise RuntimeError('Native API or UI asset unavailable')


if __name__ == '__main__':
    try:
        verify('http://127.0.0.1:8080', wait=True)
    except (OSError, ValueError, KeyError, RuntimeError, http.client.HTTPException):
        raise SystemExit('Sandbox gateway admission check failed') from None
