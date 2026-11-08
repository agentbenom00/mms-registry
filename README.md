# MMS Registry

*Formerly the Midnight Suns Suit Registry.*

A single-file mod for **Marvel's Midnight Suns** that adds **new hero, suit, palette, gear (cards), ability, character, enemy faction and Mirror Table region slots**,
so any number of those mods work side by side. Since 2.2.0 it also gives the Enhanced T.H.R.E.A.T. Room one shared
options panel, so any number of mods can add choices and rows to it. Drop `version.dll` into the game folder once; from
then on, adding or removing those mods' paks just works, on Steam and Epic.

## Why

Midnight Suns only finds heroes, outfits and palettes that are listed in its asset registry
(`CodaGame/AssetRegistry*.bin`, a main file plus 8 language variants), and there is only one registry. A mod that
adds a new hero, suit or palette has to ship a patched registry, so two such mods overwrite each other and only one
shows up.

This mod builds one shared registry, `zz_MidnightSuns_SuitRegistry_P.pak`, from the game's own registry plus every
installed hero, suit or palette mod, and keeps it up to date by itself at every launch. (The pak, folder and manifest names still say "SuitRegistry"/"SuitMods": they are kept so that mods and tools made for the old name keep working. The pak `zzzzzzzzzz_DragonCore_EngineRegistry_P.pak` of the interim "Dragon" build is deleted automatically on the first start.)

## Install (players)

1. Download the latest release zip.
2. Drag its `MidnightSuns` folder into the game folder (the one with `MidnightSuns.exe`) and let it merge. This puts
   `version.dll` in `<game>\MidnightSuns\Binaries\Win64\`.
3. Put hero/suit/palette mod paks in `<game>\MidnightSuns\Content\Paks\` (or a subfolder such as `~mods`) as usual and
   start the game.

Linux (Proton): also set the Steam launch options to `WINEDLLOVERRIDES="version=n,b" %command%`
(Heroic: environment variable `WINEDLLOVERRIDES` = `version=n,b`).

Tested on Windows and on Linux (Steam with Proton). `update.sh` stops with a clear message when no Proton is found.

**The console window** ("MMS Registry") opens on every launch by default (`show_always=1` in `options.txt`, see below). It is coloured:
orange = everything the mods add (heroes, suits, gear, abilities, characters, blueprints, palettes, effects, pak names, reasons...),
white = normal text, **light red = errors**, light blue = the banner. Its text is 25% bigger than the console's own.
It shows: how many mods in how many paks, the totals per kind, the kinds that can be cloned but have nothing yet, and then
**pak by pak, mod by mod, every cloned entry with the donor it was cloned from** (`gear  Gear_X  <- Gear_Y`), so you can see which mod cloned what.
Errors appear in light red together with everything logged before them.

`%LOCALAPPDATA%\MidnightSunsSuitRegistry\options.txt` (created on the first run):
`show_always` (1 = the window on every launch, adds about `hold_seconds` to the start; 0 = only when the registry is rebuilt),
`hold_seconds` (how long the window stays after the report, default 4), `font_percent` (default 125) and `full_list`
(1 = every entry on the screen, 0 = totals only; the log file always has everything). Text scaling works in the classic console host;
Windows Terminal ignores it (use its own zoom, Ctrl + mouse wheel).

When something changed (mod added, removed or updated, or a game update) the rebuild runs while the window is open (about
10 seconds); otherwise the check takes a fraction of a second. The first rebuild downloads the
Oodle decompression library once (see Credits). Log: `%LOCALAPPDATA%\MidnightSunsSuitRegistry\SuitRegistry.log`.

See [README.txt](README.txt) (shipped in the zip) for the details players need.

## For mod authors

A hero, suit, palette, gear or ability pak carries a manifest at `CodaGame/SuitMods/<id>.json` (the game ignores it):

```json
{"format": 1, "id": "Venom_SpaceKnight", "title": "Space Knight (Venom)",
 "sources": ["/Game/DLC_Venom/Templates/TacticalOutfits/VENM/TacticalOutfit_HR_VENM_Anti.TacticalOutfit_HR_VENM_Anti", "..."],
 "rules": [["AntiVenom", "SpaceKnight"]], "keep": []}
