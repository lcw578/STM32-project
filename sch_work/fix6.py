# -*- coding: utf-8 -*-
"""fix6: 最终修复 —— 旗子改用 net_port_bi、C11/C3/J2/R7 手术、全信号旗补齐"""
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

fails = []

# ---------- 0. 测试 net_port_bi ----------
print("== 0. flag kind test")
r = sh("sch", "netflag", "--kind", "net_port_bi", "--net", "TESTPORT", "--x", "900", "--y", "150")
time.sleep(1.0)
comps, wires, allc = measure()
test_ok = any(c.get("name") == "TESTPORT" for c in allc if c.get("componentType") == "netflag")
print("  net_port_bi works:", test_ok)
KIND = "net_port_bi" if test_ok else "net_label"
# 删测试旗
for c in allc:
    if c.get("name") == "TESTPORT":
        sh("sch", "prim-delete", "--ids", c["primitiveId"])

def dflag(kind, net, x, y):
    r = sh("sch", "netflag", "--kind", kind, "--net", net, "--x", str(round(x,1)), "--y", str(round(y,1)))
    time.sleep(0.4)
    return r.get("ok")

def add_flag(net, x, y, kind=KIND):
    ok = dflag(kind, net, x, y)
    if not ok:
        time.sleep(1.5)
        ok = dflag(kind, net, x, y)
    print(f"  flag {net} @{int(x)},{int(y)}: {'OK' if ok else 'FAIL'}")
    if not ok: fails.append(["flag", net, x, y])

def add_stub(P, comps, dx, dy, net):
    """从引脚画桩；P 引脚坐标由 comps 实测"""
    des, num = P.split(":")
    p = next(pp for pp in comps[des]["pins"] if str(pp["pinNumber"]) == str(num))
    seq = [[round(p["x"],1), round(p["y"],1)], [round(p["x"]+dx,1), round(p["y"]+dy,1)]]
    r = sh("sch", "wire", "--points", json.dumps(seq, separators=(",",":")), "--net", net)
    time.sleep(0.4)
    return r.get("ok"), (p["x"]+dx, p["y"]+dy)

# ---------- 1. 删除问题图元 ----------
print("== 1. delete broken")
comps, wires, allc = measure(wires=True)
DEL_W = {"92219ab5aaaaad61": 1, "372bbebe315a7af7": 1, "b289dcbbd5e55b7a": 1,
         "7f067eba8b149f84": 1, "f1620298e0a551b5": 1}
DEL_F = {"1acb7fa65d46807a": 1, "72744397a08c8184": 1, "956c5f8ac661c26a": 1,
         "52dceea35bfb06b4": 1, "1f9d728d0f679aea": 1}
ids = [w["primitiveId"] for w in wires if w["primitiveId"] in DEL_W]
ids += [c["primitiveId"] for c in allc if c.get("componentType") == "netflag" and c["primitiveId"] in DEL_F]
if ids:
    r = sh("sch", "prim-delete", "--ids", ",".join(ids))
    print(f"  deleted {len(ids)}: ok={r.get('ok')} {str(r.get('error',''))[:90]}")
    time.sleep(1.5)

# ---------- 2. C3 挪位重接 ----------
print("== 2. C3")
comps, wires, allc = measure(wires=True)
sh("sch", "modify", "--id", comps["C3"]["primitiveId"], "--x", "340", "--y", "80", "--rotation", "0")
time.sleep(1.2)
comps, wires, allc = measure(wires=True)
ok, far = add_stub("C3:1", comps, -25, 0, "VIN_5V")
print("  C3.1 stub:", ok)
if ok: add_flag("VIN_5V", far[0], far[1], "power")
else: fails.append(["C3.1 stub"])
r = sh("sch", "connect", "--pin", "C3:2", "--kind", "gnd", "--net", "GND")
print("  C3.2 gnd connect:", r.get("ok"))
if not r.get("ok"): fails.append(["C3.2 gnd"])

# ---------- 3. C11 旋转重接 ----------
print("== 3. C11")
comps, wires, allc = measure(wires=True)
sh("sch", "modify", "--id", comps["C11"]["primitiveId"], "--rotation", "0")
time.sleep(1.2)
comps, wires, allc = measure(wires=True)
p1 = next(p for p in comps["C11"]["pins"] if p["pinNumber"] == "1")
print("  C11 pins:", [(p["pinNumber"], round(p["x"]), round(p["y"])) for p in comps["C11"]["pins"]])
if p1["y"] > 660:  # pin1 应在下方（南）
    sh("sch", "modify", "--id", comps["C11"]["primitiveId"], "--rotation", "180")
    time.sleep(1.2)
    comps, wires, allc = measure(wires=True)
ok, far = add_stub("C11:1", comps, 0, -25, "ISENSE")
print("  C11.1 stub:", ok)
if ok: add_flag("ISENSE", far[0], far[1])
else: fails.append(["C11.1 stub"])
r = sh("sch", "connect", "--pin", "U3:2", "--kind", "gnd", "--net", "GND")
print("  U3.2 gnd reconnect:", r.get("ok"))
if not r.get("ok"): fails.append(["U3.2 gnd"])

