"""Editing cooked packages through UAssetAPI's JSON form.

A Pkg wraps one package dict. Paths are written like the engine prints them:
    /Game/Coda/Templates/X/Foo            the package
    /Game/Coda/Templates/X/Foo:Foo        an object in it (':' after the package, '.' between sub-objects)
    /Script/CodaGame:DirectDamageEffect   a native class
"""
import copy
import uuid

import ue

DEP_LISTS = ("SerializationBeforeSerializationDependencies", "CreateBeforeSerializationDependencies",
             "SerializationBeforeCreateDependencies", "CreateBeforeCreateDependencies")
NS = uuid.UUID("e4d1e550-0000-4000-8000-000000000000")   # namespace for this mod's generated GUIDs (Sabretooth 5ab7e700-..., Crossbones c7055b00-...)


def guid(seed):
    """Deterministic GUID string for a seed (stable across builds)."""
    return "{" + str(uuid.uuid5(NS, seed)).upper() + "}"


def walk(x, fn):
    """Call fn on every dict in a JSON tree (depth first)."""
    if isinstance(x, dict):
        fn(x)
        for v in x.values():
            walk(v, fn)
    elif isinstance(x, list):
        for v in x:
            walk(v, fn)


class Pkg:
    def __init__(self, d, path):
        self.d = d
        self.path = path            # package path, e.g. /Game/Coda/Templates/X/Foo

    @classmethod
    def game(cls, path):
        return cls(ue.load(path), path)

    def copy(self):
        return Pkg(copy.deepcopy(self.d), self.path)

    # ---- names ----------------------------------------------------------------------------------------------------

    def name(self, s):
        """Make sure s (an FName string) is in the name map. A name ending in _<number> (no leading zero) is stored as
        its base plus a number, so the base goes in too."""
        if s is not None:
            if s not in self.d["NameMap"]:
                self.d["NameMap"].append(s)
            base, _, num = s.rpartition("_")
            if base and num.isdigit() and (num == "0" or not num.startswith("0")) and base not in self.d["NameMap"]:
                self.d["NameMap"].append(base)
        return s

    def rename(self, mapping, strings=None):
        """Rename package paths (old package path -> new package path) everywhere in the package: name map, import
        and export names, soft paths, strings. Object names that equal an old package's short name follow it."""
        exact = {}
        for old, new in mapping.items():
            exact[old] = new
            o, n = old.rsplit("/", 1)[1], new.rsplit("/", 1)[1]
            exact[f"{old}.{o}"] = f"{new}.{n}"
            exact[o] = n
            exact[o + "_C"] = n + "_C"
            exact["Default__" + o + "_C"] = "Default__" + n + "_C"
        exact.update(strings or {})
        prefixes = sorted(mapping.items(), key=lambda kv: -len(kv[0]))

        def conv(s):
            if s in exact:
                return exact[s]
            for old, new in prefixes:
                if s.startswith(old) and len(s) > len(old) and s[len(old)] in ".:":
                    o, n = old.rsplit("/", 1)[1], new.rsplit("/", 1)[1]
                    rest = s[len(old):]
                    # /Pkg.Obj.Sub or /Pkg.Obj_C: rename the leading object too
                    if rest[1:] == o or rest[1:].startswith(o + ".") or rest[1:].startswith(o + "_C"):
                        rest = rest[0] + n + rest[1 + len(o):]
                    return new + rest
            return s

        self.d["NameMap"] = list(dict.fromkeys(conv(s) for s in self.d["NameMap"]))

        def fix(node):
            for k, v in list(node.items()):
                if isinstance(v, str) and k not in ("$type",):
                    nv = conv(v)
                    if nv != v:
                        node[k] = nv
                elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                    node[k] = [conv(x) for x in v]      # name lists (gameplay tag containers)
        walk(self.d, fix)
        if self.path in mapping:
            self.path = mapping[self.path]

    # ---- imports / exports ----------------------------------------------------------------------------------------

    def ref(self, i):
        return ue.obj_path(self.d, i)

    def find_import(self, path):
        for i in range(len(self.d["Imports"])):
            if ue.obj_path(self.d, -i - 1) == path:
                return -i - 1
        return 0

    def imp(self, path, class_package="/Script/CoreUObject", class_name="Package"):
        """Index of an import, adding it (and its outer chain) if needed. path: '/Game/A/B:Obj[.Sub]' or a bare
        package path. For objects, class_package/class_name give the object's class."""
        found = self.find_import(path)
        if found:
            return found
        if ":" not in path:
            outer, obj = 0, path
            class_package, class_name = "/Script/CoreUObject", "Package"
        else:
            pkgpath, objpath = path.split(":", 1)
            if "." in objpath:
                parent, obj = objpath.rsplit(".", 1)
                outer = self.find_import(f"{pkgpath}:{parent}")
                if not outer:
                    raise KeyError(f"import outer {pkgpath}:{parent} must be added first")
            else:
                outer, obj = self.imp(pkgpath), objpath
        for s in (obj, class_package, class_name):
            self.name(s)
        self.d["Imports"].append({"$type": "UAssetAPI.Import, UAssetAPI", "ObjectName": obj, "OuterIndex": outer,
                                  "ClassPackage": class_package, "ClassName": class_name, "PackageName": None,
                                  "bImportOptional": False})
        return -len(self.d["Imports"])

    def export(self, name):
        """(index, export dict) of the export with this ObjectName (or the main asset with name None)."""
        for i, e in enumerate(self.d["Exports"], 1):
            if (name is None and e.get("bIsAsset")) or e["ObjectName"] == name:
                return i, e
        raise KeyError(f"{self.path}: no export {name}")

    def main(self):
        return self.export(None)[1]

    # ---- properties -----------------------------------------------------------------------------------------------

    @staticmethod
    def prop(data, name):
        for p in data:
            if p.get("Name") == name:
                return p
        return None

    def get(self, export, dotted):
        """Property by dotted path inside an export dict (struct members by name, array items by [i])."""
        data = export["Data"]
        p = None
        for part in dotted.split("."):
            if part.startswith("["):
                p = p["Value"][int(part[1:-1])]
                data = p.get("Value") if isinstance(p.get("Value"), list) else None
                continue
            p = self.prop(data, part)
            if p is None:
                return None
            data = p.get("Value") if isinstance(p.get("Value"), list) else None
        return p

    def clear_array(self, p):
        """Empty an ArrayProperty. Struct arrays keep a header element (UAssetAPI's DummyStruct) for their type."""
        if p.get("ArrayType") == "StructProperty" and p["Value"] and not p.get("DummyStruct"):
            d = copy.deepcopy(p["Value"][0])
            d["Value"] = []
            p["DummyStruct"] = d
        p["Value"] = []

    def remove(self, export, name):
        export["Data"] = [p for p in export["Data"] if p.get("Name") != name]

    def set_soft(self, p, path):
        """Set a SoftObjectProperty's target ('/Game/A/B.B' or None)."""
        path = path or "None"
        self.name(path)
        p["Value"]["AssetPath"]["PackageName"] = None
        p["Value"]["AssetPath"]["AssetName"] = path
        p["Value"]["SubPathString"] = None

    def set_guid(self, p, seed):
        """Set a Guid struct property (e.g. EntitlementID) to this mod's GUID for seed."""
        p["Value"][0]["Value"] = guid(seed)

    def set_text(self, p, text, key_seed):
        """Give a TextProperty new English text under a new localization key (so the game's locres can't override)."""
        p["HistoryType"] = "Base"
        p["Namespace"] = p.get("Namespace") or ""
        p["Value"] = guid("text:" + key_seed).strip("{}").replace("-", "")
        p["CultureInvariantString"] = text.replace("\r\n", "\n").replace("\n", "\r\n")

    def _names_in(self, node):
        """Add the FNames a property node uses to the name map."""
        t = node.get("$type", "")
        cls = t.split(",")[0].split(".")[-1]
        if cls.endswith("PropertyData") and "Name" in node:
            self.name(cls[: -len("Data")])          # e.g. IntProperty: the tag's type name
        v = node.get("Value")
        ap = v.get("AssetPath") if isinstance(v, dict) else node.get("AssetPath")
        if isinstance(ap, dict):            # soft object/class paths, plain or as structs
            for kk in ("PackageName", "AssetName"):
                if ap.get(kk):
                    self.name(ap[kk])
        for kk in ("Name", "StructType", "ArrayType", "EnumType", "InnerType", "PropertyType", "KeyType", "ValueType"):
            if isinstance(node.get(kk), str) and not (kk == "Name" and node[kk].isdigit()):
                self.name(node[kk])
        if t.startswith(("UAssetAPI.PropertyTypes.Objects.NamePropertyData", "UAssetAPI.PropertyTypes.Objects.EnumPropertyData",
                         "UAssetAPI.PropertyTypes.Objects.BytePropertyData")) and isinstance(node.get("Value"), str):
            self.name(node["Value"])
        if isinstance(node.get("EnumValue"), str):          # (an enum byte's value: ByteType FName)
            self.name(node["EnumValue"])
        if t.startswith("UAssetAPI.PropertyTypes.Structs.GameplayTagContainerPropertyData"):
            for tag in node.get("Value") or []:
                self.name(tag)

    # ---- grafting exports from another package --------------------------------------------------------------------

    def _map_index(self, src, i, export_map):
        if i == 0:
            return 0
        if i > 0:
            if i not in export_map:
                raise KeyError(f"graft: {src.path} export {i} ({src.d['Exports'][i - 1]['ObjectName']}) not grafted")
            return export_map[i]
        imp = src.d["Imports"][-i - 1]
        path = src.ref(i)
        # make sure the outer chain exists first
        if imp["OuterIndex"]:
            self._map_index(src, imp["OuterIndex"], export_map)
        return self.imp(path, imp["ClassPackage"], imp["ClassName"])

    def graft(self, src, idx, outer):
        """Copy export idx of package src (with every export nested under it) into this package under export
        `outer`. Returns the new index of the copied export."""
        nested = {idx}
        changed = True
        while changed:
            changed = False
            for j, e in enumerate(src.d["Exports"], 1):
                if j not in nested and e["OuterIndex"] in nested:
                    nested.add(j)
                    changed = True
        order = sorted(nested)
        export_map = {}
        base = len(self.d["Exports"])
        taken = {e["ObjectName"] for e in self.d["Exports"]}
        for k, j in enumerate(order):
            export_map[j] = base + k + 1
        for j in order:
            e = copy.deepcopy(src.d["Exports"][j - 1])
            if j == idx:
                n, name = 0, e["ObjectName"]
                while name in taken:            # keep sub-object names unique under the same outer
                    n += 1
                    name = f"{e['ObjectName'].rsplit('_', 1)[0]}_{n + 90}"
                e["ObjectName"] = name
                e["OuterIndex"] = outer
            else:
                e["OuterIndex"] = export_map[e["OuterIndex"]]
            self.name(e["ObjectName"])
            for key in ("ClassIndex", "SuperIndex", "TemplateIndex"):
                e[key] = self._map_index(src, e[key], export_map)
            for key in DEP_LISTS:
                e[key] = [self._map_index(src, x, export_map) if not (x > 0 and x not in export_map) else export_map.get(x, 0)
                          for x in e[key]]
                e[key] = [x for x in e[key] if x]
            if j == idx:
                e["CreateBeforeCreateDependencies"] = [outer]

            def fix(node):
                if node.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData") and isinstance(node.get("Value"), int):
                    node["Value"] = self._map_index(src, node["Value"], export_map)
                self._names_in(node)
            walk(e.get("Data"), fix)
            self.d["Exports"].append(e)
            self.d.setdefault("DependsMap", []).append([])
        # the owner must know about the new object before it serializes
        if outer > 0:
            od = self.d["Exports"][outer - 1]["CreateBeforeSerializationDependencies"]
            if export_map[idx] not in od:
                od.append(export_map[idx])
        return export_map[idx]

    def copy_prop(self, src, src_export, name, dst_index):
        """Copy property `name` of src_export (an export dict of package src) onto export dst_index of this package,
        replacing an existing one. Object references are re-pointed: imports are added, exports nested under
        src_export are grafted under dst_index."""
        src_idx = src.d["Exports"].index(src_export) + 1
        p = copy.deepcopy(self.prop(src_export["Data"], name))
        if p is None:
            raise KeyError(f"{src.path}: no property {name}")
        grafted = {}

        def fix(node):
            t = node.get("$type", "")
            if t.startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData") and isinstance(node.get("Value"), int):
                v = node["Value"]
                if v > 0:
                    if src.d["Exports"][v - 1]["OuterIndex"] != src_idx:
                        raise KeyError(f"copy_prop {name}: export {v} is not a sub-object")
                    if v not in grafted:
                        grafted[v] = self.graft(src, v, dst_index)
                    node["Value"] = grafted[v]
                elif v < 0:
                    node["Value"] = self._map_index(src, v, {})
                    self.add_dep(dst_index, node["Value"])
            self._names_in(node)
        walk(p, fix)
        data = self.d["Exports"][dst_index - 1]["Data"]
        for i, q in enumerate(data):
            if q.get("Name") == name:
                data[i] = p
                break
        else:
            data.append(p)
        return p

    def obj_value(self, name, index):
        """A new ObjectPropertyData element (for arrays: name is the element index as text)."""
        return {"$type": "UAssetAPI.PropertyTypes.Objects.ObjectPropertyData, UAssetAPI", "Name": name,
                "ArrayIndex": 0, "PropertyGuid": None, "IsZero": False, "PropertyTagFlags": "None",
                "PropertyTypeName": None, "PropertyTagExtensions": "NoExtension", "Value": index}

    def add_dep(self, export_index, target):
        """Record that export_index references target (so the loader creates it first)."""
        lst = self.d["Exports"][export_index - 1]["CreateBeforeSerializationDependencies"]
        if target and target not in lst:
            lst.append(target)

    def prune_deps(self):
        """Drop dependency entries that no longer point at anything this package uses: after edits, exports that
        nothing references stay in the package (harmless) but preload lists must only hold valid indices."""
        n_imp, n_exp = len(self.d["Imports"]), len(self.d["Exports"])
        for e in self.d["Exports"]:
            for key in DEP_LISTS:
                e[key] = [x for x in e[key] if (0 < x <= n_exp) or (-n_imp <= x < 0)]

    def gc(self):
        """Remove exports nothing reachable from the main asset refers to, and imports nothing uses."""
        exports = self.d["Exports"]
        n = len(exports)

        def refs(e):
            out = []

            def f(node):
                if node.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData") and isinstance(node.get("Value"), int):
                    out.append(node["Value"])
            walk(e.get("Data"), f)
            return out

        main = [i for i, e in enumerate(exports, 1) if e.get("bIsAsset") or e["OuterIndex"] == 0]
        keep, todo = set(), list(main)
        while todo:
            i = todo.pop()
            if i in keep:
                continue
            keep.add(i)
            e = exports[i - 1]
            todo += [x for x in refs(e) if x > 0]
            if e["OuterIndex"] > 0:
                todo.append(e["OuterIndex"])
        if len(keep) < n:
            order = [i for i in range(1, n + 1) if i in keep]
            emap = {old: new for new, old in enumerate(order, 1)}

            def remap(x):
                return emap.get(x, 0) if x > 0 else x
            new_exports = []
            for old in order:
                e = exports[old - 1]
                for key in ("ClassIndex", "SuperIndex", "TemplateIndex", "OuterIndex"):
                    e[key] = remap(e[key])
                for key in DEP_LISTS:
                    e[key] = [remap(x) for x in e[key] if remap(x)]

                def f(node):
                    if node.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData") and isinstance(node.get("Value"), int):
                        node["Value"] = remap(node["Value"])
                walk(e.get("Data"), f)
                new_exports.append(e)
            self.d["Exports"] = new_exports
            self.d["DependsMap"] = [[] for _ in new_exports]
        # imports: keep those referenced anywhere (plus their outer chains)
        used = set()

        def f(node):
            if node.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData") and isinstance(node.get("Value"), int) and node["Value"] < 0:
                used.add(node["Value"])
        for e in self.d["Exports"]:
            walk(e.get("Data"), f)
            for key in ("ClassIndex", "SuperIndex", "TemplateIndex", "OuterIndex"):
                if e[key] < 0:
                    used.add(e[key])
            for key in DEP_LISTS:
                used.update(x for x in e[key] if x < 0)
        imps = self.d["Imports"]
        todo = list(used)
        while todo:
            i = todo.pop()
            o = imps[-i - 1]["OuterIndex"]
            if o < 0 and o not in used:
                used.add(o)
                todo.append(o)
        order = [-(k + 1) for k in range(len(imps)) if -(k + 1) in used]
        imap = {old: -(new + 1) for new, old in enumerate(order)}

        def remap_i(x):
            return imap.get(x, 0) if x < 0 else x
        self.d["Imports"] = [imps[-old - 1] for old in order]
        for imp in self.d["Imports"]:
            imp["OuterIndex"] = remap_i(imp["OuterIndex"])
        for e in self.d["Exports"]:
            for key in ("ClassIndex", "SuperIndex", "TemplateIndex", "OuterIndex"):
                e[key] = remap_i(e[key])
            for key in DEP_LISTS:
                e[key] = [remap_i(x) for x in e[key] if remap_i(x)]

            def g(node):
                if node.get("$type", "").startswith("UAssetAPI.PropertyTypes.Objects.ObjectPropertyData") and isinstance(node.get("Value"), int) and node["Value"] < 0:
                    node["Value"] = remap_i(node["Value"])
            walk(e.get("Data"), g)

    # ---- output ---------------------------------------------------------------------------------------------------

    def write(self, stage_root, exact=False):
        """Write as <stage_root>/<pak path of self.path>. exact: change nothing else (names, GUID, preload lists),
        for packages whose header size must not change."""
        if not exact:
            self.d["PackageGuid"] = guid("pkg:" + self.path)
            self.prune_deps()
            for e in self.d["Exports"]:
                walk(e.get("Data"), self._names_in)
        out = f"{stage_root}/{ue.pkg_file(self.path)}"
        ue.write(self.d, out)
        return out
