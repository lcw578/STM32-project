# -*- coding: utf-8 -*-
"""
scenarios.py —— S1~S7、S10 验证场景 + 指标提取 + 出图

双轨结构：
  ASIS  = 固件原样算法（duty_ramp 软启动 + track 反算跟踪）——缺陷证据轨
  FIXED = 仿真侧修复对照（ref_ramp 软启动 + clamp_track 未选中环钳位）——正式验证轨
判据出处：《01_系统设计方案.md》§2 指标表、课程任务书
"""
import os, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

from ctrl import (Controller, ControlCfg, PWM_PERIOD, CTRL_TS,
                  ST_RUN_CV, ST_RUN_CC, ST_FAULT_OV, ST_FAULT_OC, STATE_NAMES,
                  VSET_DEFAULT_COUNTS, ISET_DEFAULT_COUNTS,
                  counts_to_volts, counts_to_amps)
from plant_boost import (BoostParams, ResLoad, CCLoad, StepProfile,
                         vin_const, vin_profile, run_open_loop, run_closed_loop)

RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(RESULT_DIR, exist_ok=True)

P = BoostParams()
V_TARGET = counts_to_volts(VSET_DEFAULT_COUNTS)   # 12.0V
I_TARGET = counts_to_amps(ISET_DEFAULT_COUNTS)    # 0.5A


def asis_cfg():
    return ControlCfg(softstart_mode='duty_ramp', loop_arch='track')


def fixed_cfg():
    """修复对照最终配置（= 固件 v2 重建版口径）：ref_ramp 软启动 + limiter 架构 + S8 推荐参数
    + F7 负载跃升前馈 0.13（0.1Ω×G50 counts 口径，物理量与 v2 的 0.26@0.05Ω 等价）"""
    return ControlCfg(softstart_mode='ref_ramp', loop_arch='limiter',
                      kp_v=0.06, ki_v=50.0, load_ff=0.13)


# ---------------- 指标提取 ----------------
def window_metrics(res, t0, t1):
    idx = [k for k, t in enumerate(res.t) if t0 <= t <= t1]
    v = [res.vout[k] for k in idx]
    vmin = min(res.vout_min[k] for k in idx)
    vmax = max(res.vout_max[k] for k in idx)
    i = [res.iload[k] for k in idx]
    il = [res.il_max[k] for k in idx]
    return dict(v_avg=sum(v)/len(v), v_pp=(vmax-vmin), i_avg=sum(i)/len(i), il_pk=max(il))


def settle_time(res, t_event, target=V_TARGET, band=0.12, t_end=None):
    idx = [k for k, t in enumerate(res.t) if t >= t_event]
    last_out = None
    for k in idx:
        if t_end and res.t[k] > t_end: break
        if abs(res.vout[k] - target) > band:
            last_out = res.t[k]
    return 0.0 if last_out is None else last_out - t_event


def state_toggles(res, t0=0.0):
    n, prev = 0, None
    for k, t in enumerate(res.t):
        if t < t0: continue
        s = res.state[k]
        if s in (ST_RUN_CV, ST_RUN_CC):
            if prev is not None and s != prev: n += 1
            prev = s
    return n


