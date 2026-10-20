// Network state for Gemini (same rule as the drawer: full connectivity, no captive portal).
import Gio from 'gi://Gio';

import {geminiAvailable} from './logic.js';

export class NetworkState {
    constructor(onChange) {
        this._monitor = Gio.NetworkMonitor.get_default();
        this.available = this._compute();
        const update = () => {
            const now = this._compute();
            if (now !== this.available) {
                this.available = now;
                onChange(now);
            }
        };
        this._ids = [
            this._monitor.connect('network-changed', update),
            this._monitor.connect('notify::connectivity', update),
        ];
    }

    _compute() {
        return geminiAvailable(this._monitor.network_available, this._monitor.connectivity);
    }

    destroy() {
        this._ids.forEach(id => this._monitor.disconnect(id));
    }
}
