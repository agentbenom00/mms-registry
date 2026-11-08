// Keep zz_MidnightSuns_SuitRegistry_P.pak in sync with the installed hero, suit, palette, gear (cards), ability, character,
// animation, enemy faction, Mirror Table region and other template paks.
//
// Midnight Suns finds outfits/palettes only through its one AssetRegistry (CodaGame/AssetRegistry*.bin, main + 8
// languages), so every standalone suit has to be registered in the same patched copy. Each suit pak carries a
// manifest, CodaGame/SuitMods/<id>.json (the game ignores it):
//   {"format": 1, "id": ..., "title": ..., "sources": [original object paths to clone],
//    "rules": [[old, new], ...] (applied in order to every name), "keep": [substrings whose names stay unchanged]}
// A source may also be {"source": path, "rules": [[old, new], ...]}: those rules replace the global ones for that
// entry, so one donor can be cloned more than once (e.g. extra palettes cloned from one original palette).
// The registry pak also carries CodaGame/SuitRegistry/state.json: what it was built from (game pak sizes/dates and
// the manifests' hashes). It is rebuilt only when that no longer matches what is installed.
// Threat Room options (StrategyMissionMods sources, the "threatroom" kind) also put the shared Threat Room panel into
// the registry pak (threatroom.c), unless an installed pak ships its own WBP_MissionModsPanel_THREAT.
#include "sr.h"

// More label-only categories, recognised by a folder in the source path. Every one of them is cloned by exactly the
// same code as the others; the kind only changes the wording in the log. Checked one by one against the game's
// registry: each of these folders clones with no failure apart from the Blueprint entries, which are refused.
typedef struct { const char *kind, *one, *many, *path, *not_path; } extra_kind;
static const extra_kind EXTRA[] = {
    {"stage", "stage", "stages", "/Templates/Stages/", NULL},
    {"objective", "objective", "objectives", "/Templates/Objectives/", NULL},
    {"encounter", "encounter", "encounters", "/Templates/Encounters/", NULL},
    // a Threat Room option (StrategyMissionMod_ApplyMissionMod): also makes the registry install the shared Threat Room panel
    {"threatroom", "Threat Room option", "Threat Room options", "/StrategyMissionMods/", NULL},
    {"mission", "mission", "missions", "/Templates/Missions/", "/StrategyMissionMods/"},
    {"challenge", "challenge", "challenges", "/Templates/Challenges/", NULL},
    {"combatbonus", "combat bonus", "combat bonuses", "/Templates/CombatBonuses/", NULL},
    {"reward", "reward", "rewards", "/Templates/Rewards/", NULL},
    {"achievement", "achievement", "achievements", "/Templates/Achievements/", NULL},
    {"lore", "lore entry", "lore entries", "/Templates/Lore/", NULL},
    {"voice", "voice", "voices", "/Templates/Voices/", NULL},
    {"heroop", "hero op", "hero ops", "/Templates/HeroOpNarratives/", NULL},
    {"randset", "random set", "random sets", "/Templates/RandSets/", NULL},
    {"abbeyoutfit", "abbey outfit", "abbey outfits", "/Items/AbbeyOutfits/", NULL},
    {"photobooth", "photobooth item", "photobooth items", "/Templates/Photobooth/", NULL},
    {"resource", "resource item", "resource items", "/Templates/Items/Resources/", "/Palettes/"},
    // more label-only categories (v13). Every one of them was checked by cloning a sample of its asset class out of the game's real
    // registry, rebuilding it and re-parsing it (all 560 asset classes of the registry cloned and passed the self-check)
    {"map", "map", "maps", "/Maps/", NULL},
    {"quest", "quest asset", "quest assets", "/Strategy/Quests/", NULL},
    {"recipe", "recipe", "recipes", "/Templates/Recipes/", NULL},
    {"loot", "loot table", "loot tables", "/Templates/LootTables/", NULL},
    {"spawngroup", "spawn group", "spawn groups", "/Templates/UnitSelectors/", NULL},
    {"weapon", "weapon", "weapons", "/Items/Weapons/", NULL},
    {"cosmetic", "cosmetic", "cosmetics", "/Items/Cosmetics/", NULL},
    {"equipslot", "equipment slot", "equipment slots", "/Items/EquipmentSlots/", NULL},
    {"room", "room", "rooms", "/Strategy/Room", NULL},
    {"roomupgrade", "room upgrade", "room upgrades", "/RoomUpgrades/", NULL},
    {"friendship", "friendship entry", "friendship entries", "/Strategy/Friendship/", NULL},
    {"condition", "strategy condition", "strategy conditions", "/Strategy/Conditions/", NULL},
    {"interaction", "interaction", "interactions", "/Strategy/Interactions/", NULL},
    {"popup", "popup", "popups", "/Templates/Popups/", NULL},
    {"notification", "notification", "notifications", "/Templates/Notifications/", NULL},
    {"loadingtip", "loading tip", "loading tips", "/Templates/LoadingScreenTips/", NULL},
    {"profile", "character profile", "character profiles", "/Characters/Profiles/", NULL},
    {"difficulty", "difficulty", "difficulties", "/Templates/Difficulties/", NULL},
    {"model", "model (mesh / skeleton)", "models (meshes / skeletons)", "Model/", NULL},
    {"material", "material", "materials", "Materials/", NULL},
    {"texture", "texture", "textures", "/Textures/", NULL},
    {"fx", "visual effect", "visual effects", "/FX/", NULL},
    {"audio", "sound event", "sound events", "/WwiseAudio/Events/", NULL},
    // never guessed from a path: they are only counted when the manifest says "kind": "faction" / "region"
    {"faction", "faction", "factions", NULL, NULL},
    {"region", "region", "regions", NULL, NULL},
};
#define MAXEXTRA 64
#define NEXTRA ((int)(sizeof EXTRA / sizeof *EXTRA))

// a blueprint class entry: *_BP, VisBP_*, WBP_*, ABP_* (cloned with the export-path tag support of reg_clone)
static int is_blueprint_src(const char *src)
{
    const char *obj = strrchr(src, '/');
    if (!obj) return 0;
    obj++;
    if (!strncmp(obj, "VisBP_", 6) || !strncmp(obj, "WBP_", 4) || !strncmp(obj, "ABP_", 4)) return 1;
    const char *dot = strchr(obj, '.');
    return dot && dot - obj > 3 && !strncmp(dot - 3, "_BP", 3);
}

