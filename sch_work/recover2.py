# -*- coding: utf-8 -*-
"""恢复 v2：不动已有成功连接；修姿态 → 补缺失连线 → gnd/power 用 connect、
信号旗用 wire桩+netflag → gate 检查"""
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

# ---------- 1. 姿态 ----------
print("== 1. orient")
comps, wires = measure(wires=True)

def set_rot(des, rot):
    global comps
    sh("sch", "modify", "--id", comps[des]["primitiveId"], "--rotation", str(rot))
    time.sleep(1.0)
    comps, _ = measure()
    time.sleep(0.5)
    comps, _ = measure()

def orient(des, num, axis, want_greater):
    start = int(comps[des].get("rotation") or 0) % 360
    for rot in (start, (start+90) % 360, (start+180) % 360, (start+270) % 360):
        if rot != int(comps[des].get("rotation") or 0) % 360:
            set_rot(des, rot)
        c = comps[des]
        p = get_pin(c, num)
        other = [q for q in c["pins"] if q is not p][0]
        dx, dy = p["x"]-other["x"], p["y"]-other["y"]
        d = dx if axis == "x" else dy
        aligned = abs(dx) > abs(dy) if axis == "x" else abs(dy) > abs(dx)
        if aligned and (d > 0) == want_greater:
            print(f"  {des} rot={int(comps[des].get('rotation') or 0)} OK")
            return
    raise SystemExit(f"orient failed {des}")

orient("D1", "2", "x", False); orient("C6", "1", "x", True)
orient("R2", "1", "x", True);  orient("R11", "1", "x", True)
orient("C11", "1", "y", True)
orient("C12", "1", "y", False); orient("C13", "1", "y", False)
orient("LED1", "1", "x", False); orient("LED2", "2", "x", False); orient("LED3", "1", "x", False)

# R4 移到与 LED3 阴极同 y
comps, _ = measure()
led3c = get_pin(comps["LED3"], next(p["pinNumber"] for p in comps["LED3"]["pins"] if str(p.get("pinName","")).upper().startswith("C")))
c = comps["R4"]
if abs(c["y"] - led3c["y"]) > 1:
    sh("sch", "modify", "--id", c["primitiveId"], "--x", "770", "--y", str(led3c["y"]))
    comps, _ = measure()
    print(f"  R4 -> (770,{led3c['y']})")

def led_pin(des, anode=True):
    for p in comps[des]["pins"]:
        n = str(p.get("pinName", "")).upper()
        if (n.startswith("A") or n == "+") and anode: return str(p["pinNumber"])
        if (n.startswith("C") or n == "-") and not anode: return str(p["pinNumber"])
    raise SystemExit(f"led pin {des}")
AN = {d: led_pin(d, True) for d in ("LED1","LED2","LED3")}
CA = {d: led_pin(d, False) for d in ("LED1","LED2","LED3")}

# 删除 LED2 旧桩（姿态变了会悬空）
comps, wires = measure(wires=True)
led2a = pinxy(f"LED2:{AN['LED2']}", comps)
for w in wires:
    pts = w.get("rawLine", [])
    if w.get("net") == "CV_LED" and len(pts) >= 4:
        far = (pts[0], pts[1]) if abs(pts[0]-led2a[0])>1 or abs(pts[1]-led2a[1])>1 else (pts[-2], pts[-1])
        if abs(far[0]-led2a[0])>1 or abs(far[1]-led2a[1])>1:  # 远端不贴新阳极 → 旧桩
            r = sh("sch", "prim-delete", "--ids", w["primitiveId"])
            print("  del old LED2 stub:", r.get("ok"))

# ---------- 2. 补缺失连线 ----------
print("== 2. wires")
comps, wires = measure(wires=True)
have = set()
for w in wires:
    pts = w.get("rawLine", [])
    key = tuple(sorted({(round(pts[i]/5)*5, round(pts[i+1]/5)*5) for i in range(0, len(pts), 2)}))
    have.add((w.get("net",""), key))