```

- `sources`: the original (donor) registry entries your mod's packages were cloned from: the outfit, its palettes,
  meshes, physics assets, materials and textures.
- `rules`: `[old, new]` text replacements applied in order to every name of each cloned entry, so the registry points
  at your packages. Names containing a `keep` string stay unchanged.
- A source can also be `{"source": path, "rules": [...]}` with its own rules, to clone one donor more than once
  (e.g. extra palettes made from one original palette).
- **Factions and regions:** `"kind": "faction"` (a new enemy faction) and `"kind": "region"` (a new Mirror Table region). They are
  never guessed from a path; the log counts them on their own ("1 faction and 1 region"). `"kind": "cards"` / `"card"` means `gear`.
- `id` must be unique. A manifest without an outfit that only adds palettes counts as a palette mod;
  `"kind": "suit"` / `"palette"` overrides that. A new playable character sets `"kind": "hero"`; the log then
  counts it as a hero ("1 hero, 2 suits and 1 palette").
- **Gear and abilities:** a manifest with no outfits or palettes whose sources are gear (`/Items/Gear/...`) and/or
  abilities (an `Ability_*` object under `/Abilities/`) counts as a gear / ability mod (the log says
  "1 gear and 1 ability"); `"kind": "gear"` / `"ability"` overrides the guess. Clone a donor gear item or ability and
  rename it with `rules`, see [`examples/Hunter_QuickStrike.json`](examples/Hunter_QuickStrike.json). Projectile
  templates (`PJ_*`) can be cloned like any other entry. Ability visualization blueprints (`VisBP_*`) and other
  blueprint classes (`*_BP`) can be cloned too in this build: rename them with `rules` and ship the renamed `.uasset`/`.uexp`
  in your pak; otherwise leave them out of `sources` and reference the original ones directly.
- **Characters:** non-hero `Character_*` templates (enemies, NPCs, outside the `Heroes` folders) count as a character
  mod (the log says "1 character"); `"kind": "character"` forces it. New playable heroes keep using `"kind": "hero"`.
- **Animations:** a manifest whose sources are animation assets (AnimSequence, AnimMontage, MontageSet, MontageAlias,
  Skeleton, PoseAsset, BlendSpace, AnimComposite...) counts as an animation mod ("1 animation"). They're recognised by
  folder (`/_Anims/`, `/Anims/`, `/Animations/`, `/MontageSets/`, `/MontageAliases/`) or the `_MSet` suffix; otherwise set
  `"kind": "animation"`. The registry entry only mirrors the donor's tags: the animation itself must be in your pak at
  the new path, with the same class and skeleton as the donor. Animation Blueprints aren't cloned.
- **Tactical mods, effects, keywords:** `AbilityMod_*` / `TacticalMod_*`, `Effect_*` and `Keyword_*` sources count as
  "tactical mod", "effect" and "keyword" mods (`"kind": "mod"` / `"effect"` / `"keyword"` forces it); label only.
- **More categories (label only, same cloning code):** `stage`, `objective`, `encounter`, `mission`, `challenge`,
  `combatbonus`, `reward`, `achievement`, `lore`, `voice`, `heroop`, `randset`, `abbeyoutfit`, `photobooth`, `resource`.
  A manifest without outfits or palettes whose sources sit in the matching folder (`/Templates/Stages/`,
  `/Templates/Objectives/`, `/Templates/Encounters/`, `/Templates/Missions/`, `/Templates/Challenges/`,
  `/Templates/CombatBonuses/`, `/Templates/Rewards/`, `/Templates/Achievements/`, `/Templates/Lore/`,
  `/Templates/Voices/`, `/Templates/HeroOpNarratives/`, `/Templates/RandSets/`, `/Items/AbbeyOutfits/`,
  `/Templates/Photobooth/`, `/Templates/Items/Resources/`) is counted under it ("2 stages and 1 reward");
  `"kind": "<name>"` forces it. Also counted by folder: `map`, `quest`, `recipe`, `loot`, `spawngroup`, `weapon`,
  `cosmetic`, `equipslot`, `room`, `roomupgrade`, `friendship`, `condition`, `interaction`, `popup`, `notification`,
  `loadingtip`, `profile`, `difficulty`, `model`, `material`, `texture`, `fx` and `audio`.
- **What can be cloned:** every template class in the game's registry, Blueprint entries (`*_BP`, `VisBP_*`) included in this build
  (their `ParentClass` / `GeneratedClass` export-path tags are renamed with your `rules`). An entry with a still unsupported tag type is
  refused with a clear error and leaves the registry unchanged.
- **Safety:** the registry is built in a temporary file and only replaces the old one when everything worked. The rebuilt
  registry is also parsed again and its counts checked before it is written; any error aborts the sync and leaves the
  registry as it was. Make sure your `rules` really rename each source's object path: an entry left with the same name
  would be added a second time under that name.
- Hero mods: registry entries of blueprint classes (`*_BP`) can be cloned in this build, and so can montage sets and other
  entries with an empty tag map (e.g. `PJ_*` projectiles).
- Don't ship `AssetRegistry*.bin` files in your pak; the shared registry replaces them.
- New items need their own `EntitlementID`s and must be free (`bRequirePurchase` false; mod items can't be bought);
  new outfits also need `bUnlockedAtGameStart` true.

## Threat Room options (2.2.0)

The Enhanced T.H.R.E.A.T. Room (the Storm DLC's room upgrade) has one options panel, `WBP_MissionModsPanel_THREAT`. A
mod that ships its own edited copy of it replaces every other mod's, so the registry offers a shared panel instead.
When at least one installed mod registers a Threat Room option, the registry rebuilds the game's own panel with the
patch in `src/proxy/threatroom_panel.h` and puts it in its pak. That panel lists every registered option, so mods
add Threat Room choices without shipping the panel and without knowing about each other. With no options
registered, the registry leaves the panel alone.

A Threat Room option is a `StrategyMissionMod_ApplyMissionMod` template whose first `MissionModToApply` is a
`MissionMod_ModifyFacts`. Ship both, and register the strategy mission mod in your manifest, cloned from one of the
Storm DLC's (sources under `/StrategyMissionMods/` count as `"kind": "threatroom"`):

```json
{"format": 1, "id": "EndlessThreatRoom", "title": "Endless Threat Room", "kind": "threatroom",
 "sources": [{"source": "/DLC_Storm/Templates/Missions/StrategyMissionMods/StrategyMissionMod_AllowedEnemies_OnlyHydra.StrategyMissionMod_AllowedEnemies_OnlyHydra",
              "rules": [["/DLC_Storm/Templates/Missions/", "/Game/Coda/Templates/Missions/"], ["AllowedEnemies_OnlyHydra", "ThreatMode_Endless"]]}]}
