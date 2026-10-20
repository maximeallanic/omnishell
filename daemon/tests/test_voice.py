import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from google_hub.text import normalize
from google_hub.voice import CaptureError, Endpointer, Listener, WavSource, pcm_to_wav
from google_hub.whisper import TranscribeError, WhisperServer, audio_ctx_for, wav_duration

FIXTURES = Path(__file__).with_name("fixtures")
# Model installed by install.sh; GOOGLE_HUB_WHISPER_MODEL points the real-Whisper tests at another file.
MODEL = Path(os.environ.get("GOOGLE_HUB_WHISPER_MODEL")
             or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "google-hub/models/ggml-small.bin")
PHRASE = "bonjour, quel temps fera-t-il demain matin à Paris"


def frames(seq):
    return [rms for rms, n in seq for _ in range(n)]


def feed_all(ep, values):
    for i, v in enumerate(values, 1):
        r = ep.feed(v)
        if r:
            return r, i
    return None, len(values)


def frame_bytes(amplitude):
    return struct.pack("<320h", *([amplitude, -amplitude] * 160))


class FakeSource:
    def __init__(self, amplitudes, fail_after=None, pace=0.0):
        self.amplitudes = amplitudes
        self.fail_after = fail_after
        self.pace = pace
        self.closed = False

    def frames(self):
        for i, a in enumerate(self.amplitudes):
            if self.fail_after is not None and i >= self.fail_after:
                raise CaptureError("micro parti")
            if self.pace:
                time.sleep(self.pace)
            yield frame_bytes(a)

    def close(self):
        self.closed = True


class TestEndpointer(unittest.TestCase):
    def test_end_after_1s_silence(self):
        ep = Endpointer()
        self.assertEqual(feed_all(ep, frames([(100, 15), (3000, 50), (100, 49)])), (None, 114))
        self.assertEqual(ep.feed(100), "end")

    def test_short_blip_is_not_speech(self):
        self.assertEqual(feed_all(Endpointer(), frames([(100, 15), (3000, 2), (100, 300)])), ("nospeech", 250))

    def test_max_30s(self):
        self.assertEqual(feed_all(Endpointer(), frames([(100, 15), (3000, 2000)])), ("max", 1500))

    def test_noisy_room(self):
        self.assertEqual(feed_all(Endpointer(), frames([(1500, 15), (3000, 300)])), ("nospeech", 250))
        self.assertEqual(feed_all(Endpointer(), frames([(1500, 15), (6000, 20), (1500, 60)])), ("end", 85))


