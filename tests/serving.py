"""A server of the tests: started in a thread on a free port, and stopped at once (serve_forever looks for a
shutdown every half second by default, half a second lost by each test)."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@contextmanager
def serving(handler: type[BaseHTTPRequestHandler]) -> Iterator[str]:
    """The server's address while the block runs."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
