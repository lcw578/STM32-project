# -*- coding: utf-8 -*-
"""LOAD_FF 口径修正验证：0.26(0.05Ω counts 口径) -> 0.13(0.1Ω counts 口径)
跑两种输出方案: cer55=全陶瓷55µF, hybrid=220µF电解+55µF陶瓷"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrl
ctrl.ADC_IOUT_GAIN = 3.3 / (4095.0 * 5.0)
ctrl.ADC_IOUT_DIV = 6204.5
ctrl.ISET_DEFAULT_COUNTS = 3102
ctrl.OCP_HARD_COUNTS = 3723
ctrl.OCP_SOFT_COUNTS = 3412
ctrl.UNLOAD_DROP_COUNTS = 800.0

class _PatchedCfg(ctrl.ControlCfg):
    def __init__(self, **kw):
        kw.setdefault('i_set', ctrl.ISET_DEFAULT_COUNTS)
        kw.setdefault('v_set', ctrl.VSET_DEFAULT_COUNTS)
        super().__init__(**kw)

import plant_boost
from plant_boost import CCLoad, StepProfile, run_closed_loop
plant_boost.INA_GAIN = 5.0
plant_boost.RC_TAU = 8.83e3 * 10e-9
import scenarios
from scenarios import V_TARGET
scenarios.ControlCfg = _PatchedCfg
from ctrl import ST_FAULT_OV, ST_FAULT_OC, CTRL_TS

CAPS = {
    'cer55': dict(cout=44e-6, esr=0.005, cout_cer=11e-6, esr_cer=0.005),
    'hybrid': dict(cout=220e-6, esr=0.08, cout_cer=55e-6, esr_cer=0.005),
}

summary = {}
for tag, cap in CAPS.items():
    p = scenarios.P
    p.dcr = 0.17; p.rds = 0.030; p.vf = 0.45
    for k, v in cap.items():
        setattr(p, k, v)
    for ff in (0.13, 0.20):
        cfg = scenarios.fixed_cfg()
        cfg.load_ff = ff
        load = StepProfile([(0.0, CCLoad(0.5)), (0.150, CCLoad(0.0)), (0.300, CCLoad(0.5))])
        res = run_closed_loop(ctrl.Controller(cfg), p, load, 0.500,
                              mode='switch', init_vout=4.55)
        idx_un = [k for k, t in enumerate(res.t) if 0.150 <= t <= 0.200]
        over = max(res.vout[k] for k in idx_un) - V_TARGET
        idx_ld = [k for k, t in enumerate(res.t) if 0.300 <= t <= 0.350]
        under = V_TARGET - min(res.vout[k] for k in idx_ld)
        ovp = any(s in (ST_FAULT_OV, ST_FAULT_OC)
                  for s in res.state[int(0.16/CTRL_TS):int(0.29/CTRL_TS)])
        rec_u = scenarios.settle_time(res, 0.150)
        rec_l = scenarios.settle_time(res, 0.300)
        summary[f'S4_{tag}_ff{ff}'] = dict(
            load_ff=ff, cap=tag,
            unload_over_mv=round(over*1e3, 1), unload_rec_ms=round(rec_u*1e3, 1),
            load_under_mv=round(under*1e3, 1), load_rec_ms=round(rec_l*1e3, 1),
            fault=ovp,
            ok=(not ovp and rec_u < 0.05 and rec_l < 0.05 and over < 0.6))
        print(f"{tag} ff={ff}: over={over*1e3:.0f}mV({rec_u*1e3:.0f}ms) "
              f"under={under*1e3:.0f}mV({rec_l*1e3:.0f}ms) fault={ovp}", flush=True)

out = os.path.join(scenarios.RESULT_DIR, 'summary_ff_rescale.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
print('saved:', out)
