# -*- coding: utf-8 -*-
"""fix14: 删污染树 → 重画 VOUT/VIN/VMID 链 → 补 OSC/VSENSE/C9.1 → 清出图纸 → 保存"""
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

def delete_ids(ids, tag=""):
    ids = sorted(set(i for i in ids if i))
    for i in range(0, len(ids), 6):
        r = sh("sch", "prim-delete", "--ids", ",".join(ids[i:i+6]))
        if not r.get("ok"): fails.append(["del", tag]); print("  del FAIL")
    print(f"  deleted {len(ids)} ({tag})")
    time.sleep(1.2)

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
    args = ["sch", "connect", "--pin", P, "--kind", kind, "--net", net, "--direction", direction, "--offset", str(offset)]
    r = sh(*args)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2)
        r = sh(*args)
        ok = r.get("ok")
    print(f"  conn {P}->{net} {direction}{offset}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:100]}")
    if not ok: fails.append(["conn", P, net])
    return ok

# ---------- 1. 删除污染与出图纸 ----------
print("== 1. delete")
r = sh("sch", "list", "--include-wires", "--stay")
wires = r.get("result", {}).get("wires", [])
del_w = set()
for w in wires:
    pid = w["primitiveId"]
    if pid.startswith(("2fc1e135", "da495b52")): del_w.add(pid)
    pts = w.get("rawLine", [])
    if any(pts[i+1] > 813 and 640 <= pts[i] <= 790 for i in range(0, len(pts), 2)):  # U3 旧桩出图纸
        del_w.add(pid)
    if any(pts[i+1] > 690 and pts[i] < 45 for i in range(0, len(pts), 2)):           # J1.2 旧旗桩 x<45
        del_w.add(pid)
r2 = sh("sch", "list", "--stay")
allc = r2.get("result", {}).get("components", [])
del_f = set()
for c in allc:
    if c.get("componentType") != "netflag": continue
    x, y, n = round(c["x"]), round(c["y"]), c.get("name")
    if n == "__ROTPROBE__": continue
    if y > 813 or x < 12: del_f.add(c["primitiveId"])                                 # 出图纸旗
    if n == "3V3" and abs(x-830) < 3 and abs(y-760) < 3: del_f.add(c["primitiveId"])  # 压 VMID 线的旗
delete_ids(del_w, "wires")
delete_ids(del_f, "flags")

# ---------- 2. 重画 ----------
print("== 2. redraw")
wire([(50,795),(40,795),(40,690),(50,690)], "VIN_5V")          # J1.1 -> C5.1
wire([(320,770),(350,770)], "VOUT")                            # D1.K -> C2.1
wire([(320,770),(330,770),(330,660),(320,660)], "VOUT")        # D1.K -> C6.1
wire([(320,660),(330,660),(330,610),(320,610)], "VOUT")        # C6.1 -> Rs1.1
wire([(820,780),(830,780),(830,700),(820,700)], "VMID")        # R1.2 -> R2.1
wire([(820,700),(830,700),(830,620),(820,620)], "VMID")        # R2.1 -> R11.1

# ---------- 3. 补连接 ----------
print("== 3. reconnect")
conn("R11:2", "power", "VSENSE", "left", 25)
conn("U1:5", "power", "OSC_IN", "left", 15)
conn("U1:6", "power", "OSC_OUT", "left", 15)
conn("C9:1", "power", "3V3", "left", 15)
conn("C11:1", "power", "ISENSE", "up", 20)
conn("U3:3", "power", "VOUT", "down", 20)

# ---------- 4. 反挂旗转正 ----------
print("== 4. reversed flags")
r = sh("sch", "check", timeout=300)
raw = r.get("result", {})
txt = json.dumps(raw, ensure_ascii=False)
items = raw.get("findings", []) if isinstance(raw, dict) else []
n_rot = 0
for it in items:
    s = json.dumps(it, ensure_ascii=False)
    if "反挂" in s:
        pid = it.get("primitiveId", "")
        mm = re.search(r"应为 (\d+)", s)
        if pid and mm:
            rr = sh("sch", "modify", "--id", pid, "--rotation", mm.group(1))
            n_rot += 1
            time.sleep(0.4)
print(f"  rotated {n_rot} flags")
# 删多余重复旗（第二轮 check 后再扫一遍）
time.sleep(1)

# ---------- 5. 保存 ----------
r = sh("sch", "save", timeout=240)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:80])
if not r.get("ok"): fails.append("save")
with open("fix14_out.json", "w", encoding="utf-8") as f:
    json.dump({"fails": fails, "rot": n_rot}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
