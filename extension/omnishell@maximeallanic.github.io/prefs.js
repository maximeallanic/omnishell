import Adw from 'gi://Adw';
import Gio from 'gi://Gio';

import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

// Preferences window (Extensions app, or `gnome-extensions prefs`). The keyboard shortcuts and the drawer keys stay
// in GSettings only: see docs/configuration.md.
export default class OmnishellPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage();
        const search = new Adw.PreferencesGroup({title: _('Search')});
        const suggestions = new Adw.SwitchRow({
            title: _('Google suggestions'),
            // Translators: subtitle of the "Google suggestions" switch in the preferences window.
            subtitle: _('Sends what you type in the search to Google as you type, to suggest searches. When off, nothing you type is sent until you pick a result.'),
        });
        settings.bind('search-suggestions', suggestions, 'active', Gio.SettingsBindFlags.DEFAULT);
        search.add(suggestions);
        page.add(search);
        window.add(page);
        window._settings = settings; // kept alive with the window, as the binding needs it
    }
}
