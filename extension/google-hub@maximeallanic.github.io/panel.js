// Gemini drawer: the google-hub-panel process started as a Wayland client, anchored to the right edge, animated.
// Hidden drawer = window unmapped by the client (D-Bus Hide), never a merely hidden actor: Mutter shows again the
// actor of any window it believes visible (end of an effect, monitor or workspace change,
// meta_window_actor_sync_visibility), and a skip-taskbar window cannot be minimised.
// The window is mapped by the panel's Show, which answers only once the view has something to show; the drawer
// slides in on that answer (life cycle: logic.js, drawerNext). Until then the mapped window is kept out of sight.
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Mtk from 'gi://Mtk';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {PANEL, call} from './dbus.js';
import {_} from './i18n.js';
import {DRAWER_INITIAL, drawerNext, nextRespawnDelay, panelGeometry, shouldHideOnFocus} from './logic.js';
import {drawerMoving, placeDrawer, slideDrawer, stopDrawer} from './drawer-motion.js';

const PANEL_DIR = GLib.build_filenamev([GLib.get_user_data_dir(), 'google-hub', 'panel']);
const ARGV = ['/usr/bin/python3', '-W', 'ignore', '-m', 'google_hub_panel'];
const FOCUS_GRACE_MS = 150;
// Show is answered by the panel when its view is ready, however long the page takes (the panel bounds the wait on
// WebKit's own progress reports); a panel that dies fails the call at once.
const NO_TIMEOUT = GLib.MAXINT32;

export class PanelController {
    constructor(settings, onVisibleChanged = () => {}) {
        this._settings = settings;
        this._onVisibleChanged = onVisibleChanged;
    }

    enable() {
        this._enabled = true;
        this._state = DRAWER_INITIAL;
        this._request = 0;
        this._answered = false;
        this._lastShow = null;
        this._shown = [];
        this._animateHide = true;
        this._keepAlive = null;
        this._window = null;
        this._pending = null;
        this._client = null;
        this._failures = [];
        this._respawnId = 0;
        this._createdId = global.display.connect('window-created', (_d, w) => this._onCreated(w));
        this._mapId = global.window_manager.connect_after('map', (_wm, actor) => this._onMap(actor));
        this._monitorsId = Main.layoutManager.connect('monitors-changed', () => this._onMonitorsChanged());
        // Visible drawer: it hides when the focus goes elsewhere (after it had it, with a grace delay).
        this._hadFocus = false;
        this._focusBefore = null;
        this._graceId = 0;
        this._focusId = global.display.connect('notify::focus-window', () => this._onFocusChanged());
        // The panel takes calls once it owns its name: its first Show is asked then (and again after a respawn).
        this._nameId = Gio.bus_watch_name_on_connection(Gio.DBus.session, PANEL.name, Gio.BusNameWatcherFlags.NONE,
            () => this._dispatch('spawned'), null);
        this._spawn();
    }

    disable() {
        this._enabled = false;
        Gio.bus_unwatch_name(this._nameId);
        this._request++; // pending answers are ignored
        this._settle('failed');
        global.display.disconnect(this._createdId);
        global.window_manager.disconnect(this._mapId);
        Main.layoutManager.disconnect(this._monitorsId);
        global.display.disconnect(this._focusId);
        if (this._graceId)
            GLib.source_remove(this._graceId);
        if (this._respawnId)
            GLib.source_remove(this._respawnId);
        stopDrawer(this._window?.get_compositor_private());
        this._dropKeepAlive();
        this._client?.get_subprocess()?.force_exit();
        this._client = null;
        this._window = null;
        this._focusBefore = null;
    }

    // What the user asked for; the drawer itself is in sight once the panel has answered Show.
    get isVisible() {
        return this._state.wanted;
    }

    get phase() {
        return this._state.phase;
    }

    get lastShow() {
        return this._lastShow;
    }

    // True when some part of the drawer can be seen on a monitor.
    get inSight() {
        const actor = this._window?.get_compositor_private();
        if (!actor?.visible || actor.opacity === 0)
            return false;
        const [x, y] = actor.get_transformed_position();
        const [w, h] = actor.get_transformed_size();
        const rect = new Mtk.Rectangle({x: Math.round(x), y: Math.round(y), width: Math.round(w), height: Math.round(h)});
        return Main.layoutManager.monitors.some(m =>
            rect.intersect(new Mtk.Rectangle({x: m.x, y: m.y, width: m.width, height: m.height}))[0]);
    }

    get window() {
        return this._window;
    }

    get running() {
        return Boolean(this._client);
    }

