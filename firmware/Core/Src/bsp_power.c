#include "bsp_power.h"
#include "control.h"

volatile uint16_t adc_raw[2] = {0, 0};

static DMA_HandleTypeDef hdma_adc1;   /* 代码自建，不依赖 .ioc 的 DMA 配置 */

/* ---------- 时钟：HSE 8M ×9 = 72MHz，ADC = PCLK2/6 = 12MHz ---------- */
void bsp_force_clock_72mhz(void)
{
    RCC->CR |= RCC_CR_HSEON;
    while (!(RCC->CR & RCC_CR_HSERDY)) { /* 等待 HSE 稳定 */ }

    FLASH->ACR = FLASH_ACR_PRFTBE | FLASH_ACR_LATENCY_2;  /* 72MHz 需 2 等待周期 */

    /* PLL 关闭状态下才能改配置（复位后 PLL 本就关闭） */
    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_PLLMULL) | RCC_CFGR_PLLMULL9;
    RCC->CFGR |= RCC_CFGR_PLLSRC;                          /* PLL 源 = HSE */
    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_ADCPRE) | RCC_CFGR_ADCPRE_DIV6;

    RCC->CR |= RCC_CR_PLLON;
    while (!(RCC->CR & RCC_CR_PLLRDY)) { }

    RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL) { }

    SystemCoreClockUpdate();
}

/* ---------- GPIO：全部由代码初始化（.ioc 未分配引脚） ---------- */
void bsp_gpio_init(void)
{
    GPIO_InitTypeDef g = {0};
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    /* PA8 = TIM1_CH1 -> 图腾柱：复用推挽（CCR1=0 时输出安全低电平） */
    g.Pin = GPIO_PIN_8; g.Mode = GPIO_MODE_AF_PP; g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);
    /* PA9 = USART1_TX */
    g.Pin = GPIO_PIN_9; HAL_GPIO_Init(GPIOA, &g);
    /* PA10 = USART1_RX 浮空输入 */
    g.Pin = GPIO_PIN_10; g.Mode = GPIO_MODE_INPUT; g.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &g);
    /* PA4/PA5 = ADC 模拟输入 */
    g.Pin = GPIO_PIN_4 | GPIO_PIN_5; g.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &g);

    /* PB0=CV 灯, PB1=CC 灯（高电平点亮，初始灭），PC13=电源/故障灯（初始灭） */
    g.Pin = GPIO_PIN_0 | GPIO_PIN_1;
    g.Mode = GPIO_MODE_OUTPUT_PP; g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &g);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0 | GPIO_PIN_1, GPIO_PIN_RESET);
    g.Pin = GPIO_PIN_13;
    HAL_GPIO_Init(GPIOC, &g);
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
}

/* ---------- TIM1：100kHz PWM，PWM 模式 1，MOE 使能 ---------- */
void bsp_tim1_pwm_init(void)
{
    __HAL_RCC_TIM1_CLK_ENABLE();
    TIM1->CR1   = 0;
    TIM1->PSC   = 0;
    TIM1->ARR   = PWM_TIMER_ARR;
    TIM1->CCR1  = 0;                                   /* 上电安全态：占空比 0 */
    TIM1->CCMR1 = TIM_CCMR1_OC1M_2 | TIM_CCMR1_OC1M_1 | TIM_CCMR1_OC1PE; /* PWM1+预装载 */
    TIM1->CCER  = TIM_CCER_CC1E;
    TIM1->BDTR |= TIM_BDTR_MOE;                        /* 高级定时器必须使能主输出 */
    TIM1->CR1   = TIM_CR1_ARPE | TIM_CR1_CEN;
}

/* ---------- TIM2：10kHz 控制节拍（更新中断，控制环在 ISR 里跑） ---------- */
void bsp_tim2_ctrl_tick_init(void)
{
    __HAL_RCC_TIM2_CLK_ENABLE();
    TIM2->PSC = 71;         /* 72MHz / 72 = 1MHz */
    TIM2->ARR = 99;         /* 1MHz / 100 = 10kHz */
    TIM2->DIER = TIM_DIER_UIE;
    TIM2->SR = 0;
    HAL_NVIC_SetPriority(TIM2_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(TIM2_IRQn);
    TIM2->CR1 = TIM_CR1_CEN;
}

/* 10kHz 控制中断：只做采样 + 控制 + 写 CCR，不做任何阻塞操作。
 * 注意：如果以后在 .ioc 里也启用 TIM2，CubeMX 会在 stm32f1xx_it.c 生成同名
 * 中断函数，这里需改成回调或删除其一，避免重复定义。 */
void TIM2_IRQHandler(void)
{
    if (TIM2->SR & TIM_SR_UIF) {
        TIM2->SR = ~TIM_SR_UIF;
        control_10k();
    }
}

/* 保留给旧主循环轮询用；v2 起控制环已在中断里，不再调用 */
uint8_t bsp_ctrl_tick_due(void)
{
    if (TIM2->SR & TIM_SR_UIF) {
        TIM2->SR = ~TIM_SR_UIF;
        return 1;
    }
    return 0;
}

/* ---------- ADC1：双通道扫描连续 + DMA 循环 + F1 校准 ---------- */
void bsp_adc_start(void)
{
    ADC_ChannelConfTypeDef ch = {0};

    /* 重新配置 ADC1：扫描 + 连续 + 软件触发（与 .ioc 生成参数无关） */
    hadc1.Init.ScanConvMode = ADC_SCAN_ENABLE;
    hadc1.Init.ContinuousConvMode = ENABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = 2;
    HAL_ADC_Init(&hadc1);

    /* 绑定 DMA1_CH1（代码自建句柄），循环模式，半字 */
    __HAL_RCC_DMA1_CLK_ENABLE();
    hdma_adc1.Instance = DMA1_Channel1;
    hdma_adc1.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_adc1.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_adc1.Init.MemInc = DMA_MINC_ENABLE;
    hdma_adc1.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
    hdma_adc1.Init.MemDataAlignment = DMA_MDATAALIGN_HALFWORD;
    hdma_adc1.Init.Mode = DMA_CIRCULAR;
    hdma_adc1.Init.Priority = DMA_PRIORITY_HIGH;
    HAL_DMA_Init(&hdma_adc1);
    __HAL_LINKDMA(&hadc1, DMA_Handle, hdma_adc1);

    ch.Channel = ADC_CHANNEL_4;  ch.Rank = 1;  /* rank1 = Vout (PA4) */
    ch.SamplingTime = ADC_SAMPLETIME_239CYCLES_5;
    HAL_ADC_ConfigChannel(&hadc1, &ch);
    ch.Channel = ADC_CHANNEL_5;  ch.Rank = 2;  /* rank2 = Isense (PA5) */
    HAL_ADC_ConfigChannel(&hadc1, &ch);

    HAL_ADCEx_Calibration_Start(&hadc1);       /* F1 必做校准 */
    HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adc_raw, 2);
}

/* ---------- PWM 写入 / 关断 ---------- */
void bsp_pwm_set(uint16_t ccr)
{
    if (ccr > PWM_DUTY_MAX) ccr = PWM_DUTY_MAX;
    TIM1->CCR1 = ccr;
}

void bsp_pwm_off(void)
{
    TIM1->CCR1 = 0;
}
