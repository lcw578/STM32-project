# -*- coding: utf-8 -*-
"""fix6b: 收尾 —— C11 旋转换极、J2/R7 挪位重建、全部信号旗（power 类型）、保存"""
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
    args = ["sch", "list"] + (["--include-wires"] if wires else []) + ["--stay"]
    r = sh(*args)
    res = r.get("result", {})
    comps = {c["designator"]: c for c in res.get("components", []) if c.get("designator")}
    return comps, res.get("wires", []), res.get("components", [])

# 离线引脚地图：base(page_final) + 已知移动/旋转的覆盖值
BASE = json.load(open("page_final.json", encoding="utf-8"))["result"]["components"]
PINS = {}
for c in BASE:
    if c.get("designator"):
        PINS[c["designator"]] = {str(p["pinNumber"]): (p["x"], p["y"]) for p in c.get("pins", [])}
# 覆盖：fix3/fix6 移动过的器件（几何推算，guard 会验证）
PINS["Rs1"] = {"1": (320, 610), "2": (280, 610)}
PINS["C3"]  = {"1": (320, 80),  "2": (360, 80)}
PINS["C12"] = {"1": (560, 680), "2": (560, 720)}
PINS["C13"] = {"1": (655, 680), "2": (655, 720)}
PINS["C11"] = {"1": (720, 640), "2": (720, 680)}   # 旋转 180 后
PINS["J2"]  = {"1": (220, 475), "2": (220, 485)}   # (200,480) rot180
PINS["R7"]  = {"1": (220, 560), "2": (260, 560)}   # (240,560)

fails = []

def wire(pts, net):
    arg = json.dumps([[round(a,1), round(b,1)] for a,b in pts], separators=(",",":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    time.sleep(0.4)
    ok = r.get("ok")
    if not ok:
        time.sleep(1.5)
        r = sh("sch", "wire", "--points", arg, "--net", net)
        ok = r.get("ok")
    print(f"  wire {net} {pts[0]}->{pts[-1]}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:130]}")
    if not ok: fails.append(["wire", net, str(pts[:2])])
    return ok

def flag(net, x, y, kind="power"):
    r = sh("sch", "netflag", "--kind", kind, "--net", net, "--x", str(round(x,1)), "--y", str(round(y,1)))
    time.sleep(0.4)
    ok = r.get("ok")
    if not ok:
        time.sleep(1.5)
        r = sh("sch", "netflag", "--kind", kind, "--net", net, "--x", str(round(x,1)), "--y", str(round(y,1)))
        ok = r.get("ok")
    return ok

def conn(P, kind, net):
    r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net)
    time.sleep(0.4)
    ok = r.get("ok")
    if not ok:
        time.sleep(1.5)
        r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net)
        ok = r.get("ok")
    print(f"  connect {P}->{net}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:110]}")
    if not ok: fails.append(["conn", P, net])

# ---------- 1. 旋转与挪位 ----------
print("== 1. moves")
comps, wires, allc = measure()
sh("sch", "modify", "--id", comps["C11"]["primitiveId"], "--rotation", "90"); time.sleep(1.2)
sh("sch", "modify", "--id", comps["J2"]["primitiveId"], "--x", "200", "--y", "480", "--rotation", "180"); time.sleep(1.2)
sh("sch", "modify", "--id", comps["R7"]["primitiveId"], "--x", "240", "--y", "560"); time.sleep(1.2)
comps, wires, allc = measure()
print("  C11 rot:", comps["C11"].get("rotation"), "| J2:", comps["J2"]["x"], comps["J2"]["y"], comps["J2"].get("rotation"), "| R7:", comps["R7"]["x"], comps["R7"]["y"])

# ---------- 2. 重建 ----------
print("== 2. rebuild")
wire([(280,610),(270,610),(270,475),(230,475),(220,475)], "VLOAD")
conn("J2:2", "gnd", "GND")
wire([(220,560),(195,560)], "GATE")
flag("GATE", 195, 560)
conn("R7:2", "gnd", "GND")
wire([(720,640),(720,615)], "ISENSE")
flag("ISENSE", 720, 615)
conn("U3:2", "gnd", "GND")           # 南桩 (720,720)->(720,695)
wire([(720,680),(720,695)], "GND")   # C11.2 北桩并入同网
conn("U1:19", "gnd", "CC_LED")       # 占位错误则下面手工桩
# U1:19 实际要 CC_LED 旗：手工向西桩 + power 旗
wire([(375,565),(325,565)], "CC_LED")
flag("CC_LED", 325, 565)

# ---------- 3. 全部信号旗 ----------
print("== 3. signal flags")
comps, wires, allc = measure(wires=True)
have = [(round(c["x"]), round(c["y"]), c["name"]) for c in allc if c.get("componentType") == "netflag"]
def far_end(P):
    des, num = P.split(":")
    px, py = PINS[des][num]
    for w in wires:
        pts = w.get("rawLine", [])
        for i in range(0, len(pts), 2):
            if abs(pts[i]-px) < 1.5 and abs(pts[i+1]-py) < 1.5:
                j = 0 if i != 0 else len(pts)-2
                far = (pts[j], pts[j+1])
                if abs(far[0]-px) > 1.5 or abs(far[1]-py) > 1.5:
                    return far
    return None

SIGNALS = {
 "PWM": ["R8:1","U1:29"], "GATE": ["R6:2","Q1:1"],
 "NRST": ["U1:7","R9:2","SW1:1"], "BOOT0": ["U1:44","R10:1"],
 "SWDIO": ["U1:34","J3:2"], "SWCLK": ["U1:37","J3:3"],
 "UART_TX": ["U1:30","J4:1"], "UART_RX": ["U1:31","J4:2"],
 "VSENSE": ["R11:2","C10:1","U1:14"], "ISENSE": ["U3:1","U1:15"],
 "CV_LED": ["U1:18"], "CC_LED": ["U1:19"], "PWR_LED": ["U1:2"],
 "OSC_IN": ["C12:1"], "OSC_OUT": ["C13:1"], "VMID": ["R11:1"], "PWM_B": ["Q3:1"],
}
for net, plist in SIGNALS.items():
    for P in plist:
        des, num = P.split(":")
        px, py = PINS[des][num]
        far = far_end(P)
        if far is None:
            # 引脚 1 偏移修正：LED2 阳极是 2 号脚
            if des.startswith("LED"):
                continue
            print(f"  no stub {P} ({net})"); fails.append(["nostub", P, net]); continue
        if any(fx == round(far[0]) and fy == round(far[1]) and nm == net for fx, fy, nm in have):
            print(f"  {P} {net}: exists"); continue
        if any(abs(fx-far[0]) < 2 and abs(fy-far[1]) < 2 for fx, fy, nm in have):
            print(f"  {P} {net}: point occupied by other flag"); continue
        ok = flag(net, far[0], far[1])
        print(f"  flag {net} @{int(far[0])},{int(far[1])}: {'OK' if ok else 'FAIL'}")
        if not ok: fails.append(["flag", net, P])
        else: have.append((round(far[0]), round(far[1]), net))

# ---------- 4. 保存 ----------
print("== 4. save")
r = sh("sch", "save", timeout=180)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:150])
if not r.get("ok"): fails.append(["save"])

with open("fix6b_errors.json", "w", encoding="utf-8") as f:
    json.dump(fails, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
