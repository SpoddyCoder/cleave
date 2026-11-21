#!/usr/bin/env bash
# Back up every Cleave user folder to a dated folder in your home directory,
# then delete the originals so the next run starts from a clean slate.
#
# Folders (see cleave/paths.py and cleave/user_config.py):
#   Data      $XDG_DATA_HOME/cleave or ~/.local/share/cleave, or $CLEAVE_DATA
#             when set (projects, presets, textures, themes, models, CUDA
#             download, cleave.db)
#   Settings  $XDG_CONFIG_HOME/cleave or ~/.config/cleave (config.yaml,
#             crash log)
#
# The checkout and the conda env are left alone.
# Nothing is deleted unless every backup copy succeeds.

set -u

fail() {
    echo
    exit 1
}

if pgrep -f -- '(-m cleave|cleave\.py)( |$)' >/dev/null 2>&1; then
    echo "Cleave is running. Close it and run this script again."
    fail
fi

if [ -n "${CLEAVE_DATA:-}" ]; then
    DATA_DIR="$CLEAVE_DATA"
elif [ -n "${XDG_DATA_HOME:-}" ]; then
    DATA_DIR="$XDG_DATA_HOME/cleave"
else
    DATA_DIR="$HOME/.local/share/cleave"
fi
if [ -n "${XDG_CONFIG_HOME:-}" ]; then
    SETTINGS_DIR="$XDG_CONFIG_HOME/cleave"
else
    SETTINGS_DIR="$HOME/.config/cleave"
fi

STAMP="$(date +%Y%m%d-%H%M%S)" || {
    echo "Could not read the date and time."
    fail
}
BACKUP="$HOME/Cleave-backup-$STAMP"

# Refuse folders whose deletion would take far more than Cleave's data.
for dir in "$DATA_DIR" "$SETTINGS_DIR"; do
    resolved="$(realpath -m -- "$dir")"
    case "$resolved" in
        / | "$(realpath -m -- "$HOME")" | "$(realpath -m -- "$HOME")/.config" | "$(realpath -m -- "$HOME")/.local/share")
            echo "Refusing to delete $resolved. Check CLEAVE_DATA, XDG_DATA_HOME, and XDG_CONFIG_HOME."
            fail
            ;;
    esac
done

echo
echo "Cleave folders found:"
found=0
for dir in "$DATA_DIR" "$SETTINGS_DIR"; do
    if [ -d "$dir" ]; then
        echo "  $dir"
        found=1
    fi
done
if [ "$found" -eq 0 ]; then
    echo "  none. Nothing to back up or delete."
    echo
    exit 0
fi
echo
echo "Backup to: $BACKUP"
echo
read -r -p "Back up these folders, then DELETE them [y/N]? " answer
case "$answer" in
    [Yy] | [Yy][Ee][Ss]) ;;
    *)
        echo "Cancelled. Nothing changed."
        echo
        exit 0
        ;;
esac

mkdir -p -- "$BACKUP" || fail

backup() {
    # $1 source folder, $2 name of the copy under the backup folder.
    [ -d "$1" ] || return 0
    echo
    echo "Copying $1"
    cp -a -- "$1" "$BACKUP/$2"
}

if ! backup "$DATA_DIR" "Data" || ! backup "$SETTINGS_DIR" "Settings"; then
    echo
    echo "A backup copy failed. Nothing was deleted."
    echo "Partial backup: $BACKUP"
    fail
fi

echo
echo "Backup complete. Deleting originals..."
left=0
for dir in "$DATA_DIR" "$SETTINGS_DIR"; do
    [ -d "$dir" ] || continue
    echo "  $dir"
    rm -rf -- "$dir"
    [ -d "$dir" ] && left=1
done
if [ "$left" -eq 1 ]; then
    echo
    echo "Some folders could not be fully deleted. Close anything using them"
    echo "and delete them by hand. The backup is complete."
    fail
fi

echo
echo "Done. Backup: $BACKUP"
if [ -n "${CLEAVE_DATA:-}" ]; then
    echo "Note: CLEAVE_DATA is still set to $CLEAVE_DATA"
    echo "Unset it to use the default data folder."
fi
echo