typedef struct { char **from, **to; int n; } ruleset;

typedef struct {
    char *id, *title, *pak, hash[17];
    char **sources; int nsrc;
    ruleset *src_rules;                                         // per source; n < 0 = use the global rules
    ruleset rules;
    char **keep; int nkeep;
    int is_palette;                                             // only adds palettes (no outfit): a "palette" mod
    int is_hero;                                                // "kind": "hero": a new playable character
    int is_gear, is_ability, is_char, is_anim;                  // adds gear (Items/Gear), abilities (Ability_*), characters, animations
    int is_mod, is_effect, is_keyword;                          // tactical mods (AbilityMod_*), effects (Effect_*), keywords (Keyword_*)
    int is_extra, nextra[MAXEXTRA];                                   // the EXTRA categories above and how many of each
    int npal;                                                   // palettes it registers
    int nbp;                                                    // blueprint classes it clones (*_BP, VisBP_*, WBP_*)
    int ngear, nabil, nproj, nchar, nanim, nmod, neffect, nkeyword;                                    // gear items / abilities it registers, projectiles it clones
} manifest;

typedef struct {
    manifest *m; int n;
    buf game;                                                   // fingerprint JSON
    char **warn; int nwarn;
    int unsure;                                                 // quick mode: could not decide here
    char *panel_pak;                                            // a pak that ships its own Threat Room panel (the first one)
} scan_result;

static void warn(scan_result *s, const char *fmt, ...)
{
    char t[1024];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(t, sizeof t, fmt, ap);
    va_end(ap);
    s->warn = xrealloc(s->warn, sizeof(char *) * (s->nwarn + 1));
    s->warn[s->nwarn++] = xstrdup(t);
}

static int is_game_pak(const wchar_t *n)
{
    if (_wcsnicmp(n, L"pakchunk", 8)) return 0;
    const wchar_t *p = n + 8;
    if (!iswdigit(*p)) return 0;
    while (iswdigit(*p)) p++;
    return !_wcsicmp(p, L"-WindowsNoEditor.pak");
}

static void json_str(buf *b, const char *s)
{
    buf_u8(b, '"');
    for (; *s; s++) {
        uint8_t c = (uint8_t)*s;
        if (c == '"' || c == '\\') { buf_u8(b, '\\'); buf_u8(b, c); }
        else if (c < 0x20) { char t[8]; snprintf(t, sizeof t, "\\u%04x", c); buf_put(b, t, 6); }
        else buf_u8(b, c);
    }
    buf_u8(b, '"');
}

static int cmp_wstr(const void *a, const void *b) { return wcscmp(*(wchar_t *const *)a, *(wchar_t *const *)b); }

static char **str_array(json *a, int *n, const char *what, const char *pak)
{
    *n = 0;
    if (!a) return NULL;
    if (a->t != J_ARR) sr_fail("%s: \"%s\" in its manifest must be a list", pak, what);
    char **v = xmalloc(sizeof(char *) * (a->n + 1));
    for (int i = 0; i < a->n; i++) {
        if (a->items[i]->t != J_STR) sr_fail("%s: \"%s\" in its manifest must hold text", pak, what);
        v[i] = xstrdup(a->items[i]->s);
    }
    *n = a->n;
    return v;
}

static void parse_rules(json *rules, ruleset *rs, const char *pak)
{
    if (!rules || rules->t != J_ARR) sr_fail("%s: its manifest has no \"rules\" list", pak);
    rs->from = xmalloc(sizeof(char *) * (rules->n + 1));
    rs->to = xmalloc(sizeof(char *) * (rules->n + 1));
    for (int i = 0; i < rules->n; i++) {
        json *r = rules->items[i];
        if (r->t != J_ARR || r->n != 2 || r->items[0]->t != J_STR || r->items[1]->t != J_STR || !r->items[0]->s[0])
            sr_fail("%s: each rule in its manifest must be [\"old\", \"new\"]", pak);
        rs->from[i] = xstrdup(r->items[0]->s);
        rs->to[i] = xstrdup(r->items[1]->s);
    }
    rs->n = rules->n;
}

