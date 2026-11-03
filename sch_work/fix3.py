# -*- coding: utf-8 -*-
"""修复 v3：遵守 pin-exit-direction 规则的全部补线 + 补旗"""
import json, subprocess, os, time

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def sh(*args, timeout=120):
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
    return comps, res.get("wires", [])

def get_pin(c, num):
    return next(p for p in c["pins"] if str(p["pinNumber"]) == str(num))

def pinxy(P, comps):
    des, num = P.split(":")
    p = get_pin(comps[des], num)
    return (p["x"], p["y"])

def set_rot(des, rot):
    global comps
    sh("sch", "modify", "--id", comps[des]["primitiveId"], "--rotation", str(rot))
    time.sleep(1.0)
    comps, _ = measure()

def set_pos(des, x, y):
    global comps
    sh("sch", "modify", "--id", comps[des]["primitiveId"], "--x", str(x), "--y", str(y))
    time.sleep(1.0)
    comps, _ = measure()

fails = []

# ---------- 1. Rs1 西移离开 U1 引脚区，C3 旋转 ----------
print("== 1. moves")
comps, _ = measure()
if abs(comps["Rs1"]["x"] - 300) > 1 or abs(comps["Rs1"]["y"] - 610) > 1:
    set_pos("Rs1", 300, 610)
# Rs1 pin1 需在东（(320,610)）
c = comps["Rs1"]
p1 = get_pin(c, "1")
if not (p1["x"] > comps["Rs1"]["x"]):
    set_rot("Rs1", 180)
c = comps["C3"]
p1 = get_pin(c, "1")
if not (p1["x"] > c["x"]):
    set_rot("C3", 180)
print("  Rs1:", comps["Rs1"]["x"], comps["Rs1"]["y"], "C3 pin1 east OK")

# C12/C13 重定位（OSC 电容放 Y1 下方空档）
for des, x, y in [("C12", 560, 700), ("C13", 655, 700)]:
    c = comps[des]
    if abs(c["x"]-x) > 1 or abs(c["y"]-y) > 1:
        set_pos(des, x, y)
# C12/C13 pin1 朝下（南）
for des in ("C12", "C13"):
    c = comps[des]
    p1 = get_pin(c, "1")
    p2 = get_pin(c, "2")
    if not (p1["y"] < p2["y"]):
        set_rot(des, 180 if abs(p1["x"]-p2["x"]) > abs(p1["y"]-p2["y"]) else 0)
        # 若仍不对再试 270
        c = comps[des]; p1 = get_pin(c, "1"); p2 = get_pin(c, "2")
        if not (p1["y"] < p2["y"]):
            set_rot(des, 270)
comps, _ = measure()
print("  C12 pins:", [(p["pinNumber"], round(p["x"]), round(p["y"])) for p in comps["C12"]["pins"]])
print("  C13 pins:", [(p["pinNumber"], round(p["x"]), round(p["y"])) for p in comps["C13"]["pins"]])

