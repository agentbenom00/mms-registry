#!/usr/bin/env python3
"""Print a blueprint's Kismet bytecode (UAssetAPI JSON from uasset-json tojson) as readable pseudo-code.

    python3 tools/kismet.py <package path or .json> [function name ...]

Each statement is prefixed with its offset in the in-memory bytecode (what jumps and ubergraph entry points count).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "build"))
import ue  # noqa: E402


class Printer:
    def __init__(self, d):
        self.d = d

    def ref(self, i):
        if i is None or i == 0:
            return "None"
        if i > 0:
            return self.d["Exports"][i - 1]["ObjectName"]
        imp = self.d["Imports"][-i - 1]
        return imp["ObjectName"]

    def fullref(self, i):
        if i is None or i == 0:
            return "None"
        if i > 0:
            return "export:" + self.d["Exports"][i - 1]["ObjectName"]
        return ue.obj_path(self.d, i)

    def prop(self, p):
        if p is None:
            return "?"
        if isinstance(p, dict):
            new = p.get("New")
            if new and new.get("Path"):
                return ".".join(new["Path"])
            if p.get("Old"):
                return self.ref(p["Old"])
        return str(p)

    def text(self, v):
        if not isinstance(v, dict):
            return repr(v)
        t = v.get("TextLiteralType")
        if t in ("LocalizedText", 1, "1"):
            return f'LOCTEXT({v.get("LocalizedSource")!r} key={v.get("LocalizedKey")})'
        if t in ("InvariantText", 2):
            return f'INVTEXT({v.get("InvariantLiteralString")!r})'
        if t in ("LiteralString", 3):
            return f'TEXT({v.get("LiteralString")!r})'
        if t in ("StringTableEntry", 4):
            return f'STRTABLE({v.get("StringTableId")}, {v.get("StringTableKey")})'
        return "TEXT(empty)"

    def e(self, x):
        if x is None:
            return "∅"
        t = x["$type"].split(",")[0].split(".")[-1]
        f = getattr(self, "x_" + t, None)
        if f:
            return f(x)
        keys = {k: v for k, v in x.items() if k != "$type"}
        return f"<{t} {json.dumps(keys)[:200]}>"

    def args(self, ps):
        return ", ".join(self.e(p) for p in (ps or []))

    # variables
    def x_EX_LocalVariable(self, x): return self.prop(x["Variable"])
    def x_EX_LocalOutVariable(self, x): return "out " + self.prop(x["Variable"])
    def x_EX_InstanceVariable(self, x): return "self." + self.prop(x["Variable"])
    def x_EX_DefaultVariable(self, x): return "default." + self.prop(x["Variable"])
    def x_EX_ClassSparseDataVariable(self, x): return "sparse." + self.prop(x["Variable"])

    # assignments
    def x_EX_Let(self, x): return f'{self.e(x["Variable"])} = {self.e(x["Expression"])}'
    def x_EX_LetObj(self, x): return f'{self.e(x["VariableExpression"])} = {self.e(x["AssignmentExpression"])}'
    x_EX_LetBool = x_EX_LetObj
    x_EX_LetWeakObjPtr = x_EX_LetObj
    x_EX_LetDelegate = x_EX_LetObj
    x_EX_LetMulticastDelegate = x_EX_LetObj
    def x_EX_LetValueOnPersistentFrame(self, x):
        return f'frame.{self.prop(x["DestinationProperty"])} = {self.e(x["AssignmentExpression"])}'

    # calls
    def x_EX_FinalFunction(self, x): return f'{self.ref(x["StackNode"])}({self.args(x.get("Parameters"))})'
    x_EX_LocalFinalFunction = x_EX_FinalFunction
    def x_EX_CallMath(self, x): return f'{self.ref(x["StackNode"])}({self.args(x.get("Parameters"))})'
    def x_EX_VirtualFunction(self, x): return f'{x["VirtualFunctionName"]}({self.args(x.get("Parameters"))})'
    x_EX_LocalVirtualFunction = x_EX_VirtualFunction
    def x_EX_CallMulticastDelegate(self, x):
        return f'{self.e(x["Delegate"])}.Broadcast({self.args(x.get("Parameters"))})'
    def x_EX_Context(self, x):
        return f'{self.e(x["ObjectExpression"])}->{self.e(x["ContextExpression"])}'
    x_EX_Context_FailSilent = x_EX_Context
    x_EX_ClassContext = x_EX_Context
    def x_EX_InterfaceContext(self, x): return f'iface({self.e(x["InterfaceValue"])})'

    # flow
    def x_EX_Jump(self, x): return f'goto {x["CodeOffset"]}'
    def x_EX_JumpIfNot(self, x): return f'if not ({self.e(x["BooleanExpression"])}) goto {x["CodeOffset"]}'
    def x_EX_ComputedJump(self, x): return f'goto computed({self.e(x["CodeOffsetExpression"])})'
    def x_EX_PushExecutionFlow(self, x): return f'push_flow {x["PushingAddress"]}'
    def x_EX_PopExecutionFlow(self, x): return 'pop_flow'
    def x_EX_PopExecutionFlowIfNot(self, x): return f'pop_flow if not ({self.e(x["BooleanExpression"])})'
    def x_EX_Return(self, x): return f'return {self.e(x["ReturnExpression"])}'
    def x_EX_EndOfScript(self, x): return 'end'
    def x_EX_Nothing(self, x): return 'nop'
    def x_EX_Skip(self, x): return f'skip {x.get("CodeOffset")} ({self.e(x.get("SkipExpression"))})'
    def x_EX_SkipOffsetConst(self, x): return f'skipoff {x["Value"]}'

    # constants
    def x_EX_IntConst(self, x): return str(x["Value"])
    x_EX_ByteConst = x_EX_IntConst
    x_EX_Int64Const = x_EX_IntConst
    x_EX_UInt64Const = x_EX_IntConst
    x_EX_IntConstByte = x_EX_IntConst
    def x_EX_FloatConst(self, x): return repr(x["Value"])
    def x_EX_StringConst(self, x): return repr(x["Value"])
    x_EX_UnicodeStringConst = x_EX_StringConst
    def x_EX_NameConst(self, x): return f'N"{x["Value"]}"'
    def x_EX_TextConst(self, x): return self.text(x["Value"])
    def x_EX_ObjectConst(self, x): return f'obj({self.fullref(x["Value"])})'
    def x_EX_SoftObjectConst(self, x): return f'soft({self.e(x["Value"])})'
    def x_EX_True(self, x): return 'true'
    def x_EX_False(self, x): return 'false'
    def x_EX_Self(self, x): return 'self'
    def x_EX_NoObject(self, x): return 'None'
    def x_EX_NoInterface(self, x): return 'NoInterface'
    def x_EX_IntZero(self, x): return '0'
    def x_EX_IntOne(self, x): return '1'
    def x_EX_VectorConst(self, x): return f'vec({x["Value"]})'
    def x_EX_RotationConst(self, x): return f'rot({x.get("Value")})'
    def x_EX_TransformConst(self, x): return 'xform(...)'
    def x_EX_StructConst(self, x): return f'{self.ref(x["Struct"])}{{{self.args(x.get("Value"))}}}'
    def x_EX_ArrayConst(self, x): return f'[{self.args(x.get("Elements"))}]'
    def x_EX_SetArray(self, x): return f'{self.e(x["AssigningProperty"])} = [{self.args(x.get("Elements"))}]'
    def x_EX_SetSet(self, x): return f'{self.e(x["SetProperty"])} = set[{self.args(x.get("Elements"))}]'
    def x_EX_SetMap(self, x): return f'{self.e(x["MapProperty"])} = map[{self.args(x.get("Elements"))}]'
    def x_EX_InstanceDelegate(self, x): return f'delegate({x["FunctionName"]})'
    def x_EX_BindDelegate(self, x):
        return f'{self.e(x["Delegate"])}.Bind({self.e(x["ObjectTerm"])}, {x["FunctionName"]})'
    def x_EX_AddMulticastDelegate(self, x): return f'{self.e(x["Delegate"])} += {self.e(x["DelegateToAdd"])}'
    def x_EX_RemoveMulticastDelegate(self, x): return f'{self.e(x["Delegate"])} -= {self.e(x["DelegateToAdd"])}'
    def x_EX_ClearMulticastDelegate(self, x): return f'{self.e(x["DelegateToClear"])}.Clear()'

    # casts / members
    def x_EX_DynamicCast(self, x): return f'Cast<{self.ref(x["ClassPtr"])}>({self.e(x["Target"])})'
    x_EX_MetaCast = x_EX_DynamicCast
    x_EX_ObjToInterfaceCast = x_EX_DynamicCast
    x_EX_CrossInterfaceCast = x_EX_DynamicCast
    x_EX_InterfaceToObjCast = x_EX_DynamicCast
    def x_EX_PrimitiveCast(self, x): return f'cast{x.get("ConversionType")}({self.e(x["Target"])})'
    def x_EX_StructMemberContext(self, x):
        return f'{self.e(x["StructExpression"])}.{self.prop(x["StructMemberExpression"])}'
    def x_EX_ArrayGetByRef(self, x): return f'{self.e(x["ArrayVariable"])}[{self.e(x["ArrayIndex"])}]'
    def x_EX_SwitchValue(self, x):
        cases = "; ".join(f'{self.e(c["CaseIndexValueTerm"])}: {self.e(c["CaseTerm"])}' for c in x.get("Cases", []))
        return f'switch({self.e(x["IndexTerm"])}) {{{cases}; default: {self.e(x["DefaultTerm"])}}}'
    def x_EX_Breakpoint(self, x): return 'breakpoint'
    def x_EX_Tracepoint(self, x): return 'tracepoint'
    def x_EX_WireTracepoint(self, x): return 'wiretracepoint'
    def x_EX_InstrumentationEvent(self, x): return 'instrumentation'


def load(arg):
    if arg.endswith(".json"):
        return json.load(open(arg))
    return ue.load(arg)


def main():
    d = load(sys.argv[1])
    want = set(sys.argv[2:])
    offs = ue.kismet_offsets(d)
    p = Printer(d)
    for i, e in enumerate(d["Exports"], 1):
        sb = e.get("ScriptBytecode")
        if sb is None or (want and e["ObjectName"] not in want):
            continue
        o = offs.get(e["ObjectName"]) or []
        print(f"=== {i} {e['ObjectName']}  ({len(sb)} statements)")
        for k, st in enumerate(sb):
            off = o[k] if k < len(o) else "?"
            print(f"{off:>6}: {p.e(st)}")
        print()


if __name__ == "__main__":
    main()