```

Where the option shows depends on the first tag of its mission mod's `FactTags` (or `FactTagsToRemove`, when it adds
none):

| Tag under | Shows |
|---|---|
| `Mission.AllowedEnemies` | a new choice in **Enemy Type**, labelled with the mission mod's `DisplayName` |
| `Mission.RandomVillain` | a new choice in **Villain**, labelled with its `DisplayName` |
| `Mission.ThreatRoomOption` | a choice in a row of its own, above Number of Heroes. Options with the same `Description` share a row, and the `Description` is the row's label; `DisplayName` is the choice's label |

- In a row of its own, the choice whose mission mod adds no fact (only removes) comes first and is selected every
  time the panel opens. The others follow in the order the game lists them.
- The room's mission keeps its facts from one start to the next, so each choice's mission mod must remove the facts
  of the other choices in its row (`FactTagsToRemove`). Make your own tags, and register them in a
  `Config/Tags/*.ini`.
- The game's own 13 Enemy Type and Villain options are left as they are, including their unlock conditions.
- What a choice does is up to your mod: the panel only applies the strategy mission mod when the fight starts. A
  faction or villain still needs its entries in the room's enemy groups, and a mode needs its own fight logic.
- **Don't ship `WBP_MissionModsPanel_THREAT`.** A pak that does replaces the shared panel. The registry then leaves
  its own panel out and the report names that pak in red.

The panel's script and the patch are made by [`tools/threatroom`](tools/threatroom/README.md) from the game's own
file. The release ships only the patch (copy and insert operations, about 12 KB), never the game file. If a game
update changes the panel, the patch no longer applies; the registry says so and leaves the panel alone.

## How it works

- **Loading:** the game imports `version.dll`, and Windows looks next to the exe first. Exports that `kernelbase.dll`
  also has are real PE forwarders (`src/proxy/version.def`), so the game binds straight to the real code. The game's
  anti-tamper crashes it if an imported function starts with a `jmp`, or if a second `version.dll` is loaded during
  startup.
- **Quick check (every launch):** inside `DllMain` the DLL only reads files: the mod paks' manifests and the record
  (`CodaGame/SuitRegistry/state.json`) stored in the registry pak. If they match, nothing else happens.
- **Rebuild (when needed):** threads, downloads and windows aren't allowed under the loader lock, so the DLL copies
  itself to `%LOCALAPPDATA%\MidnightSunsSuitRegistry\SuitRegistrySync.dll` and runs
  `rundll32 SuitRegistrySync.dll,SuitRegistrySync --from-game <Paks>`, waiting for it before the game continues.
  It reads the game's registries straight from its paks, appends the cloned entries (existing indices never move)
  and writes the registry pak. With Threat Room options installed, it also rebuilds the game's Threat Room panel with
  the patch and adds it to the pak.
- Plain C, no dependencies besides Windows: pak reader (v3-v11, AES via bcrypt) and writer (v11, Zlib),
  inflate/deflate, CityHash64, a small JSON parser and the AssetRegistry v8 patcher.

| File | What |
|---|---|
| `src/proxy/version.c` | exports, the in-game check, the rundll32 entry point |
| `src/proxy/sync.c` | scanning mod paks and manifests, the state record, the rebuild |
| `src/proxy/pak.c` | pak reading and writing |
| `src/proxy/registry.c` | AssetRegistry (version 8, FixedTags) parsing and patching |
| `src/proxy/threatroom.c` | the shared Threat Room panel: applies the patch in `threatroom_panel.h` to the game's own panel |
| `src/proxy/zlib.c`, `oodle.c`, `json.c`, `util.c` | compression, Oodle loading, JSON, buffers/log/hashes |
| `tools/threatroom/` | makes the shared panel and its patch (Python, UAssetAPI); see its README |

## Building

Cross-compiled from Linux with [zig](https://ziglang.org/) 0.13:

```sh
./build.sh      # -> dist/MidnightSuns-MMSRegistry.zip (MidnightSuns/Binaries/Win64/version.dll + README.txt)
```

On Windows run `build.bat` instead (zig 0.13 on `PATH`, or set `ZIG`). `build.sh` looks for zig in `~/Tools/zig-linux-x86_64-*`; set `ZIG=/path/to/zig` otherwise. `update.sh` is a Linux
helper that runs the sync through the game's Proton without starting the game.

## Credits

- Only1DragonRage contributed 2.1.0's main changes: blueprint cloning (`*_BP`, `VisBP_*`), the report window and
  `options.txt`, the coloured console and log, and 23 more mod kinds.
- Only1DragonRage contributed 2.0.0's main changes: cloning entries with an empty tag map (montage sets, PJ_*
  projectiles, level sequences), the self-check after each rebuild, and the new mod kinds.
- Oodle is downloaded at runtime from [WorkingRobot/OodleUE](https://github.com/WorkingRobot/OodleUE) builds (as
  [FModel](https://github.com/4sval/FModel) / [CUE4Parse](https://github.com/FabianFG/CUE4Parse) do); it is not
  part of this project.
- Pak and AssetRegistry formats as documented by CUE4Parse and [repak](https://github.com/trumank/repak).
- Not affiliated with or endorsed by Firaxis, 2K or Marvel.

## License

[MIT](LICENSE)
