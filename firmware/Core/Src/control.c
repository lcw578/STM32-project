/**
 * control.c —— Boost 数字控制（v2：斜坡电压基准 + CV 调节器/电流限幅器）
 *
 * v2 相对 v1 的改动（依据《04_设计审计与整改清单》《05_第二版改版说明》）：
 *   R2 软启动：由"占空比斜坡限幅"改为"斜坡电压基准"（PI 跟踪 v_ref，不再积分饱和）
 *   R3 双环：由"双 PI 取小 + 反算跟踪"改为"CV 调节器 + 电流限幅器"（单调节器，
 *            机理上不存在临界点互钳死锁；CC 段为纯积分限流，无静差）
 *   R4 卸载快斩：电流单拍突降 >400 counts 开启 10 拍窗口，窗口内过压则积分器 ×0.45
 *   R5 PI：kp_v=0.06 / ki_v=50（S8 稳定域中心，DCR=0.17Ω + 真实采样 τ 复算通过）
 *   F7 负载跃升前馈：Δiout>100 counts 时按 0.26×Δiout 直接补积分器，抑制重载跌落
 *   F8 反馈断线保护：占空比高而电压不涨，连续 50 拍锁存；启动前 Vout 联锁
 *
 * 时基：control_10k() 由 TIM2 更新中断调用（10kHz），不在主循环里跑。
 */
#include "control.h"
#include "bsp_power.h"
#include <math.h>

control_cfg_t g_cfg;
volatile run_state_t g_state = ST_STANDBY;
volatile uint16_t    g_duty  = 0;
volatile uint16_t    g_vout  = 0;
volatile uint16_t    g_iout  = 0;

typedef struct { float kp, ki, integ; } pi_t;
static pi_t pi_v;                 /* CV 环（唯一调节器） */
static float lim_integ;           /* 电流限幅器，占空比域 */

static uint16_t ss_cnt;           /* 软启动计数 0..500 */
static uint16_t oc_cnt;           /* 硬过流连续计数 */
static uint16_t fb_cnt;           /* 反馈断线连续计数 */
static uint16_t iout_prev;        /* 上一拍电流（前馈/卸载检测） */
static uint8_t  unload_hold;      /* 卸载快斩授权窗口 */
static uint8_t  cc_dbc, cv_dbc;   /* CC/CV 标志去抖计数 */
static uint32_t blink_cnt;

#define SS_STEPS            500
#define LIM_RELAX           0.2f      /* 临界点附近欠流放松速率（防抖振） */
#define LIM_DEEP_RELAX      1.0f      /* 深度欠流（<0.8×i_set）全速放松，快速脱离钳位 */
#define LIM_DEEP_THRESHOLD  0.8f
#define UNLOAD_DROP_COUNTS  400       /* 单拍电流突降 >0.129A 判为卸载 */
#define UNLOAD_HOLD_TICKS   10
#define FAST_UNWIND_ERR     (-54.0f)  /* ≈ -0.2V */
#define FAST_UNWIND_FACTOR  25.0f
#define LOAD_FF             0.26f     /* 负载跃升前馈系数（S4 扫描：0.26 留 30% 裕度） */
#define LOAD_FF_THRESHOLD   100       /* ≈0.032A，低于此视为噪声 */
#define FB_DUTY_THRESHOLD   500       /* 0.69×720 */
#define FB_VOUT_THRESHOLD   2160      /* 8.0V / 0.0037042 */
#define FB_CONFIRM_TICKS    50        /* 5ms */

