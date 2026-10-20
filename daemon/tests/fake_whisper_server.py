"""Fake whisper-server for tests: same command line, answers /inference with a recorded response.

FAKE_WHISPER_RESPONSE  path of the JSON body to return
FAKE_WHISPER_LOG       path where the form fields of each request are appended (JSON lines)
"""
import argparse
import email.parser
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


def form_fields(content_type: str, body: bytes) -> dict:
    message = email.parser.BytesParser().parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + body)
    return {part.get_param("name", header="content-disposition"):
            (part.get_payload(decode=True).decode() if part.get_filename() is None
             else f"<{len(part.get_payload(decode=True))} bytes>")
            for part in message.get_payload()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _reply(self, data: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._reply(b"{}")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        with open(os.environ["FAKE_WHISPER_LOG"], "a", encoding="utf-8") as log:
            log.write(json.dumps(form_fields(self.headers["Content-Type"], body)) + "\n")
        with open(os.environ["FAKE_WHISPER_RESPONSE"], "rb") as response:
            self._reply(response.read())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args, _ = parser.parse_known_args()
    HTTPServer((args.host, args.port), Handler).serve_forever()
