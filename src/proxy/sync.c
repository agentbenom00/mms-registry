// Keep zz_MidnightSuns_SuitRegistry_P.pak in sync with the installed mod paks (heroes, suits, palettes, cards,
// factions, regions, abilities, characters, animations and other templates).
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
#include "sr.h"

typedef struct { char **from, **to; int n; } ruleset;

// What a mod adds, in the order the summary counts them. kind: the "kind" in its manifest (also its word in the log
// and the state); one, many: the count's words. Hero, suit, faction and region mods count once; the others count the
// sources they add ("4 cards", see counts_toward). The kinds from "ability" on only change these words: every kind is
// cloned the same way.
enum {
    K_HERO, K_SUIT, K_PALETTE, K_CARDS, K_FACTION, K_REGION,
    K_ABILITY, K_CHARACTER, K_ANIMATION, K_MOD, K_EFFECT, K_KEYWORD,
    K_STAGE, K_OBJECTIVE, K_ENCOUNTER, K_MISSION, K_CHALLENGE, K_COMBATBONUS, K_REWARD, K_ACHIEVEMENT, K_LORE, K_VOICE,
    K_HEROOP, K_RANDSET, K_ABBEYOUTFIT, K_PHOTOBOOTH, K_RESOURCE,
    K_COUNT
};
typedef struct { const char *kind, *one, *many, *dir, *skip; } kind_info;
static const kind_info kinds[K_COUNT] = {
    {"hero", "hero", "heroes"},
    {"suit", "suit", "suits"},
    {"palette", "palette", "palettes"},
    {"cards", "card", "cards"},                                 // "gear" is read as "cards" too
    {"faction", "faction", "factions"},
    {"region", "region", "regions"},
    {"ability", "ability", "abilities"},
    {"character", "character", "characters"},
    {"animation", "animation", "animations"},
    {"mod", "tactical mod", "tactical mods"},
    {"effect", "effect", "effects"},
    {"keyword", "keyword", "keywords"},
    // templates counted by folder: sources under dir, except those containing skip
    {"stage", "stage", "stages", "/Templates/Stages/"},
    {"objective", "objective", "objectives", "/Templates/Objectives/"},
    {"encounter", "encounter", "encounters", "/Templates/Encounters/"},
    {"mission", "mission", "missions", "/Templates/Missions/"},
    {"challenge", "challenge", "challenges", "/Templates/Challenges/"},
    {"combatbonus", "combat bonus", "combat bonuses", "/Templates/CombatBonuses/"},
    {"reward", "reward", "rewards", "/Templates/Rewards/"},
    {"achievement", "achievement", "achievements", "/Templates/Achievements/"},
    {"lore", "lore entry", "lore entries", "/Templates/Lore/"},
    {"voice", "voice", "voices", "/Templates/Voices/"},
    {"heroop", "hero op", "hero ops", "/Templates/HeroOpNarratives/"},
    {"randset", "random set", "random sets", "/Templates/RandSets/"},
    {"abbeyoutfit", "abbey outfit", "abbey outfits", "/Items/AbbeyOutfits/"},
    {"photobooth", "photobooth item", "photobooth items", "/Templates/Photobooth/"},
    {"resource", "resource item", "resource items", "/Templates/Items/Resources/", "/Palettes/"},
};
#define NO_MODS "no hero, suit, palette, card or other MMS Registry mod paks found"

// whether a manifest source (an object path) counts toward kind k; name = the object's name, after the last '/'
static int counts_toward(int k, const char *src)
{
    const char *slash = strrchr(src, '/'), *name = slash ? slash + 1 : src;
    switch (k) {
    case K_PALETTE: return strstr(src, "HeroSkinPalette") != NULL;
    case K_CARDS: return strstr(src, "/Items/Gear/") != NULL;
    case K_ABILITY:                                             // abilities and their projectiles
        return strstr(src, "/Abilities/") && (!strncmp(name, "Ability_", 8) || !strncmp(name, "PJ_", 3));
    case K_CHARACTER:                                           // enemies and NPCs: heroes are "hero" mods
        return strstr(src, "/Characters/") && !strstr(src, "/Characters/Hero") && !strncmp(name, "Character_", 10);
    case K_ANIMATION: {
        static const char *const marks[] = {"/_Anim/", "/_Anims/", "/Anims/", "/Animations/", "/MontageSets/",
                                            "/MontageAliases/", "_MSet."};
        for (size_t i = 0; i < sizeof marks / sizeof *marks; i++)
            if (strstr(src, marks[i])) return 1;
        return 0;
    }
    case K_MOD: return !strncmp(name, "AbilityMod_", 11) || !strncmp(name, "TacticalMod_", 12);   // card upgrades
    case K_EFFECT: return !strncmp(name, "Effect_", 7);
    case K_KEYWORD: return !strncmp(name, "Keyword_", 8);
    default: return kinds[k].dir && strstr(src, kinds[k].dir) && !(kinds[k].skip && strstr(src, kinds[k].skip));
    }
}

