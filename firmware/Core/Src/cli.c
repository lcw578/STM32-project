/**
 * cli.c —— 调试命令行（USART1 115200 8N1，轮询收发，非阻塞）
 *
 * 命令表：
 *   on            启动（进入软启动）
 *   off           停机
 *   st            状态：Vout/Iout/占空比/模式/故障
 *   sv <V>        设定电压目标（如 sv 12.0）
 *   si <A>        设定电流目标（如 si 0.5）
 *   d <n>         开环占空比 0..612（同时切换到开环模式）
 *   o             回到闭环
 *   r             清除故障锁存
 *   h             帮助
 */
#include "cli.h"
#include "control.h"
#include "bsp_power.h"
#include "usart.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static char    line[32];
static uint8_t len = 0;

void cli_print(const char *s)
{
    HAL_UART_Transmit(&huart1, (const uint8_t *)s, (uint16_t)strlen(s), 20);
}

void cli_println(const char *s)
{
    cli_print(s);
    cli_print("\r\n");
}

void cli_printf_status(void)
{
    char buf[96];
    /* 开环模式下 g_vout/g_iout 由 control_10k 持续刷新，可直接读数 */
    snprintf(buf, sizeof(buf), "state=%s duty=%u Vout=%.2fV Iout=%.3fA raw=[%u,%u]\r\n",
             control_state_name(), g_duty,
             (float)g_vout * ADC_VOUT_GAIN, (float)g_iout * ADC_IOUT_GAIN,
             g_vout, g_iout);
    cli_print(buf);
}

static void help(void)
{
    cli_println("cmds: on|off|st|sv <V>|si <A>|d <0-612>|o|ovp|clear|h");
}

static void exec(char *l)
{
    char buf[48];
    if (!strcmp(l, "on")) {
        if (control_start() == 0) cli_println("start: softstart 50ms");
        else cli_println("refused: fault latched or Vout too low (check 5V/divider)");
    } else if (!strcmp(l, "off")) {
        control_stop();
        cli_println("stop");
    } else if (!strcmp(l, "st")) {
        cli_printf_status();
    } else if (!strcmp(l, "clear") || !strcmp(l, "r")) {
        control_clear_fault();
        cli_println("fault cleared");
    } else if (!strcmp(l, "o")) {
        __disable_irq();
        g_cfg.open_loop = 0;
        __enable_irq();
        cli_println("closed loop");
    } else if (!strcmp(l, "ovp")) {
        /* OVP 注入测试：目标抬到 13.3V，软启动后越过 13.2V 即锁存。
         * 测试完先 sv 12.0 再 clear，否则下一次 on 会立刻再锁存。 */
        __disable_irq();
        g_cfg.v_set = 3600;                 /* 13.3V > OVP 3562 */
        g_cfg.open_loop = 0;
        __enable_irq();
        if (control_start() == 0)
            cli_println("OVP test: expect FAULT_OVP; then sv 12.0 + clear");
        else
            cli_println("OVP test refused (fault latched or Vout low)");
    } else if (l[0] == 's' && l[1] == 'v' && l[2] == ' ') {
        float v = (float)atof(l + 3);
        if (v < 5.0f) v = 5.0f;
        if (v > 12.8f) v = 12.8f;                 /* 12.8V < OVP 13.2V，防误锁存 */
        __disable_irq();
        g_cfg.v_set = (uint16_t)(v * ADC_VOUT_DIV);
        g_cfg.open_loop = 0;
        __enable_irq();
        snprintf(buf, sizeof(buf), "v_set=%.2fV (%u counts)\r\n", v, g_cfg.v_set);
        cli_print(buf);
    } else if (l[0] == 's' && l[1] == 'i' && l[2] == ' ') {
        float a = (float)atof(l + 3);
        if (a < 0.05f) a = 0.05f;
        if (a > 0.7f) a = 0.7f;                   /* 硬过流之下留裕度 */
        __disable_irq();
        g_cfg.i_set = (uint16_t)(a * ADC_IOUT_DIV);
        g_cfg.open_loop = 0;
        __enable_irq();
        snprintf(buf, sizeof(buf), "i_set=%.2fA (%u counts)\r\n", a, g_cfg.i_set);
        cli_print(buf);
    } else if (l[0] == 'd' && l[1] == ' ') {
        int d = atoi(l + 2);
        if (d < 0) d = 0;
        if (d > (int)PWM_DUTY_MAX) d = (int)PWM_DUTY_MAX;
        if (g_state == ST_STANDBY) {
            /* 待机时给 d 直接开环启动；control_start 会清 open_loop，所以先启动再置位 */
            if (control_start() != 0) {
                cli_println("refused: Vout too low, apply 5V first");
                return;
            }
        }
        __disable_irq();
        g_cfg.open_duty = (uint16_t)d;
        g_cfg.open_loop = 1;
        __enable_irq();
        snprintf(buf, sizeof(buf), "open-loop duty=%d\r\n", d);
        cli_print(buf);
    } else if (!strcmp(l, "h") || !strcmp(l, "?")) {
        help();
    } else if (len) {
        cli_println("unknown cmd, h=help");
    }
}

void cli_poll(void)
{
    uint8_t ch;
    /* 每次 1 字节、0 超时轮询，主循环无阻塞 */
    if (HAL_UART_Receive(&huart1, &ch, 1, 0) == HAL_OK) {
        if (ch == '\r' || ch == '\n') {
            if (len) {
                line[len] = 0;
                exec(line);
                len = 0;
            }
        } else if (ch == 0x08 || ch == 0x7F) {    /* 退格 */
            if (len) len--;
        } else if (len < sizeof(line) - 1 && ch >= 0x20 && ch < 0x7F) {
            line[len++] = (char)ch;
        }
    }
}
