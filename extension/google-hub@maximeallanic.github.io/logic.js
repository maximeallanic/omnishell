// Pure logic of the extension (tested by tests/test_logic.js, without the Shell).

import {_, format, ngettext} from './i18n.js';

export function panelGeometry(workArea, width) {
    const w = Math.min(width, workArea.width);
    return {x: workArea.x + workArea.width - w, y: workArea.y, width: w, height: workArea.height};
}

// failures: timestamps (ms) of the failures, the one that just happened included.
export function nextRespawnDelay(failures, now) {
    return failures.filter(t => now - t < 60000).length >= 3 ? 30000 : 2000;
}

// A query is worth searching once it is MIN_BYTES long in UTF-8: three Latin letters, two Cyrillic or Arabic ones,
// a single Han, kana or Hangul character. Same rule as the daemon (omnibox.py, long_enough).
const MIN_BYTES = 3;
const utf8 = new TextEncoder();

export function longEnough(query) {
    return utf8.encode(query).length >= MIN_BYTES;
}

// "Search…" and "Ask Gemini…" rows built without the daemon (same ids as the daemon's).
export function fallbackItems(query, {gemini = true} = {}) {
    const q = query.split(/\s+/).filter(Boolean).join(' ');
    if (!longEnough(q))
        return [];
    return groupItems([
        {group: 'google', id: 'google:search', name: format(_('Search “{query}” on Google'), {query: q}), description: '',
            icon: 'system-search-symbolic', kind: 'search', url: `https://www.google.com/search?q=${encodeURIComponent(q)}`},
        {group: 'google', id: 'google:gemini', name: format(_('Ask Gemini: “{query}”'), {query: q}), description: '',
            icon: 'google-hub-gemini-symbolic', kind: 'gemini', url: ''},
    ], 'google', {gemini});
}

// gemini false (offline): the "Ask Gemini" row is dropped.
export function groupItems(items, group, {gemini = true} = {}) {
    return items.filter(i => i.group === group && (gemini || i.kind !== 'gemini'));
}

const CONNECTIVITY_FULL = 4; // Gio.NetworkConnectivity.FULL

// Gemini is only usable with full connectivity (a captive portal is not enough).
export function geminiAvailable(networkAvailable, connectivity) {
    return Boolean(networkAvailable) && connectivity === CONNECTIVITY_FULL;
}

// glibc locale modifiers that name a script (sr_RS@latin).
const SCRIPT_MODIFIERS = {latin: 'Latn', cyrillic: 'Cyrl', devanagari: 'Deva'};

// BCP 47 tags of the session locale names (GLib.get_language_names_with_category('LC_TIME')),
// for Intl: 'fr_FR.UTF-8' -> 'fr-FR', 'sr_RS@latin' -> 'sr-Latn-RS'; C/POSIX and unknown tags dropped.
export function localeTags(names) {
    const tags = [];
    for (const name of names) {
        const [base, modifier] = name.split('@');
        const [lang, territory] = base.split('.')[0].split('_');
        if (!lang || lang === 'C' || lang === 'POSIX')
            continue;
        const tag = [lang, SCRIPT_MODIFIERS[modifier], territory].filter(Boolean).join('-');
        let supported;
        try {
            supported = Intl.DateTimeFormat.supportedLocalesOf(tag).length > 0;
        } catch (e) {
            if (!(e instanceof RangeError))
                throw e;
            supported = false; // not a BCP 47 tag (a locale name ICU cannot read)
        }
        if (supported && !tags.includes(tag))
            tags.push(tag);
    }
    return tags;
}

