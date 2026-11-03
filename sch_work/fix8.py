# -*- coding: utf-8 -*-
"""fix8: 清理合并损坏的 VLOAD 导线与旧残留，重画，验证，保存"""
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

# 1. 删除损坏/残留
r = sh("sch", "prim-delete", "--ids", "839fa40c19d28143,3434c5568f99e02c,0ed4971df3a3a3f8")
print("delete 3:", r.get("ok"), str(r.get("error",""))[:100])
time.sleep(1.5)

# 2. 重画 VLOAD
r = sh("sch", "wire", "--points", "[[280,610],[270,610],[270,475],[230,475],[220,475]]", "--net", "VLOAD")
time.sleep(0.5)
ok = r.get("ok")
if not ok:
    time.sleep(2)
    r = sh("sch", "wire", "--points", "[[280,610],[270,610],[270,475],[230,475],[220,475]]", "--net", "VLOAD")
    ok = r.get("ok")
print("VLOAD redraw:", ok, "" if ok else json.dumps(r.get("error",{}), ensure_ascii=False)[:130])
if not ok: fails.append("VLOAD")

# 3. R7.1 GATE 桩 + 旗
r = sh("sch", "wire", "--points", "[[220,560],[195,560]]", "--net", "GATE")
time.sleep(0.5)
ok = r.get("ok")
if not ok:
    time.sleep(2)
    r = sh("sch", "wire", "--points", "[[220,560],[195,560]]", "--net", "GATE")
    ok = r.get("ok")
print("GATE stub:", ok)
if ok:
    r = sh("sch", "netflag", "--kind", "power", "--net", "GATE", "--x", "195", "--y", "560")
    time.sleep(0.5)
    print("GATE flag:", r.get("ok"))
    if not r.get("ok"): fails.append("GATE flag")
else:
    fails.append("GATE stub")

# 4. 验证：bridge-check + check + save
for step in (["sch", "bridge-check"], ["sch", "check"], ["sch", "save"]):
    r = sh(*step, timeout=240)
    print(f"{step[1]}: ok={r.get('ok')} " + json.dumps(r.get("result", r.get("error", {})), ensure_ascii=False)[:260])
    if step[1] == "save" and not r.get("ok"): fails.append("save")

with open("fix8_errors.json", "w", encoding="utf-8") as f:
    json.dump(fails, f, ensure_ascii=False, indent=1)
print(f"\nRESULT fails={len(fails)}")
