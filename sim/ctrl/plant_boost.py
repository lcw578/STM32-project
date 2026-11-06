# -*- coding: utf-8 -*-
"""
plant_boost.py —— Boost 功率级被控对象（两档模型）

参数出处：《01_系统设计方案.md》§5 + 重建版原理图（2026-11-05 19:47 快照，sch_work/rebuild_review_20261105/）
  Vin=5V, L=100µH(FSA1365-101MT, DCR=170mΩ), Q1=AO3400A(Rds≈30mΩ@Vgs=5V, 图腾柱驱动),
  D1=SS34(Vf≈0.45V@0.5A), Cout=220µF/250V 电解 C49309214(ESR 未实测, 按 0.3Ω 代表值, 边界 0.15/0.5)
  + 2×22µF X5R 陶瓷(12V 偏压下 ≈22µF),
  Vout 采样 3k+33k/10k 分压(=10/46) + [1k+(36k‖10k)]×10nF RC(τ=88.3µs),
  Isense=100mΩ(1206W4F100LT5E)×INA180A2(G=50) = 5 V/A

模型：
  AverageModel  CCM 状态空间平均 + DCM 钳位，100µs ÷ 10 子步 —— 长场景、参数扫描
  SwitchModel   100kHz 硬开关逐周期仿真，子步 100ns —— 纹波/浪涌/混叠（与 LTspice 交叉验证）

时序（对齐固件）：控制节拍 k 上——先用第 k-1 拍算好的占空比推进被控对象一拍，
再取本拍末 ADC 采样喂给 ctrl.control_10k()，其输出作用于第 k+1 拍。
固件 ADC 为连续扫描+DMA 循环（bsp_adc_start），控制环取最新值，与本离散化等效。

  sample_mode: 'window'  20µs S/H 孔径近似（239.5 周期采样 @12MHz ADCCLK）
               'inst'    瞬时采样（S9 混叠压力测试，phi = 开关周期内相位）
"""
from dataclasses import dataclass, field, replace
from ctrl import (PWM_PERIOD, PWM_DUTY_MAX, CTRL_TS, volts_to_counts)

DIVIDER_GAIN = 10.0 / 46.0        # (R13 3k+R1 33k)/R2 10k 分压
INA_GAIN     = 0.1 * 50.0         # 100mΩ × 50V/V（重建版 Rs1）
RC_TAU       = 8.83e3 * 10e-9     # [1k+(36k‖10k)] × 10nF = 88.3µs


@dataclass
class BoostParams:
    vin: float = 5.0
    L: float = 100e-6
    dcr: float = 0.17        # FSA1365-101MT DCR
    rds: float = 0.030       # AO3400A @Vgs≈5V
    vf: float = 0.45         # SS34 @0.5A
    cout: float = 220e-6     # C49309214 220µF/250V 电解（D16×30 直插）
    esr: float = 0.3         # 250V 高压电解典型 ESR（未实测；0.15~0.5 边界均已仿真通过）
    cout_cer: float = 22e-6  # 2×22µF X5R 1206 25V @12V 偏压 derating 后
    esr_cer: float = 0.005


# ---------------- 负载模型 ----------------
class ResLoad:
    def __init__(self, r): self.r = max(r, 1e-3)
    def current(self, t, v): return v / self.r


class CCLoad:
    """电子负载 CC 模式（~0.3V 合规电压以下线性爬坡，模拟真实电子负载欠压行为）"""
    def __init__(self, i_cmd): self.i_cmd = i_cmd
    def current(self, t, v):
        if v >= 0.3: return self.i_cmd
        if v <= 0.0: return 0.0
        return self.i_cmd * (v / 0.3)


class StepProfile:
    """负载调度：[(t_switch, load_obj), ...]"""
    def __init__(self, schedule):
        self.schedule = sorted(schedule, key=lambda x: x[0])
    def current(self, t, v):
        cur = self.schedule[0][1]
        for ts, ld in self.schedule:
            if t >= ts: cur = ld
            else: break
        return cur.current(t, v)


def vin_const(v):
    return lambda t: v


def vin_profile(points):
    """[(t, vin), ...] 分段线性"""
    def f(t):
        if t <= points[0][0]: return points[0][1]
        for (t0, v0), (t1, v1) in zip(points, points[1:]):
            if t0 <= t <= t1:
                return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
        return points[-1][1]
    return f


# ---------------- 结果容器 ----------------
@dataclass
class SimResult:
    t: list = field(default_factory=list)
    vout: list = field(default_factory=list)       # 拍内平均输出电压
    vout_min: list = field(default_factory=list)   # 拍内瞬时最小/最大（纹波包络）
    vout_max: list = field(default_factory=list)
    il_avg: list = field(default_factory=list)
    il_max: list = field(default_factory=list)     # 拍内电感电流峰值
    il_min: list = field(default_factory=list)
    iload: list = field(default_factory=list)      # 输出电流（Rs 上）
    duty: list = field(default_factory=list)       # 占空比 counts
    state: list = field(default_factory=list)
    vout_counts: list = field(default_factory=list)
    iout_counts: list = field(default_factory=list)


