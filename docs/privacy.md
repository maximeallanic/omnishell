# Privacy

Google Hub connects your desktop to Google. This page says exactly what leaves your computer, and what does not.

## What is sent to Google

| When | What | Where |
|---|---|---|
| You type in the GNOME search (from three letters) | The text, to get suggestions | `suggestqueries.google.com`, with your session language |
| You open a result | The page, in your browser | The site of the result |
| Calendar & Tasks are used | Requests with the token of your Google account | `www.googleapis.com/calendar/v3`, `tasks.googleapis.com` |
| You use the drawer | Whatever you do in Gemini | `gemini.google.com`, under Google's terms |

What you type in the search goes to Google's suggestion service as you type, as in a browser's address bar. If you
do not want that, do not install Google Hub: suggestions are part of its purpose and there is no switch for them in
this release.

## What stays on your computer

- **Your voice.** Audio is recorded only while the "Listening…" pill is on screen or Gemini's microphone button is
  active. It is kept in memory, transcribed by `whisper-server` on `127.0.0.1`, and dropped. Only the transcribed text
  is sent, to Gemini, as if you had typed it.
- **Your browser history and bookmarks** are read from a copy of the profile's database in `~/.cache/google-hub/` and
  matched locally. They are never sent anywhere.
- **Your Google credentials.** The access token comes from GNOME Online Accounts and stays in the daemon's memory. The
  Gemini sign-in is a cookie in the drawer's own profile, `~/.local/share/google-hub/webkit/`.
- **Tasks** are cached in `~/.cache/google-hub/tasks.json` so that the clock menu works offline.

Google Hub has no telemetry, no analytics and no server of its own. The only other download is the speech model,
once, from Hugging Face.

## Removing your data

`uninstall.sh --purge` removes the settings, the caches, the model and the drawer's profile (your Gemini sign-in).
Your Google account stays in Settings > Online Accounts until you remove it there.