static float clampf(float x, float lo, float hi)
{
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

/* 条件积分：未饱和才积分；饱和时只允许误差把输出拉回线性区。
 * 返回值是"本拍开始时的输出"（与原固件一致，一拍延迟）。 */
static float pi_step(pi_t *p, float err)
{
    float out = p->kp * err + p->integ;
    float unsat = out;
    if (out > (float)PWM_DUTY_MAX) out = (float)PWM_DUTY_MAX;
    if (out < 0.0f) out = 0.0f;
    if (unsat < (float)PWM_DUTY_MAX && unsat > 0.0f)
        p->integ += p->ki * CTRL_TS * err;
    else if (unsat >= (float)PWM_DUTY_MAX && err < 0.0f)
        p->integ += p->ki * CTRL_TS * err;
    else if (unsat <= 0.0f && err > 0.0f)
        p->integ += p->ki * CTRL_TS * err;
    p->integ = clampf(p->integ, 0.0f, (float)PWM_DUTY_MAX);
    return out;
}

/* 电流限幅器：过流全速下压；欠流时按电流深度选择放松速率——
 * 深度欠流全速放松（避免一次硬钳位后要几百 ms 才爬回来），
 * 临界点附近 0.2× 慢速放松（防 CC/CV 边界抖振）。 */
static void limiter_update(void)
{
    float e = (float)g_iout - (float)g_cfg.i_set;
    if (e > 0.0f) {
        lim_integ -= g_cfg.ki_i * CTRL_TS * e;
    } else {
        float relax = ((float)g_iout < LIM_DEEP_THRESHOLD * (float)g_cfg.i_set)
                      ? LIM_DEEP_RELAX : LIM_RELAX;
        lim_integ += g_cfg.ki_i * CTRL_TS * (-e) * relax;
    }
    lim_integ = clampf(lim_integ, 0.0f, (float)PWM_DUTY_MAX);
}

/* CV 调节器 + 电流限幅器取小；CV 被限幅期间反算跟踪（防饱和、切换无扰） */
static float limiter_step(void)
{
    float lim;
    float err_v = (float)g_cfg.v_set - (float)g_vout;
    float out_v;

    limiter_update();
    lim = lim_integ;

    /* F7 负载跃升前馈：电流单拍突增时直接补一笔占空比。
     * 门控：只在电流未超过限流点时生效——负载已把电流推过限流点时该由限幅器
     * 下压，前馈再加占空比会把输出顶过 OVP。 */
    {
        int16_t di = (int16_t)((int32_t)g_iout - (int32_t)iout_prev);
        if (di > LOAD_FF_THRESHOLD && g_iout <= (uint16_t)(g_cfg.i_set + 100))
            pi_v.integ = clampf(pi_v.integ + LOAD_FF * (float)di, 0.0f, (float)PWM_DUTY_MAX);
    }

    out_v = pi_v.kp * err_v + pi_v.integ;

    if (out_v > lim || out_v > (float)PWM_DUTY_MAX) {
        float bound = (lim < (float)PWM_DUTY_MAX) ? lim : (float)PWM_DUTY_MAX;
        pi_v.integ = clampf(bound - pi_v.kp * err_v, 0.0f, (float)PWM_DUTY_MAX);
        out_v = pi_v.kp * err_v + pi_v.integ;
    } else if (out_v < 0.0f) {
        pi_v.integ = clampf(-pi_v.kp * err_v, 0.0f, (float)PWM_DUTY_MAX);
        out_v = 0.0f;
    } else {
        if (err_v < 0.0f && unload_hold > 0) {
            /* R4 卸载快斩：撤销泵入源 */
            pi_v.integ *= 0.45f;
        } else if (err_v < FAST_UNWIND_ERR) {
            /* 过压快泄：err_v 本身为负，这里是加法 */
            pi_v.integ += FAST_UNWIND_FACTOR * pi_v.ki * CTRL_TS * err_v;
        } else {
            pi_v.integ += pi_v.ki * CTRL_TS * err_v;
        }
        pi_v.integ = clampf(pi_v.integ, 0.0f, (float)PWM_DUTY_MAX);
        out_v = pi_v.kp * err_v + pi_v.integ;
    }

    out_v = clampf(out_v, 0.0f, (float)PWM_DUTY_MAX);
    if (out_v > lim) out_v = lim;      /* 反算跟踪在 lim<kp·err 时可能越界，硬钳位 */
    /* CC/CV 状态标志 3 拍去抖（只影响 LED 观感，不影响占空比连续性） */
    if (out_v > lim + 4.0f) {
        if (++cc_dbc >= 3) { g_state = ST_RUN_CC; cv_dbc = 0; }
    } else {
        if (++cv_dbc >= 3) { g_state = ST_RUN_CV; cc_dbc = 0; }
    }
    return out_v;
}

void control_init(void)
{
    g_cfg.kp_v = 0.06f;  g_cfg.ki_v = 50.0f;    /* R5 */
    g_cfg.kp_i = 0.02f;  g_cfg.ki_i = 80.0f;    /* kp_i 保留，ki_i 作为限幅器速率 */
    g_cfg.v_set = VSET_DEFAULT_COUNTS;
    g_cfg.i_set = ISET_DEFAULT_COUNTS;
    g_cfg.open_loop = 0;
    g_cfg.open_duty = 0;
    pi_v.kp = g_cfg.kp_v; pi_v.ki = g_cfg.ki_v; pi_v.integ = 0.0f;
    lim_integ = (float)PWM_DUTY_MAX;
    g_state = ST_STANDBY;
    g_duty = 0;
    ss_cnt = oc_cnt = fb_cnt = 0;
    iout_prev = 0;
    unload_hold = 0;
    cc_dbc = cv_dbc = 0;
    bsp_pwm_off();
}

/* 返回 0=已启动，-1=拒绝（故障未清 / 输出未建立） */
int control_start(void)
{
    if (g_state == ST_FAULT_OV || g_state == ST_FAULT_OC || g_state == ST_FAULT_FB)
        return -1;
    /* F8 启动联锁：5V 上电后输出经 L-D 直通约 4.5V（≈1215 counts）；
     * 读数明显偏低说明分压/ADC 链路异常，拒绝开 PWM */
    if (g_vout < 800) return -1;
    g_cfg.open_loop = 0;                 /* D4：不继承上次开环状态 */
    pi_v.integ = 0.0f;
    lim_integ = (float)PWM_DUTY_MAX;
    ss_cnt = 0; oc_cnt = 0; fb_cnt = 0;
    iout_prev = g_iout;
    unload_hold = 0;
    cc_dbc = cv_dbc = 0;
    g_state = ST_SOFTSTART;
    return 0;
}

void control_stop(void)
{
    g_state = ST_STANDBY;
    g_duty = 0;
    bsp_pwm_off();
}

void control_clear_fault(void)
{
    if (g_state == ST_FAULT_OV || g_state == ST_FAULT_OC || g_state == ST_FAULT_FB) {
        g_state = ST_STANDBY;
        g_duty = 0;
        fb_cnt = 0;
        bsp_pwm_off();
    }
}

/* 每 100us 由 TIM2 更新中断调用 */
void control_10k(void)
{
    uint16_t i_now = adc_raw[1];
    int16_t  di    = (int16_t)((int32_t)i_now - (int32_t)iout_prev);
    g_vout = adc_raw[0];
    g_iout = i_now;

    /* 卸载检测：单拍电流突降 → 开 10 拍快斩窗口 */
    if (di < -(int16_t)UNLOAD_DROP_COUNTS)
        unload_hold = UNLOAD_HOLD_TICKS;
    else if (unload_hold > 0)
        unload_hold--;

    /* ---- 保护在所有运行态先跑 ---- */
    if (g_state == ST_SOFTSTART || g_state == ST_RUN_CV || g_state == ST_RUN_CC) {
        if (g_vout > OVP_COUNTS) {                     /* OVP：立即锁存 */
            g_state = ST_FAULT_OV;
            g_duty = 0;
            bsp_pwm_off();
            iout_prev = i_now;
            return;
        }
        if (g_iout > OCP_HARD_COUNTS) {                /* 硬过流：持续 5ms 锁存 */
            if (++oc_cnt >= 50) {
                g_state = ST_FAULT_OC;
                g_duty = 0;
                bsp_pwm_off();
                iout_prev = i_now;
                return;
            }
        } else {
            oc_cnt = 0;
        }
        /* F8 反馈断线：占空比已很高但电压不涨（分压开路/ADC 失效） */
        if (g_state == ST_RUN_CV || g_state == ST_RUN_CC) {
            if (g_duty > FB_DUTY_THRESHOLD && g_vout < FB_VOUT_THRESHOLD) {
                if (++fb_cnt >= FB_CONFIRM_TICKS) {
                    g_state = ST_FAULT_FB;
                    g_duty = 0;
                    bsp_pwm_off();
                    iout_prev = i_now;
                    return;
                }
            } else {
                fb_cnt = 0;
            }
        }
    }

    switch (g_state) {
    case ST_STANDBY:
    case ST_FAULT_OV:
    case ST_FAULT_OC:
    case ST_FAULT_FB:
        g_duty = 0;
        break;

    case ST_SOFTSTART: {
        uint16_t limit = (uint16_t)((uint32_t)PWM_DUTY_MAX * ss_cnt / SS_STEPS);
        float duty;
        if (g_cfg.open_loop) {
            duty = (g_cfg.open_duty < limit) ? (float)g_cfg.open_duty : (float)limit;
        } else {
            /* R2 斜坡电压基准：PI 跟踪 v_ref，积分器不会饱和 */
            float v_ref = (float)g_cfg.v_set * (float)ss_cnt / (float)SS_STEPS;
            float out_v = pi_step(&pi_v, v_ref - (float)g_vout);
            limiter_update();
            duty = (out_v > lim_integ) ? lim_integ : out_v;
            if (duty > (float)limit) duty = (float)limit;   /* 仅作后备限幅 */
        }
        g_duty = (uint16_t)duty;
        bsp_pwm_set(g_duty);
        if (++ss_cnt >= SS_STEPS) g_state = ST_RUN_CV;
        break;
    }

    case ST_RUN_CV:
    case ST_RUN_CC: {
        if (g_cfg.open_loop) {
            g_duty = g_cfg.open_duty;
        } else {
            g_duty = (uint16_t)limiter_step();
        }
        bsp_pwm_set(g_duty);
        break;
    }
    }

    iout_prev = i_now;

    /* ---- 指示灯 ---- */
    if (g_state == ST_FAULT_OV || g_state == ST_FAULT_OC || g_state == ST_FAULT_FB) {
        if (++blink_cnt >= 5000) {
            blink_cnt = 0;
            GPIOC->ODR ^= GPIO_PIN_13;
        }
        GPIOB->BRR  = GPIO_PIN_0 | GPIO_PIN_1;
    } else if (g_state == ST_RUN_CV) {
        GPIOB->BSRR = GPIO_PIN_0;
        GPIOB->BRR  = GPIO_PIN_1 | GPIO_PIN_13;
    } else if (g_state == ST_RUN_CC) {
        GPIOB->BSRR = GPIO_PIN_1;
        GPIOB->BRR  = GPIO_PIN_0 | GPIO_PIN_13;
    } else {
        GPIOB->BRR = GPIO_PIN_0 | GPIO_PIN_1;
        GPIOC->BRR = GPIO_PIN_13;
    }
}

const char *control_state_name(void)
{
    switch (g_state) {
    case ST_STANDBY:    return "STANDBY";
    case ST_SOFTSTART:  return "SOFTSTART";
    case ST_RUN_CV:     return "CV";
    case ST_RUN_CC:     return "CC";
    case ST_FAULT_OV:   return "FAULT_OVP";
    case ST_FAULT_OC:   return "FAULT_OCP";
    case ST_FAULT_FB:   return "FAULT_FB";
    }
    return "?";
}
