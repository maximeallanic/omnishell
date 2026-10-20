"""Microphone capture, end-of-utterance detection and a complete listen (capture, then transcription)."""
import io
import math
import threading
import wave
from array import array
from pathlib import Path

FRAME_BYTES = 640  # 20 ms, 16 kHz, mono, S16LE
RATE = 16000
MAX_CAPTURE_MS = 30000  # longest dictation, then the endpointer cuts
FIRST_SAMPLE_S = 2  # PipeWire may take this long to deliver the first buffer
NEXT_SAMPLE_S = 1  # a later gap this long means the microphone stopped
# Worst case of the capture phase of Listener.listen(), in wall-clock seconds.
CAPTURE_BUDGET_S = MAX_CAPTURE_MS / 1000 + FIRST_SAMPLE_S


class CaptureError(Exception):
    pass


def rms(frame: bytes) -> float:
    a = array("h", frame)
    return math.sqrt(sum(x * x for x in a) / len(a)) if a else 0.0


def pcm_to_wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


class Endpointer:
    def __init__(self, frame_ms=20, silence_ms=1000, max_ms=MAX_CAPTURE_MS, nospeech_ms=5000, calib_ms=300):
        self.calib_n = calib_ms // frame_ms
        self.silence_n = silence_ms // frame_ms
        self.max_n = max_ms // frame_ms
        self.nospeech_n = nospeech_ms // frame_ms
        self.n = 0
        self.calib = []
        self.threshold = None
        self.run = 0
        self.silence = 0
        self.speech = False

    def feed(self, value: float) -> str | None:
        self.n += 1
        if self.threshold is None:
            self.calib.append(value)
            if len(self.calib) >= self.calib_n:
                floor = sorted(self.calib)[len(self.calib) // 2]
                self.threshold = max(3 * floor, 500)
            return None
        loud = value > self.threshold
        if not self.speech:
            self.run = self.run + 1 if loud else 0
            if self.run >= 3:
                self.speech = True
            elif self.n >= self.nospeech_n:
                return "nospeech"
        else:
            self.silence = 0 if loud else self.silence + 1
            if self.silence >= self.silence_n:
                return "end"
        if self.n >= self.max_n:
            return "max"
        return None

    @property
    def heard_speech(self) -> bool:
        return self.speech


class WavSource:
    def __init__(self, path: Path):
        self.path = Path(path)

    def frames(self):
        with wave.open(str(self.path), "rb") as w:
            while chunk := w.readframes(FRAME_BYTES // 2):
                yield chunk

    def close(self):
        pass


class MicSource:
    """Default microphone through PipeWire, 16 kHz mono S16LE, 20 ms frames."""

    PIPELINE = ("pipewiresrc ! audioconvert ! audioresample ! "
                "audio/x-raw,format=S16LE,rate=16000,channels=1 ! appsink name=sink sync=false")

    def __init__(self):
        import gi
        gi.require_version("Gst", "1.0")
        gi.require_version("GstApp", "1.0")
        from gi.repository import Gst, GstApp  # noqa: F401  (GstApp: appsink methods)
        Gst.init(None)
        self.Gst = Gst
        try:
            self.pipeline = Gst.parse_launch(self.PIPELINE)
        except Exception as e:  # GLib.Error
            raise CaptureError(str(e)) from None
        self.sink = self.pipeline.get_by_name("sink")
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            self.close()
            raise CaptureError("the capture pipeline was refused")

    def _check_bus(self):
        msg = self.pipeline.get_bus().pop_filtered(self.Gst.MessageType.ERROR)
        if msg:
            err, _ = msg.parse_error()
            raise CaptureError(err.message)

    def frames(self):
        buf = b""
        first = True
        while True:
            self._check_bus()
            sample = self.sink.try_pull_sample((FIRST_SAMPLE_S if first else NEXT_SAMPLE_S) * self.Gst.SECOND)
            if sample is None:
                self._check_bus()
                raise CaptureError("no sound received from the microphone")
            first = False
            b = sample.get_buffer()
            buf += b.extract_dup(0, b.get_size())
            while len(buf) >= FRAME_BYTES:
                yield buf[:FRAME_BYTES]
                buf = buf[FRAME_BYTES:]

    def close(self):
        self.pipeline.set_state(self.Gst.State.NULL)


class Listener:
    LEVEL_EVERY = 4  # frames: 12.5 states per second in real time

    def __init__(self, source_factory, transcriber, on_state):
        self.source_factory = source_factory
        self.transcriber = transcriber
        self.on_state = on_state
        self._stop = threading.Event()
        self._cancel = threading.Event()

    def stop(self):
        self._stop.set()

    def cancel(self):
        self._cancel.set()

    def listen(self) -> str:
        from .whisper import TranscribeError
        if self._cancel.is_set():  # Escape arrived before listening started
            self.on_state("idle", 0)
            return ""
        self.on_state("listening", 0.0)
        ep = Endpointer()
        pcm = bytearray()
        try:
            src = self.source_factory()
        except CaptureError:
            self.on_state("error:audio-capture", 0)
            raise
        try:
            for i, frame in enumerate(src.frames()):
                if self._cancel.is_set():
                    self.on_state("idle", 0)
                    return ""
                level = rms(frame)
                pcm += frame
                if i % self.LEVEL_EVERY == 0:
                    self.on_state("listening", min(1.0, level / 8000))
                if self._stop.is_set():
                    break
                r = ep.feed(level)
                if r == "nospeech":
                    self.on_state("idle", 0)
                    return ""
                if r:
                    break
        except CaptureError:
            self.on_state("error:audio-capture", 0)
            raise
        finally:
            src.close()
        if self._cancel.is_set() or not ep.heard_speech:
            self.on_state("idle", 0)
            return ""
        self.on_state("transcribing", 0)
        try:
            text = self.transcriber(pcm_to_wav(bytes(pcm)))
        except TranscribeError:
            self.on_state("error:network", 0)
            raise
        self.on_state("idle", 0)
        return "" if self._cancel.is_set() else text
