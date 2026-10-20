# Privacy

Omnishell connects your desktop to Google. This page says exactly what leaves your computer, and what does not.

## What is sent to Google

| When | What | Where |
|---|---|---|
| You type in the GNOME search (from three letters), while **Google suggestions** is on (the default) | The text, to get suggestions | `suggestqueries.google.com`, with your session language |
| You open a result | The page, in your browser | The site of the result |
| Calendar & Tasks are used | Requests with the token of your Google account | `www.googleapis.com/calendar/v3`, `tasks.googleapis.com` |
| You use the drawer | Whatever you do in Gemini | `gemini.google.com`, under Google's terms |

What you type in the search goes to Google's suggestion service as you type, as in a browser's address bar. To stop
it, open the extension's preferences (Extensions app, or `gnome-extensions prefs omnishell@maximeallanic.github.io`)
and turn off **Google suggestions**, or set the GSettings key `search-suggestions` to `false`
([configuration](configuration.md)). The change applies at once: the daemon, which is the process that would send
the request, reads the switch before every search and sends nothing while it is off. The search still shows "Search
on Google", "Ask Gemini", keywords, history and agenda; your text reaches a website only when you pick one of those
web results. If the daemon cannot find the extension's settings schema, it treats suggestions as off.

## What stays on your computer

- **Your voice.** Audio is recorded only while the "Listening…" pill is on screen or Gemini's microphone button is
  active. It is kept in memory, transcribed by `whisper-server` on `127.0.0.1`, and dropped. Only the transcribed text
  is sent, to Gemini, as if you had typed it.
- **Your browser history and bookmarks** are read from a copy of the profile's database in `~/.cache/omnishell/` and
  matched locally. They are never sent anywhere.
- **Your Google credentials.** The access token comes from GNOME Online Accounts and stays in the daemon's memory. The
  Gemini sign-in is a cookie in the drawer's own profile, `~/.local/share/omnishell/webkit/`.
- **Tasks** are cached in `~/.cache/omnishell/tasks.json` so that the clock menu works offline.

Omnishell has no telemetry, no analytics and no server of its own. The only other download is the speech model,
once, from Hugging Face.

## Removing your data

`uninstall.sh --purge` removes the settings, the caches, the model and the drawer's profile (your Gemini sign-in).
Your Google account stays in Settings > Online Accounts until you remove it there.
