# Refresh retained built-in News tutorials

This optional homebrew helper addresses Russian tutorial article content that can
remain even when the News interface and LocalNews SD overlay are Ukrainian.
The installed LocalNews overlay was read back and confirmed identical to the build.
This makes recopying that overlay unnecessary, but does not by itself prove the
origin of every retained article or establish the helper's device compatibility.

**Status:** compiled for Switch; parser/rewrite tests pass on the host. The actual
23.0.1 News-service update still needs a console run. This is separate from the
already confirmed system user-picker pilot. Do not claim News is fixed yet.

## Behavior

- Supports only firmware 23.0.1. Uses libnx News services; no network or keys.
- Reads the device News index and selects non-user records from nx_notice.
- Processes only Russian articles whose subjects match the known firmware tutorial
  subjects (or their translated equivalents). Other articles are skipped.
- Replaces exact known text only in subject.text, topic_name, body.text, footer.text
  and the matching action-text fields. Unknown text, IDs, language, timestamps,
  images, numeric values and unrelated fields are preserved.
- Saves and verifies every original MessagePack article on SD before any posting.
- Waits for **A** before posting. **B / +** exits the inspection without posting.
- Rechecks each live original, posts through newsPostLocalNews, and reads it back.
- On an update/readback failure, attempts to repost and verify the saved originals
  for submitted articles. The log reports how many were restored.
- Never clears the News database, subscriptions or system save directories.

Backups stay under switch/nx-ukrainian-news/backup-*/ and last-run.log records
counts/results. No user IDs or article contents are printed in the log. Keep the
backups until the result is confirmed. Do not commit them or translations.bin.

## Build and test

Generate the private translation table from the existing local firmware and overlay
using the same environment variables as the parent builder:

```sh
python3 news_refresh/prepare_table.py
python3 -m pip install --target "$NX_TRANSLATION_WORKDIR/python-deps" msgpack==1.1.2
python3 news_refresh/test_refresh.py -v
```

The tests compile the exact parser on the host with address/undefined sanitizers.
They check all 41 mappings, idempotence, unrelated topics/languages, opaque binary
images and extensions, varied numeric/container/string sizes, malformed/truncated
data, and rejection of bad mapping tables. Independent Python MessagePack decoding
checks the rewritten object, including fields that must remain unchanged.

Build with devkitPro devkitA64/libnx/switch-tools:

```sh
cd news_refresh
make
```

The initial build used the official devkitpro/devkita64 container, digest
sha256:1fc388c3a0d34bd2045a6dadcb1020e069d5f876a187fd705de14b4440c00282,
without network access during compilation. Only helper source is sent to the
builder, never firmware or keys. See build-info.json for tool versions/hashes.

## Console use

Copy nx-ukrainian-news.nro and the locally generated translations.bin into
switch/nx-ukrainian-news/ on SD. Open hbmenu normally and select **Ukrainian News
Refresh**. It inspects the existing records and verifies backups first. If matching
tutorials are found, press **A** to apply; otherwise inspect the displayed result.
Press **+** after the result to exit, then reopen News and check both article titles
and their bodies. Report any error code instead of resetting system data.

The private text map is generated locally and is excluded from Git. The source
contains no firmware resources, keys, console data or personal paths.
