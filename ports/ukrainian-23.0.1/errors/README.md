# System error messages

The error applet's UI strings and the error bodies have different sources.
Error 2110-1111 (opening eShop in flight mode) comes from the ErrorMessage data
archive, 0100000000000801, at `2110/1111/ru_DlgMsg`. Translating error.msbt alone
does not translate that body.

The popup heading also has a locale-specific MSBT label,
`ErrCmn_LblErrCode_EUru`, which still contains Russian in the English resources.
The main overlay builder explicitly translates this label to `Код помилки:`
while preserving the dynamic error-code command. The generic heading was
already Ukrainian; it is not the variant selected by this popup.

This optional, partial overlay uses existing Ukrainian catalog matches and 40
new translations for flight mode, network connections, storage space and a
generic error. Unmatched messages use their original firmware text. It does not
replace error codes, routing metadata, other languages or the firmware archive.

From the port directory, with the same Python dependencies as the main builder:

```sh
python3 errors/build_overlay.py \
  --romfs /path/to/owner-extracted/ErrorMessage/romfs \
  --catalog /path/to/translation/ukrainian.yaml \
  --output /path/to/new-output-directory
```

Each file is UTF-16LE without a terminating NUL. The builder preserves the
Russian resource's formatting commands and validates runtime substitutions,
printf arguments and button glyphs. It records input and output hashes and
lists every unmatched path. The native database's `common` and `DatabaseInfo`
files are not copied or modified.

Copy the output's atmosphere directory to the SD and reboot. To check the
reported case, open Nintendo eShop with flight mode enabled: 2110-1111 should
show a Ukrainian explanation and retain the HOME button glyph. Console testing
is pending. Offline checks do not prove how every popup wraps on screen.

Remove only `atmosphere/contents/0100000000000801` to undo this optional overlay.

[Atmosphère data archive redirection](https://github.com/Atmosphere-NX/Atmosphere/blob/1.12.1/stratosphere/ams_mitm/source/fs_mitm/fs_mitm_service.cpp)
