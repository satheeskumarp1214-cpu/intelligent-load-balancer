from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import sys

port = int(sys.argv[1])

server = ThreadingHTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)

print(f"HTTP server running on port {port}", flush=True)

server.serve_forever()
