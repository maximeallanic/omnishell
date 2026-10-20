// "Listening…" pill: dictation by the daemon (Whisper), then the question goes to Gemini.
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {HUB, call, hubProperty, onHubSignal} from './dbus.js';
import {linearIndicator, pillText} from './logic.js';
import {animate} from './m3e/animate.js';

const LEVEL_WIDTH = 120;
const LEVEL_GAP = 4; // LinearProgressIndicator.TrackActiveSpace
const STOP_SIZE = 4; // LinearProgressIndicator.StopSize
// M3E bubble (plain tooltip of Compose, Tooltip.kt): scale 0.8 <-> 1 and opacity, pivot in the centre.
const BUBBLE_SPRINGS = {opacity: 'FastEffects', scale_x: 'FastSpatial', scale_y: 'FastSpatial'};
const BUBBLE_SCALE = 0.8;

export class VoicePill {
    constructor(onText) {
        this._onText = onText;
    }

    enable() {
        this._active = false;
        this._hideId = 0;
        this._unsubscribe = onHubSignal('ListenState', ([state, level]) => {
            if (!this._active)
                return;
            if (state === 'listening' || state === 'transcribing')
                this._set(state, state === 'listening' ? level : 0);
        });
    }

    disable() {
        this._unsubscribe();
        if (this._active)
            call(HUB, 'CancelListen').catch(() => {});
        this._destroyPill({animate: false});
    }

    _build() {
        const mon = Main.layoutManager.currentMonitor;
        this._container = new St.Widget({
            layout_manager: new Clutter.BinLayout(),
            x: mon.x, y: mon.y + Main.panel.height + 12, width: mon.width,
        });
        this._pill = new St.BoxLayout({
            style_class: 'osd-window google-hub-pill',
            x_align: Clutter.ActorAlign.CENTER,
            reactive: true,
            can_focus: true,
        });
        this._icon = new St.Icon({icon_name: 'audio-input-microphone-symbolic', style_class: 'google-hub-pill-icon'});
        this._label = new St.Label({style_class: 'google-hub-pill-label', y_align: Clutter.ActorAlign.CENTER});
        // M3E determinate linear indicator: indicator, gap, track, stop indicator (colours: stylesheet.css).
        const meter = new St.Widget({
            style_class: 'google-hub-level-meter', width: LEVEL_WIDTH, y_align: Clutter.ActorAlign.CENTER,
            layout_manager: new Clutter.FixedLayout(),
        });
        this._level = new St.Widget({style_class: 'google-hub-level', width: 0});
        this._track = new St.Widget({style_class: 'google-hub-level-track', width: LEVEL_WIDTH});
        this._stop = new St.Widget({style_class: 'google-hub-level-stop', x: LEVEL_WIDTH - STOP_SIZE});
        meter.add_child(this._track);
        meter.add_child(this._level);
        meter.add_child(this._stop);
        // The track follows the width of the indicator (driven by a spring): constant gap of 4.
        this._level.connect('notify::width', () => this._layoutTrack());
        this._pill.add_child(this._icon);
        this._pill.add_child(this._label);
        this._pill.add_child(meter);
        this._container.add_child(this._pill);
        Main.layoutManager.uiGroup.add_child(this._container);
        // M3E bubble entrance.
        this._pill.set_pivot_point(0.5, 0.5);
        this._pill.opacity = 0;
        this._pill.set_scale(BUBBLE_SCALE, BUBBLE_SCALE);
        animate(this._pill, {opacity: 255, scale_x: 1, scale_y: 1}, {spring: BUBBLE_SPRINGS});

        this._pill.connect('key-press-event', (_a, event) => {
            const sym = event.get_key_symbol();
            if (sym === Clutter.KEY_Escape)
                call(HUB, 'CancelListen').catch(() => {});
            else if ((sym === Clutter.KEY_g || sym === Clutter.KEY_G) && (event.get_state() & Clutter.ModifierType.MOD4_MASK))
                call(HUB, 'StopListen').catch(() => {});
            return Clutter.EVENT_STOP;
        });
        this._pill.connect('button-press-event', () => {
            call(HUB, 'StopListen').catch(() => {});
            return Clutter.EVENT_STOP;
        });
    }

    _set(state, level = 0) {
        this._label.text = pillText(state);
        // Level: FastEffects, no overshoot (a measurement does not bounce).
        animate(this._level, {width: linearIndicator(level, LEVEL_WIDTH, LEVEL_GAP).active}, {spring: 'FastEffects'});
        this._level.get_parent().visible = state === 'listening';
    }

    _layoutTrack() {
        const w = Math.max(0, this._level.width);
        const start = w > 0 ? Math.min(LEVEL_WIDTH, w + LEVEL_GAP) : 0;
        this._track.x = start;
        this._track.width = Math.max(0, LEVEL_WIDTH - start);
        this._track.visible = this._track.width > 0;
        this._stop.visible = start < LEVEL_WIDTH - STOP_SIZE;
    }

    cancel() {
        if (this._active)
            call(HUB, 'CancelListen').catch(() => {});
    }

    async start() {
        if (this._active) {
            call(HUB, 'StopListen').catch(() => {});
            return;
        }
        this._active = true;
        this._clearHide();
        if (!this._container)
            this._build();
        this._set('listening');
        this._grab = Main.pushModal(this._pill, {actionMode: Shell.ActionMode.POPUP});
        this._pill.grab_key_focus();
        let state = 'empty';
        let text = '';
        try {
            // The daemon publishes its worst case for capture + transcription: a shorter wait would
            // report a failure while it is still transcribing. Constant for a daemon, read once.
            this._listenTimeout ??= await hubProperty('ListenTimeout');
            [text] = await call(HUB, 'Listen', null, '(s)', {timeout: this._listenTimeout});
        } catch (e) {
            state = e.message.includes('Error.AudioCapture') ? 'error:audio-capture' : 'error:network';
        }
        this._release();
        if (text.trim()) {
            this._destroyPill();
            this._onText(text.trim());
            return;
        }
        this._set(state);
        this._hideId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, state === 'empty' ? 1500 : 2000, () => {
            this._hideId = 0;
            this._destroyPill();
            return GLib.SOURCE_REMOVE;
        });
    }

    _release() {
        this._active = false;
        if (this._grab) {
            Main.popModal(this._grab);
            this._grab = null;
        }
    }

    _clearHide() {
        if (this._hideId) {
            GLib.source_remove(this._hideId);
            this._hideId = 0;
        }
    }

    _destroyPill({animate = true} = {}) {
        this._clearHide();
        this._release();
        const container = this._container;
        this._container = null;
        if (!container)
            return;
        if (!animate) {
            container.destroy();
            return;
        }
        // M3E bubble exit, then destruction.
        container.reactive = false;
        animate(this._pill, {opacity: 0, scale_x: BUBBLE_SCALE, scale_y: BUBBLE_SCALE}, {
            spring: BUBBLE_SPRINGS,
            onDone: () => container.destroy(),
        });
    }
}
