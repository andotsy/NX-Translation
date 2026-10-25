# Refresh retained built-in News articles

This optional firmware-23.0.1 helper translates known Russian News articles that
remain in storage after the system overlay is installed. It uses News services;
no keys, network, raw NAND access or separate system-save mount is needed.

**Status:** version 0.1.5 translated six tutorials, confirmed by a subsequent
console scan. Another post about subscribing to channels remained Russian.
Version 0.1.6 posted its Ukrainian copy under a local record ID; the original
record remained. Version 0.1.7 could not mount the News save (0xE02, already in use)
and verified the original unchanged. Version 0.1.8 verifies the complete Ukrainian
copy and retires only the old Russian entry through the News database service.
The new device flow remains unconfirmed. Twelve host tests pass.

## Behavior

- Supports only firmware 23.0.1 and the underlying Russian system language.
- Enumerates active non-user nx_notice records. Unrecognized subjects are skipped.
- Opens and closes a fresh reader for every read; closes the enumeration index
  before posting. Native service buffers may contain stale bytes after the first
  complete MessagePack map. Only that map is rewritten or compared; full returned
  buffers are preserved in verified SD backups.
- Replaces exact known text in topic_name, topic_description, subject.text,
  body.text, footer.text and matching action-text fields. IDs, language, images,
  button glyphs and other payload fields are preserved.
- Backs up and reads back every original on SD before **A** can apply changes.
- Updates the six original local tutorials through PostLocalNews and verifies them.
- For the remaining subscription article (numeric ID 442), requires exactly one
  local Ukrainian copy. Its entire serialized map must equal the expected
  transformation of the original, including all images and metadata. It changes
  only expire_at from 0 to 1 on the original non-local record, selected by exact
  record ID, empty user ID and nx_notice topic. The original expiration and both
  record IDs are backed up on SD. No subscriptions or unrelated records change.
- Holds background-task suspension through update, verification and rollback.
  Verifies the original is expired and the Ukrainian copy is unchanged. On failure,
  restores and verifies the previous expiration. The ordinary News UI expiration
  predicate excludes the old entry; normal cleanup may later remove it.
- Saves expected and actual bytes privately on SD if article readback differs.
- Never resets News, clears subscriptions or removes system-save directories.

Backups and results remain under switch/nx-ukrainian-news/backup-*/ and last-run.log.
Keep them until the displayed result is confirmed. Do not commit captures, backups
or the generated translation table.

## Build and test

Use the parent builder's NX_TRANSLATION_WORKDIR and NX_TRANSLATION_OUTPUT. Generate
41 private firmware mappings, optionally adding four unique source strings for the
subscription article (45 mappings total). Its capture identity, source hashes and
button glyphs must match additional-ukrainian.json. That committed file contains
Ukrainian translations and source hashes, not original article data.

```sh
python3 -m pip install --target "$NX_TRANSLATION_WORKDIR/python-deps" msgpack==1.1.2
python3 news_refresh/prepare_table.py --extra-article /path/to/private/article.bin
NX_NEWS_CAPTURE=/path/to/private/article.bin \
NX_NEWS_CAPTURE_DIR=/path/to/private/captures python3 news_refresh/test_refresh.py -v
cd news_refresh
make
```

Tests compile the actual C++ parser and verified-update helper with address and
undefined-behavior sanitizers. Independent MessagePack decoding checks all seven
private captures, all text fields, images, metadata, button glyphs, idempotence,
changing native buffer tails and malformed data. Injected write, commit, readback
and restore failures check recovery. An independent SQLite test checks the single
record selector, unchanged unrelated records, the recovered UI visibility predicate
and restoration. Host tests do not establish device IPC compatibility.

The Switch build uses devkitA64/libnx/switch-tools in the official
devkitpro/devkita64 container, pinned to digest
sha256:1fc388c3a0d34bd2045a6dadcb1020e069d5f876a187fd705de14b4440c00282,
with network disabled. Only helper source is sent to the builder. See build-info.json.

## Console use

Copy the NRO to switch/nx-ukrainian-news-0.1.8.nro and the generated
translations-0.1.6.bin to switch/nx-ukrainian-news/. Open hbmenu using the console's
existing configuration and select **Ukrainian News Refresh 0.1.8**. Press **A** after
backup verification, or **B / +** to exit without changes. After SUCCESS, press **+**,
reopen News and verify titles and bodies. Report errors without resetting data.

## Relevant firmware findings

The native posting path formats local LS/LA record IDs; it does not replace a
non-local article's existing record. The matching News UI filters include
`expire_at=0 OR expire_at>=current_time`. The News database's UpdateIntegerValue
command commits updates in its owning service. These observations motivated the
verified-copy retirement approach. Matching firmware and private captures stay
local and are excluded from this repository.
