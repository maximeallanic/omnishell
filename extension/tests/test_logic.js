// Run: gjs -m tests/test_logic.js (from extension/)
import {DRAWER_INITIAL, drawerNext, formatDay, linearIndicator, localeTags, drawerGeometry, drawerPosition, activation, fallbackItems, geminiAvailable, shouldHideOnFocus, groupItems, nextRespawnDelay, panelGeometry, pillText, taskRows} from '../omnishell@maximeallanic.github.io/logic.js';
import {format, setGettext} from '../omnishell@maximeallanic.github.io/i18n.js';

function eq(a, b, name) {
    if (JSON.stringify(a) !== JSON.stringify(b)) {
        printerr(`FAIL ${name}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`);
        imports.system.exit(1);
    }
}

// --- drawer geometry
eq(panelGeometry({x: 0, y: 36, width: 1707, height: 1031}, 600), {x: 1107, y: 36, width: 600, height: 1031}, 'primary monitor');
eq(panelGeometry({x: 2560, y: 36, width: 3840, height: 1044}, 600), {x: 5800, y: 36, width: 600, height: 1044}, 'offset second monitor');
eq(panelGeometry({x: 0, y: 0, width: 500, height: 800}, 600).width, 500, 'width clamped');
eq(nextRespawnDelay([], 100000), 2000, 'first failure');
eq(nextRespawnDelay([50000, 70000, 90000], 100000), 30000, '3 failures in 1 min');
eq(nextRespawnDelay([10000, 70000, 90000], 100000), 2000, 'old failures ignored');

// --- search
eq(fallbackItems('ab'), [], 'too short');
eq(fallbackItems('é'), [], 'one accented letter is too short');
eq(fallbackItems('猫').length > 0, true, 'one ideograph is a query');
eq(fallbackItems('мир').length > 0, true, 'three Cyrillic letters are a query');
eq(fallbackItems('chat noir').map(i => i.id), ['google:search', 'google:gemini'], 'fallback ids');
eq(fallbackItems('chat noir')[0].url, 'https://www.google.com/search?q=chat%20noir', 'search url');
eq(fallbackItems('chat noir')[0].name, 'Search “chat noir” on Google', 'search label');
eq(fallbackItems('chat noir')[1].name, 'Ask Gemini: “chat noir”', 'gemini label');
eq(fallbackItems('  chat   noir ')[1].name, 'Ask Gemini: “chat noir”', 'spaces collapsed');
eq(groupItems([{group: 'google', id: 'a'}, {group: 'chrome', id: 'b'}], 'chrome').map(i => i.id), ['b'], 'group filter');

// --- tasks and voice
const T = (bucket, title, due = '') => ({bucket, title, list: 'l', id: title, list_title: 'Personal', due, link: 'https://t/'});
eq(taskRows([], {account: false}).map(r => r.kind), ['setup'], 'no account');
eq(taskRows([T('today', 'a'), T('overdue', 'b'), T('undated', 'c'), T('later', 'd')], {account: true, online: true})
    .map(r => `${r.kind}:${r.title ?? r.text ?? ''}`),
['header:Overdue', 'task:b', 'header:Today', 'task:a', 'undated:1 undated', 'more:See all'], 'order');
eq(taskRows(Array.from({length: 12}, (_, i) => T('today', `t${i}`)), {account: true, online: true})
    .filter(r => r.kind === 'task').length, 8, '8 rows at most');
eq(taskRows(Array.from({length: 12}, (_, i) => T('today', `t${i}`)), {account: true, online: true}).at(-1).kind, 'more', 'truncated: See all');
eq(taskRows([T('today', 'a')], {account: true, online: false})[0].kind, 'offline', 'offline');
eq(taskRows([T('today', 'a')], {account: true, online: false})[0].text, 'offline', 'offline label');
eq(taskRows([T('today', 'a')], {account: true, online: true, multiList: true})[1].subtitle, 'Personal', 'list name');
eq(taskRows([T('today', 'a')], {account: true, online: true})[1].subtitle, '', 'single list');
eq(taskRows([T('week', 'w', '2026-10-09')], {account: true, online: true, locales: ['fr-FR']})[1].subtitle, 'ven. 9 oct.', 'date this week');
eq(formatDay('2026-10-09', ['en-US']), 'Fri, Oct 9', 'English date');
eq(formatDay('2026-10-09', ['ja-JP']), '10月9日(金)', 'Japanese date');
eq(formatDay('2026-10-09', ['de-DE']), 'Fr., 9. Okt.', 'German date');
eq(localeTags(['fr_FR.UTF-8', 'fr_FR', 'fr.UTF-8', 'fr', 'C']), ['fr-FR', 'fr'], 'BCP 47 tags');
eq(localeTags(['sr_RS@latin', 'sr', 'POSIX']), ['sr-Latn-RS', 'sr'], 'script modifier');
eq(localeTags(['C']), [], 'C locale');
eq(taskRows([T('week', 'w', '2026-10-09')], {account: true, online: true})[0].title, 'Next 7 days', 'week header');
eq(taskRows([], {account: true, online: true}).map(r => r.kind), ['empty'], 'nothing to do');
eq(pillText('listening'), 'Listening…', 'listening');
eq(pillText('transcribing'), 'Transcribing…', 'transcription');
eq(pillText('empty'), 'Nothing heard', 'empty');
eq(pillText('error:audio-capture'), 'Microphone unavailable', 'microphone');
eq(pillText('error:network'), 'Transcription failed', 'whisper');