# ---------------- 绘图 ----------------
def plot_res(res, title, fname, v_lines=None, ylim=None):
    fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    t_ms = [t*1e3 for t in res.t]
    axes[0].plot(t_ms, res.vout, 'b-', lw=1, label='Vout(平均)')
    axes[0].fill_between(t_ms, res.vout_min, res.vout_max, color='b', alpha=0.25, label='纹波包络')
    axes[0].axhline(V_TARGET, color='r', ls='--', lw=0.8, label='目标12V')
    axes[0].axhline(13.2, color='orange', ls=':', lw=0.8, label='OVP 13.2V')
    axes[0].set_ylabel('Vout (V)'); axes[0].legend(loc='lower right', fontsize=8)
    if ylim: axes[0].set_ylim(*ylim)
    axes[1].plot(t_ms, res.il_max, 'g-', lw=0.8, label='IL峰值包络')
    axes[1].plot(t_ms, res.il_avg, 'k-', lw=1, label='IL平均')
    axes[1].axhline(2.7, color='orange', ls=':', lw=0.8, label='Isat 2.7A')
    axes[1].set_ylabel('IL (A)'); axes[1].legend(loc='lower right', fontsize=8)
    axes[2].plot(t_ms, [d/PWM_PERIOD for d in res.duty], 'm-', lw=1)
    axes[2].set_ylabel('占空比'); axes[2].set_ylim(-0.02, 1.0)
    axes[3].plot(t_ms, res.state, 'b-', lw=1, drawstyle='steps-post')
    axes[3].set_yticks(range(6)); axes[3].set_yticklabels(STATE_NAMES, fontsize=8)
    axes[3].set_ylabel('状态'); axes[3].set_xlabel('时间 (ms)')
    if v_lines:
        for ax in axes:
            for x in v_lines: ax.axvline(x*1e3, color='gray', ls='--', lw=0.8)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    path = os.path.join(RESULT_DIR, fname)
    fig.savefig(path, dpi=130); plt.close(fig)
    return path


# ---------------- 场景 ----------------
def S1_open_loop_check(summary):
    """S1 开环工作点核对（模型自检）"""
    out = []
    for d_counts in (420, 446):
        res = run_open_loop(P, ResLoad(24.0), d_counts, 0.030, mode='switch')
        m = window_metrics(res, 0.025, 0.030)
        d = d_counts / PWM_PERIOD
        vo = 12.0
        for _ in range(50):     # 计及损耗的解析稳态（伏秒平衡）
            il = max(vo, 1.0)/24.0/(1-d)
            vo = 0.5*vo + 0.5*(d*(P.vin - il*P.rds)/(1-d) - P.vf - il*P.dcr + P.vin)
        out.append(dict(duty_counts=d_counts, v_sim=round(m['v_avg'], 3),
                        v_theory_loss=round(vo, 3), v_ideal=round(P.vin/(1-d), 3),
                        dev_vs_loss_pct=round(abs(m['v_avg']-vo)/vo*100, 2),
                        ripple_mv=round(m['v_pp']*1e3, 1),
                        il_pk=round(m['il_pk'], 3), iout=round(m['i_avg'], 3)))
    summary['S1'] = out


