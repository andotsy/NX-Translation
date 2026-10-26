# Retained built-in News articles

The 22.5.0 upstream release already includes Ukrainian News text and a
LocalNews overlay. The public release contains no article-refresh NRO. On the
tested 23.0.1 console, the installed LocalNews overlay matched the package but
previously stored Russian tutorial articles remained visible.

The optional [refresh helper](news_refresh/README.md) translates the seven known
articles through the News service. It preserves images, IDs and unrelated data,
backs up native records to SD, and verifies each resulting article. Native readers
must be closed before posting; a fresh reader is required for each article.

Version 0.1.10 is confirmed successful on the console. The six tutorial articles
and the channel-subscription article are Ukrainian. The user confirmed that only
the Ukrainian subscription copy remains visible. The saved run log reported a
successful update of the original record's per-record `opted_in` visibility flag.

The helper first verifies the entire Ukrainian copy, then backs up and hides only
its recognized Russian original. It does not change channel subscriptions,
clear News storage, delete system saves or write raw NAND. The firmware supports
updating `opted_in`; attempts to update `expire_at` in earlier versions were
rejected. The current helper retains native errors and restores the old visibility
flag if post-update verification fails. Twelve host tests pass.

The read-only `diagnose_news.py` still checks the LocalNews overlay's 43 records
(41 nonempty), native structure and optional live-SD hash. These results and the
News repair do not establish that every HOME or Settings screen has been tested.

## References

- [Upstream Ukrainian catalog](https://github.com/NX-Family/NX-Translation/blob/main/translation/ukrainian.yaml)
- [Upstream 22.5.0 release](https://github.com/NX-Family/NX-Translation/releases/tag/FW22.5.0-TR2.01)
- [libnx News API](https://github.com/switchbrew/libnx/blob/master/nx/include/switch/services/news.h)
- [Atmosphère data archive redirection](https://github.com/Atmosphere-NX/Atmosphere/blob/1.12.1/stratosphere/ams_mitm/source/fs_mitm/fs_mitm_service.cpp)
