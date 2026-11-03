# -*- coding: utf-8 -*-
"""fix11: 补回被误删的 VOUT 链与 R9.1，OSC 旗，删重复/出图纸/图签侵入旗，转正反挂旗"""
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

def wire(pts, net):
    arg = json.dumps([[round(a,1), round(b,1)] for a,b in pts], separators=(",",":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2)
        r = sh("sch", "wire", "--points", arg, "--net", net)
        ok = r.get("ok")
    print(f"  wire {net} {pts[0]}->{pts[-1]}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:110]}")
    if not ok: fails.append(["wire", net])
    return ok

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

# 1. VOUT 链重建
print("== 1. VOUT chain")
wire([(320,770),(350,770)], "VOUT")                       # D1.K -> C2.1
wire([(320,770),(330,770),(330,660),(320,660)], "VOUT")   # D1.K -> C6.1
wire([(320,660),(330,660),(330,610),(320,610)], "VOUT")   # C6.1 -> Rs1.1

# 2. R9.1 3V3（西向）
conn("R9:1", "power", "3V3", "left", 25)

# 3. U1.5/U1.6 OSC 旗（短桩西向）
conn("U1:5", "power", "OSC_IN", "left", 15)
conn("U1:6", "power", "OSC_OUT", "left", 15)

# 4. 删重复旗 / 出图纸 / 图签侵入
print("== 4. delete dups/stale")
r = sh("sch", "list", "--stay", timeout=180)
allc = r.get("result", {}).get("components", [])
dups = ["b58cce435a39307b", "facafcc5018da73b", "a6ce30c42abaf8f1", "9b4dd1a81dbd8298"]
stale = []
for c in allc:
    if c.get("componentType") != "netflag": continue
    x, y = round(c["x"]), round(c["y"])
    if (x, y) in [(580,850),(620,850)]: stale.append(c["primitiveId"])       # 出图纸
    if c["primitiveId"] == "74f09b42ebdbaed5": stale.append(c["primitiveId"]) # 图签侵入
delete_ids = dups + stale
for i in range(0, len(delete_ids), 6):
    r = sh("sch", "prim-delete", "--ids", ",".join(delete_ids[i:i+6]))
    print(f"  del {len(delete_ids[i:i+6])}: ok={r.get('ok')}")
time.sleep(1.0)

# 5. 反挂旗转正（check 给出的映射）
print("== 5. flag rotations")
r = sh("sch", "check", timeout=300)
txt = json.dumps(r.get("result", {}), ensure_ascii=False)
import re
fixes = re.findall(r'(reversed-net-flag)[^"]*?"primitiveId"?:?\s*"([0-9a-f]+)"[^}]*?旗反挂:桩朝 (\w+) 而旗 rot=(\d+)(应为 (\d+))?', txt)
print("  reversed found:", len(fixes))
DIR2ROT_GND = {"down": 0, "right": 90, "up": 180, "left": 270}
DIR2ROT_PWR = {"up": 0, "right": 270, "down": 180, "left": 90}
seen = set()
for m in re.finditer(r'"id":\s*"[0-9a-f-f]+"[^}]*?反挂[^}]*', txt):
    pass
# 简化：从 check 文本逐条解析（格式：旗反挂:桩朝 X 而旗 rot=A(应为 B)）
# check 结果里的条目带 primitiveId 字段
items = r.get("result", {}).get("findings", []) if isinstance(r.get("result"), dict) else []
rot_fixes = []
for it in items:
    s = json.dumps(it, ensure_ascii=False)
    if "反挂" in s:
        pid = it.get("primitiveId", "")
        # 从 message 提取 应为 N
        mm = re.search(r"应为 (\d+)", s)
        if pid and mm:
            rot_fixes.append((pid, int(mm.group(1))))
print("  rot fixes:", rot_fixes)
for pid, rot in rot_fixes:
    r = sh("sch", "modify", "--id", pid, "--rotation", str(rot))
    ok = r.get("ok")
    print(f"  flag {pid[:8]} -> rot {rot}: {ok}")
    if not ok: fails.append(["rot", pid])
    time.sleep(0.4)

# 6. 保存 + 总检
r = sh("sch", "save", timeout=240)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:80])
r = sh("sch", "check", timeout=300)
res = r.get("result", {})
print("  check:", json.dumps(res if isinstance(res, str) else res.get("summary", res), ensure_ascii=False)[:300])
with open("fix11_out.json", "w", encoding="utf-8") as f:
    json.dump({"fails": fails, "check": res}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
