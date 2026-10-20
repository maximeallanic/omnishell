// "Tasks" section inserted below the events in the clock menu.
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {HUB, call, hubStatus, onHubSignal} from './dbus.js';
import {_, format} from './i18n.js';
import {TASKS_URL, localeTags, taskRows} from './logic.js';

export class TasksSection {
    enable() {
        this._dateMenu = Main.panel.statusArea.dateMenu;
        this._tasks = [];
        this._status = {account: true, online: true, multi_list: false};

        this.actor = new St.BoxLayout({
            style_class: 'events-button google-hub-tasks',
            orientation: Clutter.Orientation.VERTICAL,
            x_expand: true,
        });
        const title = new St.Button({
            style_class: 'google-hub-tasks-title-button',
            child: new St.Label({style_class: 'events-title', text: _('Tasks'), x_align: Clutter.ActorAlign.START}),
            x_align: Clutter.ActorAlign.START,
        });
        title.connect('clicked', () => this._open(TASKS_URL));
        this._list = new St.BoxLayout({style_class: 'events-list', orientation: Clutter.Orientation.VERTICAL});
        this._entry = new St.Entry({
            style_class: 'google-hub-task-entry',
            hint_text: _('+ Add a task'),
            can_focus: true,
            x_expand: true,
        });
        this._entry.clutter_text.connect('activate', () => this._add());
        this.actor.add_child(title);
        this.actor.add_child(this._list);
        this.actor.add_child(this._entry);

        const events = this._dateMenu._eventsItem;
        events.get_parent().insert_child_above(this.actor, events);

        this._openId = this._dateMenu.menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this.refresh();
        });
        this._unsubscribe = onHubSignal('TasksChanged', () => this.refresh());
        this.refresh();
    }

    disable() {
        this._dateMenu.menu.disconnect(this._openId);
        this._unsubscribe();
        this.actor.destroy();
        this.actor = null;
    }

    async refresh() {
        try {
            this._status = await hubStatus();
            [this._tasks] = await call(HUB, 'ListTasks', null, '(aa{sv})');
        } catch (e) {
            console.debug(`google-hub: tasks unavailable (${e.message})`);
            this._status = {...this._status, online: false};
        }
        this._render();
    }

    _render() {
        if (!this.actor)
            return;
        const s = this._status;
        this._list.destroy_all_children();
        for (const row of taskRows(this._tasks, {account: s.account, online: s.online, multiList: s.multi_list,
            locales: localeTags(GLib.get_language_names_with_category('LC_TIME'))}))
            this._list.add_child(this._rowActor(row));
        this._entry.visible = Boolean(s.account);
    }

    _rowActor(row) {
        switch (row.kind) {
        case 'header':
            return new St.Label({style_class: 'google-hub-tasks-header', text: row.title});
        case 'task':
            return this._taskActor(row);
        case 'more':
            return this._linkButton(row.text, () => this._open(TASKS_URL));
        case 'setup':
            return this._linkButton(row.text, () => {
                this._dateMenu.menu.close();
                Gio.Subprocess.new(['gnome-control-center', 'online-accounts'], Gio.SubprocessFlags.NONE);
            });
        default: // offline, undated, empty
            return new St.Label({style_class: 'event-placeholder', text: row.text});
        }
    }

    _linkButton(text, onClick) {
        const b = new St.Button({
            style_class: 'google-hub-tasks-link',
            child: new St.Label({text}),
            x_align: Clutter.ActorAlign.START,
        });
        b.connect('clicked', onClick);
        return b;
    }

    _taskActor(row) {
        const box = new St.BoxLayout({style_class: 'event-box google-hub-task', x_expand: true});
        const check = new St.Button({
            style_class: 'google-hub-task-check',
            child: new St.Icon({icon_name: 'checkbox-symbolic'}), // size: stylesheet.css (XSmall icon button)
            y_align: Clutter.ActorAlign.CENTER,
            accessible_name: format(_('Mark “{title}” as done'), {title: row.title}),
        });
        check.connect('notify::hover', () => {
            check.child.icon_name = check.hover ? 'checkbox-checked-symbolic' : 'checkbox-symbolic';
        });
        check.connect('clicked', () => this._complete(row));
        const text = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL, x_expand: true});
        text.add_child(new St.Label({style_class: 'event-summary', text: row.title}));
        if (row.subtitle)
            text.add_child(new St.Label({style_class: 'event-time', text: row.subtitle}));
        const open = new St.Button({child: text, x_expand: true, x_align: Clutter.ActorAlign.FILL});
        open.connect('clicked', () => this._open(row.link || TASKS_URL));
        box.add_child(check);
        box.add_child(open);
        return box;
    }

    _open(uri) {
        this._dateMenu.menu.close();
        Gio.AppInfo.launch_default_for_uri(uri, null);
    }

    async _complete(row) {
        const before = this._tasks;
        this._tasks = before.filter(t => !(t.id === row.id && t.list === row.list));
        this._render();
        try {
            await call(HUB, 'CompleteTask', new GLib.Variant('(ss)', [row.list, row.id]));
        } catch (e) {
            this._tasks = before;
            this._render();
            Main.notifyError(_('Google Tasks'), e.message.replace(/^GDBus\.Error:[^ ]+ /, ''));
        }
    }

    async _add() {
        const text = this._entry.text.trim();
        if (!text)
            return;
        this._entry.text = '';
        try {
            await call(HUB, 'AddTask', new GLib.Variant('(s)', [text]), '(a{sv})');
            this.refresh();
        } catch (e) {
            this._entry.text = text;
            Main.notifyError(_('Google Tasks'), e.message.replace(/^GDBus\.Error:[^ ]+ /, ''));
        }
    }
}
