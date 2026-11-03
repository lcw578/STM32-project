# 固件导入、烧录与调试指南（boost_cccv_fw）

> 阶段四交付物：STM32CubeIDE 工程（.ioc）+ 全部源码。
> 架构：寄存器级强制初始化（时钟 72MHz / PWM 100kHz / 控制环 10kHz 全部代码内确定），
> .ioc 只负责让 CubeIDE 生成可编译的 HAL 工程骨架 —— 即使 .ioc 个别配置有偏差，固件行为不变。

## 一、导入工程（路径 A：推荐）

1. 打开 STM32CubeIDE → **File → Import → General → Existing Projects into Workspace**
2. Select root directory 浏览到 `E:\STM32_design\firmware` → 勾选 `boost_cccv_fw` → Finish
3. 如果步骤 2 列表里没有工程（.ioc 未被识别），改用路径 B

## 一、导入工程（路径 B：从 .ioc 新建）

1. **File → New → STM32 Project**，在 Target Selection 对话框顶部找到
   **"STM32Cube: project from existing .ioc file"**（或直接在资源管理器双击 `boost_cccv_fw.ioc`）
2. 选择 `E:\STM32_design\firmware\boost_cccv_fw.ioc` → 工程名保持 `boost_cccv_fw` → Finish
3. CubeMX 视图打开后：核对 **Clock Configuration 页 HSE=8MHz Crystal、SYSCLK=72MHz**
   （若有偏差：HSE 选 Crystal，PLL Source 选 HSE，×9，SYSCLK 选 PLLCLK —— 我们的代码也会强制）
4. 点齿轮 **Project → Generate Code**（会保留 main.c 里 USER CODE 段）

## 二、补充源文件（路径 B 需要）

生成后，把 `Core/Src` 下这些文件复制进工程同名目录（路径 A 已自带）：
`bsp_power.c` `control.c` `cli.c`；`Core/Inc` 下：`bsp_power.h` `control.h` `cli.h`。
（生成器会覆盖 main.c，但 USER CODE 段内的调用会保留；若被覆盖，将 main.c 与生成版比对，
把 USER CODE 2 / WHILE 段内容粘回即可——内容都在本目录 main.c 里。）

## 三、编译与烧录

1. **Project → Build Project**（锤子图标），应 0 error
   （若报 `cli.c` 找不到 `usart.h`：等 CubeMX 首次生成完成后再编译）

> ⚠ **浮点打印**：`cli_printf_status` 用了 `%.2f/%.3f`。CubeIDE 的 newlib-nano 默认不链接
> 浮点 printf，状态行会打不出电压电流。编译前在
> **Project → Properties → C/C++ Build → Settings → MCU Settings** 勾选
> **“Use float with printf from newlib-nano”**（等价于链接参数加 `-u _printf_float`）。

2. 烧录：**Run → Run Configurations → STM32 C/C++ Application** → 新建
   - C/C++ Application 指向编译出的 `boost_cccv_fw.elf`
   - Debugger 页：ST-LINK (ST-LINK GDB server)，Mode: Under Reset / Normal
3. 接线（Blue Pill 验证阶段，不接功率级）：
   - SWD：SWDIO→PA13(SWDIO)，SWCLK→PA14(SWCLK)，GND→GND，3.3V 不接（Blue Pill 自供电 USB）
   - 串口：USB-TTL 模块 RX→PA9(TX)，TX→PA10(RX)，GND 共地，115200 8N1

## 四、Blue Pill 上的验证序列（无功率级）

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 串口连上后回车 | 打印 `=== Boost CCCV PSU fw v1.0 ===` |
| 2 | `st` | state=STANDBY，raw 两路计数随万用表电压变化 |
| 3 | PA4 接 3.3V/GND | raw[0] 满量程/≈0 变化 → ADC 通路正常 |
| 4 | `d 100` | PA8 示波器：100kHz，占空比 ≈13.9%（100/720） |
| 5 | `d 360` | 占空比 50% |
| 6 | `o` `off` | 回到待机，PA8 停止翻转 |

