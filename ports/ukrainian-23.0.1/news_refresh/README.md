# Refresh retained built-in News tutorials

This optional homebrew helper addresses Russian tutorial article content that can
remain even when the News interface and LocalNews SD overlay are Ukrainian.
The installed LocalNews overlay was read back and confirmed identical to the build.
This makes recopying that overlay unnecessary, but does not by itself prove the
origin of every retained article or establish the helper's device compatibility.

**Status:** helper 0.1.4 compiles for Switch and passes nine host tests, including
all seven private native console captures. Six are recognized built-in tutorials;
the unrelated seventh post is left untouched. All 25 nonempty text fields in the
six tutorials match the local translation table. The post/readback flow still
needs console validation. Earlier builds stopped before posting because native
service-buffer bytes after the MessagePack map were treated as article data.

## Behavior

- Supports only firmware 23.0.1. Uses libnx News services; no network or keys.
- Reads the device News index and selects non-user records from nx_notice.
- Creates a fresh data-service object for every article read.
- Extracts the first complete MessagePack map from native News data-service buffers.
  Captures prove that bytes beyond the map can retain earlier article data, so
  they must not be posted or included in change/readback comparisons. Original
  backups retain the full returned buffer.
- Keeps standalone parsing strict: malformed maps, non-map roots and nonzero
  trailers outside the explicitly selected native-buffer adapter are rejected.
- Processes only Russian articles whose subjects match the known firmware tutorial
  subjects (or their translated equivalents). Other articles are skipped.
- Replaces exact known text only in subject.text, topic_name, body.text, footer.text
  and the matching action-text fields. Unknown text, IDs, language, timestamps,
  images, numeric values and unrelated fields are preserved.
- Saves and verifies every original MessagePack article on SD before any posting.
- Waits for **A** before posting. **B / +** exits the inspection without posting.
- Rechecks each live original, posts through newsPostLocalNews, and reads it back.
- On an update/readback failure, verifies originals for every attempted article.
  Already-unchanged originals are not reposted. Any necessary restore posts the
  original serialized map and compares the complete returned article map.
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
NX_NEWS_CAPTURE=/path/to/private/article.bin \
NX_NEWS_CAPTURE_DIR=/path/to/private/captures python3 news_refresh/test_refresh.py -v
```

The tests compile the exact parser on the host with address/undefined sanitizers.
They check all 41 mappings, idempotence, unrelated topics/languages, opaque binary
images and extensions, varied numeric/container/string sizes, malformed/truncated
data, and rejection of bad mapping tables. A private console fixture is optional;
when supplied via NX_NEWS_CAPTURE, the test verifies every field in the captured
zero-padded article against an independent transformation. NX_NEWS_CAPTURE_DIR
enables the full seven-record regression, including changing buffer tails, six
translated tutorials and one byte-identical unrelated post. Independent Python MessagePack decoding
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
Refresh 0.1.4**. It inspects the existing records and verifies backups first. If matching
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
