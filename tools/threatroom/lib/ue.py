"""Helpers for UAssetAPI JSON packages (from tools/uasset-json) and the extracted game files."""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
GAME = os.path.join(WORK, "game")          # extracted game files (CodaGame/...)
CACHE = os.path.join(WORK, "json")         # JSON dumps of game packages
TOOLS = os.path.expanduser("~/Tools")
# the project build (tools/build_uasset_json.sh: + fix-offsets, Niagara-safe UAssetAPI) when present
UASSET_JSON = os.path.join(WORK, "uasset-json", "uasset-json")
if not os.path.exists(UASSET_JSON):
    UASSET_JSON = os.path.join(TOOLS, "uasset-json", "uasset-json")
REPAK = os.path.join(TOOLS, "repak", "repak_cli-x86_64-unknown-linux-gnu", "repak")
PAKS = os.path.expanduser("~/.steam/steam/steamapps/common/Marvel's Midnight Suns/MidnightSuns/Content/Paks")
ENV = dict(os.environ, DOTNET_ROOT=os.path.join(TOOLS, "dotnet"), DOTNET_CLI_TELEMETRY_OPTOUT="1")

# mount roots: package path prefix -> folder inside the pak
MOUNTS = [("/Game/", "CodaGame/Content/"), ("/DLC_Storm/", "CodaGame/Plugins/DLC_Storm/Content/"),
          ("/DLC_Morbius/", "CodaGame/Plugins/DLC_Morbius/Content/"), ("/DLC_BonusMission/", "CodaGame/Plugins/DLC_BonusMission/Content/")]


def pkg_file(pkg):
    """/Game/Coda/X/Y (or /Game/Coda/X/Y.Y) -> CodaGame/Content/Coda/X/Y.uasset"""
    pkg = pkg.split(".")[0].split(":")[0]
    for a, b in MOUNTS:
        if pkg.startswith(a):
            return b + pkg[len(a):] + ".uasset"
    raise ValueError("unknown mount: " + pkg)


def file_pkg(path):
    path = path.replace(".uasset", "")
    for a, b in MOUNTS:
        if path.startswith(b):
            return a + path[len(b):]
    raise ValueError("unknown folder: " + path)


_pak_index = None


def _index():
    global _pak_index
    if _pak_index is None:
        _pak_index = {}
        key = "0x" + open(os.path.join(TOOLS, "mms_aes.hex")).read().strip()
        for pk in ("pakchunk0", "pakchunk11"):
            p = os.path.join(PAKS, pk + "-WindowsNoEditor.pak")
            out = subprocess.run([REPAK, "-a", key, "list", p], capture_output=True, text=True, check=True).stdout
            for line in out.splitlines():
                _pak_index.setdefault(line, p)
    return _pak_index


def extract(rel):
    """Make sure the game file rel (CodaGame/...) and its .uexp/.ubulk are in work/game; return the local path."""
    dst = os.path.join(GAME, rel)
    if os.path.exists(dst):
        return dst
    idx = _index()
    if rel not in idx:
        raise FileNotFoundError(rel)
    key = "0x" + open(os.path.join(TOOLS, "mms_aes.hex")).read().strip()
    base = rel[: -len(".uasset")]
    for ext in (".uasset", ".uexp", ".ubulk"):
        f = base + ext
        if f in idx:
            os.makedirs(os.path.dirname(os.path.join(GAME, f)), exist_ok=True)
            with open(os.path.join(GAME, f), "wb") as o:
                subprocess.run([REPAK, "-a", key, "get", idx[f], f], stdout=o, check=True)
    return dst


def load(pkg):
    """Game package path -> UAssetAPI JSON dict (cached)."""
    rel = pkg_file(pkg)
    js = os.path.join(CACHE, rel[: -len(".uasset")] + ".json")
    if not os.path.exists(js):
        src = extract(rel)
        os.makedirs(os.path.dirname(js), exist_ok=True)
        subprocess.run([UASSET_JSON, "tojson", src, js], check=True, env=ENV)
    with open(js) as f:
        return json.load(f)


def write(d, out_uasset):
    """UAssetAPI JSON dict -> .uasset/.uexp at out_uasset."""
    os.makedirs(os.path.dirname(out_uasset), exist_ok=True)
    tmp = out_uasset[: -len(".uasset")] + ".tmp.json"
    with open(tmp, "w") as f:
        json.dump(d, f)
    subprocess.run([UASSET_JSON, "fromjson", tmp, out_uasset], check=True, env=ENV)
    os.remove(tmp)


def kismet_offsets(d):
    """UAssetAPI JSON dict -> {function export name: start offset of each bytecode statement, then the end}, in the
    in-memory bytecode that jumps and ubergraph entry points count."""
    tmp = os.path.join(WORK, "kismet_offsets.tmp.json")
    with open(tmp, "w") as f:
        json.dump(d, f)
    subprocess.run([UASSET_JSON, "kismet-offsets", tmp, tmp + ".out"], check=True, env=ENV)
    with open(tmp + ".out") as f:
        out = json.load(f)
    os.remove(tmp)
    os.remove(tmp + ".out")
    return out


def fix_offsets(d):
    """Set every EX_Context skip offset in d to the in-memory size of the expression it skips (in place)."""
    tmp = os.path.join(WORK, "fix_offsets.tmp.json")
    with open(tmp, "w") as f:
        json.dump(d, f)
    r = subprocess.run([UASSET_JSON, "fix-offsets", tmp, tmp + ".out"], check=True, env=ENV, capture_output=True, text=True)
    with open(tmp + ".out") as f:
        new = json.load(f)
    os.remove(tmp)
    os.remove(tmp + ".out")
    d.clear()
    d.update(new)
    return r.stderr.strip()


# ---- reading values ---------------------------------------------------------------------------------------------

def ptype(p):
    return p["$type"].split(",")[0].split(".")[-1].replace("PropertyData", "")


def obj_path(d, i):
    """Object index -> 'package.Object' style path (imports) or 'export:N:Name'."""
    if i == 0:
        return None
    if i > 0:
        return f"export:{i}:{d['Exports'][i - 1]['ObjectName']}"
    imp = d["Imports"][-i - 1]
    name, outer = imp["ObjectName"], imp["OuterIndex"]
    while outer:
        o = d["Imports"][-outer - 1]
        name = f"{o['ObjectName']}.{name}" if o["OuterIndex"] else f"{o['ObjectName']}:{name}"
        outer = o["OuterIndex"]
    return name


def soft_path(p):
    ap = (p.get("Value") or {}).get("AssetPath") or {}
    return ".".join(x for x in (ap.get("PackageName"), ap.get("AssetName")) if x) or None


def find_export(d, name):
    for i, e in enumerate(d["Exports"], 1):
        if e["ObjectName"] == name:
            return i, e
    raise KeyError(name)


def prop(data, name):
    for p in data:
        if p.get("Name") == name:
            return p
    return None
