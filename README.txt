MMS REGISTRY (formerly Midnight Suns Suit Registry)
===================================================

Adds new hero slots, new suit slots and new palette slots to Marvel's Midnight Suns, and new cards, abilities,
enemy factions, Mirror Table regions and other game content.

The game only finds heroes, outfits, palettes, cards and its other content through its asset registry, and there is
only one registry, so standalone mods like these can't each bring their own. This mod is a single file, version.dll,
that builds one shared registry (zz_MidnightSuns_SuitRegistry_P.pak; the file name is kept from the old name so
existing mods keep working) from the mod paks you have installed - automatically, every time the game starts, on
Steam and Epic. Add or remove a hero, suit, palette or card pak (or any other mod made for it), press Play: done.


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
- Every launch it checks the mod paks first; when nothing changed you won't notice it.
- Mod paks can be in Content\Paks or any subfolder of it (e.g. Content\Paks\~mods).
- When something changed (a mod added/removed/updated, or a game update), a small window shows the rebuild for about
  10 seconds before the game starts.
- The very first rebuild downloads the Oodle decompression library once (needed to read the game's files). Offline?
  Put oodle-data-shared.dll or oo2core_9_win64.dll next to version.dll instead.
- If the game is in a protected folder (e.g. C:\Program Files\Epic Games) Windows asks for permission to update the
  registry pak.
- If something is wrong (e.g. a suit made for DLC you don't have) a message says so, and the game still starts.
  The registry pak is only replaced when the new one was built and checked without errors.
- "Verify game files" on Steam/Epic may remove version.dll: just copy it in again.
- Another mod that also uses version.dll can't be used at the same time.
- Log: %LOCALAPPDATA%\MidnightSunsSuitRegistry\SuitRegistry.log (Linux: inside the game's Proton prefix).


FOR MOD AUTHORS
---------------
Each mod pak carries a manifest at  CodaGame/SuitMods/<id>.json  (the game ignores it):

  {"format": 1, "id": "Venom_SpaceKnight", "title": "Space Knight (Venom)",
   "sources": ["/Game/.../TacticalOutfit_HR_VENM_Anti.TacticalOutfit_HR_VENM_Anti", "..."],
   "rules": [["AntiVenom", "SpaceKnight"]], "keep": []}

"sources" are the original (donor) registry entries: the outfit, its palettes, meshes, physics, materials and
textures. Each one is cloned with "rules" applied in order to every name ([old, new] text replacements); names
containing a "keep" string are left unchanged. "id" must be unique. Don't ship AssetRegistry files in your pak.
Make sure your "rules" really rename each source's object path: an entry whose name stays the same is added a
second time under that name.

To clone one donor more than once (e.g. extra palettes made from one original palette), give that source its own
rules, which replace the global ones for that entry:

  {"source": "/Game/.../HeroSkinPalette_HR_SPDR_DemonSpider.HeroSkinPalette_HR_SPDR_DemonSpider",
   "rules": [["HeroSkinPalette_HR_SPDR_DemonSpider", "HeroSkinPalette_HR_SPDR_BigTime4"], ["DemonSpider", "BigTime"]]}

KINDS. "kind" in the manifest says what the mod adds, and the log counts each kind on its own ("1 hero, 2 suits,
1 palette, 3 cards, 1 faction and 1 region"):

  hero         a new playable character
  suit         a new suit (outfit)
  palette      palettes only
  cards        cards (Items/Gear/...); "gear" works too
  faction      a new enemy faction
  region       a new Mirror Table region
  ability      abilities (Ability_*) and their projectiles (PJ_*) under /Abilities/
  character    enemies and NPCs (Character_* under /Characters/, outside the heroes' folders)
  animation    animations (in /_Anim/, /_Anims/, /Anims/, /Animations/, /MontageSets/, /MontageAliases/, or *_MSet)
  mod          tactical mods / card upgrades (AbilityMod_*, TacticalMod_*)
  effect       Effect_*
  keyword      Keyword_*
  stage, objective, encounter, mission, challenge, combatbonus, reward, achievement, lore, voice, heroop, randset,
  abbeyoutfit, photobooth, resource: templates in /Templates/Stages/, /Templates/Objectives/,
  /Templates/Encounters/, /Templates/Missions/, /Templates/Challenges/, /Templates/CombatBonuses/,
  /Templates/Rewards/, /Templates/Achievements/, /Templates/Lore/, /Templates/Voices/,
  /Templates/HeroOpNarratives/, /Templates/RandSets/, /Items/AbbeyOutfits/, /Templates/Photobooth/ and
  /Templates/Items/Resources/

Without a "kind", a manifest with an outfit (TacticalOutfits/...) is a suit; one without is the first kind from
"palette" on in this list that it has sources of, else a suit. Hero, faction and region are never guessed. Palette,
card and the other content mods count what they add ("3 cards"); hero, suit, faction and region mods count once.
An unknown "kind" counts as a suit, as each newer kind does in older versions. The kind only changes the log's
words: every source is cloned the same way. The folder name SuitMods is kept for all kinds, so existing mods work
unchanged.

Cards and abilities: clone an existing card's gear item, ability and card art and rename them with "rules", e.g.
  {"format": 1, "id": "Hunter_QuickStrike", "title": "Quick Strike (Hunter)", "kind": "cards",
   "sources": ["/Game/Coda/Templates/Items/Gear/Hunter/Power/Gear_HR_HNTR_QuickSlash.Gear_HR_HNTR_QuickSlash",
               "/Game/Coda/Templates/Abilities/Heroes/Hunter/Ability_HR_HNTR_QuickSlash.Ability_HR_HNTR_QuickSlash",
               "/Game/Coda/UI/Textures/CardArt/Card_HR_HNTR_QuickSlash.Card_HR_HNTR_QuickSlash"],
   "rules": [["QuickSlash", "QuickStrike"]], "keep": []}
Every new card needs its own EntitlementID. An ability's visualization blueprint (VisBP_*) can't be cloned:
reference the original one from your ability.

Animations: the registry entry only mirrors the donor's tags; the animation itself must be in your pak at the new
path, with the same class and skeleton as the donor.

WHAT CAN BE CLONED: every kind of entry in the game's registry except blueprints - Blueprint (*_BP, VisBP_*),
WidgetBlueprint (WBP_*), AnimBlueprint, and some levels and level sequences. Those stop the sync with "tag value type
4 is not handled" and the registry is left unchanged: leave them out of "sources" and reference the original ones
from your assets (direct references load fine). Montage sets and other entries with an empty tag map (e.g. PJ_*
projectiles) can be cloned.

SAFETY: the registry is rebuilt in a temporary file and only replaces the old one when everything worked. Before it
is written, the rebuilt registry is read back and its counts are checked; an error or a mismatch stops the sync and
leaves the installed registry exactly as it was.


CREDITS
-------
Only1DragonRage contributed version 2.0.0's main changes: cloning montage sets and other entries with an empty tag
map, the self-check after each rebuild, and the new mod kinds.