# ---------------- 平均模型 ----------------
class AverageModel:
    """CCM 平均 + DCM 钳位；单等效输出电容（ESR 对 10kHz 以下环路动态影响可忽略）"""
    def __init__(self, p: BoostParams, load):
        self.p, self.load = p, load
        self.il = 0.0
        self.vc = 0.0
        self.C = p.cout + p.cout_cer
        self.esr = p.esr * p.esr_cer / (p.esr + p.esr_cer)
        self.vterm = 0.0
        self.vfilt = 0.0
        self._iload = 0.0
        self._imin = self._imax = 0.0
        self._ilmin = self._ilmax = 0.0

    def precharge(self, v):
        """待机态预充电：D=0 时输出经 L-D 直通自然停在 ≈Vin-Vf"""
        self.vc = v
        self.vterm = v
        self.il = 0.0
        self.vfilt = v * DIVIDER_GAIN

    def tick(self, t, d, sample_mode='window', phi=0.0):
        p, dt = self.p, CTRL_TS / 10
        self._imin = self._imax = self.vterm
        self._ilmin = self._ilmax = self.il
        acc_v = acc_i = acc_il = 0.0
        for _ in range(10):
            i_load = self.load.current(t, max(self.vterm, 0.0))
            vterm = max(self.vc + self.esr * ((1 - d) * self.il - i_load), 0.0)
            dil = (p.vin - self.il * p.dcr - (1 - d) * vterm) / p.L
            il_new = self.il + dil * dt
            if il_new < 0.0:                     # DCM：二极管截止
                self.il = 0.0
                iC = -i_load
            else:
                self.il = il_new
                iC = (1 - d) * self.il - i_load
            self.vc = max(self.vc + iC / self.C * dt, 0.0)
            self.vterm = max(self.vc + self.esr * iC, 0.0)
            self._iload = i_load
            acc_v += self.vterm; acc_i += i_load; acc_il += self.il
            self._imin = min(self._imin, self.vterm); self._imax = max(self._imax, self.vterm)
            self._ilmin = min(self._ilmin, self.il); self._ilmax = max(self._ilmax, self.il)
            t += dt
        self.vfilt += ((self.vterm * DIVIDER_GAIN) - self.vfilt) * (CTRL_TS / RC_TAU)
        n = 10.0
        return (acc_v / n, acc_i / n, acc_il / n,
                volts_to_counts(self.vfilt), volts_to_counts(self._iload * INA_GAIN))


# ---------------- 开关模型 ----------------
class SwitchModel:
    """100kHz 硬开关逐周期模型；双电容(220µF+10µF)各自带 ESR；开关周期与控制节拍锁相"""
    def __init__(self, p: BoostParams, load, dt_sub=100e-9, fs=100e3):
        self.p, self.load = p, load
        self.dt = dt_sub
        self.n_sub_per_tick = int(round(CTRL_TS / dt_sub))          # 1000
        self.n_sub_per_cycle = int(round((1.0 / fs) / dt_sub))      # 100
        self.il = 0.0
        self.vc1, self.vc2 = 0.0, 0.0
        self.vterm = 0.0
        self.vfilt = 0.0
        self._iload = 0.0
        self.win = int(round(20e-6 / dt_sub))                       # 20µs S/H 孔径缓冲
        self.buf_v = [0.0] * self.win
        self.buf_i = [0.0] * self.win
        self.buf_idx = 0
        self._imin = self._imax = 0.0
        self._ilmin = self._ilmax = 0.0

    def precharge(self, v):
        """待机态预充电：D=0 时输出经 L-D 直通自然停在 ≈Vin-Vf"""
        self.vc1 = self.vc2 = v
        self.vterm = v
        self.il = 0.0
        self.vfilt = v * DIVIDER_GAIN
        for j in range(self.win):
            self.buf_v[j] = v * DIVIDER_GAIN
            self.buf_i[j] = 0.0

    def _cap_split(self, i_tot):
        """esr1*iC1 - esr2*iC2 = vc2-vc1 且 iC1+iC2 = i_tot 的电流分配"""
        p = self.p
        iC1 = ((self.vc2 - self.vc1) + p.esr_cer * i_tot) / (p.esr + p.esr_cer)
        return iC1, i_tot - iC1

    def tick(self, t, d, sample_mode='window', phi=0.0, rec=None):
        """rec: 可选 list，非 None 时逐子步追加 (t, vterm, il)（交叉验证绘图用）"""
        p = self.p
        self._imin = self._imax = self.vterm
        self._ilmin = self._ilmax = self.il
        acc_v = acc_i = acc_il = 0.0
        n = self.n_sub_per_tick
        for k in range(n):
            if rec is not None:
                rec.append((t, self.vterm, self.il))
            phase = k % self.n_sub_per_cycle       # 100µs = 10×10µs，锁相
            gate_on = phase < d * self.n_sub_per_cycle
            vterm = max(self.vterm, 0.0)
            i_load = self.load.current(t, vterm)
            if gate_on:
                dil = (p.vin - self.il * (p.dcr + p.rds)) / p.L
                i_tot = -i_load                    # 二极管截止
            else:
                if self.il > 0.0:
                    dil = (p.vin - self.il * p.dcr - p.vf - vterm) / p.L
                    i_tot = self.il - i_load
                else:
                    # DCM 边界：二极管正偏(vin-vf>vterm)则电流从零爬升，否则维持截止
                    dil = max((p.vin - p.vf - vterm) / p.L, 0.0)
                    i_tot = self.il - i_load
            il_new = self.il + dil * self.dt
            if il_new < 0.0:
                self.il = 0.0
                i_tot = -i_load
            else:
                self.il = il_new
            iC1, iC2 = self._cap_split(i_tot)
            self.vc1 += iC1 / p.cout * self.dt
            self.vc2 += iC2 / p.cout_cer * self.dt
            self.vterm = self.vc1 + p.esr * iC1    # ≡ vc2 + esr_cer*iC2
            self._iload = i_load
            self.buf_v[self.buf_idx] = self.vterm * DIVIDER_GAIN
            self.buf_i[self.buf_idx] = self._iload * INA_GAIN
            self.buf_idx = (self.buf_idx + 1) % self.win
            acc_v += self.vterm; acc_i += i_load; acc_il += self.il
            self._imin = min(self._imin, self.vterm); self._imax = max(self._imax, self.vterm)
            self._ilmin = min(self._ilmin, self.il); self._ilmax = max(self._ilmax, self.il)
            t += self.dt
        v_avg, i_avg, il_avg = acc_v / n, acc_i / n, acc_il / n
        # ---- ADC 采样模型 ----
        if sample_mode == 'inst':
            idx = (self.buf_idx - 1 - int(round(phi / self.dt))) % self.win
            v_adc_in, i_adc_in = self.buf_v[idx], self.buf_i[idx]
        else:  # 'window'
            v_adc_in = sum(self.buf_v) / self.win
            i_adc_in = sum(self.buf_i) / self.win
        self.vfilt += (v_adc_in - self.vfilt) * (CTRL_TS / RC_TAU)
        return (v_avg, i_avg, il_avg,
                volts_to_counts(self.vfilt), volts_to_counts(i_adc_in))


