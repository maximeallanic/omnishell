# Notices

Google Hub is released under the [MIT licence](LICENSE), Copyright (c) 2026 Maxime Allanic.

## Not affiliated with Google

Google Hub is an independent project. It is not made, endorsed or supported by Google. Google, Gemini, Google
Calendar, Google Tasks, Google Drive, Google Maps, YouTube and Chrome are trademarks of Google LLC; they are named here
only to say what the software works with. The drawer shows the real Gemini web application
(`https://gemini.google.com`), subject to Google's terms and privacy policy. The icons shipped in
`extension/google-hub@maximeallanic.github.io/icons/` are drawn for this project; they are not Google logos.

## Vendored code

| What | Where | Origin | Licence |
|---|---|---|---|
| M3E motion toolkit (spring animations, motion tokens) | `extension/google-hub@maximeallanic.github.io/m3e/` | [m3e-gnome-extensions](https://github.com/maximeallanic/m3e-gnome-extensions) `shared/m3e/`, commit `9f8f5f47866e619a876522a75a16146b721157bb` (last change to `shared/m3e/` in `499375f350ae26d0a573039bfa28b76780049a41`), files unchanged | MIT, Copyright (c) 2026 Maxime Allanic |

GNOME Shell extensions cannot import modules from one another, so each extension that uses the toolkit embeds a
copy of it, as the toolkit's own README asks. To update it, copy `shared/m3e/{animate,curve,spring,tokens,track}.js`
from a newer commit and update the commit above.

## Downloaded at install time

| What | From | Checked with | Licence |
|---|---|---|---|
| Whisper speech model `ggml-small.bin` (about 466 MB, optional) | `https://huggingface.co/ggerganov/whisper.cpp` | SHA-1 `55356645c2b361a969dfd0ef2c5a50d530afd8d5`, from whisper.cpp's `models/README.md` | MIT (OpenAI Whisper weights, converted by the whisper.cpp project) |

## Used at run time, not shipped

whisper.cpp (`whisper-server`, MIT), GNOME Shell, GJS, GLib, GTK 4, libadwaita, WebKitGTK, GStreamer, PyGObject,
dateparser (BSD-3-Clause) and Babel (BSD-3-Clause) come from your distribution.
