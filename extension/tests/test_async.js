// Run: gjs -m tests/test_async.js (from extension/)
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {untilCancelled} from '../omnishell@maximeallanic.github.io/async.js';

function eq(a, b, name) {
    if (JSON.stringify(a) !== JSON.stringify(b)) {
        printerr(`FAIL ${name}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`);
        imports.system.exit(1);
    }
}
const later = (ms, v) => new Promise(r => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => (r(v), GLib.SOURCE_REMOVE)));
const loop = new GLib.MainLoop(null, false);

(async () => {
    eq(await untilCancelled(later(10, 'x'), null), 'x', 'no cancellable');
    eq(await untilCancelled(later(10, 'x'), new Gio.Cancellable()), 'x', 'not cancelled');
    const c = new Gio.Cancellable();
    const t0 = GLib.get_monotonic_time();
    const p = untilCancelled(later(500, 'x'), c);
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 20, () => (c.cancel(), GLib.SOURCE_REMOVE));
    eq(await p, null, 'cancelled: null');
    eq((GLib.get_monotonic_time() - t0) < 200000, true, 'cancelled: without waiting for the reply');
    const c2 = new Gio.Cancellable();
    c2.cancel();
    eq(await untilCancelled(later(500, 'x'), c2), null, 'already cancelled');
    print('OK');
    loop.quit();
})().catch(e => {
    printerr(e);
    imports.system.exit(1);
});
loop.run();