static void parse_manifest(manifest *m, const uint8_t *data, size_t n, const char *pak)
{
    memset(m, 0, sizeof *m);
    json *j = json_parse((const char *)data, n);
    if (!j || j->t != J_OBJ) sr_fail("%s: its manifest is not valid JSON", pak);
    json *id = json_get(j, "id"), *title = json_get(j, "title"), *src = json_get(j, "sources");
    if (!id || id->t != J_STR || !id->s[0]) sr_fail("%s: its manifest has no \"id\"", pak);
    m->id = xstrdup(id->s);
    m->title = xstrdup(title && title->t == J_STR ? title->s : id->s);
    m->pak = xstrdup(pak);
    snprintf(m->hash, sizeof m->hash, "%016llx", (unsigned long long)fnv1a64(data, n));
    if (!src || src->t != J_ARR || !src->n) sr_fail("%s: its manifest has no \"sources\"", pak);
    m->nsrc = src->n;
    m->sources = xmalloc(sizeof(char *) * (src->n + 1));
    m->src_rules = xcalloc(src->n + 1, sizeof(ruleset));
    for (int i = 0; i < src->n; i++) {
        json *e = src->items[i];
        m->src_rules[i].n = -1;
        if (e->t == J_STR) { m->sources[i] = xstrdup(e->s); continue; }
        json *path = json_get(e, "source");
        if (e->t != J_OBJ || !path || path->t != J_STR)
            sr_fail("%s: each entry of \"sources\" must be a path or {\"source\": path, \"rules\": [...]}", pak);
        m->sources[i] = xstrdup(path->s);
        parse_rules(json_get(e, "rules"), &m->src_rules[i], pak);
    }
    m->keep = str_array(json_get(j, "keep"), &m->nkeep, "keep", pak);
    parse_rules(json_get(j, "rules"), &m->rules, pak);
    // suit, palette, gear or ability: a manifest without an outfit (TacticalOutfits/...) that registers palettes is a
    // palette mod; one without outfits or palettes whose sources are gear (/Items/Gear/...) or abilities (an
    // Ability_* object under /Abilities/) is a gear / ability mod (a manifest with both counts as both).
    // "kind": "suit" / "palette" / "hero" / "gear" / "ability" in the manifest overrides the guess (a hero is never
    // guessed)
    int outfits = 0;
    for (int i = 0; i < m->nsrc; i++) {
        const char *src = m->sources[i], *obj = strrchr(src, '/');
        outfits += strstr(src, "/TacticalOutfits/") != NULL;
        m->npal += strstr(src, "HeroSkinPalette") != NULL;
        m->ngear += strstr(src, "/Items/Gear/") != NULL;
        m->nabil += strstr(src, "/Abilities/") != NULL && obj && !strncmp(obj + 1, "Ability_", 8);
        m->nproj += strstr(src, "/Abilities/") != NULL && obj && !strncmp(obj + 1, "PJ_", 3);
        for (int e = 0; e < NEXTRA; e++)
            m->nextra[e] += EXTRA[e].path && strstr(src, EXTRA[e].path) != NULL && !(EXTRA[e].not_path && strstr(src, EXTRA[e].not_path));
        // tactical mods (card upgrades), persistent effects and ability keywords, by their object name prefix
        m->nmod += obj && (!strncmp(obj + 1, "AbilityMod_", 11) || !strncmp(obj + 1, "TacticalMod_", 12));
        m->neffect += obj && !strncmp(obj + 1, "Effect_", 7);
        m->nkeyword += obj && !strncmp(obj + 1, "Keyword_", 8);
        m->nbp += is_blueprint_src(src);
        // an animation asset (sequence, montage, montage set/alias...): recognised by its folder or suffix, so "kind":
        // "animation" is the reliable way to say it
        m->nanim += strstr(src, "/_Anim/") || strstr(src, "/_Anims/") || strstr(src, "/Anims/") ||
                    strstr(src, "/Animations/") || strstr(src, "/MontageSets/") || strstr(src, "/MontageAliases/") ||
                    (obj && strstr(obj, "_MSet."));
        // a non-hero character template (enemy, NPC...): Character_* under /Characters/ but not in a Heroes folder
        m->nchar += strstr(src, "/Characters/") != NULL && !strstr(src, "/Characters/Hero") && obj &&
                    !strncmp(obj + 1, "Character_", 10);
    }
    json *kind = json_get(j, "kind");
    const char *k = kind && kind->t == J_STR ? kind->s : NULL;
    int k_gear = k && (!_stricmp(k, "gear") || !_stricmp(k, "cards") || !_stricmp(k, "card")), k_ability = k && !_stricmp(k, "ability"), k_char = k && !_stricmp(k, "character"),
        k_anim = k && !_stricmp(k, "animation"),
        k_mod = k && !_stricmp(k, "mod"), k_effect = k && !_stricmp(k, "effect"), k_keyword = k && !_stricmp(k, "keyword");
    int k_extra = -1;
    for (int e = 0; e < NEXTRA; e++) if (k && !_stricmp(k, EXTRA[e].kind)) k_extra = e;
    if (k) {
        m->is_palette = !_stricmp(k, "palette");
        m->is_hero = !_stricmp(k, "hero");
    } else m->is_palette = outfits == 0 && m->npal > 0;
    if (m->is_palette && !m->npal) m->npal = 1;
    if (!m->is_hero && !m->is_palette && (k_gear || k_ability || k_char || k_anim || k_mod || k_effect || k_keyword || k_extra >= 0 || (!k && outfits == 0))) {
        if (k_extra >= 0 && !m->nextra[k_extra]) m->nextra[k_extra] = 1;
        for (int e = 0; e < NEXTRA; e++) m->is_extra |= m->nextra[e] > 0;
        m->is_mod = k_mod || m->nmod > 0;
        m->is_effect = k_effect || m->neffect > 0;
        m->is_keyword = k_keyword || m->nkeyword > 0;
        if (m->is_mod && !m->nmod) m->nmod = 1;
        if (m->is_effect && !m->neffect) m->neffect = 1;
        if (m->is_keyword && !m->nkeyword) m->nkeyword = 1;
        m->is_anim = k_anim || m->nanim > 0;
        if (m->is_anim && !m->nanim) m->nanim = 1;
        m->is_char = k_char || m->nchar > 0;
        if (m->is_char && !m->nchar) m->nchar = 1;
        m->is_gear = k_gear || m->ngear > 0;
        m->is_ability = k_ability || m->nabil > 0 || (m->nproj > 0 && !m->is_gear);   // a projectile-only mod belongs to abilities
        if (m->is_gear && !m->ngear) m->ngear = 1;
        if (m->is_ability && !m->nabil) m->nabil = 1;
    }
    json_free(j);
}

// rename for reg_clone (ctx: the manifest + which source): NULL = unchanged
typedef struct { manifest *m; int src; } rename_ctx;

static char *rename_name(const char *s, void *ctx)
{
    rename_ctx *rc = ctx;
    manifest *m = rc->m;
    const ruleset *rs = m->src_rules[rc->src].n >= 0 ? &m->src_rules[rc->src] : &m->rules;
    for (int i = 0; i < m->nkeep; i++)
        if (strstr(s, m->keep[i])) return NULL;
    char *cur = xstrdup(s);
    for (int i = 0; i < rs->n; i++) {
        const char *a = rs->from[i], *b = rs->to[i];
        size_t la = strlen(a), lb = strlen(b), cnt = 0;
        for (const char *p = strstr(cur, a); p; p = strstr(p + la, a)) cnt++;
        if (!cnt) continue;
        char *nw = xmalloc(strlen(cur) + cnt * lb + 1), *o = nw;
        const char *p = cur;
        for (const char *q = strstr(p, a); q; q = strstr(p, a)) {
            memcpy(o, p, q - p); o += q - p;
            memcpy(o, b, lb); o += lb;
            p = q + la;
        }
        strcpy(o, p);
        free(cur);
        cur = nw;
    }
    if (!strcmp(cur, s)) { free(cur); return NULL; }
    return cur;
}

typedef struct { int registry, json, panel; } mod_filter_ctx;

static int mod_filter(const char *dir, const char *name, void *ctx)
{
    mod_filter_ctx *c = ctx;
    if (!_stricmp(dir, "CodaGame/")) {
        if (name && !_strnicmp(name, "AssetRegistry", 13)) c->registry = 1;
        return name == NULL;                                    // only to look at the names
    }
    if (!_stricmp(dir, TRP_DIR)) {                              // a pak with its own Threat Room panel
        if (name && !_stricmp(name, TRP_NAME ".uasset")) c->panel = 1;
        return name == NULL;
    }
    if (_stricmp(dir, "CodaGame/SuitMods/")) return 0;
    if (!name) return 1;
    size_t n = strlen(name);
    return n > 5 && !_stricmp(name + n - 5, ".json");
}