WIRES = [
    ("VIN_5V", ["J1:1", "C5:1"], []),
    ("VIN_5V", ["C5:1", "C1:1"], []),
    ("VIN_5V", [None, "L1:1"], ["50,700", "110,700", "110,770"]),
    ("SW", ["Q1:3", "D1:2"], ["190,745", "210,745", "280,745", "280,770"]),
    ("SW", ["L1:2", None], ["210,745"]),
    ("VOUT", ["D1:1", "C6:1"], []),
    ("VOUT", ["C2:1", "Rs1:1"], []),
    ("VLOAD", ["Rs1:2", "J2:1"], ["390,585", "335,585", "335,555"]),
    ("PWM_B", ["Q2:1", "Q3:1"], []),
    ("MID", ["Q3:3", None], ["190,340"]),
    ("OSC_IN", ["U1:5", "Y1:1"], ["365,705", "365,770"]),
    ("OSC_OUT", ["U1:6", "Y1:2"], ["368,695", "368,490", "620,490"]),
    ("OSC_OUT", ["Y1:2", "C13:1"], []),
    ("OSC_IN", ["Y1:1", "C12:1"], []),
    ("VMID", ["R1:2", "R2:1"], []),
    ("VMID", ["R2:1", "R11:1"], []),
    ("LED1_C", [f"LED1:{CA['LED1']}", "R5:1"], []),
    ("LED2_C", [f"LED2:{CA['LED2']}", "R3:1"], []),
    ("LED3_C", [f"LED3:{CA['LED3']}", "R4:1"], []),
]
wire_fail = []
for i, (net, pins, mids) in enumerate(WIRES):
    seq = []
    if pins and pins[0]: seq.append(pinxy(pins[0], comps))
    for m in mids: seq.append(tuple(float(v) for v in m.split(",")))
    if pins and pins[1]: seq.append(pinxy(pins[1], comps))
    arg = json.dumps([[round(a,1), round(b,1)] for a,b in seq], separators=(",",":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    ok = r.get("ok", False)
    if not ok:
        time.sleep(1.5)
        r = sh("sch", "wire", "--points", arg, "--net", net)
        ok = r.get("ok", False)
    print(f"  W{i+1} {net}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:170]}")
    if not ok: wire_fail.append(net)

# ---------- 3. gnd/power 连接（connect 是可靠的，此前失败是熔断） ----------
print("== 3. gnd/power connects")
comps, wires = measure(wires=True)
# 已有桩的引脚集合：任一 wire 端点落在引脚上
stub_pins = set()
for w in wires:
    pts = w.get("rawLine", [])
    for des, c in comps.items():
        for p in c["pins"]:
            for i in range(0, len(pts), 2):
                if abs(pts[i]-p["x"]) < 1 and abs(pts[i+1]-p["y"]) < 1:
                    stub_pins.add(f"{des}:{p['pinNumber']}")

GND = ["J1:2","C5:2","C1:2","C6:2","C2:2","J2:2","R7:2","Q1:2","Q3:2","R2:2",
       "R5:2","R3:2","R4:2","R10:2","C10:2","C11:2","C12:2","C13:2","C3:2","C4:2",
       "C7:2","C8:2","C9:2","U3:2","U2:2","J3:4","J4:4","SW1:2",
       "U1:8","U1:23","U1:35","U1:47"]
V33 = ["U2:5","C4:1","C7:1","C8:1","C9:1","U3:5","R9:1","J3:1","J4:3",
       "U1:1","U1:9","U1:24","U1:36","U1:48"]
VIN = ["C3:1","Q2:3","U2:1","U2:3"]
VOUTP = ["R1:1","U3:3"]
VLOADP = ["U3:4","Rs1:2"]
conn_fail = []
todo = [(p, "gnd", "GND") for p in GND] + [(p, "power", "3V3") for p in V33] + \
       [(p, "power", "VIN_5V") for p in VIN] + [(p, "power", "VOUT") for p in VOUTP] + \
       [(p, "power", "VLOAD") for p in VLOADP]
for P, kind, net in todo:
    if P in stub_pins:
        continue  # 已有桩线（多数已带旗）
    r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net)
    ok = r.get("ok", False)
    if not ok:
        time.sleep(2)
        r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net)
        ok = r.get("ok", False)
    if not ok:
        conn_fail.append({"pin": P, "net": net, "err": json.dumps(r.get("error", r), ensure_ascii=False)[:260]})
        print(f"  ERR {P}->{net}: {conn_fail[-1]['err'][:130]}")
    else:
        print(f"  ok {P}->{net}")
print(f"  gnd/power done, fail {len(conn_fail)}")

