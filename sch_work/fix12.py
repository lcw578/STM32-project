# -*- coding: utf-8 -*-
"""fix12: 修走廊垂直合并 + VMID/VSENSE 短路 + 反挂旗 + 冗余旗"""
import json, subprocess, os, time, re

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

# ---------- 1. 找到并删除问题导线 ----------
print("== 1. locate bad wires")
r = sh("sch", "list", "--include-wires", "--stay")
wires = r.get("result", {}).get("wires", [])
del_ids = set()
for w in wires:
    pts = w.get("rawLine", [])
    pid = w["primitiveId"]
    net = w.get("net", "")
    # 走廊垂直合并线：含 (330,615)-(330,735) 竖段的多网线
    xs = [pts[i] for i in range(0, len(pts), 2)]
    ys = [pts[i+1] for i in range(0, len(pts), 2)]
    if net in ("VSENSE", "GND", "PWR_LED", "VOUT") and min(ys) <= 620 and max(ys) >= 720 and max(xs) <= 345:
        del_ids.add(pid); print("  corridor vertical:", net, pid)
    # VMID/VSENSE 重叠桩 (y=620, x 820-860)
    if any(abs(pts[i+1]-620) < 2 and 815 <= pts[i] <= 865 for i in range(0, len(pts), 2)):
        del_ids.add(pid); print("  vmid/vsense overlap:", net, pid)
if del_ids:
    ids = sorted(del_ids)
    for i in range(0, len(ids), 6):
        rr = sh("sch", "prim-delete", "--ids", ",".join(ids[i:i+6]))
        print("  del:", rr.get("ok"))
    time.sleep(1.5)

# ---------- 2. 走廊三旗错位重连 ----------
print("== 2. corridor restagger")
def conn(P, kind, net, direction, offset):
    r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net, "--direction", direction, "--offset", str(offset))
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2)
        r = sh("sch", "connect", "--pin", P, "--kind", kind, "--net", net, "--direction", direction, "--offset", str(offset))
        ok = r.get("ok")
    print(f"  conn {P}->{net} {direction}{offset}: {'OK' if ok else 'FAIL'}")
    if not ok: fails.append(["conn", P, net])
    return ok
conn("U1:14", "power", "VSENSE", "left", 25)   # (350,615)
conn("U1:8",  "gnd",   "GND",    "left", 45)   # (330,675)
conn("U1:2",  "power", "PWR_LED", "left", 65)  # (310,735)

# ---------- 3. C10 挪位重接 ----------
print("== 3. C10 move")
r = sh("sch", "list", "--stay", timeout=180)
c10 = next(c for c in r["result"]["components"] if c.get("designator") == "C10")
rr = sh("sch", "modify", "--id", c10["primitiveId"], "--x", "880", "--y", "560")
print("  C10 -> (880,560):", rr.get("ok"), rr.get("error", ""))
time.sleep(1.5)
conn("C10:1", "power", "VSENSE", "left", 25)
conn("C10:2", "gnd", "GND", "right", 25)

# ---------- 4. 删冗余 OSC_IN 旗 ----------
r = sh("sch", "prim-delete", "--ids", "fa4d3a37ae7a97c2")
print("  del dup OSC_IN flag:", r.get("ok"))

# ---------- 5. 反挂旗转正 ----------
print("== 5. reversed flags")
r = sh("sch", "check", timeout=300)
txt = json.dumps(r.get("result", {}), ensure_ascii=False)
rot_fixes = []
for it in (r.get("result", {}).get("findings", []) if isinstance(r.get("result"), dict) else []):
    s = json.dumps(it, ensure_ascii=False)
    if "反挂" in s:
        pid = it.get("primitiveId", "")
        mm = re.search(r"应为 (\d+)", s)
        if pid and mm: rot_fixes.append((pid, int(mm.group(1))))
for pid, rot in rot_fixes:
    rr = sh("sch", "modify", "--id", pid, "--rotation", str(rot))
    print(f"  {pid[:8]} -> rot {rot}: {rr.get('ok')}")
    time.sleep(0.4)
if not rot_fixes:
    print("  (none parsed — will handle next pass)")

# ---------- 6. 保存 + 总结 ----------
r = sh("sch", "save", timeout=240)
print("  save:", r.get("ok"))
rr = sh("sch", "check", timeout=300)
t = rr.get("result", {})
print("  check:", json.dumps(t if isinstance(t, str) else t.get("summary", t), ensure_ascii=False)[:260])
with open("fix12_out.json", "w", encoding="utf-8") as f:
    json.dump({"fails": fails, "check": t}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
