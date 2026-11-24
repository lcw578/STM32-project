/**
 * stm32f1xx_hal_msp.c（最小版，用于本仓库的最小构建）
 *
 * 作用：补齐 CubeMX 生成工程里 stm32f1xx_hal_msp.c 的时钟/引脚使能。
 * 仓库只带了 Core/ 的 5 个业务文件，缺此文件时：
 *   - USART1 时钟未使能 → HAL_UART_Init 等 UE 位死循环 → 串口完全无输出；
 *   - ADC1 时钟未使能 → 采样不工作。
 * 本文件即原工程该生成文件的最小等价物。
 */
#include "main.h"

void HAL_MspInit(void)
{
    __HAL_RCC_AFIO_CLK_ENABLE();
    __HAL_RCC_PWR_CLK_ENABLE();
}

void HAL_ADC_MspInit(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance == ADC1)
    {
        __HAL_RCC_ADC1_CLK_ENABLE();
    }
}

void HAL_UART_MspInit(UART_HandleTypeDef *huart)
{
    GPIO_InitTypeDef gpio = {0};

    if (huart->Instance == USART1)
    {
        __HAL_RCC_USART1_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* PA9 = USART1_TX，复用推挽 */
        gpio.Pin   = GPIO_PIN_9;
        gpio.Mode  = GPIO_MODE_AF_PP;
        gpio.Speed = GPIO_SPEED_FREQ_HIGH;
        HAL_GPIO_Init(GPIOA, &gpio);

        /* PA10 = USART1_RX，输入上拉（防悬空误触发） */
        gpio.Pin  = GPIO_PIN_10;
        gpio.Mode = GPIO_MODE_INPUT;
        gpio.Pull = GPIO_PULLUP;
        HAL_GPIO_Init(GPIOA, &gpio);
    }
}