static const wchar_t *file_name(const wchar_t *path)
{
    const wchar_t *last = path;
    for (const wchar_t *p = path; *p; p++)
        if (*p == L'\\') last = p + 1;
    return last;
}

// *.pak files in the Paks folder and its subfolders (e.g. ~mods: the game mounts those too), as paths relative to
// it. Game paks count only at the top level; copies of them elsewhere (backups) are skipped by the caller.
static void collect_paks(const wchar_t *paks, const wchar_t *rel, int depth, wchar_t ***names, int *nn)
{
    wchar_t *dir = *rel ? wpath(paks, rel) : _wcsdup(paks), *pat = wpath(dir, L"*");
    WIN32_FIND_DATAW fd;
    HANDLE f = FindFirstFileW(pat, &fd);
    free(pat);
    free(dir);
    if (f == INVALID_HANDLE_VALUE) return;
    do {
        const wchar_t *n = fd.cFileName;
        wchar_t *r = *rel ? wpath(rel, n) : _wcsdup(n);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            if (wcscmp(n, L".") && wcscmp(n, L"..") && depth < 4 && !(fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT))
                collect_paks(paks, r, depth + 1, names, nn);
        } else {
            size_t l = wcslen(n);
            if (l > 4 && !_wcsicmp(n + l - 4, L".pak")) {
                *names = xrealloc(*names, sizeof(wchar_t *) * (*nn + 1));
                (*names)[(*nn)++] = r;
                r = NULL;
            }
        }
        free(r);
    } while (FindNextFileW(f, &fd));
    FindClose(f);
}

static const char *extra_name(const manifest *m)
{
    for (int e = 0; e < NEXTRA; e++) if (m->is_extra && m->nextra[e] > 0) return EXTRA[e].kind;
    return "suit";
}

static const char *kind_name(const manifest *m)
{
    return m->is_hero ? "hero" : m->is_palette ? "palette" : m->is_gear ? "gear" : m->is_ability ? "ability" :
           m->is_char ? "character" : m->is_anim ? "animation" : m->is_mod ? "mod" :
           m->is_effect ? "effect" : m->is_keyword ? "keyword" : m->is_extra ? extra_name(m) : m->nbp ? "blueprint" : extra_name(m);
}

// Scan the Paks folder. full = 0: in DllMain (no AES/Oodle/threads); anything unusual sets unsure.
static void scan(const wchar_t *paks, int full, scan_result *s)
{
    memset(s, 0, sizeof *s);
    wchar_t **names = NULL;
    int nn = 0;
    collect_paks(paks, L"", 0, &names, &nn);
    qsort(names, nn, sizeof *names, cmp_wstr);
    buf_u8(&s->game, '[');
    int ngame = 0;
    for (int i = 0; i < nn; i++) {
        wchar_t *full_path = wpath(paks, names[i]);
        char *name8 = w_to_utf8(names[i]);
        if (is_game_pak(names[i])) {
            WIN32_FILE_ATTRIBUTE_DATA a;
            if (GetFileAttributesExW(full_path, GetFileExInfoStandard, &a)) {
                uint64_t size = ((uint64_t)a.nFileSizeHigh << 32) | a.nFileSizeLow;
                uint64_t ft = ((uint64_t)a.ftLastWriteTime.dwHighDateTime << 32) | a.ftLastWriteTime.dwLowDateTime;
                char t[64];
                if (ngame++) buf_u8(&s->game, ',');
                buf_u8(&s->game, '[');
                json_str(&s->game, name8);
                snprintf(t, sizeof t, ",%llu,%lld]", (unsigned long long)size, (long long)(ft / 10000000ull) - 11644473600ll);
                buf_put(&s->game, t, strlen(t));
            }
        } else if (_wcsicmp(names[i], REG_PAK) && _wcsicmp(names[i], REG_PAK_OLD) && !is_game_pak(file_name(names[i]))) {
            jmp_buf j, *outer = sr_jmp;
            static pak pk;
            pak_entry *volatile e = NULL;
            volatile int ne = 0;
            uint8_t *volatile data = NULL;
            memset(&pk, 0, sizeof pk);
            sr_jmp = &j;
            if (!setjmp(j)) {
                int r = pak_open(&pk, full_path, full);
                if (r == -2) s->unsure = 1;                     // encrypted index: needs AES
                else if (r < 0) warn(s, "%s: not a pak file, skipped", name8);
                else {
                    mod_filter_ctx c = {0};
                    int cnt;
                    e = pak_list(&pk, mod_filter, &c, &cnt);
                    ne = cnt;
                    if (c.registry)
                        warn(s, "%s: ships its own AssetRegistry - it conflicts with the shared registry pak (only one wins)", name8);
                    if (c.panel && !s->panel_pak) s->panel_pak = xstrdup(name8);
                    for (int k = 0; k < ne; k++) {
                        size_t n = (size_t)e[k].usize;
                        uint8_t *d = pak_read(&pk, &e[k], full);
                        data = d;
                        s->m = xrealloc(s->m, sizeof(manifest) * (s->n + 1));
                        jmp_buf j2;
                        sr_jmp = &j2;
                        if (setjmp(j2)) { sr_jmp = outer; longjmp(*outer, 1); }    // a bad manifest is an error
                        parse_manifest(&s->m[s->n], d, n, name8);
                        sr_jmp = &j;
                        s->n++;
                        free(data);
                        data = NULL;
                    }
                }
            } else {
                if (!full) s->unsure = 1;
                else warn(s, "%s: could not be read (%s), skipped", name8, sr_error);
            }
            sr_jmp = outer;
            free(data);
            if (e) pak_entries_free(e, ne);
            if (pk.h) pak_close(&pk);
        }
        free(name8);
        free(full_path);
        free(names[i]);
    }
    free(names);
    buf_u8(&s->game, ']');
    buf_u8(&s->game, 0);
}

// Threat Room options registered by the installed mods
static int threatroom_options(const scan_result *s)
{
    int e = 0, n = 0;
    while (e < NEXTRA && strcmp(EXTRA[e].kind, "threatroom")) e++;
    for (int i = 0; i < s->n; i++) n += s->m[i].nextra[e];
    return n;
}

