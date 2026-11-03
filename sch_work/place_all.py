# -*- coding: utf-8 -*-
"""批量放置全部器件：按功能分区规划坐标（A4 1170x825, y向上, 5raw网格）。
分区：
  PWR  功率级   x 50-380, y 480-815
  DRV  驱动     x 60-300, y 210-420
  LDO  电源     x 320-460, y 60-200
  MCU  最小系统 x 380-680, y 250-815
  SEN  采样     x 680-950, y 480-815
  IND  指示     x 680-950, y 220-400
  CONN 接口     x 980-1150, y 480-815
"""
import json, subprocess, os, sys

EXE = os.path.expanduser(r"~\.local\bin\easyeda.exe")
HERE = os.path.dirname(os.path.abspath(__file__))

# designator -> (x, y, rotation_deg)
PLACEMENTS = {
    # --- PWR 功率级 ---
    "J1":  (70, 790, 0),     # 输入端子
    "C5":  (70, 690, 0),     # 220uF 输入电解
    "C1":  (70, 590, 0),     # 10uF 输入陶瓷
    "L1":  (190, 770, 0),    # 100uH 电感
    "Q1":  (190, 620, 0),    # AO3400A
    "R7":  (265, 545, 0),    # 栅极下拉
    "D1":  (300, 770, 0),    # B340A
    "C6":  (300, 660, 0),    # 220uF 输出电解
    "C2":  (370, 770, 0),    # 10uF 输出陶瓷
    "Rs1": (370, 660, 0),    # 50mΩ 采样
    "J2":  (370, 550, 0),    # 输出端子
    # --- DRV 驱动 ---
    "R8":  (90, 390, 0),     # 基极串联 1k
    "Q2":  (180, 390, 0),    # S8050 NPN
    "Q3":  (180, 290, 0),    # S8550 PNP
    "R6":  (270, 340, 0),    # 栅极电阻 10Ω
    # --- LDO ---
    "U2":  (340, 150, 0),    # ME6211
    "C3":  (410, 170, 0),    # 10uF LDO 入
    "C4":  (410, 90, 0),     # 10uF LDO 出
    # --- MCU ---
    "U1":  (460, 630, 0),    # STM32 (151x251)
    "Y1":  (600, 770, 0),    # 8MHz 晶振
    "C12": (660, 770, 0),    # 22pF
    "C13": (660, 700, 0),    # 22pF
    "R9":  (600, 600, 0),    # 复位上拉 10k
    "SW1": (600, 520, 0),    # 复位按键
    "R10": (600, 430, 0),    # BOOT0 100k
    "C7":  (600, 350, 0),    # VDD 100nF
    "C8":  (600, 270, 0),    # VDDA 100nF
    # --- SEN 采样 ---
    "U3":  (720, 760, 0),    # INA180A2
    "R1":  (800, 780, 0),    # 36k 分压上
    "R2":  (800, 700, 0),    # 10k 分压下
    "R11": (800, 620, 0),    # 1k 滤波串联
    "C10": (880, 620, 0),    # 100nF Vout滤波
    "C11": (720, 660, 0),    # 100nF Isense滤波
    # --- IND 指示 ---
    "LED1": (700, 380, 0), "R5": (770, 380, 0),
    "LED2": (700, 300, 0), "R3": (770, 300, 0),
    "LED3": (700, 220, 0), "R4": (770, 220, 0),
    # --- CONN 接口 ---
    "J3":  (1060, 720, 0),   # SWD 4P
    "J4":  (1060, 580, 0),   # UART 4P
}

with open(os.path.join(HERE, "devices_selected.json"), encoding="utf-8") as f:
    devices = json.load(f)
dev_by_des = {d["designator"]: d for d in devices}

def sh(*args):
    p = subprocess.run([EXE, *args], capture_output=True, text=True, encoding="utf-8", timeout=90)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": (p.stdout + p.stderr)[:300]}

results = []
for des, (x, y, rot) in PLACEMENTS.items():
    d = dev_by_des.get(des)
    if not d:
        print(f"!! no device for {des}"); continue
    args = ["sch", "place", "--lib", d["libraryUuid"], "--uuid", d["uuid"],
            "--x", str(x), "--y", str(y), "--designator", des]
    if rot:
        args += ["--rotation", str(rot)]
    r = sh(*args)
    ok = r.get("ok", False)
    pid = r.get("result", {}).get("component", {}).get("designator", "?") if ok else str(r)[:120]
    results.append({"designator": des, "ok": ok, "info": pid})
    print(f"{'OK ' if ok else 'ERR'} {des:5s} ({x},{y}) -> {pid if ok else pid}")

with open(os.path.join(HERE, "placement_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
fails = [r for r in results if not r["ok"]]
print(f"\nplaced {len(results)-len(fails)}/{len(results)}, failed {len(fails)}")
