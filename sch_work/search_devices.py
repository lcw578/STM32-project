# -*- coding: utf-8 -*-
"""批量检索嘉立创EDA器件库，为每个 MPN 记录首选与备选结果。"""
import json, subprocess, os, re, sys

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
OUT = os.path.dirname(os.path.abspath(__file__))

# (slug, query, limit) —— limit>1 时保留备选
QUERIES = [
    ("stm32f103c8t6", "STM32F103C8T6", 2),
    ("ldo_me6211c33", "ME6211C33M5G", 3),
    ("ina180a2", "INA180A2IDBVR", 3),
    ("nmos_ao3400a", "AO3400A", 3),
    ("schottky_ss34", "SS34", 3),
    ("inductor_100uh", "100uH", 6),
    ("npn_s8050", "S8050", 3),
    ("pnp_s8550", "S8550", 3),
    ("shunt_50m", "0.05R 1206", 4),
    ("xtal_8m", "8MHz 3225", 4),
    ("term_508_2p", "KF301 2P", 4),
    ("cap_100n_0603", "100nF 0603", 2),
    ("cap_10u_0805_25v", "10uF 0805 25V", 3),
    ("cap_22u_10v", "22uF 0805 10V", 3),
    ("res_36k_0603", "36k 0603", 2),
    ("res_10k_0603", "10k 0603", 2),
    ("res_1k_0603", "1k 0603", 2),
    ("res_10r_0603", "10R 0603", 2),
    ("res_100k_0603", "100k 0603", 2),
    ("cap_22p_0603", "22pF 0603", 2),
    ("led_0603_red", "red LED 0603", 3),
    ("led_0603_green", "green LED 0603", 2),
    ("btn_6x6", "button 6x6 SMD", 3),
    ("hdr_4p", "header 4P 2.54", 4),
]

KEYS = ("name", "manufacturerId", "lcsc", "uuid", "libraryUuid", "footprintName", "symbolName", "description")

def run_query(q, limit):
    p = subprocess.run([EXE, "lib", "search", "--query", q, "--limit", str(limit)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    try:
        d = json.loads(p.stdout)
        return d.get("result", {}).get("components", [])
    except Exception as e:
        return [{"ERROR": f"{e}: {p.stdout[:120]} {p.stderr[:120]}"}]

summary = {}
for slug, q, limit in QUERIES:
    comps = run_query(q, limit)
    with open(os.path.join(OUT, f"lib_{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(comps, f, ensure_ascii=False, indent=1)
    lines = []
    for c in comps[:limit]:
        if "ERROR" in c:
            lines.append("  ERROR " + c["ERROR"]); continue
        desc = re.sub(r"[;；]", " ", c.get("description", ""))[:60]
        lines.append(f"  {c.get('name','?')} | {c.get('lcsc','-')} | {c.get('footprintName','-')} | {desc}")
    summary[slug] = lines
    print(f"== {slug} (query: {q})")
    print("\n".join(lines) if lines else "  (no results)")

with open(os.path.join(OUT, "search_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
print("\nDONE -> search_summary.json")
