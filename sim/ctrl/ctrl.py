# -*- coding: utf-8 -*-
"""
ctrl.py —— firmware/Core/Src/control.c 的逐行 Python 移植（仿真权威 = C 代码）

移植纪律：
  1. 常数全部来自 bsp_power.h，不重新设计；
  2. pi_step / pi_track / 状态机 / 软启动 / 保护逻辑与 control.c 逐行对应；
  3. C 语言的 uint16 截断（g_duty = (uint16_t)duty）用 int() 截断复现；
  4. 控制器全部在 counts 域运算（与固件一致），物理量换算只发生在采样接口。
"""
from dataclasses import dataclass, field

# ---- 硬件常数（bsp_power.h） ----
PWM_TIMER_ARR = 719
PWM_PERIOD    = 720          # 占空比分辨率 1/720
PWM_DUTY_MAX  = 612          # 0.85 × 720
CTRL_TS       = 0.0001       # 100us，10kHz（TIM2 节拍）
SS_STEPS      = 500          # 软启动 50ms

# —— limiter 修复对照专用常数（固件未改动） ——
# 不对称积分快泄：卸载(负载释放)后 Boost 无负载泵升使 Vout 快速爬升，
# P 项与常规积分退火速度均不足以在 OVP(13.2V) 前把占空比压回 DCM 边界，
# 过压超过 0.2V 时积分器以 8 倍 ki_v 速率快泄（S8/S4 实验确定的解法）
FAST_UNWIND_ERR_COUNTS = -54.0   # ≈ -0.2V
FAST_UNWIND_FACTOR     = 25.0
UNLOAD_DROP_COUNTS     = 400.0   # 单拍电流突降 >0.129A 判定为卸载（电子负载硬阶跃特征）

ADC_VOUT_GAIN = 0.0037042    # counts -> V
ADC_IOUT_GAIN = 0.00032234   # counts -> A
ADC_VOUT_DIV  = 269.96       # counts/V
ADC_IOUT_DIV  = 3102.3       # counts/A

OVP_COUNTS       = 3562      # 13.2V，立即锁存
OCP_HARD_COUNTS  = 2482      # 0.8A，持续 50 拍（5ms）锁存
OCP_SOFT_COUNTS  = 2172      # 0.7A（固件定义但未引用，仅存档）

VSET_DEFAULT_COUNTS = 3238   # 12.0V
ISET_DEFAULT_COUNTS = 1551   # 0.5A

ADC_FULL_SCALE = 4095        # 12bit
ADC_VREF       = 3.30


# 状态机（control.h run_state_t）
ST_STANDBY, ST_SOFTSTART, ST_RUN_CV, ST_RUN_CC, ST_FAULT_OV, ST_FAULT_OC = range(6)
STATE_NAMES = ["STANDBY", "SOFTSTART", "CV", "CC", "FAULT_OVP", "FAULT_OCP"]


def counts_to_volts(c): return c * ADC_VOUT_GAIN
def counts_to_amps(c):  return c * ADC_IOUT_GAIN
def volts_to_counts(v):
    """ADC 量化：12bit，满量程 3.3V，round（HAL 右对齐原始码）。"""
    raw = int(round(v / ADC_VREF * ADC_FULL_SCALE))
    return max(0, min(ADC_FULL_SCALE, raw))


