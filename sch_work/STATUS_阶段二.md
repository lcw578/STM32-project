# 阶段二原理图 — 状态（2026-11-02 第三轮后：电气设计完成 ✅）

## ✅ 最终状态（saved:true，sch check 权威结论）
- **0 floating pin / 0 multi-net wire / 0 net-marker mismatch / 0 dangling / 0 out-of-sheet / 0 图签侵入**
- 42 器件、22 网络、90+ 旗子全部电气连通且网名一致
- 2 处导线交叉已验证"无接触"（合法，INFO 级）
- 剩余 28 项全部为视觉类（不阻塞、不影响网表）：12 旗子图形重叠、5 个反挂旗（旗面方向，不影响电气）、1 冗余旗、1 重复旗、2 个可选装饰（分区框/图签字段）
- 处理方式：报告排版阶段用 `sch destagger` 一键错位 + `sch modify --rotation` 转正，或直接保留（电气正确）

## 关键工艺记录（答辩可讲）
- 器件全部来自立创商城库（带封装+C号），符号引脚实测后离线计算布线
- 手动 netflag 的旗子锚点与连接引脚存在 10~15 偏移 → 改用 `sch connect`（自动评分）
- 走廊布线纪律：垂直通道不得穿越横向桩线带（合并短路），长线改网络标签
- 分压采样链、功率链、晶振网络的几何布局经过 6 轮 check→修复→回读迭代

## ✅ 阶段三 PCB 完成记录（2026-11-03）
- 板框 70×50mm 圆角（免费打样额度内）；42 器件功能区布局（功率上带/栅极驱动中带/控制下带/采样右下）
- 布线 27/27 网络官方路由器布通（358 轨道 + 27 过孔）；双面 GND 铺铜；四角 M3；丝印避让
- **DRC PASSED（0 违规）**；Gerber 已导出：E:\STM32_design\嘉立创打样文件_70x50mm.zip
- 待人工：嘉立创下单（上传 zip，选 2 层板 70×50mm，免费额度）+ 立创商城 BOM 下单（sch_work/devices_selected.json）+ 可选 SMT 贴片
- 工艺要点：pcb modify 需 --center；布局后必须 pcb save；铺铜后 pour-rebuild 再 DRC；GND 连接类违规用"清空重布（含 GND）"解决

---
## 阶段三入口
- `easyeda pcb --help` 命令族；板框 70×50mm 两层板；功率/控制分区
- BOM 已定稿：sch_work/devices_selected.json

---
（以下为历史记录）


## ✅ 当前状态（已保存 saved:true，最新 check：55 findings）
- 42 器件、22 网络、90+ 网络旗全部就位
- **0 悬空导线、0 线压引脚、0 重复图元区、图签侵入已清**
- major 架构问题已解决：U1 西走廊全部改用 `sch connect`（自动评分定位）+ 交替偏移 25/45 重建；W13/W14 垂直通道已废除（OSC_IN/OSC_OUT 改用网络标签方式：U1.5/U1.6 短桩 + Y1 侧短桩 + 同名旗）
- C12 已挪 (655,760)，C10 已挪 (880,560)

## 🔧 剩余电气问题（下一轮优先）
1. **1 个 floating pin**：跑 `sch check` 看具体引脚（大概率是 C13.1 或 U3.2 相关）
2. **1 个 multi-net wire**：定位并删除（分压/采样区 x 750-880, y 560-780 附近，VMID/VSENSE/3V3 有残留交叉污染）
3. **8 个 net-marker-mismatch**：集中在 (750-880, 620-780) 分压采样区 —— R11.1 的 VMID 桩(820-844,620)、C10 新位置 (880,560) 的 VSENSE 桩、C9.1 的 3V3 桩 (830-860,760) 三者需要逐一核对几何，删除错误桩重连
4. **2 个 wire-crossing ERROR** @(40,785)(270,560)：合法交叉（已验证无接触证据）——可接受或微调桩长消除

## 🎨 视觉类（不阻塞，最后做）
- 8 个反挂旗：`sch check` 输出里每条都给了"应为 N"，用 `sch modify --id <pid> --rotation N`
- 11 个旗重叠：`sch destagger` 自动错位
- 12 个 out-of-sheet：旧 C12/C13 位置的残留旗和桩 (580,850)(620,850) —— fix9 删过一轮，可能还有桩线残留，按位置删除
- 2 missing-deliverable：分区框/图签 —— 用 `sch frame apply` 或忽略

## ⚠️ 工具坑备忘（重要！）
- `netflag --kind net_label/net_port_bi` 假成功（ok:true 但不落地）→ 信号旗一律用 `--kind power` + 自定义网名
- `sch connect` 是最可靠的连接方式（自动评分布局+旗子姿态正确）→ 手动 wire+netflag 只在 connect 拒绝时用
- 连接器降级时"假失败"常见 → 失败后必须先轻查询验证再重试
- 重查询 `--include-pins` 页面大时超时 → 分轻查询 + 离线几何推算
- **垂直通道 + 横向桩线 = 必然合并短路**：U1 西走廊禁止任何垂直走线
- `sch connect` 对同一引脚重复调用会再加一根桩（冗余）→ 连接前先查该脚是否已有桩

