# -*- coding: utf-8 -*-
"""恢复脚本：清理半成品 → 修姿态 → 重做连线与连接（全程完整错误捕获 + 重试）"""
import json, subprocess, os, time

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def sh(*args, timeout=120):
    p = subprocess.run([EXE, *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": ((p.stdout or "") + (p.stderr or ""))[:500]}

def measure():
    r = sh("sch", "list", "--include-pins", "--include-bbox", "--stay")
    return {c["designator"]: c for c in r.get("result", {}).get("components", []) if c.get("designator")}

def pinxy(P, comps):
    des, num = P.split(":")
    p = get_pin(comps[des], num)
    return (p["x"], p["y"])

def get_pin(c, num):
    return next(p for p in c["pins"] if str(p["pinNumber"]) == str(num))

# ---------- 1. 清理 ----------
print("== 1. cleanup")
r = sh("sch", "list", "--include-wires", "--stay")
inv = r.get("result", {})
wire_ids = sorted({w["primitiveId"] for w in inv.get("wires", []) if w.get("primitiveId")})
r2 = sh("sch", "list", "--stay")
for c in r2.get("result", {}).get("components", []):
    if c.get("componentType") == "netflag":
        wire_ids.append(c["primitiveId"])
print(f"  deleting {len(wire_ids)} primitives")
if wire_ids:
    r = sh("sch", "prim-delete", "--ids", ",".join(wire_ids))
    print("  delete ok:", r.get("ok"), str(r.get("error", ""))[:120])

# ---------- 2. 姿态修正（带对齐校验） ----------
print("== 2. orient")
comps = measure()

def set_rot(des, rot):
    global comps
    r = sh("sch", "modify", "--id", comps[des]["primitiveId"], "--rotation", str(rot))
    if not r.get("ok"):
        print(f"  {des} rot {rot} ERR {str(r)[:120]}")
    comps = measure()

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
for des, x, y in [("R5", 770, 370), ("R3", 770, 300), ("R4", 770, 210)]:
    c = comps[des]
    if abs(c["x"]-x) > 1 or abs(c["y"]-y) > 1:
        sh("sch", "modify", "--id", c["primitiveId"], "--x", str(x), "--y", str(y))
        comps = measure()
        print(f"  {des} moved")

def led_pin(des, anode=True):
    for p in comps[des]["pins"]:
        n = str(p.get("pinName", "")).upper()
        if (n.startswith("A") or n == "+") and anode: return str(p["pinNumber"])
        if (n.startswith("C") or n == "-") and not anode: return str(p["pinNumber"])
    raise SystemExit(f"led pin {des}")

AN = {d: led_pin(d, True) for d in ("LED1","LED2","LED3")}
CA = {d: led_pin(d, False) for d in ("LED1","LED2","LED3")}

# ---------- 3. 连线 ----------
print("== 3. wires")
WIRES = [
    ("VIN_5V", ["J1:1", "C5:1"], []),                          # 拆成两段避免穿过引脚
    ("VIN_5V", ["C5:1", "C1:1"], []),
    ("VIN_5V", [None, "L1:1"], ["50,700", "110,700", "110,770"]),
    ("SW", ["Q1:3", "D1:2"], ["190,745", "210,745", "280,745", "280,770"]),  # 顶点含分支点
    ("SW", ["L1:2", None], ["210,745"]),                       # 端点落在上条折线顶点
    ("VOUT", ["D1:1", "C2:1"], []),
    ("VOUT", ["D1:1", "C6:1"], []),
    ("VOUT", ["C2:1", "Rs1:1"], []),                           # 改为 C2.1 直下
    ("VLOAD", ["Rs1:2", "J2:1"], ["390,585", "335,585", "335,555"]),
    ("PWM_B", ["R8:2", "Q2:1"], []),
    ("PWM_B", ["Q2:1", "Q3:1"], []),
    ("MID", ["Q2:2", "R6:1"], ["190,340"]),                    # 拐点即分支点
    ("MID", ["Q3:3", None], ["190,340"]),                      # 端点落在拐点
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
        time.sleep(2)
        r = sh("sch", "wire", "--points", arg, "--net", net)
        ok = r.get("ok", False)
    print(f"  W{i+1} {net}: {'OK' if ok else 'FAIL ' + str(r.get('error', r))[:160]}")
    if not ok: wire_fail.append((i, net, json.dumps(r.get("error", r), ensure_ascii=False)[:300]))

# ---------- 4. 连接 ----------
print("== 4. connects")
CONN = []
def add(pins, kind, net):
    for p in pins: CONN.append((p, kind, net))
add(["J1:2","C5:2","C1:2","C6:2","C2:2","J2:2","R7:2","Q1:2","Q3:2","R2:2",
     "R5:2","R3:2","R4:2","R10:2","C10:2","C11:2","C12:2","C13:2","C3:2","C4:2",
     "C7:2","C8:2","C9:2","U3:2","U2:2","J3:4","J4:4","SW1:2",
     "U1:8","U1:23","U1:35","U1:47"], "gnd", "GND")
add(["U2:5","C4:1","C7:1","C8:1","C9:1","U3:5","R9:1","J3:1","J4:3",
     "U1:1","U1:9","U1:24","U1:36","U1:48"], "power", "3V3")
add(["U2:1","U2:3","C3:1","Q2:3"], "power", "VIN_5V")
add(["R1:1","U3:3"], "power", "VOUT")
add(["U3:4","Rs1:2"], "power", "VLOAD")
add(["R8:1","U1:29"], "net_label", "PWM")
add(["R6:2","R7:1","Q1:1"], "net_label", "GATE")
add(["U1:7","R9:2","SW1:1"], "net_label", "NRST")
add(["U1:44","R10:1"], "net_label", "BOOT0")
add(["U1:34","J3:2"], "net_label", "SWDIO")
add(["U1:37","J3:3"], "net_label", "SWCLK")
add(["U1:30","J4:1"], "net_label", "UART_TX")
add(["U1:31","J4:2"], "net_label", "UART_RX")
add(["R11:2","C10:1","U1:14"], "net_label", "VSENSE")
add(["U3:1","C11:1","U1:15"], "net_label", "ISENSE")
add(["U1:18", f"LED2:{AN['LED2']}"], "net_label", "CV_LED")
add(["U1:19", f"LED3:{AN['LED3']}"], "net_label", "CC_LED")
add(["U1:2", f"LED1:{AN['LED1']}"], "net_label", "PWR_LED")

conn_fail = []
for P, kind, net in CONN:
    r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net)
    ok = r.get("ok", False)
    if not ok:
        time.sleep(2)
        r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net)
        ok = r.get("ok", False)
    if not ok:
        conn_fail.append({"pin": P, "net": net, "err": json.dumps(r.get("error", r), ensure_ascii=False)[:300]})
        print(f"  ERR {P}->{net}: {conn_fail[-1]['err'][:140]}")
print(f"  connects: {len(CONN)-len(conn_fail)}/{len(CONN)} ok")

# ---------- 5. NC + 汇总 ----------
for des, pins in [("U1", "3,4,10,11,12,13,16,17,20,21,22,25,26,27,28,32,33,38,39,40,41,42,43,45,46"),
                  ("SW1", "3,4"), ("U2", "4")]:
    sh("sch", "no-connect", "--designator", des, "--pin", pins)
print("== NC done")
with open("recover_errors.json", "w", encoding="utf-8") as f:
    json.dump({"wire": wire_fail, "conn": conn_fail}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT: wire_fail={len(wire_fail)} conn_fail={len(conn_fail)}")