// what the registry does with the Threat Room panel: "none" (no options), "shared:<panel id>" (it ships the shared panel) or
// "skipped:<pak>" (that pak ships its own panel, which would replace the shared one)
static void threatroom_status(const scan_result *s, char *out, size_t n)
{
    if (!threatroom_options(s)) snprintf(out, n, "none");
    else if (s->panel_pak) snprintf(out, n, "skipped:%s", s->panel_pak);
    else snprintf(out, n, "shared:%s", threatroom_panel_id());
}

static int cmp_manifest_id(const void *a, const void *b)
{
    return strcmp((*(manifest *const *)a)->id, (*(manifest *const *)b)->id);
}

static char *expected_state(scan_result *s)
{
    manifest **v = xmalloc(sizeof(manifest *) * (s->n + 1));
    for (int i = 0; i < s->n; i++) v[i] = &s->m[i];
    qsort(v, s->n, sizeof *v, cmp_manifest_id);
    buf b = {0};
    const char *head = "{\"format\":4,\"game\":";
    buf_put(&b, head, strlen(head));
    buf_put(&b, s->game.p, strlen((char *)s->game.p));
    buf_put(&b, ",\"suits\":[", 10);
    for (int i = 0; i < s->n; i++) {
        if (i) buf_u8(&b, ',');
        buf_u8(&b, '[');
        json_str(&b, v[i]->id);
        buf_u8(&b, ',');
        json_str(&b, v[i]->hash);
        buf_u8(&b, ',');
        json_str(&b, kind_name(v[i]));
        buf_u8(&b, ',');
        json_str(&b, v[i]->title);
        buf_u8(&b, ']');
    }
    char tr[300];
    threatroom_status(s, tr, sizeof tr);
    buf_put(&b, "],\"threatroom\":", 15);
    json_str(&b, tr);
    buf_put(&b, "}\n", 3);                                      // (with the 0)
    free(v);
    return (char *)b.p;
}

static int state_filter(const char *dir, const char *name, void *ctx)
{
    (void)ctx;
    if (_stricmp(dir, "CodaGame/SuitRegistry/")) return 0;
    return !name || !_stricmp(name, "state.json");
}

// the state stored in the installed registry pak, NULL if none / unreadable
static char *installed_state(const wchar_t *paks, int *exists)
{
    wchar_t *p = wpath(paks, REG_PAK);
    *exists = GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES;
    char *volatile res = NULL;
    jmp_buf j, *outer = sr_jmp;
    static pak pk;
    pak_entry *volatile e = NULL;
    volatile int ne = 0;
    memset(&pk, 0, sizeof pk);
    sr_jmp = &j;
    if (*exists && !setjmp(j) && pak_open(&pk, p, 0) == 0) {
        int cnt;
        e = pak_list(&pk, state_filter, NULL, &cnt);
        ne = cnt;
        if (ne == 1) {
            uint8_t *d = pak_read(&pk, &e[0], 0);
            d[e[0].usize] = 0;
            res = (char *)d;
        }
    }
    sr_jmp = outer;
    if (e) pak_entries_free(e, ne);
    if (pk.h) pak_close(&pk);
    free(p);
    return res;
}

int sync_quick_check(const wchar_t *paks)
{
    scan_result s;
    scan(paks, 0, &s);
    if (s.unsure) return 1;
    int exists;
    char *have = installed_state(paks, &exists);
    if (s.n == 0) {
        if (exists) return 1;                                   // suits all removed: delete the registry pak
        log_open();                                             // (file writes only: fine under the loader lock)
        log_msg("Paks folder: %ls", paks);
        for (int i = 0; i < s.nwarn; i++) log_msg("warning: %s", s.warn[i]);
        log_msg("no hero, suit, palette, gear, ability, character, animation, mod, effect, keyword, faction, region or other template paks found (searched its subfolders too) - nothing to do");
        return 0;
    }
    char *want = expected_state(&s);
    int differ = !have || strcmp(have, want);
    free(have);
    free(want);
    return differ;                                              // (the small leaks of scan_result: once per launch)
}

// ---------------------------------------------------------------- full sync

enum { HERO, SUIT, PALETTE, GEAR, ABILITY, CHARACTER, ANIMATION, MOD, EFFECT, KEYWORD, BLUEPRINT, KINDS };
#define kind_col_name(k) C_OR                          /* every kind of added thing is shown in orange */
static const char *const kind_one[KINDS] = {"hero", "suit", "palette", "gear", "ability", "character", "animation", "tactical mod", "effect", "keyword", "blueprint"};
static const char *const kind_many[KINDS] = {"heroes", "suits", "palettes", "gear", "abilities", "characters", "animations", "tactical mods", "effects", "keywords", "blueprints"};

// how many of each kind ONE manifest adds (EXTRA kinds follow the KINDS ones); added into cnt
static void tally_one(const manifest *m, int *cnt)
{
    cnt[BLUEPRINT] += m->nbp;
    if (m->is_hero) cnt[HERO]++;
    else if (m->is_palette) cnt[PALETTE] += m->npal;
    else if (m->is_gear || m->is_ability || m->is_char || m->is_anim || m->is_mod || m->is_effect || m->is_keyword || m->is_extra || m->nbp) {
        if (m->is_mod) cnt[MOD] += m->nmod;
        if (m->is_effect) cnt[EFFECT] += m->neffect;
        if (m->is_keyword) cnt[KEYWORD] += m->nkeyword;
        if (m->is_anim) cnt[ANIMATION] += m->nanim;
        if (m->is_gear) cnt[GEAR] += m->ngear;
        if (m->is_ability) cnt[ABILITY] += m->nabil;
        if (m->is_char) cnt[CHARACTER] += m->nchar;
        for (int e = 0; e < NEXTRA; e++) cnt[KINDS + e] += m->nextra[e];
    }
    else cnt[SUIT]++;
}

static void tally(scan_result *s, int *cnt)
{
    _Static_assert(NEXTRA <= MAXEXTRA, "manifest.nextra is too small");
    memset(cnt, 0, sizeof(int) * (KINDS + MAXEXTRA));
    for (int i = 0; i < s->n; i++) tally_one(&s->m[i], cnt);
}

static const char *kind_label(int k, int plural)
{
    return k < KINDS ? (plural ? kind_many[k] : kind_one[k]) : (plural ? EXTRA[k - KINDS].many : EXTRA[k - KINDS].one);
}

