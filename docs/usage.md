# Using Omnishell

## Search

Press **Super** and type, as you would to find an application. From three characters (one for Chinese, Japanese or
Korean: the threshold is measured in UTF-8 bytes, so it fits every script), three groups appear below the
applications:

| Group | What it shows | Enter does |
|---|---|---|
| **Web search** | The address you typed (`github.com/gnome`), "Search on Google", "Ask Gemini", four Google suggestions, or the keyword search (`yt`, `w`, `maps`…) | Opens the browser, or the Gemini drawer with your question |
| **Chrome** | Matching bookmarks and history of your Chromium-family browser | Opens the page |
| **Calendar & Tasks** | Events of the next 30 days and open tasks that match; a day (`tomorrow`, `friday`, `12/10`) lists that day's events | Opens the event or the task in Google |

![Search for "gnome": Google suggestions in the web search group and Chrome bookmarks](../screenshots/search.png)

### Keyword searches

`yt cat videos`, `maps coffee`, `w Ada Lovelace`, `gh gnome-shell`, `drive budget` search those sites directly. Add
your own in `keywords.json` ([configuration](configuration.md#search-keywords-configomnishellkeywordsjson)).

### Create a task

`t Call the plumber tomorrow` shows "Create task: Call the plumber" with its due date. The date is read at the end
of the text, in your session language (and the `date_languages` you add): `tomorrow`, `friday`, `on the 12th`,
`12/10` in English; `demain`, `vendredi`, `le 12` in French; and so on for every language dateparser knows. A text
without a date makes a task without a due date. Created offline, the task is queued and sent when the network is back.

![Creating a task from the search](../screenshots/search-add-task.png)

## Gemini drawer

**Super+G**, or the sparkle icon in the top bar, slides the Gemini web app in from the right edge of the screen under
the pointer; the same shortcut or a click in another window hides it. It is the real gemini.google.com, signed in with
your account (sign in once in the drawer), with your history and subscription.

- The drawer is prepared at login in the background, so it opens already drawn. If Gemini is still loading, the icon
  is selected at once and the drawer slides in as soon as the page is ready.
- It is not a normal window: it does not appear in Alt+Tab, the dock or the overview.
- Offline, the icon is dimmed and the drawer says so; Gemini reloads by itself when the network comes back.
- "Ask Gemini" in the search opens the drawer and sends the question.

<img src="../screenshots/gemini-drawer.png" width="360" alt="The Gemini drawer at the right edge of the screen, showing Google's sign-in and cookie consent page">

## Voice

**Super+Shift+G** shows a "Listening…" pill at the top of the screen. Speak; when you stop, the sentence is
transcribed on your computer by Whisper and sent to Gemini in the drawer. Press Super+Shift+G again or click the pill
to stop listening early, Escape to cancel.

The microphone button inside Gemini uses the same local engine: WebKitGTK has no speech recognition, so Omnishell
provides it.

![The listening pill](../screenshots/voice-pill.png)

## Tasks in the clock menu

The clock menu gets a **Tasks** section: overdue, today and the next 7 days, from all your Google Tasks lists. Tick a
task to complete it, "+ Add a task" to create one (same date reading as `t` in the search), "See all" to open Google
Tasks. Changes made offline are kept and sent later; if Google refuses one, a notification says so.

![Tasks in the clock menu](../screenshots/clock-menu-tasks.png)

Every morning (at `summary_hour`, or at login if later) a notification sums up the day: "3 tasks today, 1 overdue".
