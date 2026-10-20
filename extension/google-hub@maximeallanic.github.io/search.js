// Three search providers (Google, Chrome, Calendar & Tasks) fed by a single Search call.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GioUnix from 'gi://GioUnix';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {HUB, call} from './dbus.js';
import {untilCancelled} from './async.js';
import {_} from './i18n.js';
import {activation, fallbackItems, groupItems, longEnough} from './logic.js';

const DEBOUNCE_MS = 150;
const SEARCH_TIMEOUT_MS = 2000;
// Queries whose items are kept: the Shell asks again for metadata and activation by id while the results are
// displayed, which only concerns the latest keystrokes.
const KEPT_QUERIES = 8;
const SEP = '\u0000';

// Names are looked up when the providers are built (enable): the translation function is only set then.
// icons: themed icon names tried in order, then the extension's own icons/<fallback>.svg (stock Adwaita has none of
// these application icons).
const GROUPS = [
    {group: 'google', name: () => 'Google', icons: ['google'], fallback: 'google-hub-search'},
    {group: 'chrome', name: () => 'Chrome', icons: ['google-chrome', 'chromium', 'chromium-browser'], fallback: 'google-hub-browser'},
    {group: 'agenda', name: () => _('Calendar & Tasks'), icons: ['org.gnome.Calendar'], fallback: 'google-hub-calendar'},
];

const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve();
    return GLib.SOURCE_REMOVE;
}));

const normalize = terms => terms.join(' ').split(/\s+/).filter(Boolean).join(' ');

// One Search per typed text, shared by the three providers. Only the call in flight is shared: typing the same
// text later asks the daemon again (tasks done, events past).
class SearchHub {
    constructor(dir) {
        this._dir = dir;
        this._pending = new Map(); // text → Promise<item[]> still in flight
        this._results = new Map(); // text → Map(display id → item), the KEPT_QUERIES latest
        this._latest = '';
    }

    get(displayId) {
        const q = displayId.slice(0, displayId.indexOf(SEP));
        return this._results.get(q)?.get(displayId);
    }

    items(terms) {
        const q = normalize(terms);
        if (!longEnough(q))
            return Promise.resolve([]);
        this._latest = q;
        let p = this._pending.get(q);
        if (!p) {
            p = this._fetch(q, terms).finally(() => {
                if (this._pending.get(q) === p)
                    this._pending.delete(q);
            });
            this._pending.set(q, p);
        }
        return p;
    }

    async _fetch(q, terms) {
        await sleep(DEBOUNCE_MS);
        if (q !== this._latest)
            return [];
        let items;
        try {
            [items] = await call(HUB, 'Search', new GLib.Variant('(as)', [terms]), '(aa{sv})',
                {timeout: SEARCH_TIMEOUT_MS});
        } catch (e) {
            console.debug(`google-hub: Search unavailable (${e.message})`);
            items = fallbackItems(q);
        }
        // Id specific to the query: the Shell reuses displayed results by id.
        const byId = new Map();
        const out = items.map(item => {
            const did = `${q}${SEP}${item.id}`;
            byId.set(did, item);
            return {...item, did};
        });
        this._remember(q, byId);
        return out;
    }

    _remember(q, byId) {
        this._results.delete(q);
        this._results.set(q, byId);
        while (this._results.size > KEPT_QUERIES)
            this._results.delete(this._results.keys().next().value);
    }

    iconPath(name) {
        return this._dir.get_child('icons').get_child(`${name}.svg`).get_path();
    }

    gicon(name) {
        if (name === 'google-hub-gemini-symbolic')
            return Gio.FileIcon.new(this._dir.get_child('icons').get_child(`${name}.svg`));
        return Gio.ThemedIcon.new(name);
    }
}

class HubProvider {
    constructor(hub, spec, onGemini, geminiAvailable) {
        this._hub = hub;
        this._geminiAvailable = geminiAvailable;
        this._group = spec.group;
        this._onGemini = onGemini;
        this.id = `google-hub-${spec.group}`;
        this.isRemoteProvider = false;
        this.canLaunchSearch = false;
        // The Shell hands appInfo to parental controls (malcontent): it must be a real GAppInfo.
        const kf = new GLib.KeyFile();
        const theme = new St.IconTheme();
        const icon = spec.icons.find(name => theme.has_icon(name)) ?? hub.iconPath(spec.fallback);
        const data = `[Desktop Entry]\nType=Application\nName=${spec.name()}\nIcon=${icon}\nExec=true\n`;
        kf.load_from_data(data, new TextEncoder().encode(data).length, GLib.KeyFileFlags.NONE);
        this.appInfo = GioUnix.DesktopAppInfo.new_from_keyfile(kf);
    }

    async getInitialResultSet(terms, cancellable) {
        const items = await untilCancelled(this._hub.items(terms), cancellable);
        if (items === null || cancellable?.is_cancelled())
            return [];
        return groupItems(items, this._group, {gemini: this._geminiAvailable()}).map(i => i.did);
    }

    getSubsearchResultSet(_previous, terms, cancellable) {
        return this.getInitialResultSet(terms, cancellable);
    }

    getResultMetas(ids) {
        return Promise.resolve(ids.map(id => {
            const item = this._hub.get(id) ?? {name: id, description: '', icon: 'system-search-symbolic'};
            return {
                id,
                name: item.name,
                description: item.description,
                createIcon: size => new St.Icon({gicon: this._hub.gicon(item.icon), icon_size: size}),
            };
        }));
    }

    filterResults(results, max) {
        return results.slice(0, max);
    }

    activateResult(id, terms) {
        const item = this._hub.get(id);
        if (!item)
            return;
        Main.overview.hide();
        const what = activation(item);
        if (what.gemini)
            this._onGemini(normalize(terms));
        else if (what.open)
            Gio.AppInfo.launch_default_for_uri(what.open, null);
        else
            call(HUB, 'Activate', new GLib.Variant('(sas)', [item.id, terms]))
                .catch(e => console.warn(`google-hub: Activate failed (${e.message})`));
    }
}

export class SearchProviders {
    constructor(dir, onGemini, geminiAvailable) {
        const hub = new SearchHub(dir);
        this._providers = GROUPS.map(spec => new HubProvider(hub, spec, onGemini, geminiAvailable));
    }

    enable() {
        for (const p of this._providers)
            Main.overview.searchController.addProvider(p);
    }

    disable() {
        for (const p of this._providers)
            Main.overview.searchController.removeProvider(p);
    }

    // For the control interface: what each group would show for this text.
    async debug(text) {
        const terms = text.split(/\s+/).filter(Boolean);
        const out = {};
        for (const p of this._providers) {
            const ids = await p.getInitialResultSet(terms, null);
            out[p.id] = (await p.getResultMetas(ids)).map(m => `${m.name}${m.description ? ` — ${m.description}` : ''}`);
        }
        return out;
    }
}
