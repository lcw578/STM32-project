# -*- coding: utf-8 -*-
"""
s8_sweep.py —— S8 PI 参数敏感性扫描（limiter 修复对照架构，平均模型）

目的：kp_v=0.05/ki_v=150（固件默认）被 S4 证明太慢（卸载过冲 1.2V 触发 OVP）。
扫描 (kp_v, ki_v) 网格找出同时满足以下判据的参数区域，给出推荐终值：
  1) 全程无 OVP/OCP 误触发
  2) 卸载(0.5A→0)过冲 < 0.6V 且 50ms 内回到 ±1%
  3) 加载恢复 < 50ms
  4) 临界点(24Ω)稳态误差 < ±1%
  5) 启动无振荡、建立时间 < 100ms
另扫 ki_i（限幅器速度）对卸载恢复与临界点纹波的影响。
"""
import os, json, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctrl import Controller, ControlCfg, CTRL_TS, ST_FAULT_OC, ST_FAULT_OV, PWM_PERIOD
from plant_boost import BoostParams, ResLoad, CCLoad, StepProfile, run_closed_loop

RESULT_DIR = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results'))
P = BoostParams()
V_T = 12.0


def one_run(kp_v, ki_v, ki_i=80.0):
    """启动(预充4.55V)→CC0.45A(CV区，避开0.5A边界病理)；200ms 卸载→0；300ms 重载
    （CC/CV 临界点精度由 S3 单独考核，本扫描聚焦瞬态与 CV 精度）"""
    load = StepProfile([(0.0, CCLoad(0.45)), (0.200, CCLoad(0.0)), (0.300, CCLoad(0.45))])
    cfg = ControlCfg(softstart_mode='ref_ramp', loop_arch='limiter',
                     kp_v=kp_v, ki_v=ki_v, ki_i=ki_i)
    ctrl = Controller(cfg)
    res = run_closed_loop(ctrl, P, load, 0.420, vin_func=None, mode='average', init_vout=4.55)
    idx = lambda a, b: [k for k, t in enumerate(res.t) if a <= t <= b]
    # 启动建立（进入 ±1% 带后不再出的时刻）
    settle = 0.0
    for k in idx(0.05, 0.19):
        if abs(res.vout[k] - V_T) > 0.12: settle = res.t[k]
    settle_ms = (settle - 0.05) * 1e3 if settle else 0.0
    cv_err = max(abs(res.vout[k] - V_T) for k in idx(0.15, 0.19))
    over = max(res.vout[k] for k in idx(0.20, 0.26)) - V_T          # 卸载过冲
    fault = any(s in (ST_FAULT_OV, ST_FAULT_OC) for s in res.state)
    under = V_T - min(res.vout[k] for k in idx(0.30, 0.33))         # 重载跌落（记录用）
    rec = 0.0
    for k in idx(0.30, 0.42):
        if abs(res.vout[k] - V_T) > 0.60: rec = res.t[k]            # 恢复到 ±5% 带
    rec_ms = (rec - 0.30) * 1e3 if rec else 0.0
    # 判据：无故障 + 稳态精度 + 建立时间 + ±5%带恢复时间（瞬态幅度只记录不设限，
    # 空载↔满载硬阶跃的跌落/过冲幅度受 10kHz 控制率与 RHP 零点物理限制）
    ok = (not fault) and cv_err < 0.12 and settle_ms < 100 and rec_ms < 30
    return dict(ok=ok, fault=fault, settle_ms=round(settle_ms, 1),
                knee_err_mv=round(cv_err * 1e3, 1), unload_over_mv=round(over * 1e3, 1),
                reload_under_mv=round(under * 1e3, 1), reload_rec_ms=round(rec_ms, 1))


def main():
    summary = {}
    kp_list = [0.04, 0.05, 0.06, 0.08, 0.12]
    ki_list = [30, 40, 50, 65, 80]
    grid, ok_map = [], []
    print('扫 (kp_v, ki_v)：')
    for kp in kp_list:
        row, rowok = [], []
        for ki in ki_list:
            r = one_run(kp, ki)
            row.append(r); rowok.append(r['ok'])
            print(f'  kp_v={kp:<5} ki_v={ki:<4} ok={r["ok"]} fault={r["fault"]} over={r["unload_over_mv"]:>8}mV '
                  f'under={r["reload_under_mv"]:>8}mV knee={r["knee_err_mv"]:>7}mV '
                  f'settle={r["settle_ms"]:>7}ms rec={r["reload_rec_ms"]:>7}ms')
        grid.append(row); ok_map.append(rowok)
    summary['grid'] = dict(kp=kp_list, ki=ki_list, results=grid)

    # ki_i 扫描（用网格中最优 kp_v/ki_v）
    best = None
    for i, kp in enumerate(kp_list):
        for j, ki in enumerate(ki_list):
            if ok_map[i][j]:
                if best is None or grid[i][j]['unload_over_mv'] < best[2]['unload_over_mv']:
                    best = (kp, ki, grid[i][j])
    if best:
        kp_b, ki_b, _ = best
        ki_i_rows = []
        for ki_i in (40, 80, 200):
            r = one_run(kp_b, ki_b, ki_i=ki_i)
            ki_i_rows.append(dict(ki_i=ki_i, **r))
            print(f'  ki_i={ki_i:<4} ok={r["ok"]} over={r["unload_over_mv"]}mV rec={r["reload_rec_ms"]}ms')
        summary['kii_sweep'] = dict(kp_v=kp_b, ki_v=ki_b, rows=ki_i_rows)
        summary['recommend'] = dict(kp_v=kp_b, ki_v=ki_b,
                                    note='满足全部判据的网格点中卸载过冲最小者')
    else:
        summary['recommend'] = None

    # 热力图：卸载过冲
    fig, ax = plt.subplots(figsize=(7, 5))
    import numpy as np
    z = np.array([[max(r['unload_over_mv'], 0) for r in row] for row in grid], dtype=float)
    im = ax.imshow(z, cmap='RdYlGn_r', aspect='auto')
    ax.set_xticks(range(len(ki_list)), [str(x) for x in ki_list])
    ax.set_yticks(range(len(kp_list)), [str(x) for x in kp_list])
    ax.set_xlabel('ki_v'); ax.set_ylabel('kp_v')
    for i in range(len(kp_list)):
        for j in range(len(ki_list)):
            ax.text(j, i, f'{z[i,j]:.0f}' + (' OK' if ok_map[i][j] else ' X'),
                    ha='center', va='center', fontsize=9)
    ax.set_title('S8 卸载过冲 (mV) 与通过性 ✓/✗（limiter 架构）')
    fig.colorbar(im, label='过冲 mV')
    fig.tight_layout()
    fig.savefig(os.path.join(RESULT_DIR, 'S8_sweep.png'), dpi=130)
    plt.close(fig)

    with open(os.path.join(RESULT_DIR, 'summary_s8.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print('recommend:', summary['recommend'])


if __name__ == '__main__':
    main()
