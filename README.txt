MMS REGISTRY (formerly Midnight Suns Suit Registry)
===================================================

Adds new hero slots, new suit slots, new palette slots, new gear (cards), abilities, characters, enemy factions, Mirror Table
regions and blueprints to Marvel's Midnight Suns.

The game only finds heroes, outfits, palettes, gear and abilities that are listed in its asset registry, and there is only one
registry, so standalone hero, suit, palette, gear and ability mods can't each bring their own. This mod is a single file,
version.dll, that builds one shared registry (zz_MidnightSuns_SuitRegistry_P.pak; the file name is kept from the old
name so existing mods keep working. The pak zzzzzzzzzz_DragonCore_EngineRegistry_P.pak of the interim "Dragon" build is
deleted automatically on the first start) from the mod paks you have installed - automatically, every time the game starts,
on Steam and Epic. Add or remove a hero, suit, palette, gear or ability pak, press Play: done.


INSTALL
-------
Drag the "MidnightSuns" folder from this zip into the game folder (the one with MidnightSuns.exe) and let it merge.
That puts version.dll in   <game>\MidnightSuns\Binaries\Win64\

  Steam: right-click the game > Manage > Browse local files
  Epic:  Library > the game's "..." > Manage > the folder icon next to Installation

Linux (Proton) only: also set the game's Steam launch options to
    WINEDLLOVERRIDES="version=n,b" %command%
(Heroic: game settings > Advanced > environment variables: WINEDLLOVERRIDES = version=n,b)

Uninstall: delete version.dll (and zz_MidnightSuns_SuitRegistry_P.pak in Content\Paks if you remove all the mods it registers).


WHAT TO EXPECT
--------------
- Every launch it checks the mod paks first.
- Hero, suit, palette, gear and ability paks can be in Content\Paks or any subfolder of it (e.g. Content\Paks\~mods).
- By default a window "MMS Registry" opens on every launch for about 4 seconds and lists every cloned thing, pak by pak and mod by mod
  (see options.txt below). When something changed (a mod added/removed/updated, or a game update) it also shows the rebuild
  for about 10 seconds before the game starts.
