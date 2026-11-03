# -*- coding: utf-8 -*-
"""PCB 布局 v2：按功能区放置 42 器件"""
import json, subprocess, os, time

EXE = os.path.expanduser(r"C:\Users\33178\.local\bin\easyeda.exe")
WIN = "b353f434-35bd-438b-a83b-efc9faf2fc20"
DOC = "b31183190bec91b8"
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def sh(*a, t=300):
    p = subprocess.run([EXE, *a], capture_output=True, text=True, encoding="utf-8", timeout=t)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": (p.stdout or "")[:150]}

d = sh("pcb", "list", "--window", WIN, "--doc", DOC)
comps = {c["designator"]: c["primitiveId"] for c in d.get("result", {}).get("components", [])}
print("comps:", len(comps))

MAP = {
    "J1": (400, 1550, 0),  "C5": (700, 1780, 0),  "C1": (700, 1400, 0),
    "L1": (1250, 1600, 0), "Q1": (1600, 1150, 0), "R7": (1880, 1150, 0),
    "D1": (1900, 1650, 0), "C6": (2200, 1720, 0), "C2": (2200, 1400, 0),
    "Rs1": (2430, 1550, 0), "J2": (2600, 1780, 0),
    "U2": (480, 700, 0),   "C3": (300, 520, 0),   "C4": (650, 520, 0),
    "U1": (1350, 480, 0),  "Y1": (950, 230, 0),   "C12": (1080, 230, 0),
    "C13": (1080, 100, 0), "R10": (500, 880, 0),  "SW1": (660, 620, 0),
    "R9": (820, 620, 0),   "C7": (1550, 780, 0),  "C8": (1700, 780, 0),
    "J3": (1600, 130, 0),  "J4": (1860, 130, 0),
    "LED1": (230, 880, 0), "R5": (360, 880, 0),   "LED2": (230, 720, 0),
    "R3": (360, 720, 0),   "LED3": (230, 560, 0), "R4": (360, 560, 0),
    "U3": (2100, 580, 0),  "C9": (2260, 460, 0),  "C11": (1950, 460, 0),
    "R1": (2430, 800, 0),  "R2": (2430, 640, 0),  "R11": (2430, 480, 0),
    "C10": (2580, 640, 0),
}

ok = fail = 0
for des, (x, y, rot) in MAP.items():
    pid = comps.get(des)
    if not pid:
        print("!! missing", des)
        fail += 1
        continue
    args = ["pcb", "modify", "--id", pid, "--center", "--x", str(x), "--y", str(y),
            "--window", WIN, "--doc", DOC]
    if rot:
        args += ["--rotation", str(rot)]
    r = sh(*args)
    if r.get("ok"):
        ok += 1
    else:
        fail += 1
        print("FAIL", des, json.dumps(r.get("error", {}), ensure_ascii=False)[:100])
    time.sleep(0.3)

print(f"placed {ok}/{ok+fail}")
r = sh("pcb", "layout-lint", "--window", WIN, "--doc", DOC, t=600)
res = r.get("result", r)
print("lint:", json.dumps(res, ensure_ascii=False)[:500])