    _spawn() {
        const launcher = new Gio.SubprocessLauncher({flags: Gio.SubprocessFlags.NONE});
        launcher.setenv('PYTHONPATH', PANEL_DIR, true);
        const url = this._settings.get_string('panel-url');
        launcher.set_cwd(GLib.get_home_dir());
        let client;
        try {
            client = Meta.WaylandClient.new_subprocess(global.context, launcher, url ? [...ARGV, '--url', url] : ARGV);
        } catch (e) {
            console.error(`google-hub: cannot start the drawer (${e.message})`);
            return;
        }
        this._client = client;
        const proc = client.get_subprocess();
        proc.wait_async(null, (p, res) => {
            try {
                p.wait_finish(res);
            } catch {}
            if (!this._enabled || this._client !== client)
                return;
            this._client = null;
            this._window = null;
            this._pending = null;
            this._request++;
            this._answered = false;
            this._dropKeepAlive();
            this._dispatch('exited');
            const now = Date.now();
            this._failures = [...this._failures.filter(t => now - t < 60000), now];
            this._respawnId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, nextRespawnDelay(this._failures, now), () => {
                this._respawnId = 0;
                this._spawn();
                return GLib.SOURCE_REMOVE;
            });
        });
    }

    // Before the first buffer (xdg_toplevel role just created, parent not known yet): out of the window list,
    // without the Shell's open effect (the drawer motion replaces it), at the drawer size from the first configure.
    // The Google sign-in window is only born from the visible drawer: any window of the client created while no
    // drawer is in place is the drawer.
    _onCreated(w) {
        if (this._window || !this._client?.owns_window(w))
            return;
        this._pending = w;
        w.hide_from_window_list();
        Main.wm.skipNextEffect(w.get_compositor_private());
        const g = this._geometry();
        w.move_resize_frame(false, g.x, g.y, g.width, g.height);
    }

    _onMap(actor) {
        const w = actor.get_meta_window();
        if (!w || !this._client?.owns_window(w))
            return;
        if (w !== this._pending) {
            w.make_above(); // Google sign-in window: a normal window, above the drawer
            return;
        }
        this._pending = null;
        this._window = w;
        w.make_above();
        w.stick();
        w.connect('unmanaged', () => {
            if (this._window !== w)
                return;
            this._window = null;
            this._dropKeepAlive();
        });
        if (this._state.phase === 'requested') {
            this._conceal(actor);
            this._maybeReplied();
        } else {
            this._park(); // mapped without a Show of ours (the panel presented itself)
        }
    }

    // Mapped but out of sight while the panel prepares its first frame. Fully transparent rather than hidden or
    // moved away: Mutter shows a hidden actor again on its own, a translated one would show on a monitor to the
    // right, and a transparent actor is neither painted nor picked (no input lands on it) while its surface still
    // gets frame callbacks (checked in the nested Shell, in and out of the overview: tests/nested).
    _conceal(actor) {
        this._dropKeepAlive();
        actor.opacity = 0;
        // Mutter suspends a window it has not considered visible for 3 s (window.c, SUSPEND_HIDDEN_TIMEOUT_S), which
        // is the case of every window in the overview the session starts in; GTK passes the suspension on and WebKit
        // then hides the page: no frame, Show stalls. A mapped clone makes the window count as visible (the rule that
        // keeps the overview's thumbnails alive, meta-window-actor.c); this one is transparent too.
        this._keepAlive = new Clutter.Clone({source: actor, opacity: 0, width: 1, height: 1});
        Main.uiGroup.add_child(this._keepAlive);
    }

    _reveal(actor) {
        actor.opacity = 255;
        this._dropKeepAlive();
    }

    _dropKeepAlive() {
        this._keepAlive?.destroy();
        this._keepAlive = null;
    }

    // Runs one step of the life cycle (logic.js) and its actions.
    _dispatch(event) {
        const before = this._state;
        const {state, actions} = drawerNext(before, event);
        this._state = state;
        if (state.wanted !== before.wanted)
            this._onVisibleChanged(state.wanted);
        if (event === 'failed' || event === 'exited' || (before.wanted && !state.wanted))
            this._settle(event === 'hide' ? 'cancelled' : 'failed');
        for (const action of actions)
            this[`_${action}`]();
    }

    // Outcome of show() for those who wait for it (ask): 'shown', 'cancelled' or 'failed'.
    _settle(outcome) {
        const waiting = this._shown;
        this._shown = [];
        waiting.forEach(resolve => resolve(outcome));
    }

    _callShow() {
        const request = ++this._request;
        this._answered = false;
        this._asked = GLib.get_monotonic_time();
        call(PANEL, 'Show', null, '(s)', {timeout: NO_TIMEOUT, autoStart: false}).then(([answer]) => {
            if (request !== this._request)
                return;
            this._lastShow = {answer, ms: Math.round((GLib.get_monotonic_time() - this._asked) / 1000)};
            if (answer === 'cancelled') {
                this._dispatch('failed'); // a Hide overtook this Show: nothing is mapped
                return;
            }
            this._answered = true;
            this._maybeReplied();
        }).catch(e => {
            if (request !== this._request)
                return;
            console.error(`google-hub: drawer not shown (${e.message})`);
            this._dispatch('failed');
        });
    }

    // The answer of Show and the map of the window come from two connections, in any order (a status page answers
    // before its first frame): the life cycle moves on once both are here.
    _maybeReplied() {
        if (!this._answered || !this._window)
            return;
        this._answered = false;
        this._dispatch('replied');
    }

    _geometry() {
        const workArea = Main.layoutManager.getWorkAreaForMonitor(global.display.get_current_monitor());
        return panelGeometry(workArea, this._settings.get_int('panel-width'));
    }

    // Monitor unplugged or rearranged: Mutter may move the open window anywhere; stick it back to the right edge.
    _onMonitorsChanged() {
        const w = this._window;
        if (!this._state.wanted || !w)
            return;
        const workArea = Main.layoutManager.getWorkAreaForMonitor(w.get_monitor());
        const g = panelGeometry(workArea, this._settings.get_int('panel-width'));
        w.move_resize_frame(true, g.x, g.y, g.width, g.height);
    }

    _focusKind(fw) {
        if (!fw)
            return 'none';
        if (fw === this._window)
            return 'panel';
        if (this._client?.owns_window(fw))
            return 'same-client';
        if (fw.find_root_ancestor() === this._window)
            return 'transient';
        return 'other';
    }

    _onFocusChanged() {
        const fw = global.display.focus_window;
        if (this._state.phase === 'requested' && fw && this._client?.owns_window(fw)) {
            // Mutter focuses every window it maps, and gives an extension no way to decline (the user time that
            // means "no focus" is not introspected): the drawer prepared out of sight hands the focus straight
            // back; it is activated when it slides in.
            const time = global.display.get_current_time_roundtrip();
            if (this._focusBefore)
                this._focusBefore.focus(time);
            else
                global.display.unset_input_focus(time);
            return;
        }
        if (!fw || !this._client?.owns_window(fw))
            this._focusBefore = fw;
        if (!this._window || !this._state.wanted || this._state.phase !== 'ready')
            return;
        const kind = this._focusKind(global.display.focus_window);
        if (kind === 'panel')
            this._hadFocus = true;
        if (!this._hadFocus || !shouldHideOnFocus(true, {kind}) || this._graceId)
            return;
        this._graceId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, FOCUS_GRACE_MS, () => {
            this._graceId = 0;
            if (this._state.wanted && shouldHideOnFocus(true, {kind: this._focusKind(global.display.focus_window)}))
                this.hide();
            return GLib.SOURCE_REMOVE;
        });
    }

    // Hidden drawer: actor hidden at once (without the Shell's close effect), then window unmapped by the client;
    // Mutter then gives the focus to the next window.
    _park() {
        const w = this._window;
        this._window = null; // a show() before the unmap asks for a new window (Hide then Show, in that order)
        const actor = w?.get_compositor_private();
        if (actor) {
            stopDrawer(actor);
            Main.wm.skipNextEffect(actor);
            actor.hide();
            this._reveal(actor);
        }
        call(PANEL, 'Hide', null, null, {autoStart: false})
            .catch(e => console.error(`google-hub: drawer not hidden (${e.message})`));
        this._dispatch('parked');
    }

    toggle() {
        if (this._state.wanted)
            this.hide();
        else
            this.show();
    }

    // Resolves to 'shown' once the drawer slides in, 'cancelled' if it was closed first, 'failed' if the panel could
    // not show it.
    show() {
        if (this._state.wanted && this._state.phase === 'ready')
            return Promise.resolve('shown');
        this._hadFocus = false;
        return new Promise(resolve => {
            this._shown.push(resolve);
            this._dispatch('show');
        });
    }

    hide({animate = true} = {}) {
        this._animateHide = animate;
        this._dispatch('hide');
        this._animateHide = true;
    }

    _slideOut() {
        const actor = this._window?.get_compositor_private();
        if (!actor) {
            this._park();
            return;
        }
        actor.remove_all_transitions();
        if (!this._animateHide) {
            this._park();
            return;
        }
        // M3E drawer closing (FastEffects, no bounce); reopening on the way resumes without a jump.
        slideDrawer(actor, false, () => {
            if (!this._state.wanted && this._state.phase === 'ready')
                this._park();
        });
    }

    _slideIn() {
        const w = this._window;
        const actor = w?.get_compositor_private();
        if (!actor)
            return;
        const g = this._geometry();
        w.make_above();
        w.move_resize_frame(true, g.x, g.y, g.width, g.height);
        actor.remove_all_transitions();
        this._reveal(actor);
        // Parked drawer: it starts from the edge. Drawer closing: it starts from where it is, with its velocity.
        if (!drawerMoving(actor))
            placeDrawer(actor, false, g.width);
        actor.show();
        // M3E drawer opening (DefaultSpatial; overshoot = stretch from the edge).
        slideDrawer(actor, true, () => {}, g.width);
        w.activate(global.get_current_time());
        this._settle('shown');
    }

    // Shows the drawer then, once its page is ready, sends the question; falls back to the clipboard if the drawer
    // cannot take it. Drawer closed in the meantime: the question is dropped with it.
    async ask(text) {
        const outcome = await this.show();
        if (outcome === 'cancelled')
            return;
        try {
            if (outcome !== 'shown')
                throw new Error('drawer not shown');
            await call(PANEL, 'Ask', new GLib.Variant('(s)', [text]), '(b)', {autoStart: false});
        } catch {
            St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
            Main.notify('Gemini', _('Question copied — paste it into Gemini'));
        }
    }
}