@dataclass
class PI:
    """control.c pi_t + pi_step + pi_track（逐行对应）"""
    kp: float
    ki: float
    integ: float = 0.0

    def step(self, err: float) -> float:
        out = self.kp * err + self.integ
        unsat = out
        if out > PWM_DUTY_MAX: out = float(PWM_DUTY_MAX)
        if out < 0.0:          out = 0.0
        # 条件积分：未饱和才积分；饱和时只允许误差把输出拉回线性区
        if unsat < PWM_DUTY_MAX and unsat > 0.0:
            self.integ += self.ki * CTRL_TS * err
        elif unsat >= PWM_DUTY_MAX and err < 0.0:
            self.integ += self.ki * CTRL_TS * err
        elif unsat <= 0.0 and err > 0.0:
            self.integ += self.ki * CTRL_TS * err
        if self.integ > PWM_DUTY_MAX: self.integ = float(PWM_DUTY_MAX)
        if self.integ < 0.0:          self.integ = 0.0
        return out

    def track(self, err: float, duty: float):
        """未选中环的反算跟踪，切换瞬间输出连续（固件原样）"""
        self.integ = duty - self.kp * err
        if self.integ > PWM_DUTY_MAX: self.integ = float(PWM_DUTY_MAX)
        if self.integ < 0.0:          self.integ = 0.0

    def clamp_track(self, err: float, duty: float):
        """仿真侧修复对照：未选中环条件积分、输出钳位到选中环 duty。
        输出未超过 duty 时允许积分（可从下方逼近），超过则钳到 duty - kp*err。
        既保持切换无扰，又不产生'取小+反算'在双误差同号时的极限环。"""
        integ_try = self.integ + self.ki * CTRL_TS * err
        out_try = self.kp * err + integ_try
        if out_try > duty:
            integ_try = duty - self.kp * err
        self.integ = min(max(integ_try, 0.0), PWM_DUTY_MAX)


@dataclass
class ControlCfg:
    kp_v: float = 0.05
    ki_v: float = 150.0
    kp_i: float = 0.02
    ki_i: float = 80.0
    v_set: int = VSET_DEFAULT_COUNTS
    i_set: int = ISET_DEFAULT_COUNTS
    open_loop: int = 0
    open_duty: int = 0
    # 软启动实现方式：
    #   'duty_ramp' = 固件原样（control.c：斜坡限幅占空比，PI 自由积分）
    #   'ref_ramp'  = 仿真侧修复对照（斜坡给定电压基准，教科书做法）——仅用于
    #                 验证"其余设计在推荐修复下是否成立"，固件文件未改动
    softstart_mode: str = 'duty_ramp'
    # 双环取小后未选中环的处理：
    #   'track'       = 固件原样（integ = duty - kp*err 反算跟踪）
    #   'clamp_track' = 中间尝试（未选中环钳位到选中环 duty）——正反向均会死锁，仅存档
    #   'limiter'     = 仿真侧修复对照（工业标准结构）：CV 环为唯一调节器，电流环降格为
    #                   占空比"限幅器"（过流下压/欠流放松），CV 环被限幅期间反算跟踪。
    #                   单调节器结构，机理上不存在双环互钳死锁
    loop_arch: str = 'track'
    # limiter 架构欠流放松速率比例（过流下压用全速 ki_i；欠流放松用 ki_i×lim_relax，
    # 非对称速率防止限幅器与 CV 环在 CC/CV 临界点互相追逐形成低频极限环）
    lim_relax: float = 0.2
    # 卸载快斩下限（占 PWM_DUTY_MAX 的比例）：0 = 原行为（积分器可被清零，
    # 重载时从 0 重建 → 5.9V 跌落）；>0 时快斩不会把积分器压到该下限以下
    unload_floor: float = 0.0
    # 负载跃升前馈：单拍电流上升超过 100 counts 时，按 load_ff × Δiout 直接给
    # 积分器加一笔占空比，抵消 10kHz 环路来不及建占空比造成的跌落
    load_ff: float = 0.0
    load_ff_threshold: int = 100