# ---------------- 仿真主循环 ----------------
def _drive(plant, res, ctrl, t, duty_counts, v_cnt, i_cnt, record):
    v_avg, i_avg, il_avg, vc, ic = plant.tick(t, duty_counts / PWM_PERIOD, record.mode, record.phi)
    ctrl.control_10k(vc, ic)   # 本拍末采样 → 控制决策（作用于下一拍）
    res.t.append(t + CTRL_TS)
    res.vout.append(v_avg)
    res.vout_min.append(plant._imin); res.vout_max.append(plant._imax)
    res.il_avg.append(il_avg)
    res.il_max.append(plant._ilmax); res.il_min.append(plant._ilmin)
    res.iload.append(i_avg)
    res.duty.append(ctrl.duty)
    res.state.append(ctrl.state)
    res.vout_counts.append(vc); res.iout_counts.append(ic)


class _SampleCfg:
    def __init__(self, mode='window', phi=0.0):
        self.mode, self.phi = mode, phi


def run_closed_loop(ctrl, params: BoostParams, load, t_end, vin_func=None,
                    mode='switch', sample_mode='window', phi=0.0,
                    dt_sub=100e-9, do_start=True, init_vout=None):
    """闭环：10kHz 节拍，采样→控制→（下一拍）作用；init_vout 用于待机预充电"""
    params = replace(params)                  # 防止 vin 调度污染共享参数对象
    vin_func = vin_func or vin_const(params.vin)
    plant = (SwitchModel(params, load, dt_sub=dt_sub) if mode == 'switch'
             else AverageModel(params, load))
    if init_vout is not None:
        plant.precharge(init_vout)
    res = SimResult()
    rec = _SampleCfg(sample_mode, phi)
    if do_start:
        ctrl.start()
    n_ticks = int(round(t_end / CTRL_TS))
    for k in range(n_ticks):
        t = k * CTRL_TS
        plant.p.vin = vin_func(t)
        _drive(plant, res, ctrl, t, ctrl.duty, 0, 0, rec)
    return res


def run_open_loop(params: BoostParams, load, duty_counts, t_end, vin_func=None,
                  mode='switch', dt_sub=100e-9):
    """开环：固定占空比（S1 工作点核对、T1 交叉验证）"""
    params = replace(params)
    vin_func = vin_func or vin_const(params.vin)
    plant = (SwitchModel(params, load, dt_sub=dt_sub) if mode == 'switch'
             else AverageModel(params, load))
    res = SimResult()
    rec = _SampleCfg('window')
    stub = type('OL', (), {'duty': int(min(max(duty_counts, 0), PWM_DUTY_MAX)),
                           'state': 0,
                           'control_10k': lambda self, v, i: self.duty})()
    n_ticks = int(round(t_end / CTRL_TS))
    for k in range(n_ticks):
        t = k * CTRL_TS
        plant.p.vin = vin_func(t)
        _drive(plant, res, stub, t, stub.duty, 0, 0, rec)
    return res
