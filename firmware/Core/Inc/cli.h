/**
 * cli.h —— 串口命令行（调试/整定/保护恢复）
 */
#ifndef CLI_H
#define CLI_H

#include <stdint.h>

void cli_poll(void);          /* 主循环调用，非阻塞 */
void cli_print(const char *s);
void cli_println(const char *s);
void cli_printf_status(void); /* 打印状态行 */

#endif