typedef struct {
    char *id, *title, *pak, hash[17];
    char **sources; int nsrc;
    ruleset *src_rules;                                         // per source; n < 0 = use the global rules
    ruleset rules;
    char **keep; int nkeep;
    int kind;                                                   // K_*
    int count;                                                  // what it adds of its kind (1 for hero, suit,
                                                                // faction and region mods)
} manifest;

typedef struct {
    manifest *m; int n;
    buf game;                                                   // fingerprint JSON
    char **warn; int nwarn;
    int unsure;                                                 // quick mode: could not decide here
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
    // "kind" in the manifest: a kind of kinds[] or its singular word ("card", "tactical mod"), or "gear" for cards.
    // Without one, a manifest without an outfit (TacticalOutfits/...) is the first kind from "palette" on that it has
    // sources of (palettes, then cards, abilities, characters...), else a suit. A hero, faction or region is never
    // guessed, and an unknown kind counts as a suit, as each newer kind did before it existed.
    int outfits = 0, cnt[K_COUNT] = {0};
    for (int i = 0; i < m->nsrc; i++) {
        outfits += strstr(m->sources[i], "/TacticalOutfits/") != NULL;
        for (int k = K_PALETTE; k < K_COUNT; k++) cnt[k] += counts_toward(k, m->sources[i]);
    }
    json *kind = json_get(j, "kind");
    m->kind = K_SUIT;
    if (kind && kind->t == J_STR) {
        if (!_stricmp(kind->s, "gear")) m->kind = K_CARDS;
        for (int k = 0; k < K_COUNT; k++)
            if (!_stricmp(kind->s, kinds[k].kind) || !_stricmp(kind->s, kinds[k].one)) m->kind = k;
    } else if (!outfits) {
        for (int k = K_PALETTE; k < K_COUNT && m->kind == K_SUIT; k++)
            if (cnt[k]) m->kind = k;
    }
    m->count = cnt[m->kind] ? cnt[m->kind] : 1;
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

typedef struct { int registry, json; } mod_filter_ctx;

static int mod_filter(const char *dir, const char *name, void *ctx)
{
    mod_filter_ctx *c = ctx;
    if (!_stricmp(dir, "CodaGame/")) {
        if (name && !_strnicmp(name, "AssetRegistry", 13)) c->registry = 1;
        return name == NULL;                                    // only to look at the names
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

static const char *kind_name(const manifest *m) { return kinds[m->kind].kind; }

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
        } else if (_wcsicmp(names[i], REG_PAK) && !is_game_pak(file_name(names[i]))) {
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
    const char *head = "{\"format\":3,\"game\":";
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
    buf_put(&b, "]}\n", 4);                                     // (with the 0)
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
        log_msg(NO_MODS " (searched its subfolders too) - nothing to do");
        return 0;
    }
    char *want = expected_state(&s);
    int differ = !have || strcmp(have, want);
    free(have);
    free(want);
    return differ;                                              // (the small leaks of scan_result: once per launch)
}

// ---------------------------------------------------------------- full sync

// "1 hero, 2 suits, 1 palette, 4 cards, 1 faction and 1 region" (palette, card and other content mods count what
// they add)
static void summary(scan_result *s, char *out, size_t n)
{
    int cnt[K_COUNT] = {0}, parts = 0, done = 0;
    for (int i = 0; i < s->n; i++) cnt[s->m[i].kind] += s->m[i].count;
    for (int k = 0; k < K_COUNT; k++) parts += cnt[k] > 0;
    *out = 0;
    for (int k = 0; k < K_COUNT; k++) {
        if (!cnt[k]) continue;
        size_t l = strlen(out);
        snprintf(out + l, n - l, "%s%d %s", done ? (done == parts - 1 ? " and " : ", ") : "", cnt[k],
                 cnt[k] == 1 ? kinds[k].one : kinds[k].many);
        done++;
    }
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
    char what[512];
    summary(s, what, sizeof what);
    log_msg("patching the game's registry for %s...", what);
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
        for (int i = 0; i < s->n; i++)
            for (int k = 0; k < s->m[i].nsrc; k++) {
                rename_ctx rc = {&s->m[i], k};
                if (reg_clone(r, s->m[i].sources[k], rename_name, &rc))
                    sr_fail("%s (%s): %s is not in the game's registry (is its DLC installed?). Remove that pak; the "
                            "registry was left unchanged.", s->m[i].title, s->m[i].pak, s->m[i].sources[k]);
            }
        size_t on;
        uint8_t *out = reg_build(r, &on);
        reg_free(r);
        log_msg("  %s", bins[q].path);
        pak_write_file(w, bins[q].path, out, on, 1);
        free(out);
    }
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
    if (!old || !fmt || fmt->num != 3 || !suits || suits->t != J_ARR) {
        log_msg("update needed: registry pak was built by an older version");
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
    if (strcmp((char *)g.p, (char *)s->game.p)) { log_msg("update needed: game files changed (game update?)"); any = 1; }
    buf_free(&g);
    for (int i = 0; i < s->n; i++) {
        const char *kind = kind_name(&s->m[i]);
        json *hit = NULL;
        for (int k = 0; k < suits->n; k++) {
            json *e = suits->items[k];
            if (e->t == J_ARR && e->n >= 2 && e->items[0]->s && !strcmp(e->items[0]->s, s->m[i].id)) hit = e;
        }
        if (!hit) { log_msg("update needed: new %s: %s", kind, s->m[i].title); any = 1; }
        else if (!hit->items[1]->s || strcmp(hit->items[1]->s, s->m[i].hash)) {
            log_msg("update needed: updated %s: %s", kind, s->m[i].title);
            any = 1;
        } else if (hit->n >= 3 && hit->items[2]->s && strcmp(hit->items[2]->s, kind)) {
            // the same manifest, counted as another kind (a registry built before these kinds existed)
            log_msg("update needed: %s is now listed as %s (was %s)", s->m[i].title, kind, hit->items[2]->s);
            any = 1;
        }
    }
    for (int k = 0; k < suits->n; k++) {
        json *e = suits->items[k];
        if (e->t != J_ARR || e->n < 4 || !e->items[0]->s) continue;
        int still = 0;
        for (int i = 0; i < s->n; i++) still |= !strcmp(s->m[i].id, e->items[0]->s);
        if (!still) { log_msg("update needed: removed %s: %s", e->items[2]->s, e->items[3]->s); any = 1; }
    }
    if (!any) log_msg("update needed: the registry pak's record does not match");
    json_free(old);
}

// 0 = up to date / updated, SYNC_NEEDS_ADMIN = the Paks folder is not writable; errors via sr_fail
int sync_run(const wchar_t *paks, int interactive)
{
    (void)interactive;
    log_msg("Paks folder: %ls", paks);
    scan_result s;
    scan(paks, 1, &s);
    for (int i = 0; i < s.nwarn; i++) log_msg("warning: %s", s.warn[i]);
    for (int i = 0; i < s.n; i++)
        for (int k = i + 1; k < s.n; k++)
            if (!strcmp(s.m[i].id, s.m[k].id))
                sr_fail("mod id %s is in two paks: %s and %s - remove one", s.m[i].id, s.m[i].pak, s.m[k].pak);
    char what[512];
    summary(&s, what, sizeof what);
    if (s.n) log_msg("found %s:", what);
    else log_msg(NO_MODS);
    for (int i = 0; i < s.n; i++)
        log_msg("  %-11s %-30s %s", kind_name(&s.m[i]), s.m[i].title, s.m[i].pak);
    int exists;
    char *have = installed_state(paks, &exists), *want = expected_state(&s);
    if (s.n == 0) {
        if (!exists) { log_msg("registry is up to date - nothing to do"); return 0; }
        console_show();
        wchar_t *p = wpath(paks, REG_PAK);
        if (!DeleteFileW(p)) {
            DWORD e = GetLastError();
            free(p);
            if (e == ERROR_ACCESS_DENIED) return SYNC_NEEDS_ADMIN;
            sr_fail("could not remove the registry pak (error %lu)", e);
        }
        free(p);
        log_msg("removed the registry pak (no MMS Registry mods installed)");
        return 0;
    }
    if (have && !strcmp(have, want)) { log_msg("registry is up to date - nothing to do"); return 0; }
    if (!exists) log_msg("update needed: registry pak missing");
    else if (!have) log_msg("update needed: registry pak was not built by this tool");
    else log_changes(have, &s);
    console_show();
    int r = build(paks, &s, want);
    if (r == 0) log_msg("installed the registry pak");
    return r;
}
