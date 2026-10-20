import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from google_hub.whisper import WhisperServer, default_threads

TESTS = Path(__file__).parent


class TestTranscribeRequest(unittest.TestCase):
    """transcribe() against a fake whisper-server started exactly like the real one (same command line)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        self.model = tmp / "model.bin"
        self.model.write_bytes(b"")
        self.binary = tmp / "whisper-server"
        self.binary.write_text(f"#!/bin/sh\nexec {sys.executable} {TESTS / 'fake_whisper_server.py'} \"$@\"\n")
        self.binary.chmod(0o755)
        self.log = tmp / "requests.jsonl"
        self.response = tmp / "response.json"
        self.response.write_text(json.dumps({"text": "  hello \n world  "}))
        patcher = mock.patch.dict(os.environ, {"FAKE_WHISPER_LOG": str(self.log),
                                               "FAKE_WHISPER_RESPONSE": str(self.response)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.server = WhisperServer(self.model, language="fr", binary=str(self.binary))
        self.addCleanup(self.server.close)

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_text_is_collapsed(self):
        self.assertEqual(self.server.transcribe(b"RIFF fake wav"), "hello world")

    def test_plain_transcribe_keeps_server_language(self):
        self.server.transcribe(b"RIFF fake wav")
        (fields,) = self.requests()
        self.assertEqual(fields["response_format"], "json")
        self.assertNotIn("language", fields)
        self.assertEqual(fields["file"], "<13 bytes>")


class TestThreads(unittest.TestCase):
    def test_default_threads_bounded(self):
        for cpus, expected in ((None, 4), (1, 1), (4, 4), (16, 8)):
            with self.subTest(cpus=cpus), mock.patch("os.cpu_count", return_value=cpus):
                self.assertEqual(default_threads(), expected)

    def test_zero_means_default(self):
        with mock.patch("os.cpu_count", return_value=2):
            self.assertEqual(WhisperServer(Path("m.bin"), threads=0).threads, 2)
            self.assertEqual(WhisperServer(Path("m.bin"), threads=3).threads, 3)


if __name__ == "__main__":
    unittest.main()
