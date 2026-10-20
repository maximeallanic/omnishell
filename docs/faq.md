# FAQ

**Is this an official Google product?**
No. It is an independent open source project, not affiliated with or endorsed by Google. See [NOTICE](../NOTICE.md).

**Do I need a Google Cloud project, an API key or a Gemini API subscription?**
No. Calendar and Tasks use the Google account you add in Settings > Online Accounts. The drawer is the Gemini web app,
with your own account and whatever plan you have.

**Does it work without a Google account?**
Yes, partly: search suggestions, keywords, browser bookmarks and history, the Gemini drawer (as a
signed-out visitor, with what Google allows then) and dictation work. Calendar and Tasks need the account.

**Is my voice sent to Google?**
No. Speech is transcribed on your computer by whisper.cpp; only the resulting text is sent to Gemini. See
[privacy](privacy.md).

**Which languages does it speak?**
Any language your session uses for dates and Google; the interface is translated into English and French so far;
dictation understands the 99 languages of Whisper's multilingual models. See
[configuration](configuration.md#language). Translations are welcome.

**Why does it need a background service?**
A GNOME Shell extension runs inside the Shell: slow network calls, audio capture or speech recognition there would
freeze the desktop. The daemon does that work in its own process.

**Can I install only the extension from extensions.gnome.org?**
Not yet. The search results, Calendar, Tasks and dictation come from the daemon and the drawer is a separate program,
which only `install.sh` installs. See [installation](installation.md#extensionsgnomeorg).

**Does it work on X11, GNOME 49 or older, KDE?**
No: GNOME Shell 50 or 51 on Wayland only.

**Can I use another browser than Chrome for the history?**
Any Chromium-based browser: set `chrome_dir` in `config.json`. Firefox is not supported.

**Can the drawer show something else than Gemini?**
The `panel-url` setting loads another address, but Omnishell's "Ask" only knows Gemini's page.

**Does it use my GPU?**
Only for dictation, if whisper.cpp was built with a GPU backend (Vulkan with `--vulkan` on Debian and Ubuntu).
