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
built from two real captures (`screenshots/search.png`, web search group only; `screenshots/clock-menu-tasks.png`, Tasks
card only), cropped and scaled, with the title, "For GNOME Shell 50 and 51", "Search, assistant and tasks for GNOME"
and "Voice transcribed on your computer · Open source · Not affiliated with Google". The Chrome logo of the search
capture is cropped out; the web search row icon is the project's own drawing. Source:
`docs/marketing/social-preview.svg`, which links the captures by relative path. librsvg refuses images outside the
SVG's own folder, so render it with a browser, from `docs/marketing/`:

```sh
google-chrome --headless=new --hide-scrollbars --force-device-scale-factor=1 --window-size=1280,640 \
    --user-data-dir="$(mktemp -d)" --screenshot="$PWD/social-preview.png" "file://$PWD/social-preview.svg"
```

## Name

**Omnishell**, subtitle "Search, assistant and tasks for GNOME"; repository `omnishell`, extension UUID
`omnishell@maximeallanic.github.io`. The project was renamed before its first release because Google's rules forbid
Google product names in an app name:

- Google's trademark guidelines: a third-party product name must not include Google trademarks or confusingly
  similar terms ([Trademark guidelines for proper usage](https://partnermarketinghub.withgoogle.com/brands/google/trademarks-and-terms/trademark-guidelines-for-proper-usage/)).
- Google API branding rules for apps that use Google APIs (Calendar and Tasks here): the app name must not contain
  Google product names ([Google Cloud help, app branding](https://support.google.com/cloud/answer/13804963)).

Google services are named only to say what the software works with ("Google suggestions", "Gemini", "Google
Tasks"), always next to the non-affiliation notice. A web search on 2026-10-20 found no GNOME or Linux desktop
project called Omnishell (an unrelated Python shell, `D1j1t0/OmniShell`, and a Dart package spelled `omnyshell`
exist). Before launch, still check extensions.gnome.org, Flathub and a trademark register.
