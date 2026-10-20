"""whisper-server (whisper.cpp) as a child process, started on demand, stopped when idle."""
import io
import json
import logging
import math
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

log = logging.getLogger(__name__)

START_TIMEOUT_S = 10  # a freshly spawned whisper-server must answer within this
PROBE_TIMEOUT_S = 1  # one readiness probe; the last one may start just before START_TIMEOUT_S
KILL_GRACE_S = 3  # SIGTERM → wait before SIGKILL
INFERENCE_TIMEOUT_S = 60
# Worst case of transcribe(): a cold start that only just succeeds, then an inference that times out
# and kills the server. Listen's client timeout is derived from it (service.LISTEN_TIMEOUT_MS).
TRANSCRIBE_BUDGET_S = START_TIMEOUT_S + PROBE_TIMEOUT_S + INFERENCE_TIMEOUT_S + KILL_GRACE_S


class TranscribeError(Exception):
    pass


def wav_duration(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError):
        return 30.0


def audio_ctx_for(duration_s: float) -> int:
    """Whisper audio context (1500 = 30 s) fitted to the real duration: encoding is about 4 times faster."""
    return min(1500, max(512, math.ceil(duration_s * 50) + 250))


def default_threads() -> int:
    """CPU threads for whisper-server: every CPU up to 8 (more brings little to the small model)."""
    return max(1, min(8, os.cpu_count() or 4))


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class WhisperServer:
    def __init__(self, model: Path, language="auto", idle_s=900, binary="whisper-server", threads=0):
        self.model = Path(os.path.expanduser(str(model)))
        self.language = language
        self.idle_s = idle_s
        self.binary = binary
        self.threads = threads or default_threads()
        self.proc = None
        self.port = None
        self._lock = threading.Lock()
        self._timer = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _start(self):
        if not self.model.exists():
            raise TranscribeError(f"model missing: {self.model}")
        self.port = _free_port()
        try:
            self.proc = subprocess.Popen(
                [self.binary, "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.port),
                 "-l", self.language, "-t", str(self.threads)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            raise TranscribeError(str(e)) from None
        deadline = time.monotonic() + START_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=PROBE_TIMEOUT_S) as r:
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)
        self._kill()
        raise TranscribeError("whisper-server did not start")

    def _kill(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            p.send_signal(signal.SIGTERM)
            try:
                p.wait(KILL_GRACE_S)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()

    def _arm_idle(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.idle_s, self._idle)
        self._timer.daemon = True
        self._timer.start()

    def _idle(self):
        with self._lock:
            self._kill()

    def _inference(self, wav_bytes: bytes, fields: tuple, timeout: float) -> dict:
        """POST wav_bytes and the form fields to /inference, starting the server if needed."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
            if not self.running:
                self._start()
            boundary = uuid.uuid4().hex
            parts = []
            for name, value in fields:
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                             f"{value}\r\n".encode())
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.wav"\r\n'
                         f"Content-Type: audio/wav\r\n\r\n".encode() + wav_bytes + b"\r\n")
            parts.append(f"--{boundary}--\r\n".encode())
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/inference", data=b"".join(parts),
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read())
            except (urllib.error.URLError, OSError, ValueError) as e:
                self._kill()
                raise TranscribeError(str(e)) from None
            finally:
                self._arm_idle()

    def transcribe(self, wav_bytes: bytes) -> str:
        fields = (("response_format", "json"), ("temperature", "0"),
                  ("audio_ctx", str(audio_ctx_for(wav_duration(wav_bytes)))))
        text = self._inference(wav_bytes, fields, timeout=INFERENCE_TIMEOUT_S).get("text", "")
        return " ".join(text.split())

    def close(self):
        if self._timer:
            self._timer.cancel()
        with self._lock:
            self._kill()
