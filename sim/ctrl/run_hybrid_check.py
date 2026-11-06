# -*- coding: utf-8 -*-
"""混合输出电容复核：5x22uF 陶瓷(~55uF eff) + 1x220uF 电解(ESR 80mΩ)
其余全部用重建版参数（Rs1=0.1Ω 固件同步、DCR 0.17、τ 88.3µs）"""
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
plant_boost.INA_GAIN = 5.0
plant_boost.RC_TAU = 8.83e3 * 10e-9
import scenarios
scenarios.ControlCfg = _PatchedCfg

p = scenarios.P
p.dcr = 0.17; p.rds = 0.030; p.vf = 0.45
p.cout = 220e-6; p.esr = 0.08          # 1 颗 220µF/25V 电解（SMD/直插均可）
p.cout_cer = 55e-6; p.esr_cer = 0.005  # 重建版 5×22µF 陶瓷

summary = {'meta': 'hybrid: 220uF electrolytic(80mOhm) + 5x22uF ceramic(55uF eff), Rs1=0.1Ohm synced'}
for fn in scenarios.ALL:
    print(f'--- {fn.__name__} ---', flush=True)
    fn(summary)
scenarios.S4_load_step(summary, kp_v=0.06, ki_v=50.0, tag='hybrid_r5', plot=False)
out = os.path.join(scenarios.RESULT_DIR, 'summary_rebuild_hybrid.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
print('saved:', out)
print(json.dumps({k: summary[k] for k in ('S2','S3','S4_hybrid_r5','S10') if k in summary},
                 ensure_ascii=False, indent=1))
