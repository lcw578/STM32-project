# -*- coding: utf-8 -*-
"""fix16: VOUT 走 x=320 通道 / C11.1 短桩 / 补齐悬浮引脚 / 清污染"""
import json, subprocess, os, time

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def sh(*args, timeout=180):
    p = subprocess.run([EXE, *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    try: return json.loads(p.stdout)
    except: return {"ok": False, "raw": ((p.stdout or "")+(p.stderr or ""))[:300]}

fails = []
def delete_ids(ids, tag=""):
    ids = sorted(set(i for i in ids if i))
    for i in range(0, len(ids), 6):
        r = sh("sch", "prim-delete", "--ids", ",".join(ids[i:i+6]))
        if not r.get("ok"): fails.append(["del", tag]); print("  del FAIL")
    if ids: print(f"  deleted {len(ids)} ({tag})")
    time.sleep(1.2)

def wire(pts, net):
    arg = json.dumps([[round(a,1), round(b,1)] for a,b in pts], separators=(",",":"))
    r = sh("sch", "wire", "--points", arg, "--net", net)
    time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2); r = sh("sch", "wire", "--points", arg, "--net", net); ok = r.get("ok")
    print(f"  wire {net} {pts[0]}->{pts[-1]}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:100]}")
    if not ok: fails.append(["wire", net])
    return ok

def conn(P, kind, net, direction, offset):
    args = ["sch", "connect", "--pin", P, "--kind", kind, "--net", net, "--direction", direction, "--offset", str(offset)]
    r = sh(*args); time.sleep(0.5)
    ok = r.get("ok")
    if not ok:
        time.sleep(2); r = sh(*args); ok = r.get("ok")
    print(f"  conn {P}->{net} {direction}{offset}: {'OK' if ok else 'FAIL ' + json.dumps(r.get('error',{}), ensure_ascii=False)[:100]}")
    if not ok: fails.append(["conn", P, net])
    return ok

# ---------- 1. 删除污染 ----------
print("== 1. delete")
r = sh("sch", "list", "--include-wires", "--stay")
del_w = set()
for w in r["result"]["wires"]:
    if w["primitiveId"].startswith(("b60db728", "a92041e0")):
        del_w.add(w["primitiveId"])
r2 = sh("sch", "list", "--stay")
del_f = set()
for c in r2["result"]["components"]:
    if c.get("componentType") != "netflag": continue
    x, y, n = round(c["x"]), round(c["y"]), c.get("name")
    if n == "__ROTPROBE__": continue
    if (x, y, n) in [(330,615,"VSENSE"),(330,675,"GND"),(330,735,"PWR_LED"),(310,735,"PWR_LED"),
                     (730,650,"ISENSE"),(730,650,"VOUT"),(730,690,"VOUT")]:
        del_f.add(c["primitiveId"])
delete_ids(del_w, "bad wires")
delete_ids(del_f, "bad flags")

# ---------- 2. VOUT 链（x=320 通道，远离走廊） ----------
print("== 2. VOUT chain")
wire([(320,770),(320,660)], "VOUT")   # D1.K -> C6.1
wire([(320,660),(320,610)], "VOUT")   # C6.1 -> Rs1.1

# ---------- 3. 走廊三旗重连（全 25，x=350） ----------
print("== 3. corridor")
conn("U1:14", "power", "VSENSE", "left", 25)
conn("U1:8",  "gnd",  "GND",    "left", 25)
conn("U1:2",  "power", "PWR_LED", "left", 25)

# ---------- 4. C11.1 / U3.3 ----------
print("== 4. x=730")
conn("C11:1", "power", "ISENSE", "up", 10)    # (730,640)
conn("U3:3",  "power", "VOUT",   "down", 20)  # (730,690)

# ---------- 5. 悬浮引脚补连 ----------
print("== 5. floating pins")
r2 = sh("sch", "list", "--stay", timeout=180)
have = [(round(c["x"]), round(c["y"]), c.get("name")) for c in r2["result"]["components"] if c.get("componentType") == "netflag"]
def has_flag(x, y, net):
    return any(abs(fx-x) < 3 and abs(fy-y) < 3 and fn == net for fx, fy, fn in have)
if not has_flag(35, 785, "GND"):
    conn("J1:2", "gnd", "GND", "left", 15)
else:
    print("  J1:2 flag exists")
conn("R11:2", "power", "VSENSE", "left", 25)
conn("Y1:2",  "power", "OSC_OUT", "right", 25)
conn("R9:2",  "power", "NRST",   "right", 25)

# ---------- 6. 保存 + 检查 ----------
print("== 6. save+check")
r = sh("sch", "save", timeout=240)
print("  save:", r.get("ok"), json.dumps(r.get("result", {}), ensure_ascii=False)[:80])
if not r.get("ok"): fails.append("save")
p = subprocess.run([EXE, "sch", "check"], capture_output=True, text=True, encoding="utf-8", timeout=300)
print(p.stdout.splitlines()[0][:220] if p.stdout else "no output")
open("check_v4.txt", "w", encoding="utf-8").write(p.stdout)
with open("fix16_out.json", "w", encoding="utf-8") as f:
    json.dump({"fails": fails}, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
