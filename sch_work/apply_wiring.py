# -*- coding: utf-8 -*-
"""原理图连线主脚本：
1. 姿态修正（旋转对齐引脚）
2. 实体连线（sch wire，引脚参照点 + 绝对拐点）
3. 网络 flag（sch connect，自动方向）
4. NC 标记
5. gate 检查
所有坐标基于 pins_all.json 实测值，脚本先旋转后重测再生成。
"""
import json, subprocess, os, sys, time

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def sh(*args, timeout=90):
    p = subprocess.run([EXE, *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": ((p.stdout or "") + (p.stderr or ""))[:400]}

def measure():
    r = sh("sch", "list", "--include-pins", "--include-bbox", "--stay", timeout=120)
    comps = [c for c in r.get("result", {}).get("components", []) if c.get("designator")]
    return {c["designator"]: c for c in comps}

def pin(P, comps, name=None):
    """P = 'U1:5' -> (x, y)；name 可选校验引脚名"""
    des, num = P.split(":")
    c = comps[des]
    for p in c["pins"]:
        if str(p["pinNumber"]) == str(num):
            if name and name.lower() not in str(p.get("pinName", "")).lower():
                raise SystemExit(f"PIN NAME MISMATCH {P}: expect~{name}, got {p.get('pinName')}")
            return (p["x"], p["y"])
    raise SystemExit(f"PIN NOT FOUND {P}")

# ---------- 1. 姿态修正（幂等，--rotation 为绝对角度） ----------
print("== 1. adjustments")
comps = measure()

def get_pin(c, num):
    return next(p for p in c["pins"] if str(p["pinNumber"]) == str(num))

def set_rot(des, rot):
    r = sh("sch", "modify", "--id", comps[des]["primitiveId"], "--rotation", str(rot))
    print(f"  {des} -> rot {rot}: ok={r.get('ok')}")
    return measure()  # 重测

def orient(des, num, axis, want_greater):
    """把 des 的 num 号引脚转到指定方位（尝试 4 个绝对角度，从当前角度开始）"""
    global comps
    start = int(comps[des].get("rotation") or 0) % 360
    for rot in (start, (start + 90) % 360, (start + 180) % 360, (start + 270) % 360):
        comps = set_rot(des, rot)
        c = comps[des]
        p = get_pin(c, num)
        other = [q for q in c["pins"] if q is not p][0]
        d = (p["x"] - other["x"]) if axis == "x" else (p["y"] - other["y"])
        if (d > 0) == want_greater:
            return
    raise SystemExit(f"orient failed {des} {num} {axis} {want_greater}")

orient("D1", "2", "x", False)    # A 在西
orient("C6", "1", "x", True)     # +(1) 在东
orient("R2", "1", "x", True)     # 1 在东 (820,700)
orient("R11", "1", "x", True)    # 1 在东 (820,620)
orient("C11", "1", "y", True)    # 立式 1 在上
orient("C12", "1", "y", False)   # 立式 1 在下（接 Y1.1）
orient("C13", "1", "y", False)   # 立式 1 在下（接 Y1.2）
orient("LED1", "1", "x", False)  # A 在西
orient("LED2", "2", "x", False)  # +(2)=A 在西
orient("LED3", "1", "x", False)  # A 在西
for des, x, y in [("R5", 770, 370), ("R3", 770, 300), ("R4", 770, 220)]:
    c = comps[des]
    if abs(c["x"] - x) > 1 or abs(c["y"] - y) > 1:
        r = sh("sch", "modify", "--id", c["primitiveId"], "--x", str(x), "--y", str(y))
        print(f"  {des} move: ok={r.get('ok')}")
        comps = measure()

# LED 引脚号解析（A/+=阳极，C/-=阴极）
def led_anode(des):
    c = comps[des]
    for p in c["pins"]:
        n = str(p.get("pinName", "")).upper()
        if n.startswith("A") or n == "+":
            return str(p["pinNumber"])
    raise SystemExit(f"no anode on {des}")

def led_cathode(des):
    c = comps[des]
    for p in c["pins"]:
        n = str(p.get("pinName", "")).upper()
        if n.startswith("C") or n == "-":
            return str(p["pinNumber"])
    raise SystemExit(f"no cathode on {des}")

AN = {des: led_anode(des) for des in ("LED1", "LED2", "LED3")}
CA = {des: led_cathode(des) for des in ("LED1", "LED2", "LED3")}
print("  LED anode/cathode:", AN, CA)

with open("pins_final.json", "w", encoding="utf-8") as f:
    json.dump(list(comps.values()), f, ensure_ascii=False, indent=1)

# ---------- 2. 实体连线 ----------
print("== 2. wires")
# 每条: (net名, [起引脚, 终引脚], [中间绝对拐点...]) 端点用引脚实测坐标
WIRES = [
    ("VIN_5V", ["J1:1", "C1:1"], []),                                   # 竖干，途中穿 C5.1
    ("VIN_5V", [None, "L1:1"], ["50,700", "110,700", "110,770"]),       # 支路到 L1
    ("SW",     ["Q1:3", "D1:2"], ["190,745", "280,745"]),               # Q1.D -> D1.A
    ("SW",     ["L1:2", None],   ["210,745"]),                          # L1.2 T 接
    ("VOUT",   ["D1:1", "C2:1"], []),
    ("VOUT",   ["D1:1", "C6:1"], []),
    ("VOUT",   [None, "Rs1:1"], ["320,720", "350,720", "350,660"]),     # T 接 -> Rs1.1
    ("VLOAD",  ["Rs1:2", "J2:1"], ["390,585", "335,585", "335,555"]),
    ("PWM_B",  ["R8:2", "Q2:1"], []),
    ("PWM_B",  ["Q2:1", "Q3:1"], []),
    ("MID",    ["Q2:2", "Q3:3"], []),
    ("MID",    [None, "R6:1"], ["190,340", "250,340"]),                 # T 接 -> R6.1
    ("OSC_IN", ["U1:5", "Y1:1"], ["365,705", "365,770"]),
    ("OSC_OUT",["U1:6", "Y1:2"], ["368,695", "368,490", "620,490"]),
    ("OSC_OUT",["Y1:2", "C13:1"], []),
    ("OSC_IN", ["Y1:1", "C12:1"], []),
    ("VMID",   ["R1:2", "R2:1"], []),                                   # 分压中点（同一节点）
    ("VMID",   ["R2:1", "R11:1"], []),
    ("LED1_C", [f"LED1:{CA['LED1']}", "R5:1"], []),
    ("LED2_C", [f"LED2:{CA['LED2']}", "R3:1"], []),
    ("LED3_C", [f"LED3:{CA['LED3']}", "R4:1"], []),
]

wire_fail = []
for i, (net, pins, mids) in enumerate(WIRES):
    seq = []
    if pins and pins[0]:
        seq.append(pin(pins[0], comps))
    for m in mids:
        seq.append(tuple(float(v) for v in m.split(",")))
    if pins and pins[1]:
        seq.append(pin(pins[1], comps))
    arg = json.dumps([[round(a, 1), round(b, 1)] for a, b in seq], separators=(",", ":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    ok = r.get("ok", False)
    print(f"  W{i+1} {net}: ok={ok}" + ("" if ok else f" {str(r)[:150]}"))
    if not ok: wire_fail.append((i, net, r))

# ---------- 3. 网络 flag ----------
print("== 3. connects")
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
        conn_fail.append((P, net, str(r)[:200]))
        print(f"  ERR {P} -> {net}: {str(r)[:150]}")
print(f"  connects done, failed {len(conn_fail)}/{len(CONN)}")

# ---------- 4. NC ----------
print("== 4. no-connect")
for des, pins in [("U1", "3,4,10,11,12,13,16,17,20,21,22,25,26,27,28,32,33,38,39,40,41,42,43,45,46"),
                  ("SW1", "3,4"), ("U2", "4")]:
    r = sh("sch", "no-connect", "--designator", des, "--pin", pins)
    print(f"  {des}: ok={r.get('ok')}")

# ---------- 5. 检查 ----------
print("== 5. gate")
for step in (["sch", "layout-lint"], ["sch", "check"], ["sch", "bridge-check"], ["sch", "drc"]):
    r = sh(*step, timeout=180)
    res = r.get("result", {})
    print(f"  {step[1]}: ok={r.get('ok')} " + json.dumps({k: res[k] for k in list(res)[:4]}, ensure_ascii=False)[:220])

print("\nwire_fail:", len(wire_fail), "| conn_fail:", len(conn_fail))
with open("wiring_errors.json", "w", encoding="utf-8") as f:
    json.dump({"wire": [w[1] for w in wire_fail], "conn": conn_fail}, f, ensure_ascii=False, indent=1)