// "1 hero, 2 suits, 1 palette, 3 gear, 1 ability and 1 character" (with colour markers)
static void fmt_counts(const int *cnt, char *out, size_t n)
{
    int parts = 0, done = 0;
    for (int k = 0; k < KINDS + NEXTRA; k++) parts += cnt[k] > 0;
    *out = 0;
    for (int k = 0; k < KINDS + NEXTRA; k++) {
        if (!cnt[k]) continue;
        size_t l = strlen(out);
        snprintf(out + l, n - l, C_WH "%s" C_OR "%d %s", done ? (done == parts - 1 ? " and " : ", ") : "", cnt[k], kind_label(k, cnt[k] != 1));
        done++;
    }
    size_t l = strlen(out);
    snprintf(out + l, n - l, C_WH);
}

static void summary(scan_result *s, char *out, size_t n)
{
    int cnt[KINDS + MAXEXTRA];
    tally(s, cnt);
    fmt_counts(cnt, out, n);
}

static void manifest_counts(const manifest *m, char *out, size_t n)
{
    int cnt[KINDS + MAXEXTRA];
    memset(cnt, 0, sizeof cnt);
    tally_one(m, cnt);
    fmt_counts(cnt, out, n);
}

// what one source of a manifest is, for the report (the cloning code is the same for all of them)
static const char *source_kind(const manifest *m, int i)
{
    const char *src = m->sources[i], *obj = strrchr(src, '/');
    if (is_blueprint_src(src)) return "blueprint";
    if (strstr(src, "/Items/Gear/")) return "gear";
    if (strstr(src, "/Abilities/") && obj && !strncmp(obj + 1, "Ability_", 8)) return "ability";
    if (strstr(src, "/Abilities/") && obj && !strncmp(obj + 1, "PJ_", 3)) return "projectile";
    if (obj && (!strncmp(obj + 1, "AbilityMod_", 11) || !strncmp(obj + 1, "TacticalMod_", 12))) return "tactical mod";
    if (obj && !strncmp(obj + 1, "Effect_", 7)) return "effect";
    if (obj && !strncmp(obj + 1, "Keyword_", 8)) return "keyword";
    if (strstr(src, "/_Anim/") || strstr(src, "/_Anims/") || strstr(src, "/Anims/") || strstr(src, "/Animations/") ||
        strstr(src, "/MontageSets/") || strstr(src, "/MontageAliases/") || (obj && strstr(obj, "_MSet."))) return "animation";
    if (strstr(src, "/Characters/") && !strstr(src, "/Characters/Hero") && obj && !strncmp(obj + 1, "Character_", 10)) return "character";
    if (strstr(src, "HeroSkinPalette")) return "palette";
    for (int e = 0; e < NEXTRA; e++)
        if (EXTRA[e].path && strstr(src, EXTRA[e].path) && !(EXTRA[e].not_path && strstr(src, EXTRA[e].not_path))) return EXTRA[e].one;
    return m->is_hero ? "hero" : m->is_palette ? "palette" : kind_name(m);
}

// the object name inside "/Game/.../Name.Name" (into out)
static void object_name(const char *path, char *out, size_t n)
{
    const char *o = strrchr(path, '/');
    o = o ? o + 1 : path;
    size_t l = strcspn(o, ".");
    if (l >= n) l = n - 1;
    memcpy(out, o, l);
    out[l] = 0;
}

// names of one clone: what the donor is called and what the new entry will be called
static void clone_names(manifest *m, int i, char *to, size_t tn, char *from, size_t fn)
{
    rename_ctx rc = {m, i};
    char *nw = rename_name(m->sources[i], &rc);
    object_name(m->sources[i], from, fn);
    object_name(nw ? nw : m->sources[i], to, tn);
    free(nw);
}

// the console / log report: totals per kind, then pak by pak, mod by mod, every cloned entry with its donor
static void overview(const int *cnt)
{
    for (int k = 0; k < KINDS + NEXTRA; k++)
        if (cnt[k]) log_msg("    " C_OR "%-32s" C_WH "%5d", kind_label(k, cnt[k] != 1), cnt[k]);
    char line[512] = "";
    int first = 1;
    for (int k = 0; k < KINDS + NEXTRA; k++) {
        if (cnt[k]) continue;
        const char *nm = kind_label(k, 1);
        if (strlen(line) + strlen(nm) + 4 > 85) {
            log_msg(C_WH "    %s%s", first ? "can also clone (none added yet): " : "                                  ", line);
            first = 0;
            line[0] = 0;
        }
        if (line[0]) strcat(line, ", ");
        strcat(line, nm);
    }
    if (line[0]) log_msg(C_WH "    %s%s", first ? "can also clone (none added yet): " : "                                  ", line);
}

static void report(scan_result *s)
{
    int cnt[KINDS + MAXEXTRA], npak = 0;
    tally(s, cnt);
    for (int i = 0; i < s->n; i++) {
        int seen = 0;
        for (int k = 0; k < i; k++) seen |= !strcmp(s->m[k].pak, s->m[i].pak);
        npak += !seen;
    }
    char what[1600];
    fmt_counts(cnt, what, sizeof what);
    log_msg("Found " C_OR "%d" C_WH " mod%s in " C_OR "%d" C_WH " pak%s, adding %s", s->n, s->n == 1 ? "" : "s", npak, npak == 1 ? "" : "s", what);
    overview(cnt);
    int tro = threatroom_options(s);
    if (tro && s->panel_pak)
        log_msg(C_RD "  Threat Room: %d option%s registered, but pak %s ships its own Threat Room panel, which replaces the shared "
                "one - those options won't show (remove that pak, or ask its author to register its options instead)" C_WH,
                tro, tro == 1 ? "" : "s", s->panel_pak);
    else if (tro)
        log_msg(C_WH "  Threat Room: " C_OR "%d" C_WH " option%s registered - the shared Threat Room panel lists them", tro, tro == 1 ? "" : "s");
    for (int i = 0; i < s->n; i++) {
        manifest *m = &s->m[i];
        if (i == 0 || strcmp(s->m[i - 1].pak, m->pak)) {
            log_msg("");
            log_msg(C_WH "  Pak " C_OR "%s", m->pak);
        }
        char c[1600];
        manifest_counts(m, c, sizeof c);
        log_msg(C_WH "    Mod " C_OR "%s" C_WH " (id %s): %s", m->title, m->id, c);
        for (int k = 0; k < m->nsrc; k++) {
            char to[256], from[256];
            clone_names(m, k, to, sizeof to, from, sizeof from);
            const char *kind = source_kind(m, k);
            if (sr_opt.full_list) log_msg("      " C_OR "%-13s %-44s" C_WH " <- %s", kind, to, from);
            else log_file_only("      %-13s %-44s <- %s", kind, to, from);
        }
    }
    if (!sr_opt.full_list) log_msg(C_WH "  (the screen shows only the totals: every entry is in " C_OR "SuitRegistry.log" C_WH "; full_list=1 in options.txt shows them here)");
}

