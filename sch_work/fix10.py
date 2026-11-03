# -*- coding: utf-8 -*-
"""fix10: 删除被合并污染的导线与旗子，全部改用 connect(自动布局) 重建西/东走廊"""
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

def delete_ids(ids, tag=""):
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 6):
        r = sh("sch", "prim-delete", "--ids", ",".join(ids[i:i+6]))
        if not r.get("ok"): fails.append(["del", tag, ids[i:i+6]]); print("  del FAIL", ids[i:i+6])
    print(f"  deleted {len(ids)} ({tag})")
    time.sleep(1.0)

def conn(P, kind, net, direction=None, offset=None):
    args = ["sch", "connect", "--pin", P, "--kind", kind, "--net", net]
    if direction: args += ["--direction", direction]
    if offset: args += ["--offset", str(offset)]
    r = sh(*args)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2)
        r = sh(*args)
        ok = r.get("ok")
    print(f"  conn {P}->{net} {'('+direction+' '+str(offset)+')' if direction else ''}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:110]}")
    if not ok: fails.append(["conn", P, net])
    return ok

# ---------- 1. 删除 ----------
print("== 1. delete contaminated")
r = sh("sch", "list", "--include-wires", "--stay")
wires = r.get("result", {}).get("wires", [])
r2 = sh("sch", "list", "--stay")
allc = r2.get("result", {}).get("components", [])
del_w, del_f = set(), set()
for w in wires:
    pts = w.get("rawLine", [])
    pid = w["primitiveId"]
    # 巨线与走廊相交的导线：任一端点在走廊盒或东盒
    hit = False
    for i in range(0, len(pts), 2):
        x, y = pts[i], pts[i+1]
        if (300 <= x <= 385 and 480 <= y <= 775) or (540 <= x <= 600 and 545 <= y <= 760) \
           or (300 <= x <= 660 and 480 <= y <= 500) or (600 <= x <= 665 and 690 <= y <= 800):
            hit = True; break
    if hit: del_w.add(pid)
for c in allc:
    if c.get("componentType") == "netflag":
        x, y, n = round(c["x"]), round(c["y"]), c.get("name")
        if n == "__ROTPROBE__": continue
        if (300 <= x <= 385 and 480 <= y <= 775) or (540 <= x <= 600 and 545 <= y <= 760) \
           or (300 <= x <= 660 and 480 <= y <= 500) or (600 <= x <= 665 and 690 <= y <= 800) \
           or (x, y) in [(580,850),(620,850)]:
            del_f.add(c["primitiveId"])
delete_ids(sorted(del_w), "wires")
delete_ids(sorted(del_f), "flags")

# ---------- 2. connect 重建 ----------
print("== 2. rebuild via connect")
WEST = [("U1:24","3V3",25),("U1:23","GND",45),("U1:19","CC_LED",25),("U1:18","CV_LED",45),
        ("U1:15","ISENSE",25),("U1:14","VSENSE",45),("U1:9","3V3",25),("U1:8","GND",45),
        ("U1:7","NRST",25),("U1:2","PWR_LED",45),("U1:1","3V3",25)]
for P, net, off in WEST:
    conn(P, "power" if net != "GND" else "gnd", net, "left", off)
EAST = [("U1:36","3V3",25),("U1:35","GND",45),("U1:34","SWDIO",25),("U1:37","SWCLK",45),
        ("U1:29","PWM",25),("U1:30","UART_TX",45),("U1:31","UART_RX",25),
        ("U1:44","BOOT0",25),("U1:47","GND",45),("U1:48","3V3",25)]
for P, net, off in EAST:
    conn(P, "power" if net != "GND" else "gnd", net, "right", off)
conn("C3:1", "power", "VIN_5V", "left", 25)
conn("C3:2", "gnd", "GND", "right", 25)
conn("C12:1", "power", "OSC_IN", "down", 25)
conn("C12:2", "gnd", "GND", "up", 25)
conn("Y1:1", "power", "OSC_IN", "left", 25)
conn("Y1:2", "power", "OSC_OUT", "right", 25)
conn("R6:1", "power", "MID", "left", 25)   # R6.1 悬空补
conn("Q3:1", "power", "PWM_B", "left", 25) # Q3.B 补

# ---------- 3. 保存 + 检查 ----------
print("== 3. save+check")
r = sh("sch", "save", timeout=240)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:100])
if not r.get("ok"): fails.append("save")
r = sh("sch", "check", timeout=300)
res = r.get("result", {})
print("  check:", json.dumps(res if isinstance(res, str) else res.get("summary", res), ensure_ascii=False)[:300])
with open("fix10_out.json", "w", encoding="utf-8") as f:
    json.dump({"fails": fails}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
