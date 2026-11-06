/**
 * bsp_power.h —— 板级强制初始化（寄存器级，行为确定性优先）
 *
 * 设计原则：时钟树、PWM、控制时基全部在代码里用寄存器直接配置，
 * 不依赖 CubeMX 生成参数的绝对正确性；.ioc 只负责让工程能编译出
 * HAL 句柄（hadc1 / huart1）。这样固件行为 100% 确定。
 */
#ifndef BSP_POWER_H
#define BSP_POWER_H

#include "stm32f1xx_hal.h"

/* ---- 硬件常数（依据《系统设计方案》§5） ---- */
#define PWM_TIMER_ARR      719u      /* 72MHz / 720 = 100kHz，占空比分辨率 1/720 */
#define PWM_DUTY_MAX       612u      /* 占空比限幅 0.85 × 720 */
#define CTRL_FREQ_HZ       10000u    /* 控制环 10kHz（TIM2） */
#define CTRL_TS            0.0001f   /* 控制周期 100us */

/* ADC 换算系数（VDDA=3.30V 名义值，串口 cal 可校准）
 * 电流链按重建版 Rs1=100mΩ(1206W4F100LT5E) × INA180A2(G=50) = 5 V/A 标定 */
#define ADC_VOUT_GAIN      0.0037042f  /* counts -> V ：×3.3/4095/(10/46) */
#define ADC_IOUT_GAIN      0.00016117f /* counts -> A ：×3.3/4095/(0.1×50) */
/* 反向：目标工程量 -> counts */
#define ADC_VOUT_DIV       269.96f     /* counts per V  = 1/gain */
#define ADC_IOUT_DIV       6204.5f     /* counts per A  = 1/gain */

/* ---- 保护阈值（counts） ----
 * 注意：0.1Ω 采样下 INA180 输出 5V/A，ADC 满量程 3.3V 对应 0.66A——
 * OCP 上限不可超过 0.66A，故硬过流整定 0.8A→0.6A（1.2 倍额定，仍有保护作用） */
#define OVP_COUNTS         3562u    /* 13.2V × 269.96 */
#define OCP_HARD_COUNTS    3723u    /* 0.6A  × 6204.5（0.8A→4.0V 超 ADC 量程，不可用） */
#define OCP_SOFT_COUNTS    3412u    /* 0.55A 软限流告警线 */

/* ---- 运行目标（counts，串口可改） ---- */
#define VSET_DEFAULT_COUNTS  3238u  /* 12.0V */
#define ISET_DEFAULT_COUNTS  3102u  /* 0.5A  */

/* ---- 采样原始值（DMA 循环缓冲，bsp 维护） ---- */
extern volatile uint16_t adc_raw[2];   /* [0]=Vout(PA4) [1]=Isense(PA5) */

void bsp_force_clock_72mhz(void);
void bsp_gpio_init(void);
void bsp_tim1_pwm_init(void);     /* 100kHz，CCR1=0（安全态） */
void bsp_tim2_ctrl_tick_init(void);/* 10kHz 控制节拍（轮询 UIF） */
void bsp_adc_start(void);          /* 重配 ADC1 双通道 + 绑定 DMA + 校准 + 启动 */
uint8_t bsp_ctrl_tick_due(void);   /* 控制节拍到点？ */
void bsp_pwm_set(uint16_t ccr);    /* 写 CCR1（内部限幅 PWM_DUTY_MAX） */
void bsp_pwm_off(void);            /* CCR1=0 并清除输出 */

#endif
