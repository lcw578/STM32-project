# -*- coding: utf-8 -*-
"""
run_rebuild_check.py —— 重建版原理图（2026-11-05）参数复核仿真

背景：器件平替后与 v2 仿真口径的差异（器件对照见 sch_work/rebuild_review_20261105/）
  L1   FSA1365-101MT 100µH DCR=0.17Ω        —— 与 v2 复跑口径一致（不变）
  Q1   AO3400A  rds=0.030Ω@Vgs≈4.3V          —— 不变
  D1   SS34     vf≈0.45V@0.5~1.5A            —— 与 B340A 同级（不变）
  Cout 5×22µF X5R 1206 25V (C6+C18~C21)      —— 原 220µF 电解(ESR 80mΩ)+10µF → 全陶瓷
        12V 偏压 derating ~50% → 每颗 ≈11µF，合计 ≈55µF；ESR 每颗 ~5mΩ
  Rs1  0.1Ω (1206W4F100LT5E) × INA180A2 G=50 → INA_GAIN=5.0 V/A   —— 原 0.05Ω
  分压 R13 3k + R1 33k / R2 10k → 10/46       —— plant_boost.DIVIDER_GAIN 已是 10/46 ✓
  采样 τ [1k+(36k‖10k)]×10nF = 88.3µs          —— RC_TAU 同 v2 复跑口径

固件同步常数（保持 Rs1=0.1Ω 的前提，bsp_power.h/control.c 需同步修改）：
  ADC_IOUT_GAIN = 3.3/4095/(0.1×50) = 0.000161172
  ADC_IOUT_DIV  = 6204.5
  ISET(0.5A)    = 3102
  UNLOAD_DROP   = 800   (0.129A/拍)
  OCP_HARD      = 0.6A → 3723   ※0.8A→INA 输出 4.0V 超 3.3V ADC 量程，0.1Ω 下不可实现
  OCP_SOFT      = 0.55A → 3412（存档）

输出：results/summary_rebuild_rs100_cer55.json（A 全场景 + B 电容边界 + C S8 网格
     + D 固件未同步反证）
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============ 固件同步常数补丁（必须先于 scenarios 导入） ============
import ctrl

INA_GAIN_NEW = 0.1 * 50.0                       # 0.1Ω × 50V/V
ctrl.ADC_IOUT_GAIN = 3.3 / (4095.0 * 5.0)       # 0.000161172 counts→A
ctrl.ADC_IOUT_DIV = 4095.0 * 5.0 / 3.3          # 6204.5 counts/A
ctrl.ISET_DEFAULT_COUNTS = 3102                 # 0.5A
ctrl.OCP_HARD_COUNTS = 3723                     # 0.6A（50 拍锁存）
ctrl.OCP_SOFT_COUNTS = 3412                     # 0.55A（存档，未引用）
ctrl.UNLOAD_DROP_COUNTS = 800.0                 # 0.129A/拍

import plant_boost
plant_boost.INA_GAIN = INA_GAIN_NEW
plant_boost.RC_TAU = 8.83e3 * 10e-9             # 88.3µs（重建实装采样常数）

# dataclass 生成的 __init__ 默认值绑定在函数签名上（类创建时定型），
# 改 __dataclass_fields__ 无效 → 用子类覆写默认并在各模块重绑名字
class _PatchedCfg(ctrl.ControlCfg):
    def __init__(self, **kw):
        kw.setdefault('i_set', ctrl.ISET_DEFAULT_COUNTS)   # 3102（0.5A @ 新增益）
        kw.setdefault('v_set', ctrl.VSET_DEFAULT_COUNTS)
        super().__init__(**kw)

import scenarios
scenarios.ControlCfg = _PatchedCfg

# ============ 重建版功率级参数 ============
def apply_rebuild_params(c_eff_total):
    """c_eff_total: 输出电容 12V 偏压下的等效总容量（5×22µF 陶瓷，derating 后）"""
    p = scenarios.P
    p.dcr = 0.17          # FSA1365-101MT
    p.rds = 0.030         # AO3400A @Vgs≈4.3V
    p.vf = 0.45           # SS34
    p.cout = c_eff_total * 0.8       # 双电容模型的"大"支路（4 颗）
    p.esr = 0.005
    p.cout_cer = c_eff_total * 0.2   # "小"支路（1 颗）
    p.esr_cer = 0.005

C_PRIMARY = 55e-6     # derating ~50%（主口径）
apply_rebuild_params(C_PRIMARY)

RESULT_DIR = scenarios.RESULT_DIR
summary = {'meta': dict(
    date='2026-11-05',
    purpose='重建版平替器件复核：Rs1=0.1Ω + 全陶瓷输出(Ceff≈55µF) + DCR 0.17',
    firmware_constants=dict(ADC_IOUT_GAIN=round(ctrl.ADC_IOUT_GAIN, 9),
                            ADC_IOUT_DIV=round(ctrl.ADC_IOUT_DIV, 1),
                            ISET=ctrl.ISET_DEFAULT_COUNTS,
                            OCP_HARD=str(ctrl.OCP_HARD_COUNTS) + ' (0.6A)',
                            UNLOAD_DROP=ctrl.UNLOAD_DROP_COUNTS),
    cout_model='5x22uF X5R25V @12V bias -> Ceff=55uF (bounds 45/66), esr=5mOhm',
)}


def phase_a_all():
    print('===== A. 全场景（Ceff=55µF，固件已同步） =====', flush=True)
    for fn in scenarios.ALL:
        print(f'--- {fn.__name__} ---', flush=True)
        fn(summary)


def phase_b_bounds():
    print('===== B. 电容容量边界（S1/S3/S4） =====', flush=True)
    for tag, c in (('Ceff45', 45e-6), ('Ceff66', 66e-6)):
        apply_rebuild_params(c)
        sub = {}
        scenarios.S1_open_loop_check(sub)
        scenarios.S2_S3_softstart_and_steady(sub)
        scenarios.S4_load_step(sub, kp_v=0.06, ki_v=50.0, tag=f'rebuild_{tag}', plot=False)
        summary[f'B_{tag}'] = {'S1': sub['S1'], 'S3': sub['S3'], 'S2': sub['S2'],
                               'S4': sub[f'S4_rebuild_{tag}']}
    apply_rebuild_params(C_PRIMARY)


def phase_c_s8():
    print('===== C. S8 稳定域网格（平均模型，重建参数） =====', flush=True)
    import s8_sweep
    s8_sweep.ControlCfg = _PatchedCfg          # one_run 直接构造 ControlCfg，同步补丁
    s8_sweep.P.dcr = 0.17
    s8_sweep.P.rds = 0.030
    s8_sweep.P.vf = 0.45
    s8_sweep.P.cout = 44e-6
    s8_sweep.P.esr = 0.005
    s8_sweep.P.cout_cer = 11e-6
    s8_sweep.P.esr_cer = 0.005
    grid_summary = {}
    s8_sweep.main.__globals__['summary'] = grid_summary  # noqa: main() 写内部 summary
    # 直接复用 one_run 而不是 main()，避免覆盖 summary_s8.json
    kp_list = [0.04, 0.05, 0.06, 0.08]
    ki_list = [30, 40, 50, 65]
    grid = []
    for kp in kp_list:
        row = []
        for ki in ki_list:
            r = s8_sweep.one_run(kp, ki)
            row.append(r)
            print(f'  kp_v={kp:<5} ki_v={ki:<4} ok={r["ok"]} over={r["unload_over_mv"]:>8}mV '
                  f'knee={r["knee_err_mv"]:>7}mV settle={r["settle_ms"]:>7}ms rec={r["reload_rec_ms"]:>7}ms',
                  flush=True)
        grid.append(row)
    summary['C_S8_grid'] = dict(kp=kp_list, ki=ki_list, results=grid,
                                note='判据同 s8_sweep：无故障+膝点<120mV+建立<100ms+恢复<30ms')


def phase_d_firmware_not_synced():
    print('===== D. 反证：保持 0.1Ω 但固件常数不动（0.05Ω 口径） =====', flush=True)
    # 把控制器常数退回旧固件值（0.05Ω 口径），功率级保持重建参数
    ctrl.ADC_IOUT_GAIN = 0.00032234
    ctrl.ADC_IOUT_DIV = 3102.3
    ctrl.OCP_HARD_COUNTS = 2482          # 固件认为的 0.8A = 实际 0.4A
    ctrl.UNLOAD_DROP_COUNTS = 400.0
    ctrl.ControlCfg.__dataclass_fields__['i_set'].default = 1551  # 固件认为的 0.5A = 实际 0.25A
    from plant_boost import CCLoad, StepProfile, run_closed_loop
    load = StepProfile([(0.0, CCLoad(0.5))])
    cfg = ctrl.ControlCfg(softstart_mode='ref_ramp', loop_arch='limiter',
                          kp_v=0.06, ki_v=50.0, load_ff=0.26)
    res = run_closed_loop(ctrl.Controller(cfg), scenarios.P, load, 0.300,
                          mode='average', init_vout=4.55)
    idx = [k for k, t in enumerate(res.t) if 0.20 <= t <= 0.30]
    i_avg = sum(res.iload[k] for k in idx) / len(idx)
    v_avg = sum(res.vout[k] for k in idx) / len(idx)
    summary['D_firmware_not_synced'] = dict(
        cmd='CV 带载 0.5A@12V（负载要求 0.5A，固件限流环给定=旧常数 1551 counts）',
        actual_i_avg=round(i_avg, 4), vout_avg=round(v_avg, 3),
        verdict=(f'输出塌到 {v_avg:.2f}V、电流 {i_avg:.3f}A：固件按 0.05Ω 解释 0.1Ω 采样，'
                 f'读数×2 → 控制器认为 1.0A 超过 0.5A 限流 → 限幅器压占空比，'
                 f'正常工作点都无法维持 12V'),
        evidence='iload/vout 均为功率级真实值（模型侧），非控制器读数')
    print(f"  实际恒流点 = {i_avg:.4f}A（应为 0.5A）", flush=True)
    # 恢复新常数（脚本结尾不再用，但保持整洁）
    ctrl.ADC_IOUT_GAIN = 3.3 / (4095.0 * 5.0)
    ctrl.ADC_IOUT_DIV = 6204.5
    ctrl.OCP_HARD_COUNTS = 3723
    ctrl.UNLOAD_DROP_COUNTS = 800.0
    ctrl.ControlCfg.__dataclass_fields__['i_set'].default = 3102


if __name__ == '__main__':
    phase_a_all()
    phase_b_bounds()
    phase_c_s8()
    phase_d_firmware_not_synced()
    out = os.path.join(RESULT_DIR, 'summary_rebuild_rs100_cer55.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print('saved:', out, flush=True)
    print(json.dumps({k: v for k, v in summary.items() if k in
                      ('S1', 'S2', 'S3', 'S4_rebuild_default', 'S5', 'S6', 'S7', 'S10',
                       'D_firmware_not_synced')}, ensure_ascii=False, indent=1))
