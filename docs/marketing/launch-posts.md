# Launch posts

Drafts for r/gnome, r/linux, Hacker News and Mastodon. Nothing has been posted. Read the venue notes before
using any draft: two of the four venues do not accept machine-written posts, and these drafts were written with an
AI assistant.

## Before posting anything

- [ ] The repository is public, `scripts/release.sh 0.1.0` has pinned the release, and the `v0.1.0` tag and release
      exist: `install.sh` downloads the pinned `v0.1.0` release, so the one-line install fails until it does.
- [ ] The one-line install works from a fresh user account (`curl … | bash`), and `verify.sh` passes.
- [ ] Social preview uploaded, description and topics set ([github-metadata.md](github-metadata.md)).
- [ ] Decide what you say about how the project was built (see "AI disclosure" below), and say the same thing
      everywhere.
- [ ] Be available for the next few hours to answer comments: Show HN requires it, and Reddit threads go quiet
      without it.
- [ ] One venue per day at most, so you can answer each one properly.

## What the venues allow (checked 2026-10-20)

| Venue | Self-promotion | AI-written text | Source |
|---|---|---|---|
| Hacker News (Show HN) | Allowed for something you made and people can try; you must be around to discuss it; no asking for upvotes or comments; "Show HN" title prefix; routine version bumps do not qualify, a first release does. | "Don't post generated text or AI-edited text. HN is for conversation between humans." This covers the post and the first comment. | [showhn.html](https://news.ycombinator.com/showhn.html), [newsguidelines.html](https://news.ycombinator.com/newsguidelines.html) |
| r/gnome | Extension announcements are common there. Could not load the sidebar (Reddit blocks automated reads): check it before posting. | GNOME's Discourse adopted "the same policy for LLM generated projects and content as the r/gnome subreddit" (2026-07-01): moderators remove posts written entirely by an LLM and posts announcing projects written entirely by an LLM. | [discourse.gnome.org/t/36006](https://discourse.gnome.org/t/llm-generated-projects-and-content-on-gnomes-discourse-instance/36006) |
| r/linux | Could not load the sidebar: check its rules on self-promotion and AI content before posting. Reddit's general norm is that most of an account's activity should not be self-promotion. | Unverified for r/linux; assume a human-written post is expected. | Reddit sidebar, by hand |
| Mastodon (e.g. Fosstodon) | Fosstodon's code of conduct encourages members to promote their own work. Other servers vary: check yours. | Fosstodon asks for disclosure when generative AI made a standalone creative work. | [hub.fosstodon.org/coc](https://hub.fosstodon.org/coc/) |

Related, for later: extensions.gnome.org rejects extensions with "indications of AI-generated output" and expects
authors to "justify and explain the code they submit"
([review guidelines](https://gjs.guide/extensions/review-guidelines/review-guidelines.html)).

**What this means in practice**

- **Hacker News: write the post and the first comment yourself.** The HN section below is a fact sheet and a
  structure, not text to paste. Pasting AI-written or AI-edited text there breaks the rules.
- **r/gnome and r/linux: rewrite the drafts in your own words.** They are a starting point for content and order.
- **Mastodon:** the draft can be used, but a toot in your own voice will do better.

**AI disclosure.** If AI assistants helped write the code, say so plainly and briefly, in your words, in every post
(for example where you describe how you built it). This audience reacts badly to finding out later, and r/gnome
removes announcements of projects written entirely by an LLM. Only you know how it was built: this file does not
make a claim either way.

## Facts you can use (all from the repository)

- GNOME Shell 50 and 51, Wayland. MIT. Version 0.1.0, first public release.
- Super, then type: "Search on Google", "Ask Gemini", Google suggestions, direct addresses, Chrome/Chromium
  bookmarks and history, Google Calendar events and Google Tasks, below the applications.
- Keywords: `yt`, `maps`, `w`, `gh`, `drive`, plus your own. `t Call the plumber tomorrow` creates a Google task with
  a due date, dates read in the session language.
- Super+G: the real gemini.google.com in a drawer from the right edge, preloaded, out of Alt+Tab and the overview.
- Super+Shift+G: ask Gemini by voice; transcription runs locally with whisper.cpp (`whisper-server` on 127.0.0.1);
  Gemini's own microphone button uses it too. Voice is for Gemini, not system-wide dictation.
- Clock menu: Google Tasks, overdue / today / next 7 days, tick to complete, add, offline queue, morning summary.
- No API key: Calendar and Tasks use the GNOME Online Accounts Google account.
- Architecture: a Shell extension (GJS), a Python daemon on D-Bus for network, audio and speech (so the Shell never
  blocks), and a GTK 4 / WebKitGTK program for the drawer.
- Goes to Google: search text from three characters (suggestions, on by default, off switch in preferences), Calendar/Tasks API calls,
  whatever you do in Gemini. Stays local: voice, browser history, credentials, tasks cache. No telemetry.
- Limits: only Debian testing run for real; Fedora lacks a `whisper-server` package (build whisper.cpp once); Gemini
  page selectors can break when Google changes the page; not on extensions.gnome.org (needs the daemon and drawer);
  installer messages in English only; UI in English and French; Chromium-family browsers only for history.
- Screenshots and the GIF are real captures in a nested GNOME Shell 51 with invented data.

## Hacker News (Show HN)

**Title** (pick one, all ≤ 80 characters, no exclamation marks, no superlatives):

- `Show HN: Google search, Gemini and Google Tasks built into GNOME Shell` (70)
- `Show HN: Omnishell – Gemini drawer and Google Tasks for GNOME Shell` (67)
- `Show HN: GNOME Shell integration for Google search, Gemini and Tasks` (68)

**URL:** `https://github.com/maximeallanic/omnishell`

**First comment: write it yourself.** A structure that works on Show HN, with what to put in each part:

1. **Why you built it** — `[AUTHOR: your own motivation, in your words. What you used before, what annoyed you.]`
2. **What it does**, in three or four plain sentences from the fact sheet above.
3. **How it works**, because HN readers ask: extension + daemon + WebKitGTK drawer, and why the daemon exists.
4. **What goes to Google and what stays local**, said up front before someone asks. Name the suggestion
   keystrokes and the preferences switch that stops them.
5. **What is rough**: Gemini selectors, only Debian testing tested, Fedora and whisper-server.
6. **How it was built**, including AI assistance if any. `[AUTHOR]`
7. **What feedback you want**: tests on other distributions, whether the privacy trade-off is acceptable, the name.

Expect these questions and have answers ready: "Why trust a Google integration on Linux?", "What happens when
Google changes the Gemini page?", "Why not a Gemini API key instead of the web app?", "Why not on
extensions.gnome.org?", "Is `curl | bash` necessary?" (answer: clone and `./install.sh --dry-run` also works).

## r/gnome

Rewrite in your own words before posting. Flair: whatever the sidebar uses for extensions. Attach the GIF or link
the repository; a native video or GIF upload usually does better than a bare link.

**Title:** `Omnishell: Google search, Gemini and Google Tasks in GNOME Shell (50/51, local Whisper voice)`

**Body:**

> I made a GNOME Shell extension (plus a small daemon) that brings the Google parts I used daily on a Chromebook
> into GNOME:
>
> - Super and type: Google suggestions, "Ask Gemini", Chrome bookmarks and history, Calendar events and Tasks in the
>   regular search
> - Super+G: Gemini in a drawer from the right edge, out of Alt+Tab and the overview
> - Super+Shift+G: ask Gemini by voice, transcribed locally with whisper.cpp
> - Google Tasks in the clock menu, works offline, morning summary
> - No API key: it uses your GNOME Online Accounts Google account
>
> Privacy, up front: what you type in the search goes to Google's suggestion service (on by default, one switch in preferences turns it off); voice,
> history and credentials stay local; no telemetry. Details in the README.
>
> Limits: GNOME 50/51 Wayland only, only tested for real on Debian testing, not on extensions.gnome.org yet because
> it needs the daemon. Fedora/Arch/Ubuntu reports are very welcome.
>
> `[AUTHOR: one line on why you built it, and how it was built.]`
>
> https://github.com/maximeallanic/omnishell
>
> Not affiliated with Google.

Note: the "Chromebook" line is a claim about you. Keep it only if it is true; otherwise replace it with your real
reason.

## r/linux

Rewrite in your own words. r/linux readers are more sceptical of Google than r/gnome: lead with what it is and the
privacy split, not with Gemini.

**Title:** `I built a GNOME Shell integration for people who live in Google services (local voice, no telemetry, MIT)`

**Body:**

> Some of us run Linux but still live in Google Calendar, Tasks and Gemini. Omnishell puts those in GNOME Shell
> instead of browser tabs: Google suggestions in the GNOME search, Gemini in a Super+G drawer, Google Tasks in the
> clock menu, and voice questions transcribed on your machine with whisper.cpp.
>
> What goes to Google: your search text for suggestions (on by default, switch in preferences), Calendar/Tasks API calls through GNOME
> Online Accounts, and whatever you do in Gemini. What stays local: voice, browser history, credentials. No
> telemetry, no server of its own. If sending search keystrokes to Google is a dealbreaker, switch suggestions off in
> the preferences: the daemon then sends nothing while you type.
>
> It is a Shell extension plus a Python daemon (so slow work never blocks the Shell) and a GTK 4/WebKitGTK drawer.
> GNOME 50/51 Wayland only. The installer handles Debian/Ubuntu, Fedora and Arch packages, but only Debian testing
> has been run for real so far.
>
> `[AUTHOR: why you built it, and how it was built.]`
>
> https://github.com/maximeallanic/omnishell — MIT, not affiliated with Google.

## Mastodon

Hashtags help discovery on the Fediverse. Attach `screenshots/search-typing.gif` with its alt text:
"Typing 'gtk docs' in the GNOME search: Google suggestions, Ask Gemini and a matching page from the browser history
appear as you type".

**Toot (455 characters; Mastodon counts the link as 23, so 436):**

```text
Omnishell 0.1.0: Google search, Gemini and Google Tasks built into GNOME Shell 50/51.

• Super + type: Google suggestions, Ask Gemini, Calendar & Tasks
• Super+G: Gemini drawer
• Super+Shift+G: ask by voice, transcribed locally (whisper.cpp)
• Tasks in the clock menu, offline-capable

Search text goes to Google for suggestions; voice and history stay local. No telemetry. MIT, unofficial.

https://github.com/maximeallanic/omnishell

#GNOME #Linux #FOSS
```

## Other venues

- **r/chromeos**: the subreddit is about using ChromeOS, so a Linux desktop project is likely off topic there. Read
  its rules first, or answer an existing "switching to Linux" thread instead of posting.
- **GNOME Discourse**: same LLM policy as r/gnome; a "Show and tell"-type post must be in your words.
- **This Week in GNOME**: covers community projects; check how to submit on [thisweek.gnome.org](https://thisweek.gnome.org).