- The very first rebuild downloads the Oodle decompression library once (needed to read the game's files). Offline?
  Put oodle-data-shared.dll or oo2core_9_win64.dll next to version.dll instead.
- If the game is in a protected folder (e.g. C:\Program Files\Epic Games) Windows asks for permission to update the
  registry pak.
- If something is wrong (e.g. a suit made for DLC you don't have) a message says so, and the game still starts.
- "Verify game files" on Steam/Epic may remove version.dll: just copy it in again.
- Another mod that also uses version.dll can't be used at the same time.
- Log: %LOCALAPPDATA%\MidnightSunsSuitRegistry\SuitRegistry.log (Linux: inside the game's Proton prefix).


FOR MOD AUTHORS
---------------
Each hero, suit, palette, gear or ability pak carries a manifest at  CodaGame/SuitMods/<id>.json  (the game ignores it):

  {"format": 1, "id": "Venom_SpaceKnight", "title": "Space Knight (Venom)",
   "sources": ["/Game/.../TacticalOutfit_HR_VENM_Anti.TacticalOutfit_HR_VENM_Anti", "..."],
   "rules": [["AntiVenom", "SpaceKnight"]], "keep": []}

"sources" are the original (donor) registry entries: the outfit, its palettes, meshes, physics, materials and
textures. Each one is cloned with "rules" applied in order to every name ([old, new] text replacements); names
containing a "keep" string are left unchanged. "id" must be unique. Don't ship AssetRegistry files in your pak.
A manifest without an outfit that only adds palettes counts as a palette mod ("2 suits and 1 palette").
A manifest without outfits or palettes whose sources are gear (paths containing /Items/Gear/) and/or abilities
(an Ability_* object under /Abilities/) counts as a gear / ability mod ("1 gear and 1 ability"; mixing both is fine).
"kind": "suit", "palette", "gear" or "ability" overrides the guess. A new playable character sets "kind": "hero"
("1 hero, 2 suits and 1 palette"). The folder name SuitMods is kept for all kinds, so existing mods work unchanged.

Gear and abilities (example: examples\Hunter_QuickStrike.json): clone an existing gear item and/or ability and
rename it with "rules", e.g. Gear_HR_HNTR_QuickSlash -> Gear_HR_HNTR_QuickStrike and Ability_HR_HNTR_QuickSlash ->
Ability_HR_HNTR_QuickStrike. Projectile templates (PJ_*, ProjectileContent) can be cloned like any other entry. Ability visualization
blueprints (VisBP_*) and other blueprint classes (*_BP) can be cloned too in this build: list them in "sources" with a
rule that renames them, and ship the matching renamed .uasset/.uexp in your pak. Without a renamed file in the pak
the new entry would point at nothing, so only clone a blueprint you really provide; otherwise reference the original.
Every new gear item needs its own EntitlementID.

Characters (non-hero, e.g. enemies and NPCs): a manifest whose sources are Character_* templates outside the
Heroes folders counts as a character mod ("1 character"); "kind": "character" forces it. New playable heroes keep
using "kind": "hero". Character blueprints (HR_*_BP and other *_BP classes) can be cloned too in this build when your pak
ships the renamed blueprint; otherwise reference the original ones.

Animations: a manifest whose sources are animation assets (AnimSequence, AnimMontage, MontageSet, MontageAlias,
Skeleton, PoseAsset, BlendSpace, AnimComposite...) counts as an animation mod ("1 animation"). Those are recognised
by folder (/_Anims/, /Anims/, /Animations/, /MontageSets/, /MontageAliases/) or the _MSet suffix; for anything else
set "kind": "animation". The registry entry only mirrors the donor's tags: the animation itself must be in your
pak at the new path, with the same class and skeleton as the donor. Animation Blueprints (AnimBlueprint) are not
cloned. See examples\Hunter_BindB_Animation.json.

Tactical mods, effects and keywords: a manifest without outfits or palettes whose sources are AbilityMod_* /
TacticalMod_* (card upgrades), Effect_* or Keyword_* templates counts as "tactical mod", "effect" or "keyword" mods;
"kind": "mod" / "effect" / "keyword" forces it. These only change the label in the log.

More categories (label only, same cloning code): stage, objective, encounter, mission, challenge, combatbonus,
reward, achievement, lore, voice, heroop, randset, abbeyoutfit, photobooth and resource. A manifest without outfits
or palettes whose sources sit in the matching folder (/Templates/Stages/, /Templates/Objectives/,
/Templates/Encounters/, /Templates/Missions/, /Templates/Challenges/, /Templates/CombatBonuses/, /Templates/Rewards/,
/Templates/Achievements/, /Templates/Lore/, /Templates/Voices/, /Templates/HeroOpNarratives/, /Templates/RandSets/,
/Items/AbbeyOutfits/, /Templates/Photobooth/, /Templates/Items/Resources/) is counted under it ("2 stages and
1 reward"); "kind": "<name>" forces it. Also counted by folder: map, quest, recipe, loot, spawngroup, weapon,
cosmetic, equipslot, room, roomupgrade, friendship, condition, interaction, popup, notification, loadingtip, profile,
difficulty, model, material, texture, fx and audio.

The report lists each cloned blueprint as "blueprint  <new name>  <- <donor>", the line of each registry file says how
many of its entries were blueprints, and the start-up summary counts them as "N blueprints".

What can be cloned: every template class in the game's registry, Blueprint entries (*_BP, VisBP_*) included in this build
(their ParentClass/GeneratedClass tags are renamed with your rules). If an entry still has an unsupported tag
type, the sync stops with a clear error and the registry is left unchanged.

Safety: the registry is rebuilt in a temporary file and only replaces the old one when everything worked. Before it
is written, the rebuilt registry is parsed again and its counts are checked; any error or mismatch aborts the sync
and leaves the registry exactly as it was. Make sure your "rules" really rename each source's object path: an entry
whose name is left unchanged would be added a second time under the same name.
Hero mods: blueprint classes (*_BP) can be cloned in this build, and so can montage sets and other entries with an
empty tag map (e.g. PJ_* projectiles).

To clone one donor more than once (e.g. extra palettes made from one original palette), give that source its own
rules, which replace the global ones for that entry:

  {"source": "/Game/.../HeroSkinPalette_HR_SPDR_DemonSpider.HeroSkinPalette_HR_SPDR_DemonSpider",
   "rules": [["HeroSkinPalette_HR_SPDR_DemonSpider", "HeroSkinPalette_HR_SPDR_BigTime4"], ["DemonSpider", "BigTime"]]}

New in this build (merged from 1.1 + 1.2.0 + blueprint cloning)
---------------------------------------------------------------
Enemy factions and Mirror Table regions: "kind": "faction" and "kind": "region" in the manifest. They are never guessed
from a path; the log counts them on their own ("1 faction and 1 region"). "kind": "cards" or "card" is the same as "gear".
Any other unknown "kind" counts as a suit, as before.

The console window: it shows, in colour, what the tool found and what it cloned: ORANGE = everything the mods add (heroes,
suits, gear, abilities, characters, blueprints, palettes, effects, pak names, reasons...), WHITE = normal text, LIGHT RED = errors,
light blue = the banner. The text is 25% bigger than the console's own. The report lists the totals per kind, the kinds that can be
cloned but have nothing yet, and then every pak, every mod in it and every cloned entry with its donor ("gear  Gear_X  <- Gear_Y"),
so you can tell which mod cloned what. SuitRegistry.log always has the same full list. Windows 10+ shows 24-bit colour; older
consoles fall back to the 16 basic colours.

options.txt (in %LOCALAPPDATA%\MidnightSunsSuitRegistry, created on the first run; delete it to get the defaults back):
  show_always=1    1 = the window on every launch (adds about hold_seconds to the start), 0 = only when the registry is rebuilt
  hold_seconds=4   how long the window stays after the report
  font_percent=125 text size in percent of the console's own (100 = unchanged). Works in the classic console host only
  full_list=1      1 = every cloned entry on the screen, 0 = only the totals (the log file always has everything)

Linux: update.sh now stops with a clear message when no Proton is found (it used to stop silently).


CREDITS
-------
Only1DragonRage contributed version 2.1.0's main changes: blueprint cloning, the report window and options.txt, the
coloured console and log, and 23 more mod kinds.
Only1DragonRage contributed version 2.0.0's main changes: cloning montage sets and other entries with an empty tag
map, the self-check after each rebuild, and the new mod kinds.