typedef struct { char *path; pak *pk; pak_entry *e; } bin_src;

static int registry_filter(const char *dir, const char *name, void *ctx)
{
    (void)ctx;
    if (_stricmp(dir, "CodaGame/")) return 0;
    if (!name) return 1;
    size_t n = strlen(name);
    return !_strnicmp(name, "AssetRegistry", 13) && n > 4 && !_stricmp(name + n - 4, ".bin");
}

static int cmp_bin(const void *a, const void *b) { return strcmp(((const bin_src *)a)->path, ((const bin_src *)b)->path); }

#define SYNC_NEEDS_ADMIN 5

static int build(const wchar_t *paks, scan_result *s, const char *state)
{
    if (!oodle_load(1)) sr_fail("Oodle is not available");
    char what[900];
    summary(s, what, sizeof what);
    log_msg("");
    log_msg(C_BL "Patching the game's registry" C_WH " (cloning %s)", what);
    // the game's registries, from its own paks (later paks win, as in the game)
    wchar_t *pat = wpath(paks, L"pakchunk*.pak");
    WIN32_FIND_DATAW fd;
    HANDLE f = FindFirstFileW(pat, &fd);
    free(pat);
    wchar_t **names = NULL;
    int nn = 0;
    if (f != INVALID_HANDLE_VALUE) {
        do if (is_game_pak(fd.cFileName)) { names = xrealloc(names, sizeof(wchar_t *) * (nn + 1)); names[nn++] = _wcsdup(fd.cFileName); }
        while (FindNextFileW(f, &fd));
        FindClose(f);
    }
    qsort(names, nn, sizeof *names, cmp_wstr);
    pak *pks = xcalloc(nn + 1, sizeof(pak));
    bin_src *bins = NULL;
    int nb = 0;
    for (int i = 0; i < nn; i++) {
        wchar_t *p = wpath(paks, names[i]);
        if (pak_open(&pks[i], p, 1)) sr_fail("the game's pak %ls could not be read", names[i]);
        free(p);
        int ne;
        pak_entry *e = pak_list(&pks[i], registry_filter, NULL, &ne);
        for (int k = 0; k < ne; k++) {
            int at = -1;
            for (int q = 0; q < nb; q++) if (!_stricmp(bins[q].path, e[k].path)) at = q;
            if (at < 0) { bins = xrealloc(bins, sizeof *bins * (nb + 1)); at = nb++; }
            else free(bins[at].e);
            bins[at].path = e[k].path;
            bins[at].pk = &pks[i];
            bins[at].e = xmalloc(sizeof(pak_entry));
            *bins[at].e = e[k];
        }
        free(e);                                                // (entries moved into bins)
    }
    int have_main = 0;
    for (int q = 0; q < nb; q++) have_main |= !_stricmp(bins[q].path, "CodaGame/AssetRegistry.bin");
    if (!have_main) sr_fail("CodaGame/AssetRegistry.bin was not found in the game's paks");
    qsort(bins, nb, sizeof *bins, cmp_bin);

    wchar_t *final_path = wpath(paks, REG_PAK), *tmp = wpath(paks, REG_PAK L".tmp");
    pak_writer *w = pak_write_begin(tmp);
    if (!w) {
        DWORD e = GetLastError();
        if (e == ERROR_ACCESS_DENIED) return SYNC_NEEDS_ADMIN;
        sr_fail("could not create %ls (error %lu)", tmp, e);
    }
    jmp_buf j, *outer = sr_jmp;
    sr_jmp = &j;
    if (setjmp(j)) { sr_jmp = outer; DeleteFileW(tmp); longjmp(*outer, 1); }
    for (int q = 0; q < nb; q++) {
        uint8_t *data = pak_read(bins[q].pk, bins[q].e, 1);
        reg *r = reg_parse(data, (size_t)bins[q].e->usize);
        int nbp_done = 0, ncl = 0;
        for (int i = 0; i < s->n; i++)
            for (int k = 0; k < s->m[i].nsrc; k++) {
                rename_ctx rc = {&s->m[i], k};
                nbp_done += is_blueprint_src(s->m[i].sources[k]);
                ncl++;
                if (reg_clone(r, s->m[i].sources[k], rename_name, &rc))
                    sr_fail("Pak %s (mod %s): %s is not in the game's registry (is its DLC installed?). Remove that pak; the "
                            "registry was left unchanged.", s->m[i].pak, s->m[i].title, s->m[i].sources[k]);
            }
        size_t on;
        uint8_t *out = reg_build(r, &on);
        reg_free(r);
        log_msg("  " C_OR "%s" C_WH ": " C_OR "%d" C_WH " registry entries cloned", bins[q].path, ncl);
        if (nbp_done) log_msg("      " C_WH "(" C_OR "%d" C_WH " of them blueprints: pawn, visualization and widget classes)", nbp_done);
        pak_write_file(w, bins[q].path, out, on, 1);
        free(out);
    }
    if (threatroom_options(s) && !s->panel_pak) threatroom_write(pks, nn, w);
    pak_write_file(w, STATE_PATH, (const uint8_t *)state, strlen(state), 0);
    pak_write_end(w);
    sr_jmp = outer;
    if (!MoveFileExW(tmp, final_path, MOVEFILE_REPLACE_EXISTING)) {
        DWORD e = GetLastError();
        DeleteFileW(tmp);
        if (e == ERROR_ACCESS_DENIED) return SYNC_NEEDS_ADMIN;
        sr_fail("could not replace %ls (error %lu)", final_path, e);
    }
    for (int i = 0; i < nn; i++) { pak_close(&pks[i]); free(names[i]); }
    free(names);
    free(final_path);
    free(tmp);
    return 0;
}

