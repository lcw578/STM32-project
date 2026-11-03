#!/usr/bin/env bash
# 一键重跑全部仿真验证（Python 控制环 + ngspice 功率级）
# 用法：cd /e/STM32_design/sim/ctrl && bash run_all.sh
set -e
NGSPICE=/d/Spice64/bin/ngspice_con.exe

echo "=== Python 控制环验证 ==="
python scenarios.py            # S1~S7、S10 + 固件原样缺陷证据
python s8_sweep.py             # PI 参数稳定域
python s9_aliasing.py          # 采样链混叠评估

echo "=== SPICE 功率级验证（ngspice-44 @ D:\\Spice64）==="
cd ../ltspice
"$NGSPICE" -b T1_boost_steady.cir
"$NGSPICE" -b T1b_fine_window.cir
"$NGSPICE" -b T2_duty_sweep.cir
"$NGSPICE" -b T3_softstart.cir

echo "=== 全部完成，结果见 sim/ctrl/results/ 与 sim/ltspice/ ==="
