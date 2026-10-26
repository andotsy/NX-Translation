# Ukrainian typing layout for 23.0.1

Optional Atmosphère patch providing Ukrainian in the Russian keyboard slot and
Cyrillic Russian in the separate Russian (Latin) slot. English US, English UK and
the other layouts are unchanged. The selector retains its existing labels.

The eight replacements are ы/Ы → і/І, ъ/Ъ → ї/Ї, э/Э → є/Є and ё/Ё → ґ/Ґ.
All shared Ukrainian letters remain at their existing positions. The secondary
slot receives the stock Russian lowercase/uppercase tables, including their
punctuation and number rows. Symbol pages and executable instructions are
unchanged. Prediction dictionaries are not translated by this patch.

Build from an owner-extracted, uncompressed main NSO for swkbd on firmware 23.0.1:

```sh
python3 build_patch.py --nso /path/to/uncompressed/main.nso --output /path/to/output
```

The generator checks the complete input hash, build ID and original key tables.
It outputs only a small IPS patch and a manifest; no executable is distributed.
Copy the generated atmosphere folder onto the SD card and reboot. Select the
existing Russian keyboard slot; it should now type Ukrainian. The Russian (Latin)
slot should type Cyrillic Russian, including ыъэё and ЫЪЭЁ. Verify іїєґ and
ІЇЄҐ, shared letters, backspace, punctuation and both English layouts in a temporary
text field. Exit that field without saving if the text is only a test.

To remove the patch, delete only its nx-ukrainian-keyboard directory beneath
atmosphere/exefs_patches and reboot. Other translation overlays stay installed.

Status: Ukrainian primary layout confirmed on a console. The secondary Russian
update passes offline checks; its console test remains pending. The 250-byte
patch contains ten records. Tests apply it to the verified source, check both
complete layouts and both English tables, and prove all other bytes unchanged.

[Atmosphère NSO patch documentation](https://github.com/Atmosphere-NX/Atmosphere/blob/master/docs/components/modules/loader.md#nso-patching)
