"""Static consistency check for the SkillTown Godot client (no Godot install needed).

Usage: python3 tools/check_godot_client.py

Verifies that $NodePath references exist in the scene that owns the script, that
APIClient/Config members exist, that signal handlers take the right number of
arguments, and that local calls resolve. This is not a GDScript parser: engine
API misuse and type errors still need the Godot editor.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "godot"
problems = []

def scene_nodes(tscn: Path):
    """Return set of node paths relative to the scene root, e.g. 'Panel/NPCName'."""
    nodes = set()
    for m in re.finditer(r'\[node name="([^"]+)"(?:[^\]]*?parent="([^"]*)")?', tscn.read_text(encoding="utf-8")):
        name, parent = m.group(1), m.group(2)
        if parent is None:      # scene root
            continue
        nodes.add(name if parent == "." else f"{parent}/{name}")
    return nodes

# scene -> script mapping via ext_resource + root script assignment
scene_script = {}
for tscn in (ROOT / "scenes").glob("*.tscn"):
    text = tscn.read_text(encoding="utf-8")
    res = dict(re.findall(r'\[ext_resource type="Script"[^\]]*path="res://([^"]+)"\s+id="([^"]+)"\]', text))
    res = {v: k for k, v in res.items()}
    root_block = text.split("[node name=")[1] if "[node name=" in text else ""
    m = re.search(r'script = ExtResource\("([^"]+)"\)', root_block)
    if m and m.group(1) in res:
        scene_script[ROOT / res[m.group(1)]] = tscn

def members(path: Path):
    text = path.read_text(encoding="utf-8")
    funcs = {m.group(1): m.group(2) for m in re.finditer(r'^func (\w+)\(([^)]*)\)', text, re.M)}
    sigs = {m.group(1): m.group(2) for m in re.finditer(r'^signal (\w+)\(([^)]*)\)', text, re.M)}
    names = set(funcs) | set(sigs)
    names |= set(re.findall(r'^(?:@onready )?var (\w+)', text, re.M))
    names |= set(re.findall(r'^const (\w+)', text, re.M))
    return names, funcs, sigs

api_names, api_funcs, api_signals = members(ROOT / "scripts/api_client.gd")
cfg_names, _, _ = members(ROOT / "scripts/config.gd")

def arity(params: str):
    params = params.strip()
    if not params:
        return 0
    return len([p for p in params.split(",") if p.strip()])

for gd in sorted((ROOT / "scripts").glob("*.gd")):
    text = gd.read_text(encoding="utf-8")
    if re.search(r'^    ', text, re.M):
        problems.append(f"{gd.name}: space-indented lines (repo uses tabs)")

    # 1. $NodePath usage must exist in the scene that owns this script
    used = set(re.findall(r'\$([A-Za-z_][\w/]*)', text))
    tscn = scene_script.get(gd)
    if used and tscn is None:
        problems.append(f"{gd.name}: uses {sorted(used)} but no scene assigns this script")
    elif used:
        available = scene_nodes(tscn)
        for path in sorted(used - available):
            problems.append(f"{gd.name}: ${path} missing in {tscn.name}")

    # 2. APIClient./Config. members must exist
    for owner, names in (("APIClient", api_names), ("Config", cfg_names)):
        for member in sorted(set(re.findall(rf'\b{owner}\.(\w+)', text))):
            if member not in names:
                problems.append(f"{gd.name}: {owner}.{member} does not exist")

    # 3. signal connect arity must match handler arity
    for sig, handler in re.findall(r'APIClient\.(\w+)\.connect\((_?\w+)\)', text):
        if sig not in api_signals:
            problems.append(f"{gd.name}: APIClient.{sig} is not a signal")
            continue
        local_funcs = members(gd)[1]
        if handler.lstrip("_") and handler not in local_funcs:
            problems.append(f"{gd.name}: handler {handler} not defined")
        elif arity(api_signals[sig]) != arity(local_funcs[handler]):
            problems.append(
                f"{gd.name}: {handler} takes {arity(local_funcs[handler])} args, "
                f"signal {sig} emits {arity(api_signals[sig])}"
            )

    # 4. local self-calls must resolve
    local_funcs = members(gd)[1]
    for call in sorted(set(re.findall(r'(?<![\w.$])(_\w+)\(', text))):
        if call not in local_funcs and call not in {"_ready", "_input", "_physics_process", "_process"}:
            problems.append(f"{gd.name}: calls undefined local function {call}()")

print(f"scripts checked: {len(list((ROOT / 'scripts').glob('*.gd')))}, scenes mapped: {len(scene_script)}")
for p in problems:
    print("FAIL:", p)
print("OK — no inconsistencies found" if not problems else f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