class TestListener(unittest.TestCase):
    def setUp(self):
        self.states = []
        self.calls = []

    def transcriber(self, wav):
        self.calls.append(wav)
        return "bonjour"

    def listener(self, source):
        self.source = source
        return Listener(lambda: source, self.transcriber, lambda s, l: self.states.append((s, l)))

    def test_states_and_text(self):
        l = self.listener(FakeSource([100] * 15 + [3000] * 50 + [100] * 60))
        self.assertEqual(l.listen(), "bonjour")
        names = [s for s, _ in self.states]
        self.assertEqual(names[0], "listening")
        self.assertEqual(names[-2:], ["transcribing", "idle"])
        self.assertTrue(any(s == "listening" and lvl > 0.3 for s, lvl in self.states))
        self.assertTrue(all(0 <= lvl <= 1 for _, lvl in self.states))
        self.assertTrue(self.calls[0].startswith(b"RIFF"))
        self.assertTrue(self.source.closed)

    def test_nospeech_returns_empty(self):
        l = self.listener(FakeSource([100] * 400))
        self.assertEqual(l.listen(), "")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.states[-1][0], "idle")

    def test_cancel(self):
        l = self.listener(FakeSource([100] * 15 + [3000] * 1000, pace=0.002))
        threading.Timer(0.1, l.cancel).start()
        self.assertEqual(l.listen(), "")
        self.assertEqual(self.calls, [])

    def test_cancel_before_listen_starts(self):
        l = self.listener(FakeSource([100] * 15 + [3000] * 50 + [100] * 60))
        l.cancel()
        self.assertEqual(l.listen(), "")
        self.assertEqual(self.calls, [])

    def test_cancel_during_transcription(self):
        l = None

        def slow(wav):
            l.cancel()
            return "bonjour"
        src = FakeSource([100] * 15 + [3000] * 50 + [100] * 60)
        l = Listener(lambda: src, slow, lambda st, lv: self.states.append((st, lv)))
        self.assertEqual(l.listen(), "")
        self.assertEqual(self.states[-1][0], "idle")

    def test_stop_transcribes_early(self):
        l = self.listener(FakeSource([100] * 15 + [3000] * 1000, pace=0.002))
        threading.Timer(0.15, l.stop).start()
        t0 = time.monotonic()
        self.assertEqual(l.listen(), "bonjour")
        self.assertLess(time.monotonic() - t0, 1.0)

    def test_stop_before_speech_skips_transcription(self):
        l = self.listener(FakeSource([100] * 1000, pace=0.002))
        threading.Timer(0.1, l.stop).start()
        self.assertEqual(l.listen(), "")
        self.assertEqual(self.calls, [])

    def test_state_rate_limited(self):
        l = self.listener(FakeSource([100] * 15 + [3000] * 50 + [100] * 60))
        l.listen()
        # one state every 4 frames of 20 ms = 12.5/s in real time (at most 15/s)
        self.assertLessEqual(sum(1 for s, _ in self.states if s == "listening"), 125 // 4 + 1)

    def test_source_failure(self):
        l = self.listener(FakeSource([3000] * 100, fail_after=5))
        with self.assertRaises(CaptureError):
            l.listen()
        self.assertEqual(self.states[-1], ("error:audio-capture", 0))
        self.assertTrue(self.source.closed)

    def test_transcribe_failure(self):
        def bad(_):
            raise TranscribeError("down")
        src = FakeSource([100] * 15 + [3000] * 50 + [100] * 60)
        l = Listener(lambda: src, bad, lambda s, lvl: self.states.append((s, lvl)))
        with self.assertRaises(TranscribeError):
            l.listen()
        self.assertEqual(self.states[-1], ("error:network", 0))

    def test_wav_roundtrip(self):
        pcm = frame_bytes(1000) * 10
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "x.wav")
            p.write_bytes(pcm_to_wav(pcm))
            got = b"".join(WavSource(p).frames())
        self.assertEqual(got, pcm)


class TestAudioCtx(unittest.TestCase):
    def test_audio_ctx_scales_with_duration(self):
        self.assertEqual(audio_ctx_for(2.66), 512)    # floor (quality drops below it)
        self.assertEqual(audio_ctx_for(10), 750)      # 50 frames/s + a margin of 250
        self.assertEqual(audio_ctx_for(28), 1500)     # capped at the 30 s window
        self.assertEqual(audio_ctx_for(40), 1500)

    def test_wav_duration(self):
        self.assertAlmostEqual(wav_duration(pcm_to_wav(b"\0\0" * 16000 * 3)), 3.0)
        self.assertEqual(wav_duration(b"not a wav"), 30.0)


def ensure_fixture():
    wav = FIXTURES / "speech.wav"
    if wav.exists():
        return wav
    if not (shutil.which("espeak-ng") and shutil.which("gst-launch-1.0")):
        return None
    FIXTURES.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d, "raw.wav")
        subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-w", str(raw), PHRASE], check=True)
        subprocess.run(["gst-launch-1.0", "-q", "filesrc", f"location={raw}", "!", "wavparse", "!",
                        "audioconvert", "!", "audioresample", "!",
                        "audio/x-raw,rate=16000,channels=1,format=S16LE", "!", "wavenc", "!",
                        "filesink", f"location={wav}"], check=True)
    return wav


@unittest.skipUnless(shutil.which("whisper-server") and MODEL.exists(), "whisper.cpp or model missing")
class TestWhisperReal(unittest.TestCase):
    def test_french_sentence(self):
        wav = ensure_fixture()
        if wav is None:
            self.skipTest("espeak-ng missing")
        server = WhisperServer(MODEL)
        try:
            text = server.transcribe(wav.read_bytes())
        finally:
            server.close()
        expected = normalize(PHRASE).replace(",", "").split()
        got = normalize(text).replace(",", "").replace("?", "").split()
        self.assertGreaterEqual(sum(1 for w in expected if w in got), 6, text)

    def test_idle_shutdown(self):
        wav = ensure_fixture()
        if wav is None:
            self.skipTest("espeak-ng missing")
        server = WhisperServer(MODEL, idle_s=1)
        try:
            server.transcribe(wav.read_bytes())
            self.assertTrue(server.running)
            time.sleep(2.5)
            self.assertFalse(server.running)
        finally:
            server.close()
