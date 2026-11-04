# MMS Registry

*Formerly the Midnight Suns Suit Registry.*

A single-file mod for **Marvel's Midnight Suns** that adds **new hero slots, new suit slots and new palette slots**,
and new cards, abilities, enemy factions, Mirror Table regions and other game content, so any number of such mods work
side by side. Drop `version.dll` into the game folder once; from then on, adding or removing those mods' paks just
works, on Steam and Epic.

## Why

Midnight Suns only finds heroes, outfits, palettes, cards and its other content through its asset registry
(`CodaGame/AssetRegistry*.bin`, a main file plus 8 language variants), and there is only one registry. A mod that
adds a new hero, suit, palette or card has to ship a patched registry, so two such mods overwrite each other and only
one shows up.

This mod builds one shared registry, `zz_MidnightSuns_SuitRegistry_P.pak`, from the game's own registry plus every
installed mod made for it, and keeps it up to date by itself at every launch. (The pak, folder and manifest
names still say "SuitRegistry"/"SuitMods": they are kept so that mods and tools made for the old name keep working.)

## Install (players)

1. Download the latest release zip.
2. Drag its `MidnightSuns` folder into the game folder (the one with `MidnightSuns.exe`) and let it merge. This puts
   `version.dll` in `<game>\MidnightSuns\Binaries\Win64\`.
3. Put the mod paks in `<game>\MidnightSuns\Content\Paks\` (or a subfolder such as `~mods`) as usual and start the
   game.

Linux (Proton): also set the Steam launch options to `WINEDLLOVERRIDES="version=n,b" %command%`
(Heroic: environment variable `WINEDLLOVERRIDES` = `version=n,b`).

Tested on Windows and on Linux (Steam with Proton).

When something changed (mod added, removed or updated, or a game update) a small window shows the rebuild for about
10 seconds before the game starts; otherwise the check takes a fraction of a second. The first rebuild downloads the
Oodle decompression library once (see Credits). Log: `%LOCALAPPDATA%\MidnightSunsSuitRegistry\SuitRegistry.log`.

See [README.txt](README.txt) (shipped in the zip) for the details players need.

## For mod authors

Each mod pak carries a manifest at `CodaGame/SuitMods/<id>.json` (the game ignores it):

```json
{"format": 1, "id": "Venom_SpaceKnight", "title": "Space Knight (Venom)",
 "sources": ["/Game/DLC_Venom/Templates/TacticalOutfits/VENM/TacticalOutfit_HR_VENM_Anti.TacticalOutfit_HR_VENM_Anti", "..."],
 "rules": [["AntiVenom", "SpaceKnight"]], "keep": []}
