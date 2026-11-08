#!/usr/bin/env python3
"""The shared Threat Room panel: WBP_MissionModsPanel_THREAT that also lists options other mods register.

    python3 build_panel.py [--header ../../src/proxy/threatroom_panel.h]
        builds work/stage/CodaGame/Plugins/DLC_Storm/.../WBP_MissionModsPanel_THREAT.* from the game's own panel and,
        with --header, writes the patches the registry applies at launch (MMSD deltas, see delta.py and threatroom.c)

A mod adds a Threat Room option by shipping a StrategyMissionMod_ApplyMissionMod whose first MissionModToApply is a
MissionMod_ModifyFacts, and registering it (MMS Registry manifest). The panel lists every registered one
(GetAllTemplateForClass_BP) by the first tag of its mission mod's FactTags (or FactTagsToRemove when it adds none):
- under Mission.AllowedEnemies: an extra choice in Enemy Type (label: the mission mod's DisplayName);
- under Mission.RandomVillain: an extra choice in Villain;
- under Mission.ThreatRoomOption: a choice in a row of its own above Number of Heroes, one row per Description
  (the row label); the choice that adds no fact comes first and is selected whenever the panel opens.
A selected choice whose mission mod's FactTags has Mission.ThreatRoomOption.Hide.Villain hides the Villain row and
resets it to None (shown again, with the Tier III upgrade, when no selected choice has it): checked when a row
changes, when the panel opens and at Start.
The game's own 13 options are skipped by identity (the panel removes locked ones from its lists before this runs).
With nothing registered the panel behaves exactly like the game's.
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
import kis  # noqa: E402
import ue  # noqa: E402
from kismet import Printer  # noqa: E402
from pkg import Pkg  # noqa: E402

PANEL = "/DLC_Storm/UI/Screens/Strategy/MissionSelect/WBP_MissionModsPanel_THREAT"
FN = "MMS_AddRegisteredOptions"
FN_CHANGED = "MMS_OnExtraRowChanged"
TAG_HIDE_VILLAIN = "Mission.ThreatRoomOption.Hide.Villain"
TAG_ENEMY, TAG_VILLAIN, TAG_ROW = "Mission.AllowedEnemies", "Mission.RandomVillain", "Mission.ThreatRoomOption"
VANILLA_ENTRIES = ["Entry_Hydra", "Entry_Soulless", "Entry_Lilin", "Entry_Vampyres", "Entry_None", "Entry_FallenVenom",
                   "Entry_Crossbones", "Entry_FallenScarletWitch", "Entry_FallenSabretooth", "Entry_DreadMaiden",
                   "Entry_FallenHulk", "Entry_Sin", "Entry_Dracula"]


class Asm:
    """A function body with labels: emit statements, jump to labels, resolve after layout."""

    def __init__(self, owner):
        self.owner = owner          # the function export index (locals' owner)
        self.items = []             # statements and ("label", name)

    def label(self, name):
        self.items.append(("label", name))

    def emit(self, st):
        self.items.append(st)
        return st

    def goto(self, name):
        return self.emit({"$type": kis.T("EX_Jump"), "CodeOffset": 0, "_label": name})

    def if_not(self, cond, name):
        return self.emit({"$type": kis.T("EX_JumpIfNot"), "CodeOffset": 0, "BooleanExpression": cond, "_label": name})

    def finish(self, d, func_name):
        stmts = [x for x in self.items if not isinstance(x, tuple)]
        stmts += [kis.ret_nothing(), {"$type": kis.T("EX_EndOfScript")}]
        fexp = next(e for e in d["Exports"] if e["ObjectName"] == func_name)
        fexp["ScriptBytecode"] = stmts
        kis.ensure_names(d, kis.field_names(stmts))
        offs = ue.kismet_offsets(d)[func_name]
        pos, at = {}, 0
        for x in self.items:
            if isinstance(x, tuple):
                pos[x[1]] = offs[at]
            else:
                at += 1
        ret_off = offs[len(stmts) - 2]
        for st in stmts:
            if "_label" in st:
                lab = st.pop("_label")
                st["CodeOffset"] = ret_off if lab == "RET" else pos[lab]
        return stmts


def build(out_root):
    p = Pkg.game(PANEL).copy()
    d = p.d
    E = d["Exports"]
    X = {}
    for i, e in enumerate(E, 1):
        X.setdefault(e["ObjectName"], i)
    CLS = X["WBP_MissionModsPanel_THREAT_C"]
    cls = E[CLS - 1]
    TREE = next(i for i, e in enumerate(E, 1) if e["ObjectName"] == "WidgetTree" and e["OuterIndex"] == CLS)
    BOX = X["FXSFocusScrollBox_78"]
    SQUAD = next(i for i, e in enumerate(E, 1) if e["ObjectName"] == "SquadSize" and e["OuterIndex"] == TREE)
    SLOT0 = Pkg.prop(E[SQUAD - 1]["Data"], "Slot")["Value"]
    UBN = next(e["ObjectName"] for e in E if e["ObjectName"].startswith("ExecuteUbergraph_"))
    NAVFN = X["SetDropDownButtonsLeftNavRule"]
    POPFN = X["PopulateGameDifficultyDropDown"]
    imp = lambda path: p.find_import(path) or (_ for _ in ()).throw(KeyError(path))  # noqa: E731

    # ---- imports
    I = {}
    I["item"] = imp("/DLC_Storm/UI/Screens/Strategy/MissionSelect/WBP_MissionModItem_Dropdown:WBP_MissionModItem_Dropdown_C")
    I["vbox"] = p.imp("/Script/FXSCore:FXSFocusVerticalBox", "/Script/CoreUObject", "Class")
    I["vbox_cdo"] = p.imp("/Script/FXSCore:Default__FXSFocusVerticalBox", "/Script/FXSCore", "FXSFocusVerticalBox")
    I["smm"] = p.imp("/Script/CodaGame:StrategyMissionMod_ApplyMissionMod", "/Script/CoreUObject", "Class")
    I["mmf"] = p.imp("/Script/CodaGame:MissionMod_ModifyFacts", "/Script/CoreUObject", "Class")
    p.imp("/Script/GameplayTags", "/Script/CoreUObject", "Package")
    p.imp("/Script/GameplayTags:BlueprintGameplayTagLibrary", "/Script/CoreUObject", "Class")
    for f in ("MatchesTag", "BreakGameplayTagContainer", "GetNumGameplayTagsInContainer", "HasTag"):
        I[f] = p.imp(f"/Script/GameplayTags:BlueprintGameplayTagLibrary.{f}", "/Script/CoreUObject", "Function")
    I["tag"] = p.imp("/Script/GameplayTags:GameplayTag", "/Script/CoreUObject", "ScriptStruct")
    I["tagc"] = p.imp("/Script/GameplayTags:GameplayTagContainer", "/Script/CoreUObject", "ScriptStruct")
    for f in ("Array_Find", "Array_Contains", "Array_Insert", "Array_Add", "Array_Get", "Array_Length"):
        I[f] = p.imp(f"/Script/Engine:KismetArrayLibrary.{f}", "/Script/CoreUObject", "Function")
    I["arraylib"] = imp("/Script/Engine:Default__KismetArrayLibrary")
    for f in ("Less_IntInt", "Add_IntInt", "EqualEqual_IntInt", "NotEqual_IntInt", "Greater_IntInt", "GreaterEqual_IntInt"):
        I[f] = p.imp(f"/Script/Engine:KismetMathLibrary.{f}", "/Script/CoreUObject", "Function")
    I["Conv_TextToString"] = imp("/Script/Engine:KismetTextLibrary.Conv_TextToString")
    p.imp("/Script/UMG:PanelWidget", "/Script/CoreUObject", "Class")
    I["AddChild"] = p.imp("/Script/UMG:PanelWidget.AddChild", "/Script/CoreUObject", "Function")
    I["panelslot"] = p.imp("/Script/UMG:PanelSlot", "/Script/CoreUObject", "Class")
    I["userwidget"] = p.imp("/Script/UMG:UserWidget", "/Script/CoreUObject", "Class")
    p.imp("/Script/UMG:WidgetBlueprintLibrary", "/Script/CoreUObject", "Class")
    I["Create"] = p.imp("/Script/UMG:WidgetBlueprintLibrary.Create", "/Script/CoreUObject", "Function")
    I["wbl"] = p.imp("/Script/UMG:Default__WidgetBlueprintLibrary", "/Script/UMG", "WidgetBlueprintLibrary")
    p.imp("/Script/Engine:GameplayStatics", "/Script/CoreUObject", "Class")
    I["GetPlayerController"] = p.imp("/Script/Engine:GameplayStatics.GetPlayerController", "/Script/CoreUObject", "Function")
    I["pc"] = p.imp("/Script/Engine:PlayerController", "/Script/CoreUObject", "Class")

    # ---- the extra-rows box (slot 1 of the scroll box, above Number of Heroes), its slot, class properties
    def dup(idx, name, outer=None):
        e = copy.deepcopy(E[idx - 1])
        e["ObjectName"] = p.name(name)
        if outer is not None:
            e["OuterIndex"] = outer
        E.append(e)
        d.setdefault("DependsMap", []).append([])
        return len(E)

    VB = dup(BOX, "MMS_ExtraRows")
    vb = E[VB - 1]
    vb["ClassIndex"], vb["TemplateIndex"] = I["vbox"], I["vbox_cdo"]
    vb["Data"] = [q for q in vb["Data"] if q["Name"] in ("Slot", "bIsVariable")]
    vis = copy.deepcopy(Pkg.prop(E[SQUAD - 1]["Data"], "Visibility"))          # ESlateVisibility::Collapsed
    vb["Data"].insert(1, vis)
    SL = dup(SLOT0, "ScrollBoxSlot_9")
    Pkg.prop(vb["Data"], "Slot")["Value"] = SL
    Pkg.prop(E[SL - 1]["Data"], "Content")["Value"] = VB
    vb["CreateBeforeSerializationDependencies"] = [SL]
    vb["SerializationBeforeCreateDependencies"] = [I["vbox"], I["vbox_cdo"]]
    E[SL - 1]["CreateBeforeSerializationDependencies"] = [VB]
    box = E[BOX - 1]
    slots = Pkg.prop(box["Data"], "Slots")["Value"]
    k = next(i for i, s in enumerate(slots) if s["Value"] == SLOT0)
    slots.insert(k, p.obj_value(str(k), SL))
    for i, s in enumerate(slots):
        s["Name"] = str(i)
    deps = box["CreateBeforeSerializationDependencies"]
    deps.insert(deps.index(SLOT0), SL)

    def cprop(name):
        return copy.deepcopy(next(q for q in cls["LoadedProperties"] if q["Name"] == name))
    pv = cprop("FXSFocusScrollBox_78")
    pv["Name"], pv["PropertyClass"] = "MMS_ExtraRows", I["vbox"]
    pr_ = cprop("AllMissionMods")
    pr_["Name"] = pr_["Inner"]["Name"] = "MMS_Rows"
    pk_ = cprop("AllMissionMods")
    pk_["Name"] = "MMS_RowKeys"
    strp = copy.deepcopy(next(q for q in E[POPFN - 1]["LoadedProperties"] if q["Name"] == "CallFunc_Conv_TextToString_ReturnValue"))
    strp["Name"], strp["PropertyFlags"] = "MMS_RowKeys", "CPF_None"
    pk_["Inner"] = strp
    pk_["PropertyFlags"] = "CPF_Edit, CPF_BlueprintVisible, CPF_DisableEditOnInstance"
    cls["LoadedProperties"] += [pv, pr_, pk_]
    for n in ("MMS_ExtraRows", "MMS_Rows", "MMS_RowKeys"):
        p.name(n)

    # ---- the new function (a copy of SetDropDownButtonsLeftNavRule's export, new body and locals)
    F = dup(NAVFN, FN)
    fexp = E[F - 1]
    navfn, popfn = E[NAVFN - 1], E[POPFN - 1]
    ub = next(e for e in E if e["ObjectName"] == UBN)
    UB = X[UBN]

    def lprop(src_exp, name, new, **kw):
        q = copy.deepcopy(next(x for x in src_exp["LoadedProperties"] if x["Name"] == name))
        q["Name"] = new
        q.setdefault("PropertyFlags", "CPF_None")
        if "PropertyFlags" not in kw and "CPF_Parm" not in str(q["PropertyFlags"]):
            q["PropertyFlags"] = "CPF_None"
        q.update(kw)
        return q
    sigfn = next(e for e in E if e["ObjectName"] == "DifficultyChangedDispatcher__DelegateSignature")
    which = lprop(sigfn, "Value", "Which")
    tstruct = cprop("ConditionsT1")
    L = [which]

    def local(name, kind, **kw):
        if kind == "int":
            q = lprop(navfn, "Temp_int_Loop_Counter_Variable", name)
        elif kind == "bool":
            q = lprop(navfn, "CallFunc_Less_IntInt_ReturnValue", name)
        elif kind == "obj":
            q = lprop(navfn, "CallFunc_Array_Get_Item", name, PropertyClass=kw["cls"])
        elif kind == "text":
            q = lprop(popfn, "CallFunc_Conv_StringToText_ReturnValue", name)
        elif kind == "str":
            q = lprop(popfn, "CallFunc_Conv_TextToString_ReturnValue", name)
        elif kind == "struct":
            q = copy.deepcopy(tstruct)
            q.update(Name=name, PropertyFlags="CPF_None", Struct=kw["struct"], ElementSize=kw["size"])
        elif kind == "tagarray":
            q = copy.deepcopy(cprop("Set In"))
            q.update(Name=name, PropertyFlags="CPF_None")
            q["Inner"].update(Name=name, Struct=I["tag"], ElementSize=8, PropertyFlags="CPF_None")
        elif kind == "templates":
            q = lprop(popfn, "CallFunc_GetAllTemplateForClass_BP_Templates", name)
        elif kind == "objarray":
            q = lprop(ub, "K2Node_MakeArray_Array", name)
            q["Inner"]["Name"] = name
        elif kind == "delegate":
            q = lprop(navfn, "K2Node_CreateDelegate_OutputDelegate", name)
        elif kind == "changed":                                   # MulticastControlSignature, as the panel binds
            q = lprop(ub, "K2Node_CreateDelegate_OutputDelegate", name)
        L.append(q)
        return name
    V = {}
    for name, kind, kw in [
        ("Templates", "templates", {}), ("GI", "obj", {"cls": None}), ("i", "int", {}), ("k", "int", {}),
        ("n", "int", {}), ("r", "int", {}), ("AddIdx", "int", {}), ("b", "bool", {}), ("bDefault", "bool", {}),
        ("T", "obj", {"cls": None}), ("M", "obj", {"cls": None}), ("MF", "obj", {"cls": I["mmf"]}),
        ("Tags", "struct", {"struct": I["tagc"], "size": 32}), ("TagArr", "tagarray", {}),
        ("Tag", "struct", {"struct": I["tag"], "size": 8}), ("Label", "text", {}), ("Key", "str", {}),
        ("Row", "obj", {"cls": I["item"]}), ("Created", "obj", {"cls": I["userwidget"]}),
        ("PC", "obj", {"cls": I["pc"]}), ("Slot", "obj", {"cls": I["panelslot"]}),
        ("Vanilla", "objarray", {}), ("Nav", "delegate", {}), ("hide", "bool", {}), ("idx", "int", {}),
        ("Changed", "changed", {}),
    ]:
        V[name] = local("MMS_" + name, kind, **kw)
    gi_src = next(x for x in popfn["LoadedProperties"] if x["Name"] == "CallFunc_GetInstance_ReturnValue")
    tget = next(x for x in popfn["LoadedProperties"] if x["Name"] == "CallFunc_Array_Get_Item")
    for q in L:
        if q["Name"] == "MMS_GI":
            q["PropertyClass"] = gi_src["PropertyClass"]
        if q["Name"] in ("MMS_T", "MMS_M"):
            q["PropertyClass"] = tget["PropertyClass"]
    fexp["LoadedProperties"] = L
    p.name(FN)
    for q in L:
        p.name(q["Name"])

    # ---- expression helpers (shapes copied from the game's own bytecode)
    lv = lambda n: kis.local(n, F)  # noqa: E731
    sv = lambda n: kis.inst(n, CLS)  # noqa: E731
    ip = lambda n: kis.inst(n, I["item"])  # noqa: E731

    def fp_none():
        return {"$type": "UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI",
                "New": {"$type": "UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI", "Path": [], "ResolvedOwner": 0}}

    def call_ctx(obj, func_idx, params, ret=None):
        rp = kis.fp(ret, F) if ret else fp_none()
        return kis.context(obj, rp, {"$type": kis.T("EX_FinalFunction"), "StackNode": func_idx, "Parameters": params})

    def arr(fn, params, ret=None):
        return call_ctx(kis.obj_const(I["arraylib"]), I[fn], params, ret)

    def let_l(name, expr):
        return kis.let(lv(name), expr)

    def let_b(name, expr):
        return kis.let_bool(lv(name), expr)

    def let_o(name, expr):
        return kis.let_obj(lv(name), expr)

    def get(obj_expr, prop, owner):
        """obj->prop (a value read through a context)"""
        return kis.context(obj_expr, kis.fp(prop, owner), kis.inst(prop, owner))

    def math(fn, *params):
        return kis.call_math(I[fn], list(params))

    def tagconst(name):
        tagx = {"$type": kis.T("EX_StructConst"), "Struct": I["tag"], "StructSize": 12,
                "Value": [kis.name_const(name)]}
        return tagx

    def cast(cls_idx, target):
        return {"$type": kis.T("EX_DynamicCast"), "ClassPtr": cls_idx, "Target": target}

    def tobool(target):
        return {"$type": kis.T("EX_PrimitiveCast"), "ConversionType": "ObjectToBool", "Target": target}

    def vcall(obj_expr, name, params):
        return kis.context(obj_expr, fp_none(), {"$type": kis.T("EX_LocalVirtualFunction"), "VirtualFunctionName": name,
                                                 "Parameters": params})

    def set_on(obj_expr, prop, owner, value):
        target = kis.context(obj_expr, kis.fp(prop, owner), kis.inst(prop, owner))
        return {"$type": kis.T("EX_Let"), "Value": kis.fp(prop, owner), "Variable": target, "Expression": value}

    def loop_head(a, idx, arr_expr, end):
        a.emit(let_l(V["n"], arr("Array_Length", [arr_expr], V["n"])))
        a.emit(let_b(V["b"], math("Less_IntInt", lv(idx), lv(V["n"]))))
        a.if_not(lv(V["b"]), end)

    def inc(a, idx):
        a.emit(let_l(idx, math("Add_IntInt", lv(idx), kis.int_const(1))))

    # ---- the body
    a = Asm(F)
    W = kis.local("Which", F)
    a.emit(let_b(V["b"], math("EqualEqual_IntInt", W, kis.int_const(3))))
    a.if_not(lv(V["b"]), "CHK4")
    # Which 3: select every extra row's first (default) choice, then the hiding below
    a.emit(let_l(V["k"], kis.int_const(0)))
    a.label("SEL")
    loop_head(a, V["k"], sv("MMS_Rows"), "HIDE")
    a.emit(arr("Array_Get", [sv("MMS_Rows"), lv(V["k"]), lv(V["Row"])]))
    inc(a, V["k"])
    a.emit(vcall(lv(V["Row"]), "SetSelection", [kis.int_const(0)]))
    a.goto("SEL")
    a.label("CHK4")
    a.emit(let_b(V["b"], math("EqualEqual_IntInt", W, kis.int_const(4))))
    a.if_not(lv(V["b"]), "COLLECT")
    a.goto("HIDE")

    a.label("COLLECT")
    # Which 2 runs once per panel: rows already made (a second Construct) stay as they are
    a.emit(let_b(V["b"], math("EqualEqual_IntInt", W, kis.int_const(2))))
    a.if_not(lv(V["b"]), "COLLECT2")
    a.emit(let_l(V["n"], arr("Array_Length", [sv("MMS_Rows")], V["n"])))
    a.emit(let_b(V["b"], math("Greater_IntInt", lv(V["n"]), kis.int_const(0))))
    a.if_not(lv(V["b"]), "COLLECT2")
    a.goto("RET")
    a.label("COLLECT2")
    a.emit({"$type": kis.T("EX_SetArray"), "AssigningProperty": lv(V["Vanilla"]), "ArrayInnerProp": None,
            "Elements": [sv(n) for n in VANILLA_ENTRIES]})
    a.emit({"$type": kis.T("EX_SetArray"), "AssigningProperty": lv(V["Templates"]), "ArrayInnerProp": None, "Elements": []})
    getinst = next(st for st in popfn["ScriptBytecode"] if Printer(d).e(st).startswith("CallFunc_GetInstance_ReturnValue = GetInstance("))
    s_gi = kis.set_owner(copy.deepcopy(getinst), POPFN, F)
    s_gi["VariableExpression"] = lv(V["GI"])
    a.emit(s_gi)
    gat = next(st for st in popfn["ScriptBytecode"] if "->GetAllTemplateForClass_BP(" in Printer(d).e(st))
    s_gat = kis.set_owner(copy.deepcopy(gat), POPFN, F)
    s_gat["ObjectExpression"] = lv(V["GI"])
    prm = s_gat["ContextExpression"]["Parameters"]
    prm[0] = kis.obj_const(I["smm"])
    prm[1] = lv(V["Templates"])
    a.emit(s_gat)
    a.emit(let_l(V["i"], kis.int_const(0)))
    a.label("LOOP")
    loop_head(a, V["i"], lv(V["Templates"]), "AFTER")
    a.emit(arr("Array_Get", [lv(V["Templates"]), lv(V["i"]), lv(V["T"])]))
    inc(a, V["i"])
    a.emit(let_b(V["b"], arr("Array_Contains", [lv(V["Vanilla"]), lv(V["T"])], V["b"])))
    a.if_not(lv(V["b"]), "NOTVANILLA")
    a.goto("LOOP")
    a.label("NOTVANILLA")
    mta = get(lv(V["T"]), "MissionModToApply", I["smm"])
    a.emit(let_l(V["n"], arr("Array_Length", [mta], V["n"])))
    a.emit(let_b(V["b"], math("Greater_IntInt", lv(V["n"]), kis.int_const(0))))
    a.if_not(lv(V["b"]), "LOOP")
    a.emit(arr("Array_Get", [get(lv(V["T"]), "MissionModToApply", I["smm"]), kis.int_const(0), lv(V["M"])]))
    a.emit(kis.let(lv(V["MF"]), cast(I["mmf"], lv(V["M"]))))
    a.emit(let_b(V["b"], tobool(lv(V["MF"]))))
    a.if_not(lv(V["b"]), "LOOP")
    a.emit(kis.let(lv(V["Tags"]), get(lv(V["MF"]), "FactTags", I["mmf"])))
    a.emit(let_l(V["n"], math("GetNumGameplayTagsInContainer", lv(V["Tags"]))))
    a.emit(let_b(V["bDefault"], math("EqualEqual_IntInt", lv(V["n"]), kis.int_const(0))))
    a.if_not(lv(V["bDefault"]), "HAVETAGS")
    a.emit(kis.let(lv(V["Tags"]), get(lv(V["MF"]), "FactTagsToRemove", I["mmf"])))
    a.emit(let_l(V["n"], math("GetNumGameplayTagsInContainer", lv(V["Tags"]))))
    a.emit(let_b(V["b"], math("Greater_IntInt", lv(V["n"]), kis.int_const(0))))
    a.if_not(lv(V["b"]), "LOOP")
    a.label("HAVETAGS")
    a.emit(math("BreakGameplayTagContainer", lv(V["Tags"]), lv(V["TagArr"])))
    a.emit(arr("Array_Get", [lv(V["TagArr"]), kis.int_const(0), lv(V["Tag"])]))
    a.emit(kis.let(lv(V["Label"]), get(lv(V["MF"]), "DisplayName", I["mmf"])))
    # Which 0: Enemy Type
    a.emit(let_b(V["b"], math("EqualEqual_IntInt", W, kis.int_const(0))))
    a.if_not(lv(V["b"]), "VIL")
    a.emit(let_b(V["b"], math("MatchesTag", lv(V["Tag"]), tagconst(TAG_ENEMY), kis.false())))
    a.if_not(lv(V["b"]), "LOOP")
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [sv("EnemyTypeLabel"), lv(V["Label"])], V["AddIdx"])))
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [sv("EnemyTypeEntry"), lv(V["T"])], V["AddIdx"])))
    a.goto("LOOP")
    # Which 1: Villain
    a.label("VIL")
    a.emit(let_b(V["b"], math("EqualEqual_IntInt", W, kis.int_const(1))))
    a.if_not(lv(V["b"]), "ROW")
    a.emit(let_b(V["b"], math("MatchesTag", lv(V["Tag"]), tagconst(TAG_VILLAIN), kis.false())))
    a.if_not(lv(V["b"]), "LOOP")
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [sv("VillainLabel"), lv(V["Label"])], V["AddIdx"])))
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [sv("VillainEntry"), lv(V["T"])], V["AddIdx"])))
    a.goto("LOOP")
    # Which 2: rows of their own, one per Description
    a.label("ROW")
    a.emit(let_b(V["b"], math("EqualEqual_IntInt", W, kis.int_const(2))))
    a.if_not(lv(V["b"]), "LOOP")
    a.emit(let_b(V["b"], math("MatchesTag", lv(V["Tag"]), tagconst(TAG_ROW), kis.false())))
    a.if_not(lv(V["b"]), "LOOP")
    a.emit(kis.let(lv(V["Key"]), math("Conv_TextToString", get(lv(V["MF"]), "Description", I["mmf"]))))
    a.emit(let_l(V["r"], arr("Array_Find", [sv("MMS_RowKeys"), lv(V["Key"])], V["r"])))
    a.emit(let_b(V["b"], math("NotEqual_IntInt", lv(V["r"]), kis.int_const(-1))))
    a.if_not(lv(V["b"]), "NEWROW")
    a.emit(arr("Array_Get", [sv("MMS_Rows"), lv(V["r"]), lv(V["Row"])]))
    a.goto("CHOICE")
    a.label("NEWROW")
    a.emit(let_o(V["PC"], math("GetPlayerController", {"$type": kis.T("EX_Self")}, kis.int_const(0))))
    a.emit(let_o(V["Created"], call_ctx(kis.obj_const(I["wbl"]), I["Create"],
                                        [{"$type": kis.T("EX_Self")}, kis.obj_const(I["item"]), lv(V["PC"])], V["Created"])))
    a.emit(kis.let(lv(V["Row"]), cast(I["item"], lv(V["Created"]))))
    a.emit(let_b(V["b"], tobool(lv(V["Row"]))))
    a.if_not(lv(V["b"]), "LOOP")
    a.emit(set_on(lv(V["Row"]), "LabelText", I["item"], get(lv(V["MF"]), "Description", I["mmf"])))
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [sv("MMS_RowKeys"), lv(V["Key"])], V["AddIdx"])))
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [sv("MMS_Rows"), lv(V["Row"])], V["AddIdx"])))
    a.label("CHOICE")
    a.if_not(lv(V["bDefault"]), "APPEND")
    a.emit(arr("Array_Insert", [get(lv(V["Row"]), "DropdownEntryText", I["item"]), lv(V["Label"]), kis.int_const(0)]))
    a.emit(arr("Array_Insert", [get(lv(V["Row"]), "MissionMods", I["item"]), lv(V["T"]), kis.int_const(0)]))
    a.goto("LOOP")
    a.label("APPEND")
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [get(lv(V["Row"]), "DropdownEntryText", I["item"]), lv(V["Label"])], V["AddIdx"])))
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [get(lv(V["Row"]), "MissionMods", I["item"]), lv(V["T"])], V["AddIdx"])))
    a.goto("LOOP")
    # after the loop, Which 2: put the rows in the box (their Construct runs now, with every choice), give them the
    # mission ID and Apply on start (AllMissionMods), and the same left-navigation rule as the other rows
    a.label("AFTER")
    a.emit(let_b(V["b"], math("EqualEqual_IntInt", W, kis.int_const(2))))
    a.if_not(lv(V["b"]), "RET")
    a.emit(let_l(V["k"], kis.int_const(0)))
    a.label("PLACE")
    loop_head(a, V["k"], sv("MMS_Rows"), "RET")
    a.emit(arr("Array_Get", [sv("MMS_Rows"), lv(V["k"]), lv(V["Row"])]))
    inc(a, V["k"])
    a.emit(let_o(V["Slot"], call_ctx(sv("MMS_ExtraRows"), I["AddChild"], [lv(V["Row"])], V["Slot"])))
    a.emit(let_l(V["AddIdx"], arr("Array_Add", [sv("AllMissionMods"), lv(V["Row"])], V["AddIdx"])))
    navst = navfn["ScriptBytecode"]
    pr = Printer(d)
    bind = kis.set_owner(copy.deepcopy(next(st for st in navst if ".Bind(" in pr.e(st))), NAVFN, F)
    bind["Delegate"] = lv(V["Nav"])
    a.emit(bind)
    setnav = kis.set_owner(copy.deepcopy(next(st for st in navst if "SetNavigationRuleCustom" in pr.e(st))), NAVFN, F)
    # K2Node_DynamicCast_AsWBP_Mission_Mod_Item_Dropdown->WBP_CodaDropdown->DropdownButton->SetNavigationRuleCustom(0, delegate)
    kis.replace_field(setnav, "K2Node_DynamicCast_AsWBP_Mission_Mod_Item_Dropdown", V["Row"])
    kis.replace_field(setnav, "K2Node_CreateDelegate_OutputDelegate", V["Nav"])
    a.emit(setnav)
    ubst = ub["ScriptBytecode"]
    bind2 = kis.set_owner(copy.deepcopy(next(st for st in ubst if pr.e(st).endswith(".Bind(self, On Difficulty Changed)"))), UB, F)
    bind2["Delegate"], bind2["FunctionName"] = lv(V["Changed"]), FN_CHANGED
    a.emit(bind2)
    addd = kis.set_owner(copy.deepcopy(next(st for st in ubst if kis.kind(st) == "EX_AddMulticastDelegate")), UB, F)
    addd["Delegate"]["ObjectExpression"]["ObjectExpression"] = lv(V["Row"])    # self.MissionLevel -> the row
    addd["DelegateToAdd"] = lv(V["Changed"])
    a.emit(addd)
    a.goto("PLACE")

    # Which 4 (and after 3): hide Villain while a selected choice says so, reset it to None; else show it (Tier III)
    a.label("HIDE")
    a.emit(let_b(V["hide"], kis.false()))
    a.emit(let_l(V["k"], kis.int_const(0)))
    a.label("HLOOP")
    loop_head(a, V["k"], sv("MMS_Rows"), "HAPPLY")
    a.emit(arr("Array_Get", [sv("MMS_Rows"), lv(V["k"]), lv(V["Row"])]))
    inc(a, V["k"])
    a.emit(let_l(V["idx"], get(lv(V["Row"]), "CurrentIndex", I["item"])))
    a.emit(let_b(V["b"], math("GreaterEqual_IntInt", lv(V["idx"]), kis.int_const(0))))
    a.if_not(lv(V["b"]), "HLOOP")
    a.emit(let_l(V["n"], arr("Array_Length", [get(lv(V["Row"]), "MissionMods", I["item"])], V["n"])))
    a.emit(let_b(V["b"], math("Less_IntInt", lv(V["idx"]), lv(V["n"]))))
    a.if_not(lv(V["b"]), "HLOOP")
    a.emit(arr("Array_Get", [get(lv(V["Row"]), "MissionMods", I["item"]), lv(V["idx"]), lv(V["T"])]))
    a.emit(let_l(V["n"], arr("Array_Length", [get(lv(V["T"]), "MissionModToApply", I["smm"])], V["n"])))
    a.emit(let_b(V["b"], math("Greater_IntInt", lv(V["n"]), kis.int_const(0))))
    a.if_not(lv(V["b"]), "HLOOP")
    a.emit(arr("Array_Get", [get(lv(V["T"]), "MissionModToApply", I["smm"]), kis.int_const(0), lv(V["M"])]))
    a.emit(kis.let(lv(V["MF"]), cast(I["mmf"], lv(V["M"]))))
    a.emit(let_b(V["b"], tobool(lv(V["MF"]))))
    a.if_not(lv(V["b"]), "HLOOP")
    a.emit(let_b(V["b"], math("HasTag", get(lv(V["MF"]), "FactTags", I["mmf"]), tagconst(TAG_HIDE_VILLAIN), kis.true())))
    a.if_not(lv(V["b"]), "HLOOP")
    a.emit(let_b(V["hide"], kis.true()))
    a.goto("HLOOP")
    a.label("HAPPLY")
    vis = next(st for st in ubst if pr.e(st) == "self.SquadSize->SetVisibility(4)")
    a.if_not(lv(V["hide"]), "SHOW")
    hidev = kis.replace_field(copy.deepcopy(vis), "SquadSize", "Villain")
    hidev["ContextExpression"]["Parameters"][0]["Value"] = 1                    # ESlateVisibility::Collapsed
    a.emit(hidev)
    a.emit(kis.replace_field(copy.deepcopy(next(st for st in ubst if pr.e(st) == "self.Villain->SetSelection(0)")), "x", "x"))
    a.goto("RET")
    a.label("SHOW")
    t2 = copy.deepcopy(next(st for st in ubst if "EvaluateStrategyConditionSet(self, self.ConditionsT2" in pr.e(st)))
    t2["VariableExpression" if "VariableExpression" in t2 else "Variable"] = lv(V["b"])
    if "Value" in t2 and isinstance(t2["Value"], dict) and "New" in t2["Value"]:
        t2["Value"] = kis.fp(V["b"], F)
    a.emit(t2)
    a.if_not(lv(V["b"]), "RET")
    a.emit(kis.replace_field(copy.deepcopy(vis), "SquadSize", "Villain"))
    a.goto("RET")
    a.finish(d, FN)

    # ---- the function's preload list: everything its bytecode and locals name (as the cooker writes it)
    fdeps = []

    def add_dep(x):
        if isinstance(x, int) and x and x not in (F, CLS) and x not in fdeps:
            fdeps.append(x)

    def scan_deps(node):
        if isinstance(node, dict):
            t = node.get("$type", "")
            for key in ("StackNode", "ClassPtr", "Struct", "PropertyClass", "Enum", "SignatureFunction"):
                add_dep(node.get(key))
            if t.startswith(kis.E + "EX_ObjectConst"):
                add_dep(node["Value"])
            if t.startswith("UAssetAPI.UnrealTypes.FFieldPath"):
                add_dep(node.get("ResolvedOwner"))
            for v in node.values():
                scan_deps(v)
        elif isinstance(node, list):
            for v in node:
                scan_deps(v)
    scan_deps(fexp["ScriptBytecode"])
    scan_deps(fexp["LoadedProperties"])
    add_dep(X["HandleLeftNavigationPressed"])
    fexp["CreateBeforeSerializationDependencies"] = fdeps
    if I["vbox"] not in cls["CreateBeforeSerializationDependencies"]:
        cls["CreateBeforeSerializationDependencies"].append(I["vbox"])

    # ---- the class knows the function
    cls["FuncMap"].append([FN, F])
    if isinstance(cls.get("Children"), list):
        cls["Children"].append(F)
    cls["CreateBeforeSerializationDependencies"].insert(0, F)
    fexp["SerializationBeforeSerializationDependencies"] = []

    # ---- MMS_OnExtraRowChanged(TargetControl, Value): bound to each extra row's dropdown, runs the hiding (Which 4)
    F2 = dup(X["On Difficulty Changed"], FN_CHANGED)
    f2 = E[F2 - 1]
    f2["ScriptBytecode"] = [{"$type": kis.T("EX_LocalVirtualFunction"), "VirtualFunctionName": FN,
                             "Parameters": [kis.int_const(4)]}, kis.ret_nothing(), {"$type": kis.T("EX_EndOfScript")}]
    f2["CreateBeforeSerializationDependencies"] = [x for x in f2["CreateBeforeSerializationDependencies"] if x < 0]
    cls["FuncMap"].append([FN_CHANGED, F2])
    if isinstance(cls.get("Children"), list):
        cls["Children"].append(F2)
    cls["CreateBeforeSerializationDependencies"].insert(0, F2)
    p.name(FN_CHANGED)

    # ---- calls from the ubergraph
    ubs = ub["ScriptBytecode"]
    txt = [pr.e(st) for st in ubs]

    def find(pred, what):
        hits = [i for i, t in enumerate(txt) if pred(t)]
        if len(hits) != 1:
            raise RuntimeError(f"panel: expected one statement {what}, found {len(hits)}")
        return hits[0]

    def call(which_val):
        return {"$type": kis.T("EX_LocalVirtualFunction"), "VirtualFunctionName": FN, "Parameters": [kis.int_const(which_val)]}
    i_enemy = find(lambda t: t == "self.EnemyType->self.MissionMods = self.EnemyTypeEntry", "giving Enemy Type its mods")
    i_vil = find(lambda t: t == "self.Villain->self.MissionMods = self.VillainEntry", "giving Villain its mods")
    i_t1 = find(lambda t: "EvaluateStrategyConditionSet(self, self.ConditionsT1" in t and "ReturnValue_1 " in t,
                "testing Tier II in Construct")
    i_vis = find(lambda t: t == "self.SquadSize->SetVisibility(4)", "showing Number of Heroes")
    sel_fn = next(e for e in E if e["ObjectName"] == "SetSelection" and e.get("ScriptBytecode"))
    i_sel = ue.kismet_offsets(d)[UBN].index(sel_fn["ScriptBytecode"][0]["Parameters"][0]["Value"])
    show = kis.replace_field(copy.deepcopy(ubs[i_vis]), "SquadSize", "MMS_ExtraRows")
    start_fn = next(e for e in E if e["ObjectName"] == "OnStartMission" and e.get("ScriptBytecode"))
    i_start = ue.kismet_offsets(d)[UBN].index(start_fn["ScriptBytecode"][0]["Parameters"][0]["Value"])
    kis.insert(d, UBN, [(i_enemy, [call(0)]), (i_vil, [call(1)]), (i_t1, [call(2)]), (i_vis + 1, [show]),
                        (i_start, [call(4)]), (i_sel, [call(3)])], ubergraph=True)
    for n in (FN, FN_CHANGED, "MMS_ExtraRows", TAG_ENEMY, TAG_VILLAIN, TAG_ROW, TAG_HIDE_VILLAIN, "SetSelection"):
        p.name(n)
    msg = ue.fix_offsets(d)
    for e in d["Exports"]:
        for q in e.get("LoadedProperties") or []:
            p.name(q["Name"])
    for n in kis.field_names([e.get("ScriptBytecode") for e in d["Exports"]]):
        p.name(n)
    out = p.write(out_root)
    return out, msg


def write_header(stage, path):
    import delta
    rel = ue.pkg_file(PANEL)[: -len(".uasset")]
    parts = []
    for ext, name in ((".uasset", "TRP_UASSET"), (".uexp", "TRP_UEXP")):
        src = open(os.path.join(ue.GAME, rel + ext), "rb").read()
        dst = open(os.path.join(stage, rel + ext), "rb").read()
        dl = delta.make(src, dst)
        assert delta.apply(dl, src) == dst
        parts.append(delta.c_array(name, dl))
        print(f"  {ext}: {len(src)} -> {len(dst)} bytes, patch {len(dl)} bytes")
    with open(path, "w") as f:
        f.write("// Generated by tools/threatroom/build_panel.py --header: the shared Threat Room panel as patches against the\n"
                "// game's own WBP_MissionModsPanel_THREAT (MMSD deltas, applied by threatroom.c). Don't edit by hand.\n")
        f.write("#pragma once\n")
        f.write("\n\n".join(parts) + "\n")
    print("wrote", path)


if __name__ == "__main__":
    stage = os.path.join(ue.WORK, "stage")
    out, msg = build(stage)
    print(msg)
    print("wrote", out)
    if "--header" in sys.argv:
        write_header(stage, sys.argv[sys.argv.index("--header") + 1])
