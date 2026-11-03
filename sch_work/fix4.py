# -*- coding: utf-8 -*-
"""fix4: 最后两处修复 + 全量检查 + 网表对账 + 保存"""
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

# 1. OSC_OUT 改走 x=345 通道（避开 J2 本体与引脚 lead）
r = sh("sch", "wire", "--points", "[[375,695],[345,695],[345,490],[630,490],[630,770],[620,770]]", "--net", "OSC_OUT")
ok = r.get("ok")
if not ok:
    time.sleep(2)
    r = sh("sch", "wire", "--points", "[[375,695],[345,695],[345,490],[630,490],[630,770],[620,770]]", "--net", "OSC_OUT")
    ok = r.get("ok")
print("OSC_OUT:", "OK" if ok else json.dumps(r.get("error", r), ensure_ascii=False)[:200])
if not ok: fails.append("OSC_OUT")

# 2. U1:19 加长桩向西 50 + 旗
r = sh("sch", "wire", "--points", "[[375,565],[325,565]]", "--net", "CC_LED")
if r.get("ok"):
    r = sh("sch", "netflag", "--kind", "net_label", "--net", "CC_LED", "--x", "325", "--y", "565")
    print("CC_LED stub+flag:", r.get("ok"))
    if not r.get("ok"): fails.append("CC_LED flag")
else:
    print("CC_LED stub FAIL:", json.dumps(r.get("error", r), ensure_ascii=False)[:150]); fails.append("CC_LED stub")

# 3. C1:1 向西桩 + VIN 旗
r = sh("sch", "wire", "--points", "[[50,590],[25,590]]", "--net", "VIN_5V")
if r.get("ok"):
    r = sh("sch", "netflag", "--kind", "power", "--net", "VIN_5V", "--x", "25", "--y", "590")
    print("C1 VIN stub+flag:", r.get("ok"))
    if not r.get("ok"): fails.append("C1 flag")
else:
    print("C1 stub FAIL:", json.dumps(r.get("error", r), ensure_ascii=False)[:150]); fails.append("C1 stub")

# 4. gate 四项检查
print("\n== gate checks")
gate = {}
for step in (["sch", "layout-lint"], ["sch", "check"], ["sch", "bridge-check"], ["sch", "drc"]):
    r = sh(*step, timeout=240)
    res = r.get("result", {})
    gate[step[1]] = {"ok": r.get("ok"), "result": res}
    print(f"  {step[1]}: ok={r.get('ok')}")
    print("   ", json.dumps(res, ensure_ascii=False)[:400])
with open("gate_results.json", "w", encoding="utf-8") as f:
    json.dump(gate, f, ensure_ascii=False, indent=1)

# 5. 网表导出 + 对账
print("\n== netlist")
r = sh("sch", "netlist", timeout=180)
nl = r.get("result", {})
with open("netlist_actual.json", "w", encoding="utf-8") as f:
    json.dump(nl, f, ensure_ascii=False, indent=1)
nets = nl.get("nets", nl if isinstance(nl, list) else [])
print("netlist keys:", list(nl.keys()) if isinstance(nl, dict) else "list")
print(json.dumps(nets, ensure_ascii=False)[:600])

print("\nRESULT fails:", fails)