class Controller:
    """control.c 控制器主体：control_init / control_start / control_10k"""

    def __init__(self, cfg: ControlCfg | None = None):
        self.cfg = cfg or ControlCfg()
        self.init()

    def init(self):
        c = self.cfg
        self.pi_v = PI(c.kp_v, c.ki_v)
        self.pi_i = PI(c.kp_i, c.ki_i)
        self.state = ST_STANDBY
        self.duty = 0            # g_duty（counts）
        self.vout = 0            # g_vout counts
        self.iout = 0            # g_iout counts
        self.ss_cnt = 0
        self.oc_cnt = 0
        self._iout_prev = 0
        self._unload_hold = 0
        self._cc_dbc = 0
        self._cv_dbc = 0
        self.lim_integ = float(PWM_DUTY_MAX)   # limiter 架构的电流限幅器（占空比域）

    def start(self):
        if self.state in (ST_FAULT_OV, ST_FAULT_OC):
            return
        self.pi_v.integ = 0; self.pi_i.integ = 0
        self.lim_integ = float(PWM_DUTY_MAX)
        self.ss_cnt = 0; self.oc_cnt = 0
        self.state = ST_SOFTSTART

    def stop(self):
        self.state = ST_STANDBY
        self.duty = 0

    def clear_fault(self):
        if self.state in (ST_FAULT_OV, ST_FAULT_OC):
            self.state = ST_STANDBY
            self.duty = 0

    def control_10k(self, vout_counts: int, iout_counts: int) -> int:
        """每 100us 调用一次；输入为 DMA 采样原始 counts；返回本拍占空比 counts"""
        self._iout_prev = self.iout
        self.vout = vout_counts
        self.iout = iout_counts
        c = self.cfg
        # 卸载事件窗口：电流单拍突降后 10 拍内授权"快斩"（配合 err_v<0 使用）
        if (self._iout_prev - self.iout) > UNLOAD_DROP_COUNTS:
            self._unload_hold = 10
        elif self._unload_hold > 0:
            self._unload_hold -= 1

        # ---- 保护在所有运行态先跑（含软启动） ----
        if self.state in (ST_SOFTSTART, ST_RUN_CV, ST_RUN_CC):
            if self.vout > OVP_COUNTS:
                self.state = ST_FAULT_OV
                self.duty = 0
                return self.duty
            if self.iout > OCP_HARD_COUNTS:
                self.oc_cnt += 1
                if self.oc_cnt >= 50:
                    self.state = ST_FAULT_OC
                    self.duty = 0
                    return self.duty
            else:
                self.oc_cnt = 0

        if self.state in (ST_STANDBY, ST_FAULT_OV, ST_FAULT_OC):
            self.duty = 0

        elif self.state == ST_SOFTSTART:
            limit = int(PWM_DUTY_MAX * self.ss_cnt / SS_STEPS)   # C 整数除法语义
            if c.open_loop:
                duty = float(min(c.open_duty, limit))
                self.duty = int(duty)
            elif c.softstart_mode == 'ref_ramp':
                # 仿真侧修复对照：斜坡电压基准，PI 调节跟踪给定（无积分器饱和）
                v_ref = c.v_set * self.ss_cnt / SS_STEPS
                duty = self.pi_v.step(v_ref - float(self.vout))
                if duty > limit: duty = float(limit)             # 限幅仅作后备
                if c.loop_arch == 'limiter':
                    duty = min(duty, self._limiter_update())     # 软启动期间限流器同样生效
                else:
                    self._track_i(float(c.i_set - self.iout), duty)
                self.duty = int(duty)
            else:
                duty = self.pi_v.step(float(c.v_set - self.vout))
                if duty > limit: duty = float(limit)
                self._track_i(float(c.i_set - self.iout), duty)
                self.duty = int(duty)                            # (uint16_t) 截断
            self.ss_cnt += 1
            if self.ss_cnt >= SS_STEPS:
                self.state = ST_RUN_CV

        elif self.state in (ST_RUN_CV, ST_RUN_CC):
            if c.open_loop:
                self.duty = c.open_duty
            elif c.loop_arch == 'limiter':
                self.duty = int(self._limiter_step())
            else:
                duty_v = self.pi_v.step(float(c.v_set - self.vout))
                duty_i = self.pi_i.step(float(c.i_set - self.iout))
                duty = duty_v if duty_v < duty_i else duty_i     # 取小：CC/CV 无扰切换
                if duty > PWM_DUTY_MAX: duty = float(PWM_DUTY_MAX)
                if duty < 0.0:          duty = 0.0
                self.state = ST_RUN_CV if duty_v <= duty_i else ST_RUN_CC
                err_i = float(c.i_set - self.iout)
                err_v = float(c.v_set - self.vout)
                if self.state == ST_RUN_CV:
                    self._track_i(err_i, duty)
                else:
                    self._track_v(err_v, duty)
                self.duty = int(duty)

        # bsp_pwm_set 内部限幅
        return min(self.duty, PWM_DUTY_MAX)

    def _track_i(self, err_i: float, duty: float):
        if self.cfg.loop_arch == 'clamp_track':
            self.pi_i.clamp_track(err_i, duty)
        else:
            self.pi_i.track(err_i, duty)

    def _track_v(self, err_v: float, duty: float):
        if self.cfg.loop_arch == 'clamp_track':
            self.pi_v.clamp_track(err_v, duty)
        else:
            self.pi_v.track(err_v, duty)

    # ---- limiter 架构（仿真侧修复对照） ----
    def _limiter_update(self) -> float:
        """电流限幅器：过流全速下压、欠流放松。
        深度欠流（iout < 0.8×i_set）时全速放松，避免一次硬钳位后要几百 ms 才爬回来；
        临界点附近仍用 lim_relax 慢速放松，防 CC/CV 边界抖振。"""
        c = self.cfg
        if self.iout > c.i_set:
            self.lim_integ -= c.ki_i * CTRL_TS * (self.iout - c.i_set)
        else:
            relax = 1.0 if self.iout < 0.8 * c.i_set else c.lim_relax
            self.lim_integ += c.ki_i * CTRL_TS * (c.i_set - self.iout) * relax
        self.lim_integ = min(max(self.lim_integ, 0.0), float(PWM_DUTY_MAX))
        return self.lim_integ

    def _limiter_step(self) -> float:
        """CV 环唯一调节器 + 电流限幅器取小；CV 被限幅期间反算跟踪（防饱和、切换无扰）"""
        c = self.cfg
        lim = self._limiter_update()
        # 负载跃升前馈：电流单拍突增时直接补占空比，避免积分器从 0 慢慢爬。
        # 门控：只在电流未超过限流点（i_set+100）时生效——负载把电流推过限流点时
        # 该由限幅器下压，前馈再加占空比会把输出顶过 OVP。
        di = self.iout - self._iout_prev
        if c.load_ff > 0.0 and di > c.load_ff_threshold and self.iout <= c.i_set + 100:
            self.pi_v.integ = min(self.pi_v.integ + c.load_ff * di, float(PWM_DUTY_MAX))
        err_v = float(c.v_set - self.vout)
        out_v = c.kp_v * err_v + self.pi_v.integ
        limited = out_v > lim
        if out_v > lim or out_v > PWM_DUTY_MAX:
            bound = min(lim, float(PWM_DUTY_MAX))
            self.pi_v.integ = min(max(bound - c.kp_v * err_v, 0.0), float(PWM_DUTY_MAX))
            out_v = c.kp_v * err_v + self.pi_v.integ
        elif out_v < 0.0:
            self.pi_v.integ = min(max(-c.kp_v * err_v, 0.0), float(PWM_DUTY_MAX))
            out_v = 0.0
        else:
            if err_v < 0.0 and self._unload_hold > 0:
                # 卸载快斩：卸载瞬间电感储能+原占空比泵入以 ~2V/ms 推高 Vout，
                # 10kHz 环路来不及响应（6 拍即触 OVP）；电流单拍突降开启 10 拍授权
                # 窗口，窗口内且出现过压趋势即让积分器塌向 DCM，撤销泵入源
                cut = self.pi_v.integ * 0.45
                floor = c.unload_floor * float(PWM_DUTY_MAX)
                self.pi_v.integ = cut if cut > floor else floor
            elif err_v < FAST_UNWIND_ERR_COUNTS:
                # 过压快泄：err_v<0 时按 factor 倍速快速退火（注意是加法，err_v 本身为负）
                self.pi_v.integ += FAST_UNWIND_FACTOR * c.ki_v * CTRL_TS * err_v
            else:
                self.pi_v.integ += c.ki_v * CTRL_TS * err_v
            self.pi_v.integ = min(max(self.pi_v.integ, 0.0), float(PWM_DUTY_MAX))
            out_v = c.kp_v * err_v + self.pi_v.integ
        out_v = min(max(out_v, 0.0), float(PWM_DUTY_MAX))
        out_v = min(out_v, lim)          # 反算跟踪在 lim<kp·err 时可能越界，硬钳位
        if out_v > lim + 4.0:
            self._cc_dbc += 1; self._cv_dbc = 0
            if self._cc_dbc >= 3: self.state = ST_RUN_CC
        else:
            self._cv_dbc += 1; self._cc_dbc = 0
            if self._cv_dbc >= 3: self.state = ST_RUN_CV
        return min(out_v, lim)
