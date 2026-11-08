# tools/threatroom: the shared Threat Room panel

`build_panel.py` makes the MMS Registry's shared `WBP_MissionModsPanel_THREAT` from the game's own panel, and with
`--header` writes the patch the registry applies at launch (`src/proxy/threatroom_panel.h`, read by
`src/proxy/threatroom.c`). The release carries only that patch, never the game file.

```sh
uasset-json/build.sh                                       # once: work/uasset-json (UAssetAPI JSON CLI + fix-offsets)
python3 build_panel.py --header ../../src/proxy/threatroom_panel.h
```

It needs the game's paks (Steam install, path in `lib/ue.py`), repak 0.2.3 and the pak key in `~/Tools/mms_aes.hex`
(the same tools as the hero mods), and the .NET 10 SDK with UAssetAPI for `uasset-json`. Game files are cached in
`work/` (git-ignored).

## What the panel adds to the game's

- **Class:** `MMS_ExtraRows`, an `FXSFocusVerticalBox` in slot 1 of the scroll box (above Number of Heroes), shown
  with the Tier II upgrade like the game's rows; `MMS_Rows` and `MMS_RowKeys`.
- **Function `MMS_AddRegisteredOptions(Which)`:**
  - It lists every registered `StrategyMissionMod_ApplyMissionMod` (`GetAllTemplateForClass_BP`), skips the
    panel's own 13 `Entry_*` options by identity, and reads the first tag of each mission mod's `FactTags` (or
    `FactTagsToRemove`).
  - `Which` 0 adds `Mission.AllowedEnemies` options to Enemy Type, 1 adds `Mission.RandomVillain` options to
    Villain, and 2 creates one `WBP_MissionModItem_Dropdown` row per `Description` for `Mission.ThreatRoomOption`
    options.
  - With `Which` 2, the choice that adds no fact goes first. The rows are put in the box and added to
    `AllMissionMods`, so they get the mission ID and are applied on start, and they get the left-navigation rule.
  - `Which` 3 selects every row's first choice, then runs `Which` 4.
  - `Which` 4 hides the Villain row (and resets it to None) while a selected choice's mission mod has
    `Mission.ThreatRoomOption.Hide.Villain`, and shows it again otherwise, as the game does with Tier III.
- **Function `MMS_OnExtraRowChanged(TargetControl, Value)`:** bound to each extra row's `OnChangedCallback` (after
  the row's own handler, which updates `CurrentIndex`); it runs `Which` 4.
- **Calls in the event graph:**
  - 0 just before Enemy Type gets its mods, after the Lilin check has run.
  - 1 just before Villain gets its mods, after the unlock checks.
  - 2 after `AllMissionMods` is built in Construct.
  - 3 at the start of `SetSelection`.
  - 4 at the start of `OnStartMission`, before the dropdowns apply their mods.

Every statement copies a shape from the game's own bytecode (the panel's, `PopulateGameDifficultyDropDown`'s,
`WBP_CodaDropdown`'s). Context skip sizes come from `uasset-json fix-offsets`, which changes nothing in the game's
blueprints. Statement insertion moves every jump and entry point (`lib/kis.py`).

## delta.py

The MMSD patch format: `"MMSD"`, version 1, the source's size and SHA-1, the result's size and SHA-1, then copy
(source offset, length) and insert (bytes) operations. The registry checks both hashes, so a different game file is
refused, not patched wrongly.
