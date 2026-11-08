// The shared Threat Room panel. Midnight Suns' Enhanced T.H.R.E.A.T. Room (Storm DLC) has one options panel,
// WBP_MissionModsPanel_THREAT, so two mods that each ship an edited copy of it collide (only one is used). Instead,
// the registry writes one shared panel into its pak, rebuilt from the game's own file with the patches in
// threatroom_panel.h (made by tools/threatroom/build_panel.py). It lists every registered Threat Room option: a
// StrategyMissionMod_ApplyMissionMod whose mission mod adds or removes a fact under Mission.AllowedEnemies (Enemy Type),
// Mission.RandomVillain (Villain) or Mission.ThreatRoomOption (a row of its own, one per Description). See README.md.
#include "sr.h"
#include "threatroom_panel.h"

// Rebuild a file from src with an MMSD patch ("MMSD", version 1, source size + SHA-1, result size + SHA-1, then copy
// and insert operations). NULL if src isn't the file the patch was made for; errors in the patch itself fail.
static uint8_t *mmsd_apply(const uint8_t *delta, size_t dn, const uint8_t *src, size_t sn, size_t *out_n)
{
    rd r = {delta, dn, 0};
    rd_need(&r, 60);
    if (memcmp(delta, "MMSD", 4) || rd32(delta + 4) != 1) sr_fail("the Threat Room panel patch is damaged");
    uint32_t ssize = rd32(delta + 8), dsize = rd32(delta + 32), nops = rd32(delta + 56);
    uint8_t h[20];
    if (sn != ssize) return NULL;
    sha1(src, sn, h);
    if (memcmp(h, delta + 12, 20)) return NULL;
    uint8_t *out = xmalloc(dsize + 1);
    size_t at = 0;
    r.at = 60;
    for (uint32_t i = 0; i < nops; i++) {
        uint8_t t = rd_u8(&r);
        uint32_t a = rd_u32(&r);
        if (t == 0) {
            uint32_t len = rd_u32(&r);
            if ((uint64_t)a + len > sn || at + len > dsize) sr_fail("the Threat Room panel patch is damaged");
            memcpy(out + at, src + a, len);
            at += len;
        } else {
            rd_need(&r, a);
            if (at + a > dsize) sr_fail("the Threat Room panel patch is damaged");
            memcpy(out + at, r.p + r.at, a);
            r.at += a;
            at += a;
        }
    }
    sha1(out, at, h);
    if (at != dsize || memcmp(h, delta + 36, 20)) sr_fail("the Threat Room panel patch is damaged");
    *out_n = dsize;
    return out;
}

static int panel_filter(const char *dir, const char *name, void *ctx)
{
    (void)ctx;
    if (_stricmp(dir, TRP_DIR)) return 0;
    if (!name) return 1;
    return !_stricmp(name, TRP_NAME ".uasset") || !_stricmp(name, TRP_NAME ".uexp");
}

// Write the shared panel into the registry pak being built (pks: the game's paks, in load order). 1 = written;
// 0 = not possible here (the reason is logged; the rest of the registry is unaffected).
int threatroom_write(pak *pks, int npks, pak_writer *w)
{
    static const struct { const char *ext; const unsigned char *delta; size_t n; } part[2] = {
        {".uasset", TRP_UASSET, sizeof TRP_UASSET}, {".uexp", TRP_UEXP, sizeof TRP_UEXP}};
    pak *src_pk[2] = {0};
    pak_entry src_e[2];
    for (int i = 0; i < npks; i++) {                            // later paks win, as in the game
        int ne;
        pak_entry *e = pak_list(&pks[i], panel_filter, NULL, &ne);
        for (int k = 0; k < ne; k++)
            for (int q = 0; q < 2 && e[k].path; q++) {
                size_t l = strlen(e[k].path), x = strlen(part[q].ext);
                if (l > x && !_stricmp(e[k].path + l - x, part[q].ext)) { src_pk[q] = &pks[i]; src_e[q] = e[k]; e[k].path = NULL; e[k].blocks = NULL; }
            }
        pak_entries_free(e, ne);
    }
    if (!src_pk[0] || !src_pk[1]) {
        log_msg(C_RD "  Threat Room panel: the game's WBP_MissionModsPanel_THREAT was not found (is the Storm DLC installed?) - "
                "registered Threat Room options won't show" C_WH);
        return 0;
    }
    uint8_t *out[2] = {0};
    size_t on[2];
    for (int q = 0; q < 2; q++) {
        uint8_t *data = pak_read(src_pk[q], &src_e[q], 1);
        if (!data) sr_fail("the game's %s%s could not be read (%s)", TRP_NAME, part[q].ext, sr_error);
        out[q] = mmsd_apply(part[q].delta, part[q].n, data, (size_t)src_e[q].usize, &on[q]);
        free(data);
        if (!out[q]) {
            free(out[0]);
            log_msg(C_RD "  Threat Room panel: the game's %s%s is not the one this version was made for (a game update?) - "
                    "registered Threat Room options won't show until the MMS Registry is updated" C_WH, TRP_NAME, part[q].ext);
            return 0;
        }
    }
    for (int q = 0; q < 2; q++) {
        char path[300];
        snprintf(path, sizeof path, "%s%s%s", TRP_DIR, TRP_NAME, part[q].ext);
        pak_write_file(w, path, out[q], on[q], 1);
        free(out[q]);
    }
    log_msg("  " C_OR "Threat Room panel" C_WH ": the shared panel is in the registry pak");
    return 1;
}
