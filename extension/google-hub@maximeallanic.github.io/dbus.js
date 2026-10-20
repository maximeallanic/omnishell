// D-Bus calls to the daemon (D-Bus activatable) and to the drawer (never auto-started).
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

Gio._promisify(Gio.DBusConnection.prototype, 'call');

export const HUB = {name: 'io.github.maximeallanic.GoogleHub', path: '/io/github/maximeallanic/GoogleHub', iface: 'io.github.maximeallanic.GoogleHub'};
export const PANEL = {name: 'io.github.maximeallanic.GoogleHubPanel', path: '/io/github/maximeallanic/GoogleHubPanel', iface: 'io.github.maximeallanic.GoogleHubPanel'};

export async function call(target, method, params = null, replyType = null, {timeout = 10000, autoStart = true, cancellable = null} = {}) {
    const reply = await Gio.DBus.session.call(target.name, target.path, target.iface, method, params,
        replyType ? new GLib.VariantType(replyType) : null,
        autoStart ? Gio.DBusCallFlags.NONE : Gio.DBusCallFlags.NO_AUTO_START, timeout, cancellable);
    return reply ? reply.recursiveUnpack() : null;
}

export async function hubProperty(name, {timeout = 10000} = {}) {
    const [value] = await Gio.DBus.session.call(HUB.name, HUB.path, 'org.freedesktop.DBus.Properties', 'Get',
        new GLib.Variant('(ss)', [HUB.iface, name]), new GLib.VariantType('(v)'),
        Gio.DBusCallFlags.NONE, timeout, null).then(r => r.recursiveUnpack());
    return value;
}

export function hubStatus() {
    return hubProperty('Status', {timeout: 5000});
}

// Subscribes to a daemon signal; returns the unsubscribe function.
export function onHubSignal(name, callback) {
    const id = Gio.DBus.session.signal_subscribe(HUB.name, HUB.iface, name, HUB.path, null,
        Gio.DBusSignalFlags.NONE, (_c, _s, _p, _i, _n, params) => callback(params.recursiveUnpack()));
    return () => Gio.DBus.session.signal_unsubscribe(id);
}

export function isCancelled(e) {
    return e instanceof GLib.Error && e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED);
}
