"""Kismet bytecode helpers for UAssetAPI JSON packages: expression constructors and statement insertion with every
absolute code offset (jumps, execution-flow pushes, latent resume points, switch offsets, ubergraph entry points)
moved to the new layout.

Offsets are in-memory byte offsets, as the VM counts them (`ue.kismet_offsets`). EX_Context skip sizes are fixed
afterwards with `ue.fix_offsets` (the game's own packages come through it unchanged).
"""
import copy

import ue

E = "UAssetAPI.Kismet.Bytecode.Expressions."


def T(name):
    return E + name + ", UAssetAPI"


def kind(x):
    return x["$type"].split(",")[0].split(".")[-1]


# ---- constructors -------------------------------------------------------------------------------------------------

def fp(name, owner):
    """A property pointer (FFieldPath) to `name`, declared by struct/class/function `owner` (package index)."""
    return {"$type": "UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI",
            "New": {"$type": "UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI", "Path": [name], "ResolvedOwner": owner}}


def local(name, owner):
    return {"$type": T("EX_LocalVariable"), "Variable": fp(name, owner)}


def out_local(name, owner):
    return {"$type": T("EX_LocalOutVariable"), "Variable": fp(name, owner)}


def inst(name, owner):
    return {"$type": T("EX_InstanceVariable"), "Variable": fp(name, owner)}


def let(var_expr, value_expr):
    """var = value (ints, structs, names...: EX_Let; the property pointer is the variable's)."""
    return {"$type": T("EX_Let"), "Value": copy.deepcopy(var_expr["Variable"]), "Variable": var_expr,
            "Expression": value_expr}


def let_bool(var_expr, value_expr):
    return {"$type": T("EX_LetBool"), "VariableExpression": var_expr, "AssignmentExpression": value_expr}


def let_obj(var_expr, value_expr):
    return {"$type": T("EX_LetObj"), "VariableExpression": var_expr, "AssignmentExpression": value_expr}


def int_const(v):
    return {"$type": T("EX_IntConst"), "Value": v}


def true():
    return {"$type": T("EX_True")}


def false():
    return {"$type": T("EX_False")}


def obj_const(index):
    return {"$type": T("EX_ObjectConst"), "Value": index}


def name_const(s):
    return {"$type": T("EX_NameConst"), "Value": s}


def call_math(func_index, params):
    return {"$type": T("EX_CallMath"), "StackNode": func_index, "Parameters": params}


def local_final(func_index, params):
    return {"$type": T("EX_LocalFinalFunction"), "StackNode": func_index, "Parameters": params}


def context(obj_expr, rvalue_ptr, ctx_expr):
    """obj->ctx_expr. The skip offset is filled in by ue.fix_offsets."""
    return {"$type": T("EX_Context"), "ObjectExpression": obj_expr, "Offset": 0, "PropertyType": 0,
            "RValuePointer": rvalue_ptr, "ContextExpression": ctx_expr}


def jump_if_not(cond_expr, target):
    """`target` is a statement dict (resolved to its offset by insert())."""
    return {"$type": T("EX_JumpIfNot"), "CodeOffset": 0, "BooleanExpression": cond_expr, "_target": target}


def ret_nothing():
    return {"$type": T("EX_Return"), "ReturnExpression": {"$type": T("EX_Nothing")}}


# ---- walking ------------------------------------------------------------------------------------------------------

def walk(x, fn):
    """Depth first over an expression tree. `_target` (a jump's statement reference) is not descended into."""
    if isinstance(x, dict):
        fn(x)
        for k, v in x.items():
            if k != "_target":
                walk(v, fn)
    elif isinstance(x, list):
        for v in x:
            walk(v, fn)


def field_names(stmts):
    """Every FName an expression tree uses (property paths, name constants, virtual function names)."""
    out = []

    def f(n):
        t = n.get("$type", "")
        if t.startswith("UAssetAPI.UnrealTypes.FFieldPath"):
            out.extend(n.get("Path") or [])
        elif t.startswith(T("EX_NameConst").split(",")[0]):
            out.append(n["Value"])
        elif "VirtualFunctionName" in n:
            out.append(n["VirtualFunctionName"])
    walk(stmts, f)
    return out


def replace_field(stmt, old, new):
    """Rename every property-path element `old` to `new` in an expression tree (in place)."""
    def f(n):
        if n.get("$type", "").startswith("UAssetAPI.UnrealTypes.FFieldPath") and n.get("Path"):
            n["Path"] = [new if p == old else p for p in n["Path"]]
    walk(stmt, f)
    return stmt


