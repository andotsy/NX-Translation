# Refresh retained built-in News articles

This optional homebrew helper addresses Russian tutorial article content that can
remain even when the News interface and LocalNews SD overlay are Ukrainian.
The installed LocalNews overlay was read back and confirmed identical to the build.
This makes recopying that overlay unnecessary, but does not by itself prove the
origin of every retained article or establish the helper's device compatibility.

**Status:** helper 0.1.7 compiles for Switch and passes eleven host tests against all
seven private native captures. Version 0.1.5 translated the six original tutorials;
a subsequent console scan confirms all six are already translated. Version 0.1.6 added translations for the remaining channel-subscription article,
but its post/readback failed; rollback verified the original. Version 0.1.7 updates
only this article's existing file through the journaled News save filesystem, with
a full original file backup, commit/readback checks and recovery on failure.
Its console result is pending. Other unrecognized posts remain untouched.

## Behavior

- Supports only firmware 23.0.1. Uses libnx News services; no network or keys.
- Reads the device News index and selects non-user records from nx_notice.
- Creates a fresh data-service object for every article read and closes it before
  returning, including on exceptions. Closes the index after enumeration. No helper
  reader session remains open during posting or rollback.
- Extracts the first complete MessagePack map from native News data-service buffers.
  Captures prove that bytes beyond the map can retain earlier article data, so
  they must not be posted or included in change/readback comparisons. Original
  backups retain the full returned buffer.
- Keeps standalone parsing strict: malformed maps, non-map roots and nonzero
  trailers outside the explicitly selected native-buffer adapter are rejected.
- Processes only Russian articles whose subjects match the known firmware tutorial
  subjects (or their translated equivalents). Other articles are skipped.
- Replaces exact known text only in subject.text, topic_name, topic_description, body.text, footer.text
  and the matching action-text fields. Unknown text, IDs, language, timestamps,
  images, numeric values and unrelated fields are preserved.
- Saves and verifies every original MessagePack article on SD before any posting.
- Waits for **A** before posting. **B / +** exits the inspection without posting.
- Rechecks each live original, posts the original six tutorials through
  newsPostLocalNews, and reads them back. For article 442 only, pauses background
  News tasks and opens system save 0x8000000000000090 through the filesystem API.
  Its existing record selects one file under /data; exact original content must
  match the service read and be backed up before writing. The database, other
  articles and subscriptions are untouched. It commits and verifies the file,
  then independently verifies it through the News data service. Failed writes,
  commits or file readbacks restore and verify the original. A service readback
  mismatch saves expected/actual bytes privately on SD before rollback.
- On an update/readback failure, verifies originals for every attempted article.
  Already-unchanged originals are not reposted. Any necessary restore posts the
  original serialized map and compares the complete returned article map.
- Never clears the News database, subscriptions or system save directories.

Backups stay under switch/nx-ukrainian-news/backup-*/ and last-run.log records
counts/results. No user IDs or article contents are printed in the log. Keep the
backups until the result is confirmed. Do not commit them or translations.bin.

## Build and test

Generate the private translation table from the existing local firmware and overlay
using the same environment variables as the parent builder. To include the remaining
channel-subscription article, supply its private native MessagePack capture:

```sh
python3 -m pip install --target "$NX_TRANSLATION_WORKDIR/python-deps" msgpack==1.1.2
python3 news_refresh/prepare_table.py --extra-article /path/to/private/article.bin
NX_NEWS_CAPTURE=/path/to/private/article.bin \
NX_NEWS_CAPTURE_DIR=/path/to/private/captures python3 news_refresh/test_refresh.py -v
```

The tests compile the exact parser on the host with address/undefined sanitizers.
The table has 41 firmware mappings, or 45 with the four additional unique article
strings. The latter are verified against source hashes and article identity in
additional-ukrainian.json; that file contains Ukrainian text, not original captures.
The tests check all mappings, idempotence, unrelated topics/languages, opaque binary
images and extensions, varied numeric/container/string sizes, malformed/truncated
data, and rejection of bad mapping tables. A private console fixture is optional;
when supplied via NX_NEWS_CAPTURE, the test verifies every field in the captured
zero-padded article against an independent transformation. NX_NEWS_CAPTURE_DIR
enables the full seven-record regression, including changing buffer tails and the
subscription article when its mappings are present. A dedicated test verifies all
five of that article's text fields, button glyphs, images and metadata. Independent
Python MessagePack decoding checks the complete rewritten object. A separate
sanitized test exercises the storage transaction: success/idempotence, changed
original rejection, partial writes, failed commits, wrong readback, failed restore
and initial read failure. These tests do not replace a console test of the save API.

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

Copy the built NRO to switch/nx-ukrainian-news-0.1.7.nro and the generated
translations-0.1.6.bin into switch/nx-ukrainian-news/ on SD. Open hbmenu normally
and select **Ukrainian News Refresh 0.1.7**. It inspects the existing records and verifies backups first. If matching
tutorials are found, press **A** to apply; otherwise inspect the displayed result.
Press **+** after the result to exit, then reopen News and check both article titles
and their bodies. Report any error code instead of resetting system data.

The private text map is generated locally and is excluded from Git. The source
contains no firmware resources, keys, console data or personal paths.

## Native data-service finding

Six captured tutorial buffers are 524,288 bytes. Their complete MessagePack maps
are 66,632–292,400 bytes. In four captures, the suffix after the map exactly
matches bytes at the same offset in a previously read article buffer. It is not
stable article content. A seventh, unrelated post is returned as a complete
346,353-byte object without a suffix. An independent MessagePack decoder agrees
with every map boundary used by the C++ adapter.

Opening another article on the same data-service object returns 0xA7D. Every
read therefore creates a fresh object. These findings came from read-only console
captures; no original capture, Nintendo text or console data is committed.

## Posting lock finding

On the owner's 23.0.1 console, version 0.1.4 reported `Update tutorial: 0x0000127D`
before the first post succeeded. Original readback matched the verified backup.
Local analysis of the matching firmware identifies this result at the exclusive
lock check before parsing the posted payload. Data-reader and database-reader
objects hold shared locks for their lifetime, so retaining either blocks posting.
Version 0.1.5 closes both before posting; each verification/rollback read also
releases its reader on return. Its next console scan confirmed all six original
tutorials translated. Host data tests alone do not validate this IPC lifecycle.
Firmware binaries and captures remain private and are excluded from this repository.

## Remaining article result

Version 0.1.6 accepted the posting command for article 442, but article readback
differed; rollback verified the original. Local firmware analysis shows that
PostLocalNews formats local LS/LA record IDs and can return success for an ignored
post. Version 0.1.7 avoids this posting route for article 442, verifies the exact
existing file selected by its indexed record, and changes only that file through
the save filesystem. No raw NAND access or database edits are used.
