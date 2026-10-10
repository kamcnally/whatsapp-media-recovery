# WhatsApp media re-linker

Recover media from an old pre-E2EE WhatsApp Google Drive backup without restoring it in the app, which wipes chats received since.

Matches downloaded files against hashes in your current `msgstore.db`, then copies them to the paths the database expects, ready to push to the phone.

## Safety warnings

- **Turn off automatic Google Drive backup first** (Settings > Chats > Chat backup > Back up to Google Drive > Never). The next backup overwrites the old one.
- **Finish the Drive download (step 2) before enabling E2EE backup (step 3).** A new Drive backup replaces the old one. Keep Drive backup on Never in step 3. Re-check the old backup's date and size under Drive > Settings > Manage backups.
- **A master token is as sensitive as your Google password.** Revoke it afterwards at <https://myaccount.google.com/permissions>.
- **Repeated failed logins can lock your account.** After two failures, switch method.
- **`msgstore.db` and the E2EE key expose your whole chat history.** Keep them private and out of git. Check `git status` before every commit.

## How it works

Each `message_media` row stores the expected `file_path` and `file_hash` (base64 SHA-256). Filenames differ per device, so matching is by content hash. `original_file_hash` is also checked, for transcoded copies.

## Limits

- Media shows in a chat only if the current database references it. Files for messages that exist only in the old backup are downloaded but never matched.
- The old backup's `msgstore.db.crypt14` is ignored (decrypting needs root).
- No full Drive restore in the app (wipes recent chats). No wabdd (needs an E2EE `.crypt15` backup).
- Placeholder re-linking confirmed on one device only. Test one file before a bulk push.

## Requirements

Python 3.8+, `sqlite3`, `adb` (USB debugging on), Google account with 2-step verification.

## 1. Prepare

Use a virtualenv so the pip packages never touch system libraries. Keep it activated for every later step (re-run `. .venv/bin/activate` in a new shell).

The downloader is a separate GPL project, so it is cloned (git-ignored), not vendored. Commit pinned:

```bash
git clone https://github.com/kamcnally/WhatsApp-GD-Extractor-Multithread downloader
git -C downloader checkout cbcffac2e8b1e1a854da06889938acea31b21328
python3 -m venv .venv && . .venv/bin/activate
pip install -r downloader/requirements.txt
pip install -U gpsoauth
adb shell settings get secure android_id
mkdir work && cp settings.cfg.example work/settings.cfg
```

Set `gmail` and `android_id` in `work/settings.cfg`.

## 2. Download the Drive backup

Authenticate with a master token (app passwords no longer work, hence the fork):

1. Open <https://accounts.google.com/EmbeddedSetup>, log in, click "I agree", let it hang.
2. DevTools > Application > Cookies > accounts.google.com: copy `oauth_token`. Short-lived, single use.
3. Straight away: `cd work && python3 ../downloader/get_master_token.py` and paste it.
4. Put the printed `aas_et/...` value in `master_token =`.

If you get `Error: Need Browser`, visit <https://accounts.google.com/b/0/DisplayUnlockCaptcha> and retry.

The downloader writes to the **current directory**, so run it from `work/`:

```bash
cd work
python3 ../downloader/WhatsAppGDExtract.py info    # confirm backup date and size
python3 ../downloader/WhatsAppGDExtract.py list    # file names
python3 ../downloader/WhatsAppGDExtract.py sync    # download
md5sum --check md5sum.txt
cd ..
```

Answer `y` to the backup you checked. Re-running `sync` resumes. HTTP errors are printed, not fatal: use `md5sum --check` to find failed files.

## 3. Decrypt a current database

Only after step 2 is verified. With the venv active, enable E2EE backup, save the 64-digit key in a password manager, back up with Drive on Never, then copy `msgstore-*.crypt15` from `Android/media/com.whatsapp/WhatsApp/Databases/`:

```bash
pip install wa-crypt-tools
wadecrypt <64-digit-key> msgstore.db.crypt15 msgstore.db
sqlite3 msgstore.db "select count(*) from message_media;"
```

## 4. Export expected hashes

```bash
sqlite3 -init /dev/null -tabs -noheader msgstore.db "
select coalesce(file_hash,''), coalesce(original_file_hash,''), file_path
from message_media
where file_path is not null and file_path <> '';" > expected-all.tsv
```

`-init /dev/null` stops a personal `~/.sqliterc` changing output mode (box or table mode breaks the TSV).

## 5. Match

```bash
python3 match.py work expected-all.tsv out-all
```

Hashes every non-JSON file under `work/` (layout irrelevant), prints `hashed N unique files, overlap M`, copies each match to `out-all/<expected path>` (skipping existing files), and writes `missing.txt` to the current directory.

- Paths are cut to start at their `Media/` segment. Absolute paths with no `Media/` segment go under `out-all/other/`; delete it before pushing.
- Media expected at several paths is copied once per path.

Back up `out-all` before touching the phone.

## 6. Diagnose gaps

`missing.txt` lists expected paths not found. Look for a pattern:

```bash
sed -E 's#(Media/[^/]+(/Sent)?)/.*#\1#' missing.txt | sort | uniq -c | sort -rn   # category
sed -n 's/.*\.\([A-Za-z0-9]*\)$/\L\1/p' missing.txt | sort | uniq -c | sort -rn   # extension
grep -oE '(IMG|VID)-[0-9]{4}' missing.txt | cut -d- -f2 | sort | uniq -c           # year
```

One category, extension or year usually means the backup never held those files. Failed downloads show in `md5sum --check md5sum.txt`. If overlap is 0, check the TSV is tab-separated (`head -3 expected-all.tsv | cat -A`) and that a known file's hash (`openssl dgst -sha256 -binary <file> | base64`) exists in `message_media.file_hash`.

## 7. Push to the phone

Delete `out-all/other` if present. Then:

1. Check the phone has room for a second copy of `out-all`: `adb shell df -h /sdcard`.
2. Push without overwriting. The script force-stops WhatsApp, stages the files, copies with `cp -rn`, then deletes the staging folder:

   ```bash
   scripts/push-staged.sh out-all/Media
   ```
3. **Force stop WhatsApp again and clear its cache. Do not clear data.** Settings > Apps > WhatsApp > Force stop, then Storage > Clear cache. Otherwise WhatsApp ignores the files.
4. Reopen WhatsApp.

Test one file first and check the message in the chat. If Syncthing syncs this `Media` folder, pause it before a large push.
