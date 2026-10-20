# shellcheck shell=bash
# Removal of what install.sh installed. Only exact paths, never patterns. Requires common.sh.
#
# Removed: the extension, the daemon, the drawer, their catalogues, the service and D-Bus files, the launcher, the
# icon, the copy of the browser history and the daily summary marker.
# Kept unless --purge: settings (config.json, keywords.json), the Gemini sign-in (WebKit profile), the Whisper model,
# and tasks.json (its "pending" queue may hold task changes made offline and not sent yet).

do_uninstall() {
    local purge=$1 path
    msg_step "Removing Omnishell"
    if session_ready && ((SESSION_CHECK)); then
        run python3 -I "$LIB/enabled_extensions.py" remove "$UUID" >/dev/null || msg_warn "could not edit enabled-extensions"
        run systemctl --user disable --now "$UNIT" >/dev/null 2>&1 || true
    fi
    for path in "$EXT_DIR" "$DATA/daemon" "$DATA/panel" "$DATA/locale" "$UNIT_DIR/$UNIT" \
        "$UNIT_DIR/graphical-session.target.wants/$UNIT" "$DBUS_SERVICE" "$DESKTOP_FILE" "$ICON_FILE" \
        "$CACHE/History" "$CACHE/History.tmp" "$STATE"; do
        if [[ -e $path || -L $path ]]; then run rm -rf -- "$path" && msg_ok "removed $path"; fi
    done
    if session_ready && ((SESSION_CHECK)); then run systemctl --user daemon-reload || true; fi
    if ((purge)); then
        for path in "$CONF" "$DATA/webkit" "$DATA/models" "$CACHE"; do
            if [[ -e $path ]]; then run rm -rf -- "$path" && msg_ok "removed $path"; fi
        done
    else
        msg_info "Kept (remove them with --purge):"
        for path in "$CONF" "$DATA/webkit" "$DATA/models" "$CACHE/tasks.json"; do
            [[ -e $path ]] && msg_info "  $path"
        done
    fi
    # Last: the copy of the release this script may be running from.
    if [[ -e $DATA/source ]]; then run rm -rf -- "$DATA/source"; fi
    if ((purge)) && [[ -d $DATA ]] && [[ -z $(ls -A "$DATA") ]]; then run rmdir -- "$DATA"; fi
    msg_ok "Omnishell removed. Log out and back in to unload the extension from the running Shell."
}
