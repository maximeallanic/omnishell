// D-Bus control interface (scripts, verify.sh, nested-Shell tests).
// Exported only while the session is unlocked (extension.js creates and destroys it with the session mode).
// The *Debug methods (focus, overview, search) are only exported on the nested test bench, where the Shell's
// unsafe mode is also switched on so that the bench driver can use org.gnome.Shell.Eval and Screenshot.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const NAME = 'io.github.maximeallanic.GoogleHubShell';
const PATH = '/io/github/maximeallanic/GoogleHubShell';
const METHODS = `
  <method name="Ping"/>
  <method name="Toggle"/>
  <method name="Ask"><arg type="s" name="text" direction="in"/></method>
  <method name="Voice"/>
  <method name="GetState"><arg type="s" name="json" direction="out"/></method>`;
const DEBUG_METHODS = `
  <method name="OverviewDebug"><arg type="b" name="shown" direction="in"/></method>
  <method name="FocusDebug"><arg type="s" name="title" direction="in"/></method>
  <method name="SearchDebug"><arg type="s" name="text" direction="in"/><arg type="s" name="json" direction="out"/></method>`;

export class Control {
    // debug: true only on the nested test bench; it exports the test hooks handlers.overview/focus/search.
    constructor(handlers, debug) {
        const xml = `<node><interface name="${NAME}">${METHODS}${debug ? DEBUG_METHODS : ''}
</interface></node>`;
        const impl = {
            Ping: () => {},
            Toggle: () => handlers.toggle(),
            Ask: text => handlers.ask(text),
            Voice: () => handlers.voice(),
            GetState: () => JSON.stringify(handlers.state()),
        };
        if (debug) {
            global.context.unsafe_mode = true;
            Object.assign(impl, {
                OverviewDebug: shown => handlers.overview(shown),
                FocusDebug: title => handlers.focus(title),
                SearchDebugAsync: ([text], invocation) => {
                    handlers.search(text)
                        .then(r => invocation.return_value(new GLib.Variant('(s)', [JSON.stringify(r)])))
                        .catch(e => invocation.return_error_literal(Gio.DBusError, Gio.DBusError.FAILED, e.message));
                },
            });
        }
        this._impl = Gio.DBusExportedObject.wrapJSObject(xml, impl);
        this._impl.export(Gio.DBus.session, PATH);
        this._own = Gio.bus_own_name_on_connection(Gio.DBus.session, NAME, Gio.BusNameOwnerFlags.NONE, null, null);
    }

    destroy() {
        Gio.bus_unown_name(this._own);
        this._impl.unexport();
    }
}
