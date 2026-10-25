# News tutorial articles: observed coverage gap

Console photos confirm Ukrainian News controls, but Russian titles, channel name
and body text in the built-in tutorial articles. This is a distinct coverage check
from HOME, Settings or the successfully tested user-selection screen.

The exact photographed text is present in the stock 23.0.1 LocalNews data archive
(010000000000080B). The full overlay already includes Ukrainian replacements for
all 41 nonempty records in message/EUru/localNews.msbt.szs (two other records are
empty in the original), including the article subjects,
channel name, eShop button and footer. No new translation is necessary for these
specific screens. A translated file in a package does not prove the console uses it.

## Read-only diagnostic

With the same local inputs/environment as the builder:

```sh
python3 diagnose_news.py
python3 diagnose_news.py --sd-root /path/to/mounted/sd
```

This validates the package, the 43-record coverage, the stock metadata preservation
and (optionally) the installed file hash. It never writes to the SD or News database.

Next steps:

1. Verify the live SD file against the built package and confirm its parent path.
2. If identical, distinguish a system-data mounting/redirection problem from a
   retained article copy in News storage. Do not assume cache is proven by photos.
3. Inspect/export only the relevant built-in tutorial records through the News
   service before selecting a refresh method. Preserve existing records first.
4. A later updater should use the same tutorial IDs and preserve metadata/images;
   it must not clear the whole News database or alter subscriptions to repair text.

The installed SD resource has now been verified byte-for-byte against the package.
An optional [News refresh helper](news_refresh/README.md) is built and tested offline.
Console captures contain six Russian tutorials and one channel-subscription
article. The original six tutorials have 25 nonempty translated text fields.
Native data-service buffers can retain earlier article bytes after the complete
MessagePack map; each article also needs a fresh reader object. Helper 0.1.4
passed regressions against all seven captures, but its first update returned
0x127D. The attempted article was verified unchanged. Analysis of the matching
firmware traces this result to the exclusive posting lock: both article readers
and the database reader retain shared locks until their sessions close. Helper
0.1.5 closes the index after enumeration and every article reader on return,
including exceptions. A subsequent console scan confirms all six original
tutorials translated. The user reports the remaining subscription article is
still Russian. Version 0.1.6 adds its title, channel name/description, body and
footer, with exact source hashes verified from the private capture and button
glyphs preserved. Version 0.1.6 accepted the post but failed article readback; rollback verified the
original. Version 0.1.7 instead uses a guarded single-file update through the
journaled News save filesystem, leaving the index unchanged. Eleven host tests
cover all seven captures and injected storage failures; the new device flow still
needs console validation. No News storage reset has been performed.
Do not describe the full system translation as completely console-validated.

## Relevant upstream interfaces

- [Atmosphere 1.12.1 filesystem redirection](https://github.com/Atmosphere-NX/Atmosphere/blob/1.12.1/stratosphere/ams_mitm/source/fs_mitm/fs_mitm_service.cpp)
  includes OpenDataStorageByDataId. Its presence alone does not prove this caller
  uses that interception path.
- [libnx News API](https://github.com/switchbrew/libnx/blob/master/nx/include/switch/services/news.h)
  exposes reading News records/data and posting local News, separate from files
  supplied by an SD overlay.
- [libnx implementation](https://github.com/switchbrew/libnx/blob/master/nx/source/services/news.c)
  provides the IPC details. A documented command is not a tested 23.0.1 updater.
- [Observed News MessagePack structure](https://gist.github.com/jarrodnorwell/90629c3bf9e472e3277ffac0aa4a670f)
  illustrates separate subject, topic name, body, footer, image and action fields.

The normal System Settings “Clear Cache” action concerns web data and should not
be prescribed as a verified method for refreshing these tutorial records.