// what changed since the installed registry pak was built (its state.json), in words
static void log_changes(const char *have, scan_result *s)
{
    json *old = json_parse(have, strlen(have));
    json *fmt = json_get(old, "format"), *game = json_get(old, "game"), *suits = json_get(old, "suits");
    if (!old || !fmt || fmt->num != 4 || !suits || suits->t != J_ARR) {
        log_msg(C_OR "Reason: the registry pak was built by an older version");
        json_free(old);
        return;
    }
    int any = 0;
    // the game part: compare the fingerprint text the same way the state is made
    buf g = {0};
    if (game && game->t == J_ARR) {
        buf_u8(&g, '[');
        for (int i = 0; i < game->n; i++) {
            json *e = game->items[i];
            if (i) buf_u8(&g, ',');
            if (e->t != J_ARR || e->n != 3) continue;
            buf_u8(&g, '[');
            json_str(&g, e->items[0]->s ? e->items[0]->s : "");
            char t[64];
            snprintf(t, sizeof t, ",%.0f,%.0f]", e->items[1]->num, e->items[2]->num);
            buf_put(&g, t, strlen(t));
        }
        buf_u8(&g, ']');
    }
    buf_u8(&g, 0);
    if (strcmp((char *)g.p, (char *)s->game.p)) { log_msg(C_OR "Reason: the game files changed (game update?)"); any = 1; }
    buf_free(&g);
    for (int i = 0; i < s->n; i++) {
        const char *kind = kind_name(&s->m[i]);
        json *hit = NULL;
        for (int k = 0; k < suits->n; k++) {
            json *e = suits->items[k];
            if (e->t == J_ARR && e->n >= 2 && e->items[0]->s && !strcmp(e->items[0]->s, s->m[i].id)) hit = e;
        }
        if (!hit) { log_msg(C_OR "Reason: " C_WH "new %s%s" C_WH ": %s (pak " C_OR "%s" C_WH ")", kind_col_name(kind), kind, s->m[i].title, s->m[i].pak); any = 1; }
        else if (!hit->items[1]->s || strcmp(hit->items[1]->s, s->m[i].hash)) {
            log_msg(C_OR "Reason: " C_WH "updated %s%s" C_WH ": %s (pak " C_OR "%s" C_WH ")", kind_col_name(kind), kind, s->m[i].title, s->m[i].pak);
            any = 1;
        } else if (hit->n >= 3 && hit->items[2]->s && strcmp(hit->items[2]->s, kind)) {
            // the same manifest, counted as another kind (a registry built before that kind existed)
            log_msg(C_OR "Reason: " C_WH "%s (pak " C_OR "%s" C_WH ") is now listed as %s%s" C_WH " (was %s)", s->m[i].title, s->m[i].pak, kind_col_name(kind), kind, hit->items[2]->s);
            any = 1;
        }
    }
    for (int k = 0; k < suits->n; k++) {
        json *e = suits->items[k];
        if (e->t != J_ARR || e->n < 4 || !e->items[0]->s) continue;
        int still = 0;
        for (int i = 0; i < s->n; i++) still |= !strcmp(s->m[i].id, e->items[0]->s);
        if (!still) { log_msg(C_OR "Reason: " C_WH "removed %s%s" C_WH ": %s", kind_col_name(e->items[2]->s), e->items[2]->s, e->items[3]->s); any = 1; }
    }
    json *tro = json_get(old, "threatroom");
    char tr[300];
    threatroom_status(s, tr, sizeof tr);
    if (!tro || !tro->s || strcmp(tro->s, tr)) { log_msg(C_OR "Reason: " C_WH "the Threat Room panel changes (%s)", tr); any = 1; }
    if (!any) log_msg(C_OR "Reason: the registry pak's record does not match");
    json_free(old);
}

// 0 = up to date / updated, SYNC_NEEDS_ADMIN = the Paks folder is not writable; errors via sr_fail
int sync_run(const wchar_t *paks, int interactive)
{
    (void)interactive;
    log_msg(C_WH "Paks folder: " C_OR "%ls", paks);
    if (sr_opt.show_always) console_show();                     // the report window on every launch (options.txt: show_always)
    {   // an interim build named its registry pak REG_PAK_OLD: remove it, two registry paks would conflict
        wchar_t *old = wpath(paks, REG_PAK_OLD);
        if (GetFileAttributesW(old) != INVALID_FILE_ATTRIBUTES) {
            if (!DeleteFileW(old)) {
                DWORD e = GetLastError();
                free(old);
                if (e == ERROR_ACCESS_DENIED) return SYNC_NEEDS_ADMIN;
                sr_fail("could not remove the old registry pak (error %lu)", e);
            }
            log_msg(C_WH "Removed the old registry pak " C_OR "%ls" C_WH " (replaced by " C_OR "%ls" C_WH ")", REG_PAK_OLD, REG_PAK);
        }
        free(old);
    }
    scan_result s;
    scan(paks, 1, &s);
    for (int i = 0; i < s.nwarn; i++) log_msg(C_OR "warning: %s" C_WH, s.warn[i]);
    for (int i = 0; i < s.n; i++)
        for (int k = i + 1; k < s.n; k++)
            if (!strcmp(s.m[i].id, s.m[k].id))
                sr_fail("mod id %s is in two paks: %s and %s - remove one", s.m[i].id, s.m[i].pak, s.m[k].pak);
    if (s.n) report(&s);
    else log_msg("No hero, suit, palette, gear, ability, character, animation, mod, effect, keyword, faction, region or other template paks found");
    int exists;
    char *have = installed_state(paks, &exists), *want = expected_state(&s);
    if (s.n == 0) {
        if (!exists) { log_msg(C_WH "Registry is up to date - nothing to do"); return 0; }
        console_show();
        wchar_t *p = wpath(paks, REG_PAK);
        if (!DeleteFileW(p)) {
            DWORD e = GetLastError();
            free(p);
            if (e == ERROR_ACCESS_DENIED) return SYNC_NEEDS_ADMIN;
            sr_fail("could not remove the registry pak (error %lu)", e);
        }
        free(p);
        log_msg(C_WH "Removed the registry pak (no mods installed)");
        return 0;
    }
    if (have && !strcmp(have, want)) { log_msg(C_WH "Registry is up to date - nothing to do"); return 0; }
    if (!exists) log_msg(C_OR "Reason: the registry pak does not exist yet" C_WH);
    else if (!have) log_msg(C_OR "Reason: the registry pak was not built by this tool" C_WH);
    else log_changes(have, &s);
    console_show();
    int r = build(paks, &s, want);
    if (r == 0) log_msg("\n" C_BL "Done." C_WH " Registry pak installed: " C_OR "%ls" C_WH " - the game starts now.", REG_PAK);
    return r;
}
