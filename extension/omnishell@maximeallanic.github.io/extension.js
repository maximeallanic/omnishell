import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

import {stopAll} from './m3e/animate.js';
import {_, setGettext} from './i18n.js';
import {Control} from './control.js';
import {NetworkState} from './network.js';
import {PanelController} from './panel.js';
import {SearchProviders} from './search.js';
import {TasksSection} from './tasks-menu.js';
import {VoicePill} from './voice-pill.js';

export default class Omnishell extends Extension {
    enable() {
        setGettext(this.gettext.bind(this), this.ngettext.bind(this));
        this._settings = this.getSettings();
        this._net = new NetworkState(() => this._updateAvailability());
        // Top-bar button pressed (:checked, like Activities in the overview) while the drawer is visible.
        this._panel = new PanelController(this._settings, visible => {
            if (visible)
                this._button?.add_style_pseudo_class('checked');
            else
                this._button?.remove_style_pseudo_class('checked');
        });
        this._panel.enable();
        this._search = new SearchProviders(this.dir, text => this._ask(text), () => this._net.available);
        this._search.enable();
        this._tasks = new TasksSection();
        this._tasks.enable();
        this._voice = new VoicePill(text => this._ask(text));
        this._voice.enable();

        this._button = new PanelMenu.Button(0.5, 'Omnishell', true);
        this._button.add_child(new St.Icon({
            gicon: Gio.FileIcon.new(this.dir.get_child('icons').get_child('omnishell-gemini-symbolic.svg')),
            style_class: 'system-status-icon',
        }));
        const click = new Clutter.ClickGesture();
        click.set_recognize_on_press(true);
        click.connect('recognize', () => this._toggle());
        this._button.add_action(click);
        Main.panel.addToStatusArea(this.uuid, this._button);

        const modes = Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW;
        Main.wm.addKeybinding('toggle-panel', this._settings, Meta.KeyBindingFlags.NONE, modes,
            () => this._toggle());
        Main.wm.addKeybinding('voice', this._settings, Meta.KeyBindingFlags.NONE, modes,
            () => this._onVoice());

        // Lock screen: the extension stays enabled (the drawer and its conversation survive), but nothing is
        // reachable while the screen is locked, not even the D-Bus control interface.
        this._modeId = Main.sessionMode.connect('updated', () => this._onSessionMode());
        this._onSessionMode();
        this._updateAvailability();
    }

    // The control interface exists only while unlocked; the *Debug test hooks only on the nested test bench,
    // whose tests/nested/run.sh adds the omnishell-bench key to a copy of metadata.json (never present once installed).
    _createControl() {
        return new Control({
            toggle: () => this._toggle(),
            ask: text => this._ask(text),
            voice: () => this._onVoice(),
            state: () => this._state(),
            search: text => this._search.debug(text),
            // Tests: the nested Shell starts in the overview, where no window actor is painted.
            overview: shown => {
                if (shown)
                    Main.overview.show();
                else
                    Main.overview.hide();
            },
            // Tests: gives the focus to the window with this title ("" = no window).
            focus: title => {
                const time = global.display.get_current_time_roundtrip();
                const win = title && global.get_window_actors().map(a => a.meta_window).find(w => w.get_title() === title);
                if (win)
                    win.activate(time);
                else
                    global.display.unset_input_focus(time);
            },
        }, 'omnishell-bench' in this.metadata);
    }

    _state() {
        const actor = this._panel.window?.get_compositor_private();
        return {
            panelVisible: this._panel.isVisible,
            panelPhase: this._panel.phase,
            overview: Main.overview.visible,
            panelLastShow: this._panel.lastShow,
            panelInSight: this._panel.inSight,
            buttonChecked: this._button.has_style_pseudo_class('checked'),
            panelProcess: this._panel.running,
            panelWindow: Boolean(this._panel.window),
            panelActorVisible: Boolean(actor?.visible),
            panelRect: this._panel.window ? (r => [r.x, r.y, r.width, r.height])(this._panel.window.get_frame_rect()) : null,
            skipTaskbar: Boolean(this._panel.window?.skip_taskbar),
            geminiAvailable: this._net.available,
            buttonSensitive: this._button.reactive,
            focusIsPanel: Boolean(this._panel.window) && global.display.focus_window === this._panel.window,
            focusTitle: global.display.focus_window?.get_title() ?? null,
            tasksRows: this._tasks?.actor ? this._tasks._list.get_children().map(a => a.text ?? a.get_children?.()[1]?.child?.get_children?.()[0]?.text ?? a.child?.text ?? '?') : null,
            tasksInDateMenu: Boolean(this._tasks?.actor?.get_parent()),
            pill: this._voice?._container ? this._voice._label.text : null,
        };
    }

    // Offline: icon at 38 % opacity, Gemini and dictation refused with an OSD bubble (an open drawer can still close).
    _updateAvailability() {
        const available = this._net.available;
        this._button.setSensitive(available);
        // Disabled M3 button: content at 38 % (IconButton.DisabledOpacity).
        this._button.opacity = available ? 255 : Math.round(0.38 * 255);
    }

    _offline() {
        if (this._net.available)
            return false;
        Main.osdWindowManager.showOne(global.display.get_current_monitor(),
            Gio.ThemedIcon.new('network-offline-symbolic'), _('Gemini is unavailable offline'));
        return true;
    }

    // Panel, question and dictation are refused while the screen is locked, whatever the caller.
    _toggle() {
        if (Main.sessionMode.isLocked)
            return;
        if (this._panel.isVisible || !this._offline())
            this._panel.toggle();
    }

    _ask(text) {
        if (!Main.sessionMode.isLocked && !this._offline())
            this._panel.ask(text);
    }

    _onSessionMode() {
        const locked = Main.sessionMode.isLocked;
        this._button.visible = !locked;
        if (locked) {
            this._control?.destroy();
            this._control = null;
            this._panel.hide({animate: false});
            this._voice.cancel();
        } else {
            this._control ??= this._createControl();
        }
    }

    disable() {
        Main.sessionMode.disconnect(this._modeId);
        this._net.destroy();
        this._net = null;
        this._control?.destroy();
        this._control = null;
        this._search.disable();
        this._search = null;
        this._tasks.disable();
        this._tasks = null;
        this._voice.disable();
        this._voice = null;
        Main.wm.removeKeybinding('toggle-panel');
        Main.wm.removeKeybinding('voice');
        this._button.destroy();
        this._button = null;
        this._panel.disable();
        this._panel = null;
        this._settings = null;
        // M3E springs (this extension's m3e/ copy): the drawer and the pill were already put away above.
        stopAll();
    }

    _onVoice() {
        if (!Main.sessionMode.isLocked && !this._offline())
            this._voice.start();
    }
}