// Short day of a task due date (YYYY-MM-DD) in the CLDR pattern of locales: "ven. 9 oct.", "Fri, Oct 9", "10月9日(金)".
export function formatDay(iso, locales) {
    const [y, m, d] = iso.split('-').map(Number);
    return new Intl.DateTimeFormat(locales, {weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC'})
        .format(new Date(Date.UTC(y, m - 1, d)));
}

// Titles are looked up when the rows are built: the translation function is only set at enable.
const BUCKETS = [['overdue', () => _('Overdue')], ['today', () => _('Today')], ['week', () => _('Next 7 days')]];
const MAX_TASKS = 8;
export const TASKS_URL = 'https://tasks.google.com/';

// Rows of the "Tasks" section of the clock menu.
// locales: BCP 47 tags for the due dates (localeTags), undefined = the default locale of the JS engine.
export function taskRows(tasks, {account = true, online = true, multiList = false, locales} = {}) {
    if (!account)
        return [{kind: 'setup', text: _('Connect your Google account')}];
    const rows = online ? [] : [{kind: 'offline', text: _('offline')}];
    let shown = 0;
    let truncated = false;
    for (const [bucket, title] of BUCKETS) {
        const inBucket = tasks.filter(t => t.bucket === bucket);
        if (!inBucket.length)
            continue;
        if (shown >= MAX_TASKS) {
            truncated = true;
            continue;
        }
        rows.push({kind: 'header', title: title()});
        for (const t of inBucket) {
            if (shown >= MAX_TASKS) {
                truncated = true;
                break;
            }
            const date = bucket !== 'today' && t.due ? formatDay(t.due, locales) : '';
            rows.push({kind: 'task', title: t.title, subtitle: [date, multiList ? t.list_title : ''].filter(Boolean).join(' · '),
                id: t.id, list: t.list, link: t.link});
            shown++;
        }
    }
    const undated = tasks.filter(t => t.bucket === 'undated').length;
    if (undated)
        rows.push({kind: 'undated', text: format(ngettext('{n} undated', '{n} undated', undated), {n: undated})});
    if (truncated || undated || tasks.some(t => t.bucket === 'later'))
        rows.push({kind: 'more', text: _('See all')});
    if (!rows.some(r => r.kind !== 'offline'))
        rows.push({kind: 'empty', text: _('No upcoming tasks')});
    return rows;
}

export function pillText(state) {
    return {
        'listening': _('Listening…'),
        'transcribing': _('Transcribing…'),
        'empty': _('Nothing heard'),
        'error:audio-capture': _('Microphone unavailable'),
    }[state] ?? (state.startsWith('error:') ? _('Transcription failed') : '');
}

// What activating a result does: the extension opens the URL of the item on screen (the daemon only knows its
// latest search, not necessarily the one on screen after a backspace).
export function activation(item) {
    if (item.kind === 'gemini')
        return {gemini: true};
    if (['url', 'search', 'event', 'task'].includes(item.kind) && item.url)
        return {open: item.url};
    return {daemon: true};
}

// The visible drawer hides when the focus goes elsewhere, except to its own windows
// (kind: 'panel', 'same-client' = Google sign-in, 'transient' = attached dialog, 'other', 'none').
export function shouldHideOnFocus(visible, focus) {
    return visible && (focus.kind === 'other' || focus.kind === 'none');
}

// Drawer = modal navigation drawer of Compose (NavigationDrawer.kt) anchored to the right edge. `position` (px): 0 =
// hidden, width = open. Beyond that (overshoot of the DefaultSpatial spring) the drawer does not leave the edge: it
// stretches horizontally from the screen edge (horizontalScaleUp: scaleX = 1 + overshoot / width, pivot on the edge).
export function drawerGeometry(position, width) {
    const w = width > 0 ? width : 1;
    const p = Number.isFinite(position) ? position : 0;
    return {translation: Math.max(0, w - Math.max(0, p)), scale: p > w ? 1 + (p - w) / w : 1};
}

// Inverse: position read back from the actor.
export function drawerPosition(translation, scale, width) {
    const w = width > 0 ? width : 1;
    return scale > 1 ? w * scale : w - translation;
}

// M3E determinate linear indicator (LinearProgressIndicatorTokens): width of the indicator, then a gap, then the track
// up to the end (the stop indicator sits at the end of the track). Without a level there is no gap: track only.
export function linearIndicator(level, width, gap) {
    const n = Math.min(1, Math.max(0, Number.isFinite(level) ? level : 0));
    const active = Math.round(n * width);
    if (active <= 0)
        return {active: 0, trackStart: 0, track: width};
    const trackStart = Math.min(width, active + gap);
    return {active, trackStart, track: Math.max(0, width - trackStart)};
}

// Drawer life cycle. The panel window is mapped by a Show call that the panel answers only once its view has something
// to show (panel/google_hub_panel/readiness.py); until then the Shell keeps the mapped window out of sight.
//   wanted: what the user asked for (top-bar button checked);
//   phase:  'absent' (no panel on the bus), 'unmapped' (no window), 'requested' (Show in flight, window out of
//           sight), 'ready' (Show answered).
// A never-mapped web view has no frame at all and its first map costs seconds, so the Shell asks for a first Show as
// soon as the panel is on the bus ('spawned'), wanted or not: the later ones answer within a frame.
// Events: 'spawned', 'show', 'hide', 'replied' (Show answered), 'failed' (Show call failed), 'parked' (window sent
// back to the panel with Hide), 'exited' (process gone). Actions, for panel.js: 'callShow', 'slideIn', 'slideOut',
// 'park'.
export const DRAWER_INITIAL = Object.freeze({wanted: false, phase: 'absent'});

export function drawerNext(state, event) {
    const {wanted, phase} = state;
    const to = (next, ...actions) => ({state: {...state, ...next}, actions});
    switch (event) {
    case 'spawned':
        return to({phase: 'requested'}, 'callShow');
    case 'show':
        if (wanted)
            return to({});
        if (phase === 'unmapped')
            return to({wanted: true, phase: 'requested'}, 'callShow');
        return to({wanted: true}, ...phase === 'ready' ? ['slideIn'] : []);
    case 'hide':
        // A pending Show is not cancelled: the window keeps warming up out of sight and is parked when it answers.
        return wanted ? to({wanted: false}, ...phase === 'ready' ? ['slideOut'] : []) : to({});
    case 'replied':
        if (phase !== 'requested')
            return to({});
        return to({phase: 'ready'}, wanted ? 'slideIn' : 'park');
    case 'parked':
        return to({phase: 'unmapped'});
    case 'failed':
        return to({wanted: false, phase: 'unmapped'});
    case 'exited':
        return to({wanted: false, phase: 'absent'});
    default:
        throw new Error(`drawerNext: unknown event ${event}`);
    }
}