# ---------- 4. 信号旗：复用已有桩线 + netflag ----------
print("== 4. signal flags")
comps, wires = measure(wires=True)
def stub_far_end(P, comps, wires):
    des, num = P.split(":")
    p = get_pin(comps[des], num)
    for w in wires:
        pts = w.get("rawLine", [])
        for i in range(0, len(pts), 2):
            if abs(pts[i]-p["x"]) < 1 and abs(pts[i+1]-p["y"]) < 1:
                j = 0 if i == 0 else len(pts)-2
                far = (pts[j], pts[j+1])
                if abs(far[0]-p["x"])>1 or abs(far[1]-p["y"])>1:
                    return far, w["primitiveId"]
    return None, None

SIGNALS = [
    ("R8:1","PWM"), ("U1:29","PWM"),
    ("R6:2","GATE"), ("R7:1","GATE"), ("Q1:1","GATE"),
    ("U1:7","NRST"), ("R9:2","NRST"), ("SW1:1","NRST"),
    ("U1:44","BOOT0"), ("R10:1","BOOT0"),
    ("U1:34","SWDIO"), ("J3:2","SWDIO"),
    ("U1:37","SWCLK"), ("J3:3","SWCLK"),
    ("U1:30","UART_TX"), ("J4:1","UART_TX"),
    ("U1:31","UART_RX"), ("J4:2","UART_RX"),
    ("R11:2","VSENSE"), ("C10:1","VSENSE"), ("U1:14","VSENSE"),
    ("U3:1","ISENSE"), ("C11:1","ISENSE"), ("U1:15","ISENSE"),
    (f"LED2:{AN['LED2']}","CV_LED"), ("U1:18","CV_LED"),
    (f"LED3:{AN['LED3']}","CC_LED"), ("U1:19","CC_LED"),
    (f"LED1:{AN['LED1']}","PWR_LED"), ("U1:2","PWR_LED"),
]
flag_fail = []
for P, net in SIGNALS:
    des, num = P.split(":")
    p = get_pin(comps[des], num)
    far, wid = stub_far_end(P, comps, wires)
    if far is None:
        # 补桩：引脚朝外方向 25
        cx = (comps[des]["pins"] and p["x"]) or p["x"]
        # 朝向：用引脚相对器件中心的方向
        bb = None
        d = p
        # 简化：向西（U1 左侧）/向东（U1 右侧）……通用：离中心方向
        ox, oy = comps[des]["x"], comps[des]["y"]
        dx, dy = p["x"]-ox, p["y"]-oy
        if abs(dx) >= abs(dy): ex, ey = p["x"] + (25 if dx > 0 else -25), p["y"]
        else: ex, ey = p["x"], p["y"] + (25 if dy > 0 else -25)
        r = sh("sch", "wire", "--points", json.dumps([[round(p["x"],1),round(p["y"],1)],[round(ex,1),round(ey,1)]], separators=(",",":")), "--net", net)
        if not r.get("ok"):
            flag_fail.append({"pin": P, "net": net, "err": "stub " + json.dumps(r.get("error",{}), ensure_ascii=False)[:150]})
            print(f"  ERR stub {P}: {flag_fail[-1]['err'][:120]}")
            continue
        far = (ex, ey)
    # 该远端是否已有旗
    has_flag = any(abs(f["x"]-far[0])<1 and abs(f["y"]-far[1])<1 for f in
                   [c for c in comps.values() if c.get("componentType")=="netflag"] ) if False else None
    r = sh("sch", "netflag", "--kind", "net_label", "--net", net, "--x", str(round(far[0],1)), "--y", str(round(far[1],1)))
    ok = r.get("ok", False)
    if not ok:
        time.sleep(1.5)
        r = sh("sch", "netflag", "--kind", "net_label", "--net", net, "--x", str(round(far[0],1)), "--y", str(round(far[1],1)))
        ok = r.get("ok", False)
    if not ok:
        flag_fail.append({"pin": P, "net": net, "err": json.dumps(r.get("error", r), ensure_ascii=False)[:200]})
        print(f"  ERR flag {P}->{net} @{far}: {flag_fail[-1]['err'][:130]}")
    else:
        print(f"  flag {net} @{int(far[0])},{int(far[1])}")
print(f"  flags done, fail {len(flag_fail)}")

with open("recover2_errors.json", "w", encoding="utf-8") as f:
    json.dump({"wire": wire_fail, "conn": conn_fail, "flag": flag_fail}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT wire={len(wire_fail)} conn={len(conn_fail)} flag={len(flag_fail)}")
