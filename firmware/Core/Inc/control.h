/**
 * control.h —— CV 调节器 + 电流限幅器 + 保护状态机（v2）
 */
#ifndef CONTROL_H
#define CONTROL_H

#include <stdint.h>

typedef enum {
    ST_STANDBY = 0,   /* PWM 关断，等待 on 命令 */
    ST_SOFTSTART,     /* 斜坡电压基准 0→v_set（50ms） */
    ST_RUN_CV,        /* CV 调节器起作用 */
    ST_RUN_CC,        /* 电流限幅器起作用 */
    ST_FAULT_OV,      /* 过压锁存 */
    ST_FAULT_OC,      /* 过流锁存 */
    ST_FAULT_FB,      /* 反馈断线 / 占空比高而电压不涨，锁存 */
} run_state_t;

/* 运行目标（counts）与整定参数（串口可改） */
typedef struct {
    float    kp_v, ki_v;        /* CV 调节器 PI */
    float    kp_i, ki_i;        /* kp_i 保留；ki_i 作为电流限幅器速率 */
    uint16_t v_set, i_set;      /* 目标（counts） */
    uint8_t  open_loop;         /* 1 = 开环模式（duty 由串口直给） */
    uint16_t open_duty;         /* 开环占空比 */
} control_cfg_t;

extern control_cfg_t      g_cfg;
extern volatile run_state_t g_state;
extern volatile uint16_t  g_duty;          /* 当前输出占空比（CCR1） */
extern volatile uint16_t  g_vout, g_iout;  /* 最近一次采样的实测 counts */

void control_init(void);
int  control_start(void);             /* on：进入软启动；0=成功，-1=拒绝 */
void control_stop(void);              /* off：回到 STANDBY */
void control_clear_fault(void);       /* r：清除锁存 */
void control_10k(void);               /* 10kHz，由 TIM2 更新中断调用 */
const char *control_state_name(void);

#endif