// --- activation: the extension opens the URL of the displayed item itself
eq(activation({kind: 'search', url: 'https://www.google.com/search?q=foo'}), {open: 'https://www.google.com/search?q=foo'}, 'search');
eq(activation({kind: 'url', url: 'https://github.com/'}), {open: 'https://github.com/'}, 'url');
eq(activation({kind: 'event', url: 'https://cal/e1'}), {open: 'https://cal/e1'}, 'event');
eq(activation({kind: 'task', url: 'https://tasks.google.com/'}), {open: 'https://tasks.google.com/'}, 'task');
eq(activation({kind: 'gemini', url: ''}), {gemini: true}, 'gemini');
eq(activation({kind: 'new-task', url: ''}), {daemon: true}, 'new task');
eq(activation({kind: 'setup', url: ''}), {daemon: true}, 'account');
eq(activation({kind: 'url', url: ''}), {daemon: true}, 'missing url: daemon');

// --- network: Gemini only with full connectivity (Gio.NetworkConnectivity: 1 local, 2 limited, 3 portal, 4 full)
eq(geminiAvailable(true, 4), true, 'full connectivity');
eq(geminiAvailable(true, 3), false, 'captive portal');
eq(geminiAvailable(true, 2), false, 'limited connectivity');
eq(geminiAvailable(false, 4), false, 'network unavailable');
eq(fallbackItems('chat noir', {gemini: false}).map(i => i.id), ['google:search'], 'no Gemini row offline');
eq(groupItems([{group: 'google', id: 'google:gemini', kind: 'gemini'}, {group: 'google', id: 'google:search', kind: 'search'}], 'google', {gemini: false}).map(i => i.id),
    ['google:search'], 'daemon Gemini row dropped offline');

// --- focus loss: the drawer hides (except for its own windows)
eq(shouldHideOnFocus(true, {kind: 'other'}), true, 'other window');
eq(shouldHideOnFocus(true, {kind: 'none'}), true, 'no window (desktop)');
eq(shouldHideOnFocus(true, {kind: 'panel'}), false, 'drawer itself');
eq(shouldHideOnFocus(true, {kind: 'same-client'}), false, 'Google sign-in of the drawer');
eq(shouldHideOnFocus(true, {kind: 'transient'}), false, 'attached dialog (file chooser)');
eq(shouldHideOnFocus(false, {kind: 'other'}), false, 'drawer already hidden');

print('OK');

// --- M3E: drawer and linear indicator
eq(drawerGeometry(0, 480), {translation: 480, scale: 1}, 'drawer hidden');
eq(drawerGeometry(240, 480), {translation: 240, scale: 1}, 'drawer half way');
eq(drawerGeometry(480, 480), {translation: 0, scale: 1}, 'drawer open');
eq(drawerGeometry(487.2, 480), {translation: 0, scale: 1.015}, 'overshoot: stuck to the edge, stretched');
eq(drawerGeometry(-5, 480).translation, 480, 'below 0: hidden');
eq(drawerPosition(240, 1, 480), 240, 'position read back');
eq(Math.round(drawerPosition(0, 1.015, 480) * 1000) / 1000, 487.2, 'position read back in overshoot');
eq(linearIndicator(0, 120, 4), {active: 0, trackStart: 0, track: 120}, 'zero level: track only');
eq(linearIndicator(0.5, 120, 4), {active: 60, trackStart: 64, track: 56}, 'half level');
eq(linearIndicator(1, 120, 4), {active: 120, trackStart: 120, track: 0}, 'full');
eq(linearIndicator(2, 120, 4).active, 120, 'clamped');
print('M3E: ok');