```

- `sources`: the original (donor) registry entries your mod's packages were cloned from: the outfit, its palettes,
  meshes, physics assets, materials and textures.
- `rules`: `[old, new]` text replacements applied in order to every name of each cloned entry, so the registry points
  at your packages. Names containing a `keep` string stay unchanged. Make sure the rules really rename each source's
  object path: an entry whose name stays the same is added a second time under that name.
- A source can also be `{"source": path, "rules": [...]}` with its own rules, to clone one donor more than once
  (e.g. extra palettes made from one original palette).
- `id` must be unique.
- Don't ship `AssetRegistry*.bin` files in your pak; the shared registry replaces them.
- New items need their own `EntitlementID`s and must be free (`bRequirePurchase` false; mod items can't be bought);
  new outfits also need `bUnlockedAtGameStart` true.

### Kinds

`"kind"` says what the mod adds; the log counts each kind on its own ("1 hero, 2 suits, 1 palette, 3 cards,
1 faction and 1 region"). The kind only changes the log's words: every source is cloned the same way.

| `kind` | Adds | Counted from (without a `kind`) |
|---|---|---|
| `hero` | a new playable character | never guessed |
| `suit` | a new suit | any mod with an outfit (`TacticalOutfits/`) |
| `palette` | palettes only | `HeroSkinPalette` sources |
| `cards` (or `gear`) | cards | `/Items/Gear/` sources |
| `faction` | a new enemy faction | never guessed |
| `region` | a new Mirror Table region | never guessed |
| `ability` | abilities and their projectiles | `Ability_*` and `PJ_*` under `/Abilities/` |
| `character` | enemies and NPCs | `Character_*` under `/Characters/`, outside the heroes' folders |
| `animation` | animations | `/_Anim/`, `/_Anims/`, `/Anims/`, `/Animations/`, `/MontageSets/`, `/MontageAliases/`, `*_MSet` |
| `mod` | tactical mods (card upgrades) | `AbilityMod_*`, `TacticalMod_*` |
| `effect`, `keyword` | effects, keywords | `Effect_*`, `Keyword_*` |
| `stage`, `objective`, `encounter`, `mission`, `challenge`, `combatbonus`, `reward`, `achievement`, `lore`, `voice`, `heroop`, `randset`, `abbeyoutfit`, `photobooth`, `resource` | other templates | `/Templates/Stages/`, `/Templates/Objectives/`, `/Templates/Encounters/`, `/Templates/Missions/`, `/Templates/Challenges/`, `/Templates/CombatBonuses/`, `/Templates/Rewards/`, `/Templates/Achievements/`, `/Templates/Lore/`, `/Templates/Voices/`, `/Templates/HeroOpNarratives/`, `/Templates/RandSets/`, `/Items/AbbeyOutfits/`, `/Templates/Photobooth/`, `/Templates/Items/Resources/` |

Without a `kind`, a manifest with an outfit is a suit; one without is the first kind from `palette` on (in the
table's order) that it has sources of, else a suit. Palette, card and the other content mods count what they add
("3 cards"); hero, suit, faction and region mods count once. An unknown `kind` counts as a suit, as each newer kind
does in older versions. The folder name `SuitMods` is kept for all kinds, so existing mods work unchanged.

A card mod clones an existing card's gear item, ability and card art, e.g. from
`/Game/Coda/Templates/Items/Gear/Hunter/Power/Gear_HR_HNTR_QuickSlash.Gear_HR_HNTR_QuickSlash`,
`/Game/Coda/Templates/Abilities/Heroes/Hunter/Ability_HR_HNTR_QuickSlash.Ability_HR_HNTR_QuickSlash` and
`/Game/Coda/UI/Textures/CardArt/Card_HR_HNTR_QuickSlash.Card_HR_HNTR_QuickSlash` with the rule
`["QuickSlash", "QuickStrike"]`. An animation's registry entry only mirrors the donor's tags: the animation itself
must be in your pak at the new path, with the same class and skeleton as the donor.

### What can be cloned

Every kind of entry in the game's registry except blueprints: `Blueprint` (`*_BP`, `VisBP_*`), `WidgetBlueprint`
(`WBP_*`), `AnimBlueprint`, and some levels and level sequences (their tags hold export paths). They stop the sync with
`tag value type 4 is not handled` and the registry stays unchanged; leave them out of `sources` and reference the
original ones from your assets (direct references load fine). Montage sets and other entries with an empty tag map
(e.g. `PJ_*` projectiles) can be cloned. On the game's registry that is 521,833 of its 531,586 entries.

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
  It reads the game's registries straight from its paks, appends the cloned entries (existing indices never move),
  reads each rebuilt registry back to check its counts, and only then replaces the registry pak (written to a
  temporary file first). Any error leaves the installed registry pak as it was.
- Plain C, no dependencies besides Windows: pak reader (v3-v11, AES via bcrypt) and writer (v11, Zlib),
  inflate/deflate, CityHash64, a small JSON parser and the AssetRegistry v8 patcher.

| File | What |
|---|---|
| `src/proxy/version.c` | exports, the in-game check, the rundll32 entry point |
| `src/proxy/sync.c` | scanning mod paks and manifests, the state record, the rebuild |
| `src/proxy/pak.c` | pak reading and writing |
| `src/proxy/registry.c` | AssetRegistry (version 8, FixedTags) parsing and patching |
| `src/proxy/zlib.c`, `oodle.c`, `json.c`, `util.c` | compression, Oodle loading, JSON, buffers/log/hashes |

## Building

Cross-compiled from Linux with [zig](https://ziglang.org/) 0.13:

```sh
./build.sh      # -> dist/MidnightSuns-MMSRegistry.zip (MidnightSuns/Binaries/Win64/version.dll + README.txt)
```

`build.sh` looks for zig in `~/Tools/zig-linux-x86_64-*`; set `ZIG=/path/to/zig` otherwise. `update.sh` is a Linux
helper that runs the sync through the game's Proton without starting the game.

## Credits

- Only1DragonRage contributed 2.0.0's main changes: cloning entries with an empty tag map (montage sets, PJ_*
  projectiles, level sequences), the self-check after each rebuild, and the new mod kinds.
- Oodle is downloaded at runtime from [WorkingRobot/OodleUE](https://github.com/WorkingRobot/OodleUE) builds (as
  [FModel](https://github.com/4sval/FModel) / [CUE4Parse](https://github.com/FabianFG/CUE4Parse) do); it is not
  part of this project.
- Pak and AssetRegistry formats as documented by CUE4Parse and [repak](https://github.com/trumank/repak).
- Not affiliated with or endorsed by Firaxis, 2K or Marvel.

## License

[MIT](LICENSE)
