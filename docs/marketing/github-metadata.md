# GitHub metadata

What to type in the repository's settings when it is created. Nothing here is applied automatically.

## Description (338 characters, limit 350)

```text
Unofficial Google integration for GNOME Shell 50/51: Google search and suggestions in the GNOME search, a Gemini drawer (Super+G), Google Tasks in the clock menu with offline changes and a morning summary, calendar events in search, and voice questions to Gemini transcribed locally by whisper.cpp. No API key: uses GNOME Online Accounts.
```

"Unofficial" comes first on purpose: the description is what search results and link previews show, and the name
alone reads like a Google product.

Short variant, for places with a tight limit (Mastodon bio, link titles, 115 characters):

```text
Google search, Gemini and Google Tasks built into GNOME Shell. Voice transcribed on your computer. Unofficial, MIT.
```

## Website field

Leave empty until there is a page of its own; the README is the landing page.

## Topics (12)

```text
gnome gnome-shell gnome-shell-extension search-provider gemini google-tasks google-calendar
gnome-online-accounts whisper-cpp speech-to-text wayland linux-desktop
```

Why these: `gnome-shell-extension`, `gnome-shell` and `gnome` are where people browse for extensions; `gemini`,
`google-tasks` and `google-calendar` match how Google users search for integrations; `whisper-cpp` and
`speech-to-text` reach the local speech crowd, which cares about the on-device part; `search-provider` and
`gnome-online-accounts` describe the mechanism for developers. Not used: `chromeos` (it would suggest the project
runs on ChromeOS) and `google` alone (too broad, and it strengthens the official-product reading).

## Social preview

`docs/marketing/social-preview.png`, 1280×640, under 1 MB. Upload it in Settings > General > Social preview. It is
built from two real captures (`screenshots/search.png`, Google group only; `screenshots/clock-menu-tasks.png`, Tasks
card only), cropped and scaled, with the title, "For GNOME Shell 50 and 51", "Search, Gemini and Tasks in GNOME
Shell" and "Voice transcribed on your computer · Open source · Unofficial". The Chrome logo of the search capture is
cropped out; the "Google" row icon is the project's own drawing.

## Name check (recommendation only, nothing renamed)

Current: **Google Hub for GNOME**, repository `gnome-google-hub`, extension UUID
`google-hub@maximeallanic.github.io`.

What works: it says what it is in two words, and "for GNOME" is searchable. No other GNOME or Linux project called
"Google Hub" turned up in a search on 2026-10-20 (there are two unrelated extensions named "GnomeHub").

What does not:

- **Google's brand guidance says not to put Google names in a product name.** Google's brand guidance for apps
  that use its APIs reads "Don't use any Google product names, or confusingly similar names, as part of your
  company name, product name, domain name, or social media profile", and asks for a name that is "wholly your
  own" ([about.google, APIs guidance](https://about.google/brand-resource-center/guidance/apis/)). Google Hub calls
  the Calendar and Tasks APIs, so this guidance applies. Saying what the software works with, as the README does,
  is fine; having "Google" lead the name is the part it advises against.
- **It reads as official.** "Google Hub" sounds like a Google product (and close to Google's own "Nest Hub", once
  sold as "Google Home Hub"). The non-affiliation notice counters this, but the name often shows up alone: in
  search results, link previews and the Extensions app.
- **It is hard to search for.** "Google Hub" results are dominated by Google's own hardware.

Options, if the owner decides to rename before or after launch (each needs a collision check on GitHub,
extensions.gnome.org, Flathub and a trademark search first):

| Name | Pattern | Note |
|---|---|---|
| **Tabless** | "Tabless: Google search, Gemini and Tasks for GNOME" | Says the benefit (fewer browser tabs); wholly its own. |
| **Daybar** | "Daybar for GNOME" | Fits the clock menu and morning summary; weaker on search and Gemini. |
| **Sidekick for GNOME** | "Sidekick: Google search, Gemini and Tasks in GNOME Shell" | Generic word, likely crowded. |
| Keep "Google Hub" | As today | Lowest effort; accept the risk that Google, GitHub or extensions.gnome.org asks for a change later. |

A rename touches the UUID, GSettings schema id, D-Bus names, paths under `~/.local/share/google-hub` and the
installer, so it is cheaper before the first public release than after. That is a code change and is out of scope
here.
