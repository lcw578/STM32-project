# -*- coding: utf-8 -*-
"""fix9: U1 西走廊重建（阶梯桩）+ 全部 A 类电气修复"""
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

def delete_ids(ids):
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 6):
        batch = ids[i:i+6]
        r = sh("sch", "prim-delete", "--ids", ",".join(batch))
        print(f"  del {len(batch)}: ok={r.get('ok')}")
        if not r.get("ok"): fails.append(["del", batch])
        time.sleep(1.0)

def wire(pts, net):
    arg = json.dumps([[round(a,1), round(b,1)] for a,b in pts], separators=(",",":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2)
        r = sh("sch", "wire", "--points", arg, "--net", net)
        ok = r.get("ok")
    print(f"  wire {net} {pts[0]}->{pts[-1]}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:120]}")
    if not ok: fails.append(["wire", net, str(pts[:2])])
    return ok

def flag(net, x, y, kind="power", rot=None):
    args = ["sch", "netflag", "--kind", kind, "--net", net, "--x", str(round(x,1)), "--y", str(round(y,1))]
    if rot is not None: args += ["--rotation", str(rot)]
    r = sh(*args)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(1.5)
        r = sh(*args)
        ok = r.get("ok")
    print(f"  flag {net} @{int(x)},{int(y)} rot={rot}: {'OK' if ok else 'FAIL'}")
    if not ok: fails.append(["flag", net, x, y])
    return ok

# ---------- 1. 清空走廊 ----------
print("== 1. corridor clean")
d1 = json.load(open("s1.json", encoding="utf-8"))
del_ids = []
for c in d1["result"]["components"]:
    if c.get("componentType") == "netflag":
        x, y = round(c["x"]), round(c["y"])
        if 315 <= x <= 380 and 505 <= y <= 755:
            del_ids.append(c["primitiveId"])
        if (x, y) in [(580,850),(620,850)]:          # 出图纸残留
            del_ids.append(c["primitiveId"])
        if c.get("name") == "VSENSE" and abs(x-820) < 2 and abs(y-620) < 2:  # 重复 VSENSE
            del_ids.append(c["primitiveId"])
d2 = json.load(open("s2.json", encoding="utf-8"))
for w in d2["result"]["wires"]:
    pts = w.get("rawLine", [])
    pid = w["primitiveId"]
    inside = [i for i in range(0, len(pts), 2) if 315 <= pts[i] <= 380 and 505 <= pts[i+1] <= 755]
    if inside and len(inside) == len(pts)//2:
        del_ids.append(pid)
    if any(abs(pts[i]-580) < 2 and abs(pts[i+1]-820) < 2 for i in range(0, len(pts), 2)):
        del_ids.append(pid)
    if any(abs(pts[i]-620) < 2 and abs(pts[i+1]-820) < 2 for i in range(0, len(pts), 2)):
        del_ids.append(pid)
print(f"  deleting {len(set(del_ids))} primitives")
delete_ids(sorted(set(del_ids)))

# ---------- 2. C12 挪位 ----------
print("== 2. C12 move")
r = sh("sch", "modify", "--id", [c for c in d1["result"]["components"] if c.get("designator")=="C12"][0]["primitiveId"],
       "--x", "655", "--y", "760")
print("  C12 -> (655,760):", r.get("ok"))
time.sleep(1.5)

# ---------- 3. 走廊重建（阶梯桩） ----------
print("== 3. corridor rebuild")
CORR = [
    ("3V3",     (375,515), (350,515), "power", 90),
    ("GND",     (375,525), (330,525), "gnd", 270),
    ("CC_LED",  (375,565), (325,565), "power", 90),
    ("CV_LED",  (375,575), (350,575), "power", 90),
    ("ISENSE",  (375,605), (350,605), "power", 90),
    ("VSENSE",  (375,615), (330,615), "power", 90),
    ("3V3",     (375,665), (330,665), "power", 90),
    ("GND",     (375,675), (350,675), "gnd", 270),
    ("NRST",    (375,685), (330,685), "power", 90),
    ("PWR_LED", (375,735), (350,735), "power", 90),
    ("3V3",     (375,745), (330,745), "power", 90),
]
for net, p, far, kind, rot in CORR:
    if wire([p, far], net):
        flag(net, far[0], far[1], kind, rot)

# ---------- 4. 其余 A 类 ----------
print("== 4. rest")
wire([(545,625),(575,625)], "3V3")          # VDD_2（旗已在）
wire([(545,745),(575,745)], "3V3")          # VDD_3（旗已在）
wire([(545,705),(575,705)], "BOOT0")        # BOOT0（旗已在，C12 已挪走）
wire([(320,80),(295,80)], "VIN_5V")         # C3.1
flag("VIN_5V", 295, 80, "power", 90)
wire([(360,80),(385,80)], "GND")            # C3.2
flag("GND", 385, 80, "gnd", 90)
wire([(190,310),(190,340),(250,340)], "MID")  # Q3.C -> R6.1
wire([(190,370),(190,340)], "MID")            # Q2.E -> 拐点
wire([(655,740),(655,720)], "OSC_IN")         # C12.1 南桩
flag("OSC_IN", 655, 720, "power", 180)
wire([(655,780),(655,795)], "GND")            # C12.2 北桩
flag("GND", 655, 795, "gnd", 180)
flag("GND", 460, 90, "gnd", 90)               # C4.2 悬桩补旗

# ---------- 5. 保存 + 检查 ----------
print("== 5. save+check")
r = sh("sch", "save", timeout=240)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:100])
r = sh("sch", "check", timeout=300)
res = r.get("result", {})
summary = res if isinstance(res, str) else res.get("summary", res)
print("  check:", json.dumps(summary, ensure_ascii=False)[:400])
with open("fix9_out.json", "w", encoding="utf-8") as f:
    json.dump({"fails": fails, "check": res}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
