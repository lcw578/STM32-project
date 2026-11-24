/**
 * stm32f1xx_it.c（最小版，用于本仓库的最小构建）
 * 只提供固件实际依赖的两个中断向量：
 *   SysTick      —— HAL 时基（HAL_UART_Transmit 超时等依赖 HAL_GetTick）
 *   DMA1_CH1     —— ADC1 连续采样 DMA（循环模式，仅需清标志）
 * TIM2 的 10kHz 控制中断已在 bsp_power.c 内实现（TIM2_IRQHandler）。
 */
#include "main.h"

void SysTick_Handler(void)
{
    HAL_IncTick();
}

void DMA1_Channel1_IRQHandler(void)
{
    /* 循环模式 DMA：清 Channel1 全局中断标志即可（ADC 数据由 bsp 直接读缓冲） */
    DMA1->IFCR = DMA_IFCR_CGIF1;
}