def set_owner(stmt, old_owner, new_owner):
    """Point property paths owned by old_owner (e.g. a function's locals) at new_owner."""
    def f(n):
        if n.get("$type", "").startswith("UAssetAPI.UnrealTypes.FFieldPath") and n.get("ResolvedOwner") == old_owner:
            n["ResolvedOwner"] = new_owner
    walk(stmt, f)
    return stmt


def ensure_names(d, names):
    """Add FNames to the package's name map (a name ending in _<number> also needs its base, as in pkg.Pkg.name)."""
    nm = d["NameMap"]
    have = set(nm)
    for s in names:
        if s is None:
            continue
        base, _, num = s.rpartition("_")
        for x in (s, base if base and num.isdigit() and (num == "0" or not num.startswith("0")) else None):
            if x and x not in have:
                nm.append(x)
                have.add(x)


# ---- insertion ----------------------------------------------------------------------------------------------------

def _absolute_offsets(stmts, fn):
    """Call fn(node, key) for every absolute code offset in a function's statements."""
    def f(n):
        k = kind(n) if "$type" in n else ""
        if k in ("EX_Jump", "EX_JumpIfNot", "EX_Skip") and "_target" not in n:
            fn(n, "CodeOffset")
        elif k == "EX_PushExecutionFlow":
            fn(n, "PushingAddress")
        elif k == "EX_SkipOffsetConst":
            fn(n, "Value")
        elif k == "EX_SwitchValue":
            fn(n, "EndGotoOffset")
            for c in n.get("Cases") or []:
                fn(c, "NextOffset")
    walk(stmts, f)


def insert(d, func_name, inserts, ubergraph=False):
    """Insert statements into function `func_name` of package dict d.

    inserts: [(old statement index, [statements])]: each list goes in before the statement that had that index (len
    = append before the end). Jumps and entry points that pointed at that statement now point at the first inserted
    one, so the inserted code runs whenever the original statement would have. Inserted EX_JumpIfNot statements may
    carry `_target` (a statement dict, original or inserted). ubergraph: also move the entry-point constants other
    functions pass to this one.
    """
    fidx, fexp = next((i, e) for i, e in enumerate(d["Exports"], 1) if e["ObjectName"] == func_name)
    ensure_names(d, field_names([new for _, new in inserts]))
    ensure_names(d, [q["Name"] for q in fexp.get("LoadedProperties") or []])
    stmts = fexp["ScriptBytecode"]
    old_offs = ue.kismet_offsets(d)[func_name]
    groups = {}
    for i, new in inserts:
        groups.setdefault(i, []).extend(new)
    out, ins_points = [], []          # ins_points: (old statement index, old offset, inserted statements)
    for i in range(len(stmts) + 1):
        if i in groups:
            ins_points.append((i, old_offs[i], groups[i]))
            out.extend(groups[i])
        if i < len(stmts):
            out.append(stmts[i])
    fexp["ScriptBytecode"] = out
    targets = {}                      # statement references can't go through JSON: park them as ids (UAssetAPI
                                      # ignores unknown members) while the offsets are computed

    def park(n):
        t = n.get("_target")
        if isinstance(t, dict):
            targets[id(t)] = t
            del n["_target"]
            n["_tid"] = id(t)
    walk(out, park)
    new_offs = ue.kismet_offsets(d)[func_name]

    def unpark(n):
        if "_tid" in n:
            n["_target"] = targets[n.pop("_tid")]
    walk(out, unpark)
    pos = {id(s): new_offs[k] for k, s in enumerate(out)}
    end_new = new_offs[-1]
    sizes = []                        # (old offset, in-memory size of the group inserted there)
    for i, off, new in ins_points:
        after = pos[id(stmts[i])] if i < len(stmts) else end_new
        sizes.append((off, after - pos[id(new[0])]))

    def shift(v):
        return v + sum(sz for off, sz in sizes if off < v)

    def move(n, key):
        n[key] = shift(n[key])
    _absolute_offsets(out, move)      # originals, and copies of originals inside the groups

    def res(n):
        if isinstance(n.get("_target"), dict):
            n["CodeOffset"] = pos[id(n.pop("_target"))]
    walk(out, res)
    if ubergraph:
        def entry(n):
            if "$type" in n and kind(n) in ("EX_LocalFinalFunction", "EX_FinalFunction") and n.get("StackNode") == fidx:
                p = n["Parameters"]
                if p and kind(p[0]) == "EX_IntConst":
                    p[0]["Value"] = shift(p[0]["Value"])
        for e in d["Exports"]:
            if e is not fexp and e.get("ScriptBytecode"):
                walk(e["ScriptBytecode"], entry)
    return pos
