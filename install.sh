#!/bin/sh
# Installs token-usage into its own virtualenv and links the commands into ~/.local/bin.
#
#   curl -fsSL https://raw.githubusercontent.com/leoalmeidasa/token-usage/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/leoalmeidasa/token-usage/main/install.sh | sh -s -- --tray --autostart
#
# Options:
#   --tray        also install the tray / top bar icon
#   --autostart   start with the session (the icon with --tray, otherwise the dashboard)
#   --uninstall   remove everything this script installed
set -eu

REPO="leoalmeidasa/token-usage"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/token-usage"
VENV="$DATA/venv"
BIN="$HOME/.local/bin"
TRAY=0
AUTOSTART=0
UNINSTALL=0

die() { echo "error: $*" >&2; exit 1; }

for arg in "$@"; do
    case "$arg" in
        --tray) TRAY=1 ;;
        --autostart) AUTOSTART=1 ;;
        --uninstall) UNINSTALL=1 ;;
        *) die "unknown option: $arg (use --tray, --autostart or --uninstall)" ;;
    esac
done

if [ "$UNINSTALL" = 1 ]; then
    if [ -x "$VENV/bin/token-usage" ]; then
        "$VENV/bin/token-usage" autostart --remove || true
    fi
    rm -f "$BIN/token-usage" "$BIN/token-usage-tray"
    rm -rf "$DATA"
    echo "token-usage removed"
    exit 0
fi

PY=$(command -v python3 || true)
[ -n "$PY" ] || die "python3 not found; install Python 3.10 or newer"
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || die "Python 3.10 or newer is required ($("$PY" --version 2>&1) found)"

# run from a checkout: install that code; piped from curl: the main branch
SRC="https://github.com/$REPO/archive/refs/heads/main.zip"
case "$0" in
    *install.sh)
        dir=$(cd "$(dirname "$0")" && pwd)
        if [ -f "$dir/pyproject.toml" ]; then SRC="file://$dir"; fi
        ;;
esac

SPEC="token-usage @ $SRC"
VENV_OPTS=""
if [ "$TRAY" = 1 ]; then
    SPEC="token-usage[tray] @ $SRC"
    if [ "$(uname -s)" = Linux ]; then
        # PyGObject comes from the distro; the venv sees it through the system site-packages
        if ! "$PY" -c 'import gi' 2>/dev/null; then
            echo "The tray icon on Linux needs PyGObject with AppIndicator. Install it and run this again:" >&2
            echo "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1" >&2
            echo "  Fedora:        sudo dnf install python3-gobject libayatana-appindicator-gtk3" >&2
            echo "  Arch:          sudo pacman -S python-gobject libayatana-appindicator" >&2
            exit 1
        fi
        VENV_OPTS="--system-site-packages"
    fi
fi

echo "Installing token-usage into $VENV"
mkdir -p "$DATA" "$BIN"
rm -rf "$VENV"
# shellcheck disable=SC2086
"$PY" -m venv $VENV_OPTS "$VENV" \
    || die "could not create the virtualenv (on Debian/Ubuntu: sudo apt install python3-venv)"
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check "$SPEC"

ln -sf "$VENV/bin/token-usage" "$BIN/token-usage"
if [ "$TRAY" = 1 ]; then
    ln -sf "$VENV/bin/token-usage-tray" "$BIN/token-usage-tray"
fi

if [ "$AUTOSTART" = 1 ]; then
    if [ "$TRAY" = 1 ]; then
        "$VENV/bin/token-usage" autostart --tray
    else
        "$VENV/bin/token-usage" autostart
    fi
fi

echo
echo "Done. Run: token-usage --open$([ "$TRAY" = 1 ] && echo "   or: token-usage tray")"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "Note: $BIN is not in your PATH. Add it to your shell profile, or run $BIN/token-usage" ;;
esac