// --- drawer life cycle: the drawer slides in only once the panel answered Show
function play(events, from = DRAWER_INITIAL) {
    const actions = [];
    let state = from;
    for (const e of events) {
        const r = drawerNext(state, e);
        state = r.state;
        actions.push(...r.actions);
    }
    return {...state, actions};
}
const UNMAPPED = {wanted: false, phase: 'unmapped'};
eq(play(['spawned']), {wanted: false, phase: 'requested', actions: ['callShow']}, 'warm-up Show when the panel reaches the bus');
eq(play(['spawned', 'replied']), {wanted: false, phase: 'ready', actions: ['callShow', 'park']}, 'warm-up answered: parked, never in sight');
eq(play(['spawned', 'replied', 'parked']), {...UNMAPPED, actions: ['callShow', 'park']}, 'warm-up over');
eq(play(['show']), {wanted: true, phase: 'absent', actions: []}, 'click before the panel is on the bus: button checked, nothing to call');
eq(play(['show', 'spawned', 'replied']).actions, ['callShow', 'slideIn'], 'click before the panel is on the bus: served by its first Show');
eq(play(['show'], UNMAPPED), {wanted: true, phase: 'requested', actions: ['callShow']}, 'click: Show asked, button checked, no slide yet');
eq(play(['show', 'replied'], UNMAPPED), {wanted: true, phase: 'ready', actions: ['callShow', 'slideIn']}, 'slide in on the answer only');
eq(play(['spawned', 'show']), {wanted: true, phase: 'requested', actions: ['callShow']}, 'click during the warm-up: same Show, no second call');
eq(play(['spawned', 'show', 'replied']).actions, ['callShow', 'slideIn'], 'click during the warm-up: slides in on the answer');
eq(play(['show', 'hide'], UNMAPPED), {wanted: false, phase: 'requested', actions: ['callShow']}, 'second click cancels: nothing slides');
eq(play(['show', 'hide', 'replied'], UNMAPPED).actions, ['callShow', 'park'], 'cancelled request: parked on the answer');
eq(play(['show', 'hide', 'show', 'replied'], UNMAPPED).actions, ['callShow', 'slideIn'], 'third click: wanted again, still one Show');
eq(play(['show', 'replied', 'hide'], UNMAPPED), {wanted: false, phase: 'ready', actions: ['callShow', 'slideIn', 'slideOut']}, 'close');
eq(play(['show', 'replied', 'hide', 'show'], UNMAPPED).actions, ['callShow', 'slideIn', 'slideOut', 'slideIn'], 'reopened while closing: no new Show');
eq(play(['show', 'replied', 'hide', 'parked'], UNMAPPED), {...UNMAPPED, actions: ['callShow', 'slideIn', 'slideOut']}, 'closed');
eq(play(['show', 'replied', 'hide', 'parked', 'show'], UNMAPPED).actions.at(-1), 'callShow', 'reopened after parking: new Show');
eq(play(['show', 'replied', 'show'], UNMAPPED).actions, ['callShow', 'slideIn'], 'show while open: nothing');
eq(play(['hide'], UNMAPPED), {...UNMAPPED, actions: []}, 'hide while closed: nothing');
eq(play(['replied'], UNMAPPED), {...UNMAPPED, actions: []}, 'stray answer ignored');
eq(play(['show', 'failed'], UNMAPPED), {...UNMAPPED, actions: ['callShow']}, 'Show failed: button released');
eq(play(['show', 'replied', 'exited'], UNMAPPED), {wanted: false, phase: 'absent', actions: ['callShow', 'slideIn']}, 'process gone');
print('drawer: ok');

// --- translations: lookups happen when rows are built, plurals go through ngettext, values are inserted verbatim
eq(format('Open {url}', {url: 'a$&b$1'}), 'Open a$&b$1', 'format: no replacement pattern in values');
eq(format('{n} of {missing}', {n: 2}), '2 of {missing}', 'format: unknown placeholder kept');
const FR = {'Overdue': 'En retard', 'Search “{query}” on Google': 'Rechercher « {query} » sur Google'};
setGettext(msgid => FR[msgid] ?? msgid, (one, many, n) => (n > 1 ? '{n} sans dates' : '{n} sans date'));
eq(fallbackItems('chat noir')[0].name, 'Rechercher « chat noir » sur Google', 'translated label');
eq(taskRows([T('overdue', 'b'), T('undated', 'c'), T('undated', 'e')], {account: true, online: true})
    .map(r => r.title ?? r.text), ['En retard', 'b', '2 sans dates', 'See all'], 'translated rows and plural');