# ---------- 4. J2/R7 挪位 + 重建 ----------
print("== 4. J2/R7")
comps, wires, allc = measure(wires=True)
sh("sch", "modify", "--id", comps["J2"]["primitiveId"], "--x", "200", "--y", "480", "--rotation", "180")
time.sleep(1.2)
sh("sch", "modify", "--id", comps["R7"]["primitiveId"], "--x", "240", "--y", "560")
time.sleep(1.2)
comps, wires, allc = measure(wires=True)
print("  J2:", comps["J2"]["x"], comps["J2"]["y"], "R7:", comps["R7"]["x"], comps["R7"]["y"])
# 计算旋转后引脚（旋转 180: 偏移取反）
def pin_at(des, num, comps):
    c = comps[des]
    for p in c["pins"]:
        if str(p["pinNumber"]) == str(num): return (p["x"], p["y"])
    return None
j21 = pin_at("J2", "1", comps); j22 = pin_at("J2", "2", comps)
r71 = pin_at("R7", "1", comps); r72 = pin_at("R7", "2", comps)
print("  J2.1:", j21, "J2.2:", j22, "R7.1:", r71, "R7.2:", r72)
rs2 = pin_at("Rs1", "2", comps)
pts = [[rs2[0], rs2[1]], [270, rs2[1]], [270, j21[1]], [j21[0]+10, j21[1]], [j21[0], j21[1]]]
r = sh("sch", "wire", "--points", json.dumps([[round(a,1),round(b,1)] for a,b in pts], separators=(",",":")), "--net", "VLOAD")
print("  VLOAD wire:", r.get("ok"))
if not r.get("ok"): fails.append(["VLOAD wire"])
r = sh("sch", "connect", "--pin", "J2:2", "--kind", "gnd", "--net", "GND")
print("  J2.2 gnd:", r.get("ok"))
if not r.get("ok"): fails.append(["J2.2 gnd"])
# R7.1 GATE 向西桩+旗、R7.2 gnd
ok, far = add_stub("R7:1", comps, -25, 0, "GATE")
print("  R7.1 stub:", ok)
if ok: add_flag("GATE", far[0], far[1])
else: fails.append(["R7.1 stub"])
r = sh("sch", "connect", "--pin", "R7:2", "--kind", "gnd", "--net", "GND")
print("  R7.2 gnd:", r.get("ok"))
if not r.get("ok"): fails.append(["R7.2 gnd"])
# CC_LED 桩（J2 已挪走）
ok, far = add_stub("U1:19", comps, -50, 0, "CC_LED")
print("  U1:19 stub:", ok)
if ok: add_flag("CC_LED", far[0], far[1])
else: fails.append(["U1:19 stub"])

# ---------- 5. 全部信号旗 ----------
print("== 5. all signal flags")
comps, wires, allc = measure(wires=True)
have_flags = [(round(c["x"]), round(c["y"]), c["name"]) for c in allc if c.get("componentType") == "netflag"]
def far_end(P, comps, wires):
    des, num = P.split(":")
    p = next(pp for pp in comps[des]["pins"] if str(pp["pinNumber"]) == str(num))
    for w in wires:
        pts = w.get("rawLine", [])
        for i in range(0, len(pts), 2):
            if abs(pts[i]-p["x"]) < 1.5 and abs(pts[i+1]-p["y"]) < 1.5:
                j = 0 if i != 0 else len(pts)-2
                far = (pts[j], pts[j+1])
                if abs(far[0]-p["x"])>1.5 or abs(far[1]-p["y"])>1.5:
                    return far
    return None

SIGNALS = ["PWM","GATE","NRST","BOOT0","SWDIO","SWCLK","UART_TX","UART_RX",
           "VSENSE","ISENSE","CV_LED","CC_LED","PWR_LED","OSC_IN","OSC_OUT","VMID","PWM_B"]
PINS = {
 "PWM": ["R8:1","U1:29"], "GATE": ["R6:2","Q1:1"],
 "NRST": ["U1:7","R9:2","SW1:1"], "BOOT0": ["U1:44","R10:1"],
 "SWDIO": ["U1:34","J3:2"], "SWCLK": ["U1:37","J3:3"],
 "UART_TX": ["U1:30","J4:1"], "UART_RX": ["U1:31","J4:2"],
 "VSENSE": ["R11:2","C10:1","U1:14"], "ISENSE": ["U3:1","U1:15"],
 "CV_LED": ["U1:18"], "CC_LED": ["U1:19"], "PWR_LED": ["U1:2"],
 "OSC_IN": ["C12:1"], "OSC_OUT": ["C13:1"], "VMID": ["R11:1"], "PWM_B": ["Q3:1"],
}
for net, plist in PINS.items():
    for P in plist:
        des, num = P.split(":")
        p = next(pp for pp in comps[des]["pins"] if str(pp["pinNumber"]) == str(num))
        # 已有旗在此引脚桩远端？
        far = far_end(P, comps, wires)
        if far is None:
            print(f"  no stub for {P} ({net}) — skip")
            fails.append(["nostub", P, net]); continue
        if any(fx == round(far[0]) and fy == round(far[1]) and nm == net for fx, fy, nm in have_flags):
            print(f"  {P} {net}: flag exists"); continue
        if any(abs(fx-far[0])<2 and abs(fy-far[1])<2 for fx, fy, nm in have_flags):
            print(f"  {P} {net}: other flag at same point — skip"); continue
        add_flag(net, far[0], far[1])

with open("fix6_errors.json", "w", encoding="utf-8") as f:
    json.dump(fails, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