def S2_S3_softstart_and_steady(summary):
    """S2 软启动 + S3 CV 稳态纹波（开关模型，24Ω 满载=CC/CV 临界点）"""
    # ---- ASIS：固件原样（缺陷证据：积分器饱和→斜坡推高→必触 OVP）----
    res0 = run_closed_loop(Controller(asis_cfg()), P, ResLoad(24.0), 0.150, mode='switch')
    fault0 = next((res0.t[k] for k, s in enumerate(res0.state) if s == ST_FAULT_OV), None)
    summary['S2_firmware_asis'] = dict(
        cfg='duty_ramp+track（固件原样）', ovp_latch_at_ms=round(fault0*1e3, 1) if fault0 else None,
        verdict='启动必然失败：PI 积分器 1.7ms 内饱和至 612，占空比被斜坡推高越过 OVP 阈值')
    plot_res(res0, 'S2 固件原样软启动 —— 必触 OVP 锁存（缺陷证据）', 'S2_firmware_asis.png', ylim=(0, 16))
    # ---- ASIS-arch：ref_ramp 软启动 + track：暴露 CC/CV 临界点钉死 ----
    cfg_t = ControlCfg(softstart_mode='ref_ramp', loop_arch='track')
    res_t = run_closed_loop(Controller(cfg_t), P, ResLoad(24.0), 0.400, mode='switch')
    m_t = window_metrics(res_t, 0.300, 0.400)
    summary['S3_firmware_track_knee'] = dict(
        cfg='ref_ramp+track（仅换软启动）', v_avg=round(m_t['v_avg'], 4),
        err_pct=round((m_t['v_avg']-V_TARGET)/V_TARGET*100, 3),
        verdict='24Ω=CC/CV 临界点时取小+反算跟踪形成 2 拍极限环，占空比被钉死，稳态误差 -2.3%')
    plot_res(res_t, 'S3 固件 track 结构 @ CC/CV 临界点（24Ω）—— 稳态误差 -2.3%（缺陷证据）',
             'S3_track_knee.png')
    # ---- FIXED：正式验证（待机预充电 4.55V ≈ Vin-Vf，代表"按 ON 键"场景）----
    ctrl = Controller(fixed_cfg())
    res = run_closed_loop(ctrl, P, ResLoad(24.0), 0.400, mode='switch', init_vout=4.55)
    v_max = max(res.vout[:int(0.15/CTRL_TS)])
    v_max = max(res.vout[:int(0.15/CTRL_TS)])
    il_pk = max(res.il_max[:int(0.15/CTRL_TS)])
    ovp = any(s == ST_FAULT_OV for s in res.state[:int(0.15/CTRL_TS)])
    settle = settle_time(res, 0.0, t_end=0.30)
    m = window_metrics(res, 0.300, 0.400)
    summary['S2'] = dict(cfg='ref_ramp+clamp_track（修复对照）',
                         v_overshoot_v=round(max(v_max-V_TARGET, 0), 3), inrush_il_pk=round(il_pk, 3),
                         ovp_false_trigger=ovp, settle_s=round(settle, 4),
                         pass_ovp=(not ovp), pass_overshoot=(v_max-V_TARGET < 0.5),
                         pass_inrush=(il_pk < 2.7))
    summary['S3'] = dict(v_avg=round(m['v_avg'], 4), err_pct=round((m['v_avg']-V_TARGET)/V_TARGET*100, 3),
                         ripple_mv=round(m['v_pp']*1e3, 1), ripple_pct=round(m['v_pp']/V_TARGET*100, 2),
                         il_pk=round(m['il_pk'], 3), iout=round(m['i_avg'], 3),
                         pass_err=(abs(m['v_avg']-V_TARGET) < 0.12), pass_ripple=(m['v_pp'] < 0.36))
    plot_res(res, 'S2+S3 软启动(修复对照)与CV稳态（24Ω满载，开关模型）', 'S2_S3_fixed.png')


def S4_load_step(summary, kp_v=0.05, ki_v=150.0, tag='default', plot=True):
    """S4 CV 负载阶跃：0.5A→0→0.5A（卸载是数字电源最苛刻瞬态）"""
    load = StepProfile([(0.0, CCLoad(0.5)), (0.150, CCLoad(0.0)), (0.300, CCLoad(0.5))])
    cfg = fixed_cfg(); cfg.kp_v, cfg.ki_v = kp_v, ki_v
    ctrl = Controller(cfg)
    res = run_closed_loop(ctrl, P, load, 0.500, mode='switch', init_vout=4.55)
    idx_un = [k for k, t in enumerate(res.t) if 0.150 <= t <= 0.200]
    over = max(res.vout[k] for k in idx_un) - V_TARGET
    idx_ld = [k for k, t in enumerate(res.t) if 0.300 <= t <= 0.350]
    under = V_TARGET - min(res.vout[k] for k in idx_ld)
    ovp_un = any(s in (ST_FAULT_OV, ST_FAULT_OC) for s in res.state[int(0.16/CTRL_TS):int(0.29/CTRL_TS)])
    rec_un = settle_time(res, 0.150)
    rec_ld = settle_time(res, 0.300)
    s4 = dict(kp_v=kp_v, ki_v=ki_v, tag=tag,
              unload_overshoot_mv=round(over*1e3, 1), unload_recover_ms=round(rec_un*1e3, 1),
              load_undershoot_mv=round(under*1e3, 1), load_recover_ms=round(rec_ld*1e3, 1),
              fault_during_unload=ovp_un,
              pass_step=(not ovp_un and over < 0.6 and rec_un < 0.05 and rec_ld < 0.05))
    summary[f'S4_{tag}'] = s4
    if plot:
        plot_res(res, f'S4 CV负载阶跃 0.5A→0→0.5A（kp_v={kp_v}, ki_v={ki_v}, {tag}）',
                 f'S4_{tag}.png', v_lines=[0.15, 0.30])
    return s4