## 五、上自制板联调序列（板子到手后）

1. 上电前：万用表量 5V-GND / 12V-GND 阻抗排短路；ST-Link 只接 SWD
2. 5V 上电 → `st` 看 raw[0]（应 ≈ 4.5V/0.2174 → ~1216 counts，Boost 直通特性）
3. `d 100` 开环小占空比 → 万用表看 12V 母线爬升（几百 mV～1V 量级）
4. 逐步 `d 200/300/400`，观察输出是否按 Boost 关系上升（对照万用表）
5. 一切正常后 `o`（闭环）→ `on` → 软启动到 12V CV
6. 接电子负载（CC 模式 0.1A 起步）→ 观察负载调整率 → 加到 0.5A 看是否切 CC
7. `sv 11.0` / `si 0.4` 等验证设定切换；最后测保护（`ovp` 注入 13.3V 触发 OVP 锁存 →
   `sv 12.0` → `clear` 恢复）

## 六、命令速查

```
on        启动（软启动 50ms）      off      停机
st        状态（V/I/占空比/模式）  clear    清除故障锁存
sv 12.0   电压目标（5~12.8V）      si 0.5   电流目标（0.05~0.7A）
d 300     开环占空比 0..612        o        回闭环
ovp       OVP 注入测试（13.3V，触发后先 sv 12.0 再 clear）
```

> v2 起控制环在 **TIM2 更新中断**里跑（10kHz），主循环只跑命令行；
> 串口打印再慢也不会丢控制拍。`sv` 上限收到 12.8V（< OVP 13.2V），
> OVP 测试请用 `ovp` 命令，避免手滑 `sv 13.5` 把板子锁死。

## 七、与设计文档的偏差说明（报告里如实写）

- 采样架构：《系统设计方案》§5.7 写的是“TIM1 触发注入组逐周期采样”；
  实现采用 **ADC 连续扫描 + DMA 循环 + 10kHz 控制环（TIM2 更新中断）**。
  理由：对 CC/CV 慢速闭环功能等效，免除注入组配置复杂度；v2 起控制环进中断，
  串口打印不再阻塞控制。
- **v2 控制结构**（对应 04 清单 R2~R5 / F7 / F8）：
  - R2 软启动改为**斜坡电压基准** `v_ref = v_set × ss_cnt/500`，PI 跟踪 v_ref；
    原来的“占空比斜坡限幅”会让积分器 1.7ms 饱和、38ms 必触 OVP。
  - R3 双环改为 **CV 调节器 + 电流限幅器**：CV 是唯一调节器，电流环降格为占空比
    限幅器（过流全速下压 / 深度欠流全速放松 / 临界点 0.2× 慢放），单调节器结构
    机理上不存在双环互钳死锁。
  - R4 卸载快斩：电流单拍突降 >400 counts 开 10 拍窗口，窗口内过压则积分器 ×0.45。
  - R5 PI：**kp_v=0.06 / ki_v=50**（DCR=0.17Ω + 真实采样 τ=883µs 复算的稳定域中心）。
  - F7 负载跃升前馈：Δi 突增且未超限流点时，按 0.26×Δi 直接补积分器；
    S4 重载跌落从 5907mV 降到 1969mV（恢复 7.5ms）。
  - F8 反馈断线保护：占空比 >0.69 而 Vout <8V 连续 5ms 锁存 `FAULT_FB`；
    启动前 `Vout<3V` 拒绝开 PWM。
  - CC/CV 状态标志 3 拍去抖，S5 的标志抖动从 1244 次降到 0。
- 旧 PI 初值（kp_v=0.05, ki_v=150）已被 v2 取代；若要用串口在线整定，
  改 `control_init` 里的数值重新烧录即可。