# ---------- 2. 补线 ----------
print("== 2. wires")
comps, wires = measure(wires=True)
WIRES = [
    ("VIN_5V", ["J1:1", "C5:1"], ["40,795", "40,690"]),
    ("SW", ["Q1:3", "D1:2"], ["190,745", "220,745", "260,745", "260,770"]),
    ("SW", ["L1:2", None], ["220,770", "220,745"]),
    ("VOUT", ["D1:1", "C6:1"], ["330,770", "330,660"]),
    ("VOUT", ["C6:1", "Rs1:1"], ["330,660", "330,610"]),
    ("VLOAD", ["Rs1:2", "J2:1"], ["270,610", "270,555", "340,555"]),
    ("OSC_IN", ["U1:5", "Y1:1"], ["355,705", "355,760", "570,760", "570,770"]),
    ("OSC_OUT", ["U1:6", "Y1:2"], ["360,695", "360,490", "630,490", "630,770"]),
    ("VMID", ["R1:2", "R2:1"], ["830,780", "830,700"]),
]
for i, (net, pins, mids) in enumerate(WIRES):
    seq = []
    if pins and pins[0]: seq.append(pinxy(pins[0], comps))
    for m in mids: seq.append(tuple(float(v) for v in m.split(",")))
    if pins and pins[1]: seq.append(pinxy(pins[1], comps))
    # 已存在则跳过（端点重合判定）
    def _close(a, b): return all(abs(a[k]-b[k]) < 2 for k in (0, 1))
    exist = False
    for w in wires:
        if w.get("net") != net: continue
        pts = w.get("rawLine", [])
        wp = [(pts[k], pts[k+1]) for k in range(0, len(pts), 2)]
        if len(wp) >= 2 and _close(wp[0], seq[0]) and _close(wp[-1], seq[-1]):
            exist = True; break
    if exist:
        print(f"  {net}: SKIP exists"); continue
    arg = json.dumps([[round(a,1), round(b,1)] for a,b in seq], separators=(",",":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    ok = r.get("ok", False)
    if not ok:
        time.sleep(2)
        r = sh("sch", "wire", "--points", arg, "--net", net)
        ok = r.get("ok", False)
    err = json.dumps(r.get("error", r.get("result", {}).get("geometryGuard", {})), ensure_ascii=False)[:200] if not ok else ""
    print(f"  {net}: {'OK' if ok else 'FAIL ' + err}")
    if not ok: fails.append({"wire": net, "err": err})

# ---------- 3. 补旗 ----------
print("== 3. flags")
comps, wires = measure(wires=True)

def stub_far_end(P, comps, wires):
    des, num = P.split(":")
    p = get_pin(comps[des], num)
    for w in wires:
        pts = w.get("rawLine", [])
        for i in range(0, len(pts), 2):
            if abs(pts[i]-p["x"]) < 1 and abs(pts[i+1]-p["y"]) < 1:
                j = 0 if i != 0 else len(pts)-2
                far = (pts[j], pts[j+1])
                if abs(far[0]-p["x"])>1 or abs(far[1]-p["y"])>1:
                    return far
    return None

def add_flag(net, kind, x, y):
    r = sh("sch", "netflag", "--kind", kind, "--net", net, "--x", str(round(x,1)), "--y", str(round(y,1)))
    ok = r.get("ok", False)
    if not ok:
        time.sleep(1.5)
        r = sh("sch", "netflag", "--kind", kind, "--net", net, "--x", str(round(x,1)), "--y", str(round(y,1)))
        ok = r.get("ok", False)
    print(f"  flag {net} @{int(x)},{int(y)}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:130]}")
    if not ok: fails.append({"flag": net, "at": [x, y]})

def add_stub_flag(P, net, kind, dx, dy):
    """从引脚画桩 (dx,dy 偏移) 并放旗"""
    comps, wires = measure(wires=True)
    far = stub_far_end(P, comps, wires)
    if far is None:
        p = pinxy(P, comps)
        seq = [[round(p[0],1), round(p[1],1)], [round(p[0]+dx,1), round(p[1]+dy,1)]]
        r = sh("sch", "wire", "--points", json.dumps(seq, separators=(",",":")), "--net", net)
        if not r.get("ok"):
            print(f"  stub {P} FAIL: {json.dumps(r.get('error',{}), ensure_ascii=False)[:130]}")
            fails.append({"stub": P, "net": net}); return
        far = (p[0]+dx, p[1]+dy)
    add_flag(net, kind, far[0], far[1])

# 已有桩直接补旗（修 j 下标 bug 后能找到远端）
add_stub_flag("J4:1", "UART_TX", "net_label", 0, 0)
add_stub_flag("U1:19", "CC_LED", "net_label", 0, 0)
add_stub_flag("U1:2", "PWR_LED", "net_label", 0, 0)
# U1:36 / U1:48 的桩在首轮已存在，端点 (575,625)/(575,745)
add_flag("3V3", "power", 575, 625)
add_flag("3V3", "power", 575, 745)
# C12.1/C13.1 朝南桩 + OSC 旗
add_stub_flag("C12:1", "OSC_IN", "net_label", 0, -25)
add_stub_flag("C13:1", "OSC_OUT", "net_label", 0, -25)
# C12.2/C13.2 gnd
add_stub_flag("C12:2", "GND", "gnd", 0, 25)
add_stub_flag("C13:2", "GND", "gnd", 0, 25)
# R11.1 VMID 桩向东
add_stub_flag("R11:1", "VMID", "net_label", 25, 0)
# W2 起点 (50,700) 补 VIN 旗
add_flag("VIN_5V", "power", 50, 700)
# C3.1 向东桩 + VIN 旗
add_stub_flag("C3:1", "VIN_5V", "power", 25, 0)
# Rs1.2 向西桩 + VLOAD 旗
add_stub_flag("Rs1:2", "VLOAD", "power", -25, 0)
# U1:9 VDDA 重试 connect（Rs1 已移走）
r = sh("sch", "connect", "--pin", "U1:9", "--kind", "power", "--net", "3V3")
print("  U1:9 connect:", r.get("ok"), "" if r.get("ok") else json.dumps(r.get("error", r), ensure_ascii=False)[:130])
if not r.get("ok"): fails.append({"conn": "U1:9"})

with open("fix3_errors.json", "w", encoding="utf-8") as f:
    json.dump(fails, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
