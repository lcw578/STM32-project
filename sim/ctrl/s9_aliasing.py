# -*- coding: utf-8 -*-
"""
s9_aliasing.py —— S9 采样链混叠/量化评估（开关模型，limiter 修复对照）

背景：固件 ADC 为连续扫描+DMA（bsp_adc_start），控制环 10kHz 取最新值，
     与 100kHz 开关周期锁相（100µs = 10×10µs 整）→ 采样点落在开关周期内的
     固定相位，读数含与相位有关的静态偏差。电压路有 1k+100nF RC(fc=1.6kHz)
     + 20µs S/H 孔径；电流路（INA180 输出）无 RC，仅靠 20µs 孔径平均。

方法：稳态下对比 (a) 20µs 窗口平均采样（基线，近似 S/H 孔径）与
     (b) 瞬时采样相位 phi = 0~9.5µs 步进 0.5µs 的读数偏差与调节结果偏移。
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctrl import Controller, ControlCfg, counts_to_volts, counts_to_amps
from plant_boost import BoostParams, ResLoad, run_closed_loop

P = BoostParams()
OUT = {}


def run_case(sample_mode, phi=0.0, load_r=24.0, t_end=0.120):
    cfg = ControlCfg(softstart_mode='ref_ramp', loop_arch='limiter')
    ctrl = Controller(cfg)
    res = run_closed_loop(ctrl, P, ResLoad(load_r), t_end, mode='switch',
                          sample_mode=sample_mode, phi=phi, init_vout=4.55)
    idx = [k for k, t in enumerate(res.t) if t >= t_end - 0.02]
    v_true = sum(res.vout[k] for k in idx) / len(idx)
    i_true = sum(res.iload[k] for k in idx) / len(idx)
    v_read = sum(counts_to_volts(res.vout_counts[k]) for k in idx) / len(idx)
    i_read = sum(counts_to_amps(res.iout_counts[k]) for k in idx) / len(idx)
    return dict(v_true=v_true, v_read=v_read, i_true=i_true, i_read=i_read,
                v_err=v_read - v_true, i_err=i_read - i_true)


def main():
    for tag, r in [('24Ω', 24.0), ('30Ω', 30.0)]:
        base = run_case('window', load_r=r)
        rows = []
        ph = 0.0
        while ph < 10e-6 - 1e-9:
            c = run_case('inst', phi=ph, load_r=r)
            rows.append(dict(phi_us=round(ph * 1e6, 1),
                             v_err_mv=round(c['v_err'] * 1e3, 1),
                             i_err_ma=round(c['i_err'] * 1e3, 2)))
            ph += 0.5e-6
        worst_v = max(rows, key=lambda x: abs(x['v_err_mv']))
        worst_i = max(rows, key=lambda x: abs(x['i_err_ma']))
        OUT[tag] = dict(
            baseline_window=dict(v_err_mv=round(base['v_err'] * 1e3, 2),
                                 i_err_ma=round(base['i_err'] * 1e3, 2)),
            inst_phases=rows,
            worst_phase_v=worst_v, worst_phase_i=worst_i,
            note='瞬时采样的读数偏差为固定相位的静态偏差（100µs=10×10µs 锁相）；'
                 '真实链路 20µs S/H 孔径+电压路 RC 使偏差收敛到基线水平')
        print(f'{tag}: 基线 v_err={base["v_err"]*1e3:.2f}mV i_err={base["i_err"]*1e3:.2f}mA | '
              f'最差相位 v {worst_v["v_err_mv"]}mV @phi={worst_v["phi_us"]}µs, '
              f'i {worst_i["i_err_ma"]}mA @phi={worst_i["phi_us"]}µs')
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'results', 'summary_s9.json'), 'w', encoding='utf-8') as f:
        json.dump(OUT, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
