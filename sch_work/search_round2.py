# -*- coding: utf-8 -*-
"""第二轮：精确定位第一轮未命中的器件。"""
import json, subprocess, os, re

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
OUT = os.path.dirname(os.path.abspath(__file__))

QUERIES = [
    ("inductor_sdr1306", "SDR1306", 4),
    ("inductor_cd75", "CD75", 4),
    ("schottky_ss34b", "SS34B", 4),
    ("schottky_b340a", "B340A", 4),
    ("shunt_50m_1206", "50mR 1206", 4),
    ("shunt_r050", "R050 1206", 4),
    ("cap_10u_x7r", "CL21B106KBQNNNE", 2),
    ("cap_elec_220u_25v", "220uF 25V", 6),
    ("cap_elec_100u_16v", "100uF 16V", 6),
    ("res_1k_rc0603", "RC0603FR-071KL", 2),
    ("res_10r_rc0603", "RC0603FR-0710KL", 2),
    ("res_100k_rc0603", "RC0603FR-07100KL", 2),
    ("xtal_hc49s", "8MHz HC-49S", 4),
    ("hdr_254_4p", "2.54 4P 排针", 5),
]

def run_query(q, limit):
    p = subprocess.run([EXE, "lib", "search", "--query", q, "--limit", str(limit)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    try:
        d = json.loads(p.stdout)
        return d.get("result", {}).get("components", [])
    except Exception as e:
        return [{"ERROR": f"{e}: {p.stdout[:120]} {p.stderr[:120]}"}]

for slug, q, limit in QUERIES:
    comps = run_query(q, limit)
    with open(os.path.join(OUT, f"lib_{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(comps, f, ensure_ascii=False, indent=1)
    print(f"== {slug} (query: {q})")
    for c in comps[:limit]:
        if "ERROR" in c:
            print("  ERROR " + c["ERROR"]); continue
        desc = re.sub(r"[;；]", " ", c.get("description", ""))[:66]
        print(f"  {c.get('name','?')} | {c.get('lcsc','-')} | {c.get('footprintName','-')} | {desc}")
print("DONE")
