#!/usr/bin/env bash
# Push downloaded Media/ to the phone without overwriting existing files.
# Usage: scripts/push-staged.sh work/out/Media
set -euo pipefail
src=${1:?usage: $0 path/to/Media}
media=/sdcard/Android/media/com.whatsapp/WhatsApp/Media
stage=/sdcard/WA-staging

adb shell am force-stop com.whatsapp
adb shell mkdir -p "$stage"
adb push "$src/." "$stage/"
# toybox cp -n never overwrites; the trailing /. merges contents (no Media/Media)
adb shell cp -rn "$stage/." "$media/"
adb shell rm -rf "$stage"
echo "Done. Force stop WhatsApp and clear its cache (not data), then reopen."
