# Ukrainian EUru port tooling for firmware 23.0.1

This work-in-progress ports the Ukrainian system overlay to 23.0.1 by rebuilding
message text inside the current firmware's own MSBT structure. It replaces Russian
(EUru), preserving each current file's labels, attributes, unknown sections and indices.
The system locale remains Russian; games can continue following that language.

## Current progress

- Verified local extraction of the 19 relevant system titles using the owner's keys.
- Compared original 22.5.0 and 23.0.1 English/Russian resources against the existing
  22.5.0-TR2.01 Ukrainian release, matching by title, path, label and source meaning.
- Found 117 added labels and three removed labels among the existing 51 overlay files.
- Included two additional user-page message tables, for a total of 53 overlay files.
- Matched 10,898 records against the verified previous source/translation, used five
  exact plain-text upstream YAML matches, and retained 14 nonlinguistic records.
- Added 87 distinct Ukrainian translations covering 191 remaining record instances.
- Built local full and user-selection pilot ZIPs; all 11,108 record instances resolved.
- Offline checks pass. **The system user-selection pilot is confirmed working on a console.**
  The reported prompt is “Хто користується програмою”. Full HOME/Settings testing remains outstanding.

No keys, firmware NCAs, extracted original resources, generated translation catalog,
console identifiers or local paths are included. This directory contains the new
builder, tests and Ukrainian additions. The translation candidate ZIPs remain local.
Do not install the old 22.5.0 binary overlay on 23.0.1.

## Known News coverage gap

Console photos show translated News controls with Russian built-in tutorial articles.
The LocalNews translation is already built; runtime use and retained article content
require separate checks. The installed overlay now matches the package byte-for-byte.
See [NEWS.md](NEWS.md), the read-only diagnose_news.py and the optional
[News refresh helper](news_refresh/README.md). The six original tutorials are
confirmed translated. Version 0.1.8 verifies the remaining article's Ukrainian copy
and retires only its obsolete Russian record through the News service. Its device
validation is pending.

## Local inputs

Obtain your own firmware and existing translation release. This tool does not download
firmware, acquire keys, write to NAND or automatically install anything.

Set these variables to directories outside the Git checkout:

```sh
export NX_TRANSLATION_WORKDIR=/path/to/local-port-work
export NX_TRANSLATION_OLD_CONTENTS=/path/to/old-ukrainian/atmosphere/contents
export NX_TRANSLATION_OUTPUT=/path/to/local-build-output
# Optional: override the repository's translation/ukrainian.yaml
# export NX_TRANSLATION_YAML=/path/to/ukrainian.yaml
```

Use Python 3.10 or newer (tested on 3.12, macOS arm64). From this directory:

```sh
python3 -m pip install --target "$NX_TRANSLATION_WORKDIR/python-deps" -r requirements.txt
```

Build [hactool](https://github.com/SciresM/hactool) locally at commit
`1d64a83450e025622f3468c28fc4164dad2c5ef6`, placing its executable at
`$NX_TRANSLATION_WORKDIR/tools/hactool/hactool`. The source includes mbedTLS;
copy its config.mk.template to config.mk and build with an appropriate C compiler.
This revision was successfully tested on the selected NCAs. Do not assume an older
prebuilt release has the same compatibility.

Prepare the two owner-supplied firmware ZIPs, checking each against its trusted archive
SHA-256 where available. Each NCA's hash must also match its content-ID filename.
The version argument labels the input directory; provide the correct archive yourself.

```sh
python3 prepare_firmware.py --version 23.0.1 --zip /path/to/Firmware.23.0.1.zip --sha256 EXPECTED_HASH
python3 prepare_firmware.py --version 22.5.0 --zip /path/to/Firmware.22.5.0.zip --sha256 EXPECTED_HASH
python3 extract_system_resources.py --keys /path/to/own/prod.keys
python3 extract_system_resources.py --version 22.5.0 --keys /path/to/own/prod.keys
python3 compare_resources.py
python3 prepare_translations.py
python3 test_msbt.py -v
python3 build_overlay.py
```

Key material is read only by the local extractor, with key output suppressed. Raw tool
logs are not stored. Collection retains EUru/EUen language resources and public NCA
metadata; full temporary RomFS extractions are removed after the narrow files are kept.

## How translation matching works

The 23.0.1 file is always the binary base. Existing Ukrainian strings are eligible only
when the original English source matches; this comparison includes substitution
identities and plural-word payloads. Formatting commands may differ between languages.
Substitution contracts and printf arguments are checked before a translated string is
reused. Source-label reindexing is handled explicitly, not by copying old record numbers.

Ambiguous or changed sources enter manual-required.json in the local work directory.
The committed manual-ukrainian.json maps deterministic source hashes to Ukrainian
strings. `<C0/>`, `<C1/>`, etc. stand for the current Russian record's exact opaque
commands. Every command must remain exactly once and in order. These markers are
compiled back into binary and may not appear in the final UI. Private-use button glyphs
and printf arguments are checked as well. New unresolved strings stop the build.

The writer changes only TXT2 and the necessary section/file sizes. Tests cover:

- Byte-identical no-change round trips for all 106 current MSBT resources.
- Changed string lengths/offsets, verified with a separate parser.
- Preservation of labels and every nontext section, including Mii's TSY1.
- Rejection of malformed or unterminated control sequences.
- Independent native Yaz0 decompression/recompression checks.
- Lossless control-template round trips across all 22,216 current record instances.

## Output and console validation

The builder generates manifest.json, validation.json and two deterministic ZIPs:

- ukrainian-23.0.1-EUru-pilot-user-selection.zip: only title 0100000000001007.
- ukrainian-23.0.1-EUru-full.zip: all 53 files across 19 system titles.

Both ZIPs include exact installed paths and SHA-256 hashes. No ExeFS, font overrides,
system settings, keys or firmware NCAs are packaged. The MSBP project resource stays stock.

Before any install, establish a normal boot and working game from the current SD.
Back up only files that the manifest would replace. Merge the pilot's atmosphere
folder into the SD root, keep the system language set to Russian, then test opening,
canceling and choosing a user. Check Ukrainian glyphs and launching a working game.
After the pilot succeeds, add HOME/Settings and other components in small stages.
Do not replace the whole contents directory or touch unrelated modules/game mods.

Test cold boot, HOME/Settings, sleep/wake, controllers, Album, user selection,
keyboard labels and dynamic/long text. Do not delete users, erase/reset the console,
transfer saves or update firmware just to reach a translated screen. Screens that
cannot safely be exercised remain untested.

Rollback through Hekate USB storage or a card reader: remove only newly created overlay
files from the manifest and restore any replaced files from backup. Reboot to use the
stock Russian resources. No NAND changes are involved. Do not rename/delete all of
atmosphere/contents or change unrelated settings, hosts or modules.

## Licensing and sources

New tooling in this directory is MIT licensed (see LICENSE); this does not relicense
the upstream translation, Nintendo content or dependencies. This is an unofficial
personal test build. Distribution/acceptance by upstream is a separate decision.

- [NX-Translation](https://github.com/NX-Family/NX-Translation)
- [Existing translation release](https://github.com/NX-Family/NX-Translation/releases/tag/FW22.5.0-TR2.01)
- [hactool](https://github.com/SciresM/hactool)
- [MessageStudio format implementation](https://github.com/EPD-Libraries/MessageStudio)
- [oead](https://github.com/zeldamods/oead)
