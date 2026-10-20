# shellcheck shell=bash
# Install steps. Each one is idempotent and changes only the current user's home directory.
# Requires common.sh; REPO_ROOT is the source tree being installed.

# copy_tree SRC DST: DST becomes an exact copy of SRC, without Python bytecode caches, git metadata or screenshots.
copy_tree() {
    local src=$1 dst=$2
    run rm -rf -- "$dst"
    run mkdir -p -- "$dst"
    if ((DRY_RUN)); then return 0; fi
    tar -C "$src" --exclude=__pycache__ --exclude=.git --exclude=./screenshots -cf - . | tar -C "$dst" -xf -
}

# compile_catalogues DIR: po/LANG.po -> DIR/LANG/LC_MESSAGES/google-hub.mo for every language in po/.
compile_catalogues() {
    local po lang
    for po in "$REPO_ROOT"/po/*.po; do
        lang=$(basename "$po" .po)
        run mkdir -p "$1/$lang/LC_MESSAGES"
        run msgfmt --check -o "$1/$lang/LC_MESSAGES/google-hub.mo" "$po"
    done
}

step_model() {
    local model=$DATA/models/$MODEL_NAME
    msg_step "Speech model for dictation"
    if [[ -f $model ]] && echo "$MODEL_SHA1  $model" | sha1sum -c --quiet >/dev/null 2>&1; then
        msg_ok "Whisper model already present ($model)"
        return 0
    fi
    if ! ask "Download the Whisper speech model now (about 466 MB, from huggingface.co)?" y; then
        msg_warn "model skipped: dictation stays off until you run $REINSTALL (or set whisper_model)"
        return 0
    fi
    run mkdir -p "$DATA/models"
    # curl -C - resumes an interrupted download of the .part file.
    run curl -fL -C - --progress-bar -o "$model.part" "$MODEL_URL" || die "model download failed (run $REINSTALL to resume)"
    if ((DRY_RUN)); then return 0; fi
    if ! echo "$MODEL_SHA1  $model.part" | sha1sum -c --quiet >/dev/null 2>&1; then
        rm -f -- "$model.part"
        die "the downloaded model has a wrong SHA-1 checksum; it was deleted, run $REINSTALL"
    fi
    mv -- "$model.part" "$model"
    msg_ok "Whisper model downloaded and checked ($model)"
}

step_files() {
    msg_step "Daemon, Gemini drawer and settings"
    copy_tree "$REPO_ROOT/daemon/google_hub" "$DATA/daemon/google_hub"
    copy_tree "$REPO_ROOT/panel/google_hub_panel" "$DATA/panel/google_hub_panel"
    compile_catalogues "$DATA/locale"
    run mkdir -p "$CONF" "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")" "$UNIT_DIR" "$(dirname "$DBUS_SERVICE")"
    if [[ -f $CONF/keywords.json ]]; then msg_ok "keeping your $CONF/keywords.json"
    else run cp "$REPO_ROOT/daemon/google_hub/defaults/keywords.json" "$CONF/keywords.json"; fi
    if [[ -f $CONF/config.json ]]; then msg_ok "keeping your $CONF/config.json"
    elif ((DRY_RUN)); then printf '    %s[dry run]%s write %s\n' "$C_DIM" "$C_OFF" "$CONF/config.json"
    else
        # The defaults come from the code (google_hub/config.py), never from a second copy here.
        python3 -I - "$REPO_ROOT/daemon" >"$CONF/config.json" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
from google_hub.config import DEFAULTS
print(json.dumps(DEFAULTS, indent=2))
PY
    fi
    run cp "$REPO_ROOT/data/$PANEL_APP_ID.desktop" "$DESKTOP_FILE"
    run cp "$REPO_ROOT/extension/$UUID/icons/google-hub-gemini-symbolic.svg" "$ICON_FILE"
    install_unit "$REPO_ROOT/data/$UNIT" "$UNIT_DIR/$UNIT"
    run cp "$REPO_ROOT/data/$BUS_NAME.service" "$DBUS_SERVICE"
    msg_ok "files installed under $DATA and $CONF"
}

# The unit names the daemon directory where this installer put it, which follows XDG_DATA_HOME ("%" doubled: it
# starts a systemd specifier).
install_unit() {
    local daemon_dir=$DATA/daemon content
    if ((DRY_RUN)); then printf '    %s[dry run]%s write %s\n' "$C_DIM" "$C_OFF" "$2"; return 0; fi
    [[ $daemon_dir != *[\"\\]* ]] || die "the data directory contains a quote or a backslash: $daemon_dir"
    content=$(<"$1")
    printf '%s\n' "${content//@DAEMON_DIR@/${daemon_dir//%/%%}}" >"$2"
}

step_service() {
    msg_step "Background daemon (systemd user service)"
    if ((! SESSION_CHECK)) || ! session_ready; then
        msg_warn "no session bus: the service is enabled at your next login"
        run mkdir -p "$UNIT_DIR/graphical-session.target.wants"
        run ln -sf "$UNIT_DIR/$UNIT" "$UNIT_DIR/graphical-session.target.wants/$UNIT"
        return 0
    fi
    run systemctl --user daemon-reload
    run systemctl --user enable "$UNIT" >/dev/null 2>&1
    if run systemctl --user restart "$UNIT"; then msg_ok "$UNIT running"
    else msg_warn "$UNIT did not start: journalctl --user -u $UNIT"; fi
}

step_extension() {
    msg_step "GNOME Shell extension"
    copy_tree "$REPO_ROOT/extension/$UUID" "$EXT_DIR"
    run glib-compile-schemas "$EXT_DIR/schemas"
    compile_catalogues "$EXT_DIR/locale"
    if ((! SESSION_CHECK)) || ! session_ready; then
        msg_warn "no session bus: enable it after login with: gnome-extensions enable $UUID"
        return 0
    fi
    # The key is edited directly: the running Shell only discovers a freshly copied extension at the next login.
    run python3 -I "$REPO_ROOT/lib/enabled_extensions.py" add "$UUID" >/dev/null
    msg_ok "extension $UUID installed and enabled"
    if [[ $(gsettings get org.gnome.shell disable-user-extensions 2>/dev/null) == true ]]; then
        msg_warn "user extensions are switched off globally (Extensions app, top switch): turn them on"
    fi
}

# Keep a copy of the installed release, so uninstall.sh and verify.sh stay available after a one-line install.
step_source_copy() {
    [[ $(readlink -f "$REPO_ROOT") == "$(readlink -f "$DATA/source" 2>/dev/null)" ]] && return 0
    copy_tree "$REPO_ROOT" "$DATA/source"
}
