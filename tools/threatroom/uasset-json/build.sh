#!/bin/sh
# ../work/uasset-json: the UAssetAPI JSON CLI (from the hero mods' tools, plus fix-offsets) that build_panel.py uses.
# Needs the .NET 10 SDK in ~/Tools/dotnet and UAssetAPI (UASSETAPI_DIR, default ~/Tools/uasset-json-src, a UAssetAPI
# copy with the Niagara JSON patch; a plain clone of github.com/atenfyr/UAssetAPI works too).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/Tools/dotnet}" DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
SRC="$HERE/../work/uasset-json-src"
rm -rf "$SRC"; mkdir -p "$SRC"
cp "$HERE/Program.cs" "$HERE/uasset-json.csproj" "$SRC/"
"$DOTNET_ROOT/dotnet" publish "$SRC/uasset-json.csproj" -c Release -o "$HERE/../work/uasset-json" \
    -p:UASSETAPI_DIR="${UASSETAPI_DIR:-$HOME/Tools/uasset-json-src}" -p:GeneratePackageOnBuild=false -nologo -v quiet
echo "built $HERE/../work/uasset-json/uasset-json"
