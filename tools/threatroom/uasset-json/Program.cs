// uasset-json: round-trip cooked UE 4.26 packages (Midnight Suns) through UAssetAPI's JSON form.
//   uasset-json tojson   <in.uasset> <out.json>
//   uasset-json tojson-raw <in.uasset> <out.json>    (exports left as raw bytes: header-only edits, e.g. renaming
//                                                    names to other lengths, on packages UAssetAPI can't round-trip)
//   uasset-json fromjson <in.json>   <out.uasset>     (writes .uasset + .uexp)
//   uasset-json verify   <in.uasset>                  (re-serialize and compare bytes)
//   uasset-json fix-offsets <in.json> <out.json>     (EndlessRL: every EX_Context skip offset set to the in-memory
//                                                    size of the expression it skips, as the VM counts it)
//   uasset-json kismet-offsets <in.json> <out.json>  (each function's statement start offsets in its in-memory
//                                                    bytecode, as jumps count them, plus the end offset)
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UAssetAPI;
using UAssetAPI.ExportTypes;
using UAssetAPI.Kismet.Bytecode;
using UAssetAPI.Kismet.Bytecode.Expressions;
using UAssetAPI.UnrealTypes;

static class Program
{
    const EngineVersion Ver = EngineVersion.VER_UE4_26;

    static int Main(string[] args)
    {
        if (args.Length < 2) { Console.Error.WriteLine("usage: uasset-json tojson|fromjson|verify <in> [out]"); return 2; }
        try
        {
            switch (args[0])
            {
                case "tojson":
                    File.WriteAllText(args[2], new UAsset(args[1], Ver).SerializeJson(true));
                    return 0;
                case "tojson-raw":
                    File.WriteAllText(args[2], new UAsset(args[1], Ver, null, CustomSerializationFlags.SkipParsingExports).SerializeJson(true));
                    return 0;
                case "fromjson":
                    UAsset.DeserializeJson(File.ReadAllText(args[1])).Write(args[2]);
                    return 0;
                case "fix-offsets":
                {
                    var a = UAsset.DeserializeJson(File.ReadAllText(args[1]));
                    int changed = 0, total = 0;
                    foreach (var e in a.Exports.OfType<StructExport>().Where(e => e.ScriptBytecode != null))
                        foreach (var st in e.ScriptBytecode)
                        {
                            uint o = 0;
                            st.Visit(a, ref o, (x, _) =>
                            {
                                if (x is EX_Context c)
                                {
                                    total++;
                                    uint want = c.ContextExpression.GetSize(a);
                                    if (c.Offset != want) { c.Offset = want; changed++; }
                                }
                            });
                        }
                    File.WriteAllText(args[2], a.SerializeJson(true));
                    Console.Error.WriteLine($"fix-offsets: {changed} of {total} context offsets changed");
                    return 0;
                }
                case "kismet-offsets":
                {
                    var a = UAsset.DeserializeJson(File.ReadAllText(args[1]));
                    var res = new Dictionary<string, List<int>>();
                    foreach (var e in a.Exports.OfType<StructExport>().Where(e => e.ScriptBytecode != null))
                    {
                        var w = new AssetBinaryWriter(new MemoryStream(), a);
                        var offs = new List<int> { 0 };
                        foreach (var st in e.ScriptBytecode)
                            offs.Add(offs[^1] + ExpressionSerializer.WriteExpression(st, w));
                        res[e.ObjectName.ToString()] = offs;
                    }
                    File.WriteAllText(args[2], Newtonsoft.Json.JsonConvert.SerializeObject(res));
                    return 0;
                }
                case "verify":
                {
                    var a = new UAsset(args[1], Ver);
                    var tmp = Path.Combine(Path.GetTempPath(), "uaj_verify_" + Environment.ProcessId + ".uasset");
                    a.Write(tmp);
                    bool same = Same(args[1], tmp) && Same(Path.ChangeExtension(args[1], ".uexp"), Path.ChangeExtension(tmp, ".uexp"));
                    var b = UAsset.DeserializeJson(a.SerializeJson());
                    b.Write(tmp);
                    bool sameJson = Same(args[1], tmp) && Same(Path.ChangeExtension(args[1], ".uexp"), Path.ChangeExtension(tmp, ".uexp"));
                    int raw = a.Exports.Count(e => e.GetType().Name == "RawExport");
                    Console.WriteLine($"{args[1]}: binary {(same ? "ok" : "DIFF")}, json {(sameJson ? "ok" : "DIFF")}, raw exports {raw}");
                    File.Delete(tmp); File.Delete(Path.ChangeExtension(tmp, ".uexp"));
                    return same && sameJson ? 0 : 1;
                }
            }
        }
        catch (Exception e) { Console.Error.WriteLine($"{args[1]}: {e.GetType().Name}: {e.Message}"); return 1; }
        Console.Error.WriteLine("unknown command " + args[0]);
        return 2;
    }

    static bool Same(string a, string b) => File.Exists(a) == File.Exists(b) && (!File.Exists(a) || File.ReadAllBytes(a).AsSpan().SequenceEqual(File.ReadAllBytes(b)));
}