## 下一步
1. 清完上面 3 项电气问题 → check 到 0 ERROR/0 multi-net → save
2. `sch netlist --type kicad` 导出 + 与设计对账 → `sch export-image` 归档（export 需先 doc reload）
3. 阶段三：PCB（`easyeda pcb` 命令族，70×50mm 两层板，功率/控制分区）

## ✅ 已完成
- 42 个器件全部放置（boost-cccv-psu 工程 P1 页，A4 图纸 1170×825 raw）
- 22 个电气网络全部建立并有旗子：GND(33) 3V3(14) VIN_5V(5) VOUT(2) VLOAD(2) PWM(2) GATE(2) NRST(2) BOOT0(2) SWDIO(2) SWCLK(2) UART_TX(2) UART_RX(2) VSENSE(3) ISENSE(2) CV_LED(1) CC_LED(2) PWR_LED(1) OSC_IN(1) OSC_OUT(1) VMID(1) PWM_B(1) —— 共 86 个 netflag
- 主要实体连线完成：功率级(SW/VOUT/VLOAD/VIN)、图腾柱(MID/PWM_B)、晶振(OSC_IN/OUT)、分压(VMID)
- 28 个 NC 标记（U1 未用脚、SW1.3/4、U2.4）
- **已保存 saved:true**（最新状态在嘉立创EDA云端）
- 注意：信号旗用了 power 类型（net_label/net_port_bi 两种 kind 静默失败，写入 ok 但不落地——工具缺陷）

## 🔧 待修复清单（按 `sch check` 的 73 项 findings，均附修复命令）

### A. 电气类（必须修）
1. **multi-net-wire @ U1 西侧走廊 primitive 5e4a5ae465cc9478**：U1 左侧引脚桩线全部 30 长且平行，旗子图形互相接触被判多网合并。
   修法：删 (345,515)/(345,525)/(345,665)/(345,675)/(345,685) 附近的桩+旗，按阶梯长度重画（25/45/25/45/25 交错），旗位错开 ≥15。涉及引脚：U1:24(VDD_1,515) U1:23(VSS_1,525) U1:19(PB1,565)✓已325 U1:18(PB0,575)✓350 U1:15(PA5,605)✓ U1:14(PA4,615)✓ U1:9(VDDA,665) U1:8(VSSA,675) U1:7(NRST,685)
2. **VSENSE 旗误放 @ (375,685)**（NRST 引脚点上）→ 删除该旗（找 net=VSENSE 位于 375,685 的 netflag prim），重放 @ (345,615)
3. **U1:36/U1:48 悬空**：3V3 旗在 (575,625)/(575,745) 但没桩线 → 补桩 [(545,625),(575,625)] 与 [(545,745),(575,745)] net=3V3
4. **C3 两脚悬空**（fix6 崩溃点）→ 桩 [(320,80),(295,80)] + VIN_5V power 旗；桩 [(360,80),(385,80)] + gnd
5. **R6.1 悬空** → MID 支线 [(190,310),(190,340),(250,340)] net=MID + [(190,370),(190,340)] net=MID（端点落在拐点）
6. **BOOT0 桩穿 C12 本体** (545,705)→(575,705)：C12 挪到 (655,760)（pin1 南 (655,740)→OSC_IN 桩南 20；pin2 北 (655,780)→gnd 桩北 15），然后重画 BOOT0 桩 [(545,705),(575,705)]（旗 @575,705 已在）
7. **dangling stub @ (460,90)**（C4.2 的旗被删线还在）→ 直接补 gnd 旗 @ (460,90)
8. **duplicate/redundant markers**：按 check 建议删除 5 个重复旗（facafcc5, 6936745c, edce9f6a, 7c4e3384, d8312d7b）

### B. 合法交叉（6 处 ERROR，EasyEDA 交叉不导通，属证据链问题）
(40,785)(270,560)(630,530)(630,600)(560,735)(345,545) —— 下轮用导线数据逐个确认无接触；如需彻底消除可微调桩长。

### C. 视觉类（不紧急）
- 11 个旗反挂（reversed-net-flag）：按 check 提示的 rot 值用 `sch modify --id <flag> --rotation <角度>` 转正
- 11 个旗重叠：`sch destagger` 自动错位
- 10 个 out-of-sheet / 1 个 titleblock-overlap：GND @ (580,850)(620,850) 是旧 C12/C13 残留→删除；(460,170) 区旗位调整

## 下一步（阶段二收尾 → 阶段三）
1. 修完 A 类 → `sch check` 复查到 0 ERROR → `sch save`
2. `sch netlist --type kicad` 导出网表，与 `sch_work/预期网表`（见 01_系统设计方案.md 第 5/6 节）对账
3. `sch export-image` 导出图纸 PNG/PDF 归档（当前 export 超时，需 doc reload 后再试）
4. 阶段三 PCB：`easyeda pcb` 命令族 + `sch block-apply`/同步，70×50mm 两层板

## 工具备忘
- 重查询 `sch list --include-pins` 页面大时会超时 → 分两次轻查询 + 离线推算引脚（旋转=绕放置点，偏移取反）
- `netflag --kind net_label|net_port_bi` 假成功 → 用 `--kind power`（自定义网名电源旗电气等效）
- 连接器会"降级熔断"报假失败 → 失败后先轻查询验证是否真失败再重试
- 批量 prim-delete >10 个可能压垮连接器 → 分批 ≤8 个