def S5_cc_cv_transition(summary):
    """S5 CC/CV 切换：电阻负载 30Ω→20Ω→30Ω（正规降阻法，CC 段 V≈10V/I=0.5A）
    另附固件原样结构在'欠额'工况（CC 负载 0.55A>限流）下的振荡证据"""
    # ---- FIXED：电阻降阻 ----
    load = StepProfile([(0.0, ResLoad(30.0)), (0.150, ResLoad(20.0)), (0.320, ResLoad(30.0))])
    ctrl = Controller(fixed_cfg())
    res = run_closed_loop(ctrl, P, load, 0.480, mode='switch', init_vout=4.55)
    idx_cc = [k for k, t in enumerate(res.t) if 0.180 <= t <= 0.300]
    i_cc = [res.iload[k] for k in idx_cc]
    v_cc = [res.vout[k] for k in idx_cc]
    i_err = (sum(i_cc)/len(i_cc) - I_TARGET)/I_TARGET*100
    toggles = state_toggles(res, 0.160)
    rec = settle_time(res, 0.320, target=V_TARGET, t_end=0.48)
    summary['S5'] = dict(cfg='ref_ramp+clamp_track（修复对照）',
                         cc_i_avg=round(sum(i_cc)/len(i_cc), 4), cc_err_pct=round(i_err, 2),
                         cc_vout=round(sum(v_cc)/len(v_cc), 3), cc_vout_expected=I_TARGET*20.0,
                         state_toggles_in_cc=toggles, recover_ms=round(rec*1e3, 1),
                         pass_cc=(abs(i_err) < 5), pass_no_osc=(toggles <= 30))
    plot_res(res, 'S5 CC/CV切换 电阻30Ω→20Ω→30Ω（修复对照，开关模型）', 'S5_fixed.png',
             v_lines=[0.15, 0.32])
    # ---- ASIS：欠额工况（CC 负载 0.55A > 0.5A 限流）振荡证据 ----
    load2 = StepProfile([(0.0, ResLoad(30.0)), (0.150, CCLoad(0.55))])
    res2 = run_closed_loop(Controller(ControlCfg(softstart_mode='ref_ramp', loop_arch='track')),
                            P, load2, 0.400, mode='switch')
    tg2 = state_toggles(res2, 0.160)
    idx2 = [k for k, t in enumerate(res2.t) if 0.180 <= t <= 0.380]
    summary['S5_firmware_asis_deficit'] = dict(
        cfg='ref_ramp+track（固件原样）', state_toggles_in_140ms=tg2,
        vout_mean=round(sum(res2.vout[k] for k in idx2)/len(idx2), 3),
        vout_min=round(min(res2.vout[k] for k in idx2), 3),
        vout_max=round(max(res2.vout[k] for k in idx2), 3),
        verdict='欠额工况(CC负载0.55A>限流)输出塌落至二极管直通平台≈4.5V，'
                '限流在D≈0时不可执行（0.55A持续），电流环失去调节能力')
    plot_res(res2, 'S5 固件原样结构 @ 欠额工况（CC负载0.55A）—— CV/CC 抖振（缺陷证据）',
             'S5_asis_deficit.png', v_lines=[0.15])


