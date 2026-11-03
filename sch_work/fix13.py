# -*- coding: utf-8 -*-
"""fix13: 走廊终版重建 + U3/C11/C12/C13 挪位重接 + R11/J1 补连"""
import json, subprocess, os, time

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def sh(*args, timeout=180):
    p = subprocess.run([EXE, *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": ((p.stdout or "") + (p.stderr or ""))[:400]}

fails = []

def delete_zone(del_ids, tag):
    ids = sorted(set(del_ids))
    for i in range(0, len(ids), 6):
        r = sh("sch", "prim-delete", "--ids", ",".join(ids[i:i+6]))
        if not r.get("ok"): fails.append(["del", tag]); print("  del FAIL")
    print(f"  deleted {len(ids)} ({tag})")
    time.sleep(1.2)

def move(des, x, y, rot=None, comps=None):
    c = comps[des]
    args = ["sch", "modify", "--id", c["primitiveId"], "--x", str(x), "--y", str(y)]
    if rot is not None: args += ["--rotation", str(rot)]
    r = sh(*args)
    time.sleep(1.2)
    print(f"  move {des} -> ({x},{y}) rot={rot}: {r.get('ok')}")
    if not r.get("ok"): fails.append(["move", des])

def conn(P, kind, net, direction, offset):
    args = ["sch", "connect", "--pin", P, "--kind", kind, "--net", net,
            "--direction", direction, "--offset", str(offset)]
    r = sh(*args)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2)
        r = sh(*args)
        ok = r.get("ok")
    print(f"  conn {P}->{net} {direction}{offset}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:100]}")
    if not ok: fails.append(["conn", P, net])
    return ok

# ---------- 1. 清理四大区域 ----------
print("== 1. zone cleanup")
r = sh("sch", "list", "--include-wires", "--stay")
wires = r.get("result", {}).get("wires", [])
r2 = sh("sch", "list", "--stay")
allc = r2.get("result", {}).get("components", [])
del_w, del_f = set(), set()
ZONES = [(300,385,480,775), (640,790,580,815), (815,865,605,635), (0,45,770,800)]
def inbox(x, y):
    return any(a <= x <= b and c <= y <= d for a,b,c,d in ZONES)
for w in wires:
    pts = w.get("rawLine", [])
    if any(inbox(pts[i], pts[i+1]) for i in range(0, len(pts), 2)):
        del_w.add(w["primitiveId"])
for c in allc:
    if c.get("componentType") == "netflag":
        x, y, n = round(c["x"]), round(c["y"]), c.get("name")
        if n == "__ROTPROBE__":
            del_f.add(c["primitiveId"]); continue
        if inbox(x, y):
            del_f.add(c["primitiveId"])
delete_zone(del_w, "wires")
delete_zone(del_f, "flags")

# ---------- 2. 挪位 ----------
print("== 2. moves")
comps = {c["designator"]: c for c in allc if c.get("designator")}
move("U3", 720, 710, None, comps)
move("C11", 730, 610, 270, comps)
move("C13", 760, 640, 270, comps)
move("C12", 655, 745, 180, comps)
r = sh("sch", "list", "--stay", timeout=180)
comps = {c["designator"]: c for c in r["result"]["components"] if c.get("designator")}
for des in ("U3","C11","C13","C12"):
    c = comps[des]
    print(f"  {des}: ({c['x']},{c['y']}) rot={c.get('rotation')} pins={[(p['pinNumber'],round(p['x']),round(p['y'])) for p in c.get('pins',[])]}" if c.get("pins") else f"  {des}: ({c['x']},{c['y']})")

# ---------- 3. 重连 ----------
print("== 3. reconnect")
CORR = [("U1:24","3V3",25),("U1:23","GND",45),("U1:19","CC_LED",25),("U1:18","CV_LED",45),
        ("U1:15","ISENSE",25),("U1:14","VSENSE",45),("U1:9","3V3",25),("U1:8","GND",45),
        ("U1:7","NRST",25),("U1:2","PWR_LED",45),("U1:1","3V3",25)]
for P, net, off in CORR:
    conn(P, "gnd" if net == "GND" else "power", net, "left", off)
conn("U3:1", "power", "ISENSE", "down", 20)
conn("U3:2", "gnd", "GND", "down", 20)
conn("U3:3", "power", "VOUT", "down", 20)
conn("U3:4", "power", "VLOAD", "up", 20)
conn("U3:5", "power", "3V3", "up", 20)
conn("C11:1", "power", "ISENSE", "down", 20)
conn("C11:2", "gnd", "GND", "up", 20)
conn("C13:1", "power", "OSC_OUT", "down", 20)
conn("C13:2", "gnd", "GND", "up", 20)
conn("C12:1", "power", "OSC_IN", "up", 10)
conn("C12:2", "gnd", "GND", "down", 20)
conn("R11:1", "power", "VMID", "right", 25)
conn("J1:2", "gnd", "GND", "left", 15)

# ---------- 4. 保存 + 检查 ----------
print("== 4. save+check")
r = sh("sch", "save", timeout=240)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:80])
if not r.get("ok"): fails.append("save")
r = sh("sch", "check", timeout=300)
txt = json.dumps(r.get("result", {}), ensure_ascii=False)
head = [l for l in txt.split("\\n") if "finding" in l]
print("  check:", (head[0][:260] if head else txt[:260]))
with open("fix13_out.json", "w", encoding="utf-8") as f:
    json.dump({"fails": fails, "check_raw": txt[:3000]}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
