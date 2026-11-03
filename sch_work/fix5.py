# -*- coding: utf-8 -*-
"""fix5: J2/R7 挪位离开 U1 引脚走廊，重建受影响连接，然后全量验证"""
import json, subprocess, os, time

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def sh(*args, timeout=150):
    p = subprocess.run([EXE, *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": ((p.stdout or "") + (p.stderr or ""))[:400]}

def measure(wires=False):
    args = ["sch", "list", "--include-pins", "--include-bbox"] + (["--include-wires"] if wires else []) + ["--stay"]
    r = sh(*args)
    res = r.get("result", {})
    comps = {c["designator"]: c for c in res.get("components", []) if c.get("designator")}
    return comps, res.get("wires", []), res.get("components", [])

fails = []

# 1. 找并删旧 W-VLOAD / J2.2 gnd 桩旗 / R7 桩旗
print("== 1. delete stale")
comps, wires, allc = measure(wires=True)
del_ids = set()
for w in wires:
    pts = w.get("rawLine", [])
    net = w.get("net", "")
    pset = [(pts[i], pts[i+1]) for i in range(0, len(pts), 2)]
    # 旧 VLOAD 路线：含 (340,555) 或 (350,555) 端点
    if net == "VLOAD" and any(abs(x-340) < 2 and abs(y-555) < 2 for x, y in pset):
        del_ids.add(w["primitiveId"])
    # J2 旧 gnd 桩：端点在 (350,545) 附近
    if net in ("", "GND") and any(abs(x-350) < 3 and abs(y-545) < 3 for x, y in pset):
        del_ids.add(w["primitiveId"])
    # R7 旧桩：端点在 (285,545)/(310,545) 或 (245,545)/(220,545) 附近
    if net in ("", "GND", "GATE") and any((abs(x-285) < 3 and abs(y-545) < 3) or (abs(x-220) < 4 and abs(y-545) < 4) for x, y in pset):
        del_ids.add(w["primitiveId"])
for c in allc:
    if c.get("componentType") == "netflag":
        x, y, n = c.get("x"), c.get("y"), c.get("name")
        if (abs(x-310) < 4 and abs(y-545) < 4) or (abs(x-220) < 5 and abs(y-545) < 5) or (n == "GND" and abs(x-330) < 15 and abs(y-545) < 8):
            del_ids.add(c["primitiveId"])
if del_ids:
    r = sh("sch", "prim-delete", "--ids", ",".join(sorted(del_ids)))
    print(f"  delete {len(del_ids)}: ok={r.get('ok')} {str(r.get('error',''))[:100]}")
    time.sleep(1.5)

# 2. 移动 J2 / R7
print("== 2. moves")
comps, wires, allc = measure(wires=True)
sh("sch", "modify", "--id", comps["J2"]["primitiveId"], "--x", "200", "--y", "480", "--rotation", "180")
time.sleep(1.2)
sh("sch", "modify", "--id", comps["R7"]["primitiveId"], "--x", "240", "--y", "560")
time.sleep(1.2)
comps, wires, allc = measure(wires=True)
print("  J2 pins:", [(p["pinNumber"], p.get("pinName"), round(p["x"]), round(p["y"])) for p in comps["J2"]["pins"]])
print("  R7 pins:", [(p["pinNumber"], round(p["x"]), round(p["y"])) for p in comps["R7"]["pins"]])

# 3. 重建
print("== 3. rebuild")
def get_pin(c, num): return next(p for p in c["pins"] if str(p["pinNumber"]) == str(num))

# VLOAD: Rs1.2 -> J2.1
rs2 = get_pin(comps["Rs1"], "2"); j21 = get_pin(comps["J2"], "1")
pts = [[rs2["x"], rs2["y"]], [270, rs2["y"]], [270, j21["y"]], [j21["x"]+10, j21["y"]], [j21["x"], j21["y"]]]
r = sh("sch", "wire", "--points", json.dumps([[round(a,1),round(b,1)] for a,b in pts], separators=(",",":")), "--net", "VLOAD")
print("  VLOAD wire:", r.get("ok"), "" if r.get("ok") else json.dumps(r.get("error", r), ensure_ascii=False)[:160])
if not r.get("ok"): fails.append("VLOAD wire")

# J2.2 gnd
j22 = get_pin(comps["J2"], "2")
r = sh("sch", "connect", "--pin", f"J2:2", "--kind", "gnd", "--net", "GND")
print("  J2:2 gnd:", r.get("ok"), "" if r.get("ok") else json.dumps(r.get("error", r), ensure_ascii=False)[:140])
if not r.get("ok"): fails.append("J2:2")

# R7.1 GATE（向西桩+旗）、R7.2 gnd（向东桩+旗）
r71 = get_pin(comps["R7"], "1"); r72 = get_pin(comps["R7"], "2")
r = sh("sch", "wire", "--points", f"[[{round(r71['x'],1)},{round(r71['y'],1)}],[{round(r71['x']-25,1)},{round(r71['y'],1)}]]", "--net", "GATE")
ok1 = r.get("ok")
if ok1:
    r = sh("sch", "netflag", "--kind", "net_label", "--net", "GATE", "--x", str(round(r71["x"]-25,1)), "--y", str(round(r71["y"],1)))
    ok1 = r.get("ok")
print("  R7:1 GATE:", ok1)
if not ok1: fails.append("R7:1 GATE")
r = sh("sch", "connect", "--pin", "R7:2", "--kind", "gnd", "--net", "GND")
print("  R7:2 gnd:", r.get("ok"), "" if r.get("ok") else json.dumps(r.get("error", r), ensure_ascii=False)[:140])
if not r.get("ok"): fails.append("R7:2")

# CC_LED 桩重试（J2 已挪走）
r = sh("sch", "wire", "--points", "[[375,565],[325,565]]", "--net", "CC_LED")
ok = r.get("ok")
if ok:
    r = sh("sch", "netflag", "--kind", "net_label", "--net", "CC_LED", "--x", "325", "--y", "565")
    ok = r.get("ok")
print("  CC_LED:", ok)
if not ok: fails.append("CC_LED")

# 4. 检查原始输出
print("\n== 4. raw check output")
r = sh("sch", "check", timeout=240)
print("check raw head:", json.dumps(r, ensure_ascii=False)[:700])

with open("fix5_errors.json", "w", encoding="utf-8") as f:
    json.dump(fails, f, ensure_ascii=False, indent=1)
print("\nRESULT fails:", fails)