def S6_short_circuit(summary):
    """S6 短路：满载运行中输出突短路（50mΩ）——电容储能先泻放，随后 OCP 5ms 锁存"""
    load = StepProfile([(0.0, ResLoad(24.0)), (0.150, ResLoad(0.05))])
    ctrl = Controller(fixed_cfg())
    res = run_closed_loop(ctrl, P, load, 0.300, mode='switch', init_vout=4.55)
    idx = [k for k, t in enumerate(res.t) if 0.150 <= t <= 0.170]
    i_pk = max(res.iload[k] for k in idx)
    fault_at = next((res.t[k] for k, s in enumerate(res.state) if s == ST_FAULT_OC), None)
    summary['S6'] = dict(i_capdump_pk=round(i_pk, 3),
                         fault_latched=(fault_at is not None),
                         fault_at_ms=round(fault_at*1e3, 1) if fault_at else None,
                         ocp_delay_ms=round((fault_at-0.150)*1e3, 1) if fault_at else None,
                         i_end=round(res.iload[-1], 3), state_end=STATE_NAMES[res.state[-1]])
    plot_res(res, 'S6 输出突短路（50mΩ）—— OCP 锁存行为（修复对照）', 'S6_short.png', v_lines=[0.15])


def S7_ovp_injection(summary):
    """S7 OVP 注入：运行中把采样计数抬到 3600（>3562）持续 2 拍，应立即锁存且保持"""
    ctrl = Controller(fixed_cfg())
    orig = ctrl.control_10k
    sim_t = [0.0]
    def hooked(v, i):
        if 0.150 <= sim_t[0] < 0.150 + 2*CTRL_TS: v = 3600
        r = orig(v, i)
        sim_t[0] += CTRL_TS
        return r
    ctrl.control_10k = hooked
    res = run_closed_loop(ctrl, P, ResLoad(24.0), 0.250, mode='switch', init_vout=4.55)
    fault_at = next((res.t[k] for k, s in enumerate(res.state) if s == ST_FAULT_OV), None)
    stays = all(s == ST_FAULT_OV for s in res.state[-10:])
    summary['S7'] = dict(inject_at_ms=150, fault_at_ms=round(fault_at*1e3, 1) if fault_at else None,
                         latch_holds=bool(stays), state_end=STATE_NAMES[res.state[-1]],
                         duty_end=res.duty[-1])
    plot_res(res, 'S7 OVP注入（150ms 起 2 拍采样=3600 counts）', 'S7_ovp.png', v_lines=[0.15])


def S10_vin_sag(summary):
    """S10 输入 5.0V→4.75V（10ms 缓变），闭环维持 12V±1%"""
    vin = vin_profile([(0.0, 5.0), (0.100, 5.0), (0.110, 4.75), (0.400, 4.75)])
    ctrl = Controller(fixed_cfg())
    res = run_closed_loop(ctrl, P, ResLoad(24.0), 0.450, vin_func=vin, mode='average',
                          init_vout=4.55)
    idx = [k for k, t in enumerate(res.t) if 0.150 <= t <= 0.400]
    dev = max(abs(res.vout[k] - V_TARGET) for k in idx)
    duty_end = res.duty[-1]/PWM_PERIOD
    summary['S10'] = dict(v_dev_max_mv=round(dev*1e3, 1), duty_end=round(duty_end, 3),
                          duty_limit_ok=(duty_end <= 0.85), pass_sag=(dev < 0.12))
    plot_res(res, 'S10 输入 5.0V→4.75V 跌落（平均模型，修复对照）', 'S10_vin_sag.png',
             v_lines=[0.10, 0.11])


ALL = [S1_open_loop_check, S2_S3_softstart_and_steady, S4_load_step, S5_cc_cv_transition,
       S6_short_circuit, S7_ovp_injection, S10_vin_sag]

if __name__ == '__main__':
    summary = {}
    for fn in ALL:
        print(f'--- {fn.__name__} ---', flush=True)
        fn(summary)
    with open(os.path.join(RESULT_DIR, 'summary_main.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
