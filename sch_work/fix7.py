# -*- coding: utf-8 -*-
"""fix7: 最后5处修复 + 旗子清点 + 保存"""
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

fails = []

def wire(pts, net):
    arg = json.dumps([[round(a,1), round(b,1)] for a,b in pts], separators=(",",":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2)
        r = sh("sch", "wire", "--points", arg, "--net", net)
        ok = r.get("ok")
    print(f"  wire {net}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:120]}")
    return ok

def flag(net, x, y, kind="power"):
    r = sh("sch", "netflag", "--kind", kind, "--net", net, "--x", str(round(x,1)), "--y", str(round(y,1)))
    time.sleep(0.5)
    return r.get("ok")

def conn(P, kind, net):
    r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net)
    time.sleep(0.5)
    return r.get("ok")

# 1. J2:2 gnd 手工桩（东向 25）
if wire([(220,485),(245,485)], "GND"):
    ok = flag("GND", 245, 485, "gnd")
    print("  J2.2 gnd flag:", ok)
    if not ok: fails.append("J2.2 flag")

# 2. R7:1 GATE 重试 connect
ok = conn("R7:1", "power", "GATE")
print("  R7:1 GATE connect:", ok)
if not ok:
    if wire([(220,560),(195,560)], "GATE"):
        ok = flag("GATE", 195, 560)
        print("  R7.1 manual:", ok)
if not ok: fails.append("R7:1 GATE")

# 3. R7:2 gnd 重试
ok = conn("R7:2", "gnd", "GND")
print("  R7:2 gnd connect:", ok)
if not ok:
    if wire([(260,560),(285,560)], "GND"):
        ok = flag("GND", 285, 560, "gnd")
        print("  R7.2 manual:", ok)
if not ok: fails.append("R7:2 gnd")

# 4. Q3:1 PWM_B 桩+旗
if wire([(170,290),(145,290)], "PWM_B"):
    ok = flag("PWM_B", 145, 290)
    print("  Q3.1 PWM_B:", ok)
    if not ok: fails.append("Q3.1 flag")
else:
    fails.append("Q3.1 stub")

# 5. 清点全部旗子，补缺失
r = sh("sch", "list", "--stay", timeout=180)
allc = r.get("result", {}).get("components", [])
flags = [(round(c["x"]), round(c["y"]), c["name"]) for c in allc if c.get("componentType") == "netflag"]
print(f"\n  total netflags: {len(flags)}")
nets_seen = {}
for x, y, n in flags:
    if n not in ("__ROTPROBE__",):
        nets_seen.setdefault(n, 0)
        nets_seen[n] += 1
for n, k in sorted(nets_seen.items()):
    print(f"    {n}: {k}")

# 需要的旗（每个信号网至少 1 个；每个旗应 >=2 端的网络列出）
NEED = ["PWM","GATE","NRST","BOOT0","SWDIO","SWCLK","UART_TX","UART_RX",
        "VSENSE","ISENSE","CV_LED","CC_LED","PWR_LED","OSC_IN","OSC_OUT","VMID","PWM_B",
        "GND","3V3","VIN_5V","VOUT","VLOAD"]
missing = [n for n in NEED if n not in nets_seen]
print("  missing nets:", missing)
if missing:
    fails.append({"missing": missing})

# 6. 保存
r = sh("sch", "save", timeout=180)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:120])
if not r.get("ok"): fails.append("save")

with open("fix7_errors.json", "w", encoding="utf-8") as f:
    json.dump(fails, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
