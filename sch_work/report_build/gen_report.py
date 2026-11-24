# -*- coding: utf-8 -*-
"""生成课程设计报告 DOCX（按大纲七章+附录，素材来自 01~09 文档）"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = r"E:/STM32_design/Microcomputers_and_Embedded_Systems课程设计报告_v3.docx"

doc = Document()

# ---------- 页面与基础样式 ----------
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.top_margin = sec.bottom_margin = Cm(2.54)
sec.left_margin, sec.right_margin = Cm(3.0), Cm(2.5)
sec.header_distance = Cm(1.5)
sec.footer_distance = Cm(1.5)

def set_font(run, name_cn="宋体", name_en="Times New Roman", size=10.5, bold=False, color=None):
    run.font.name = name_en
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name_cn)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(10.5)
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
normal.paragraph_format.space_after = Pt(0)

# 标题样式统一为黑色（避免内置 Heading 的蓝色主题色）
for _hn in ("Heading 1", "Heading 2", "Heading 3"):
    _st = doc.styles[_hn]
    _st.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
    _st.font.name = "Times New Roman"
    _st.element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")


def h1(text, page_break=True):
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = page_break
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(14)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    set_font(r, "黑体", "Times New Roman", 16, True, (0, 0, 0))
    p.style = doc.styles["Heading 1"]
    return p

def h2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    set_font(r, "黑体", "Times New Roman", 14, True, (0, 0, 0))
    p.style = doc.styles["Heading 2"]
    return p

def h3(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_font(r, "黑体", "Times New Roman", 12, True, (0, 0, 0))
    p.style = doc.styles["Heading 3"]
    return p

def p(text, indent=True, size=10.5, bold=False, align=None, space_after=3):
    par = doc.add_paragraph()
    par.paragraph_format.first_line_indent = Cm(0.74) if indent else Cm(0)
    par.paragraph_format.space_after = Pt(space_after)
    if align == "center":
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run(text)
    set_font(r, "宋体", "Times New Roman", size, bold)
    return par

def bullet(text):
    par = doc.add_paragraph(style="List Bullet")
    par.paragraph_format.space_after = Pt(2)
    r = par.add_run(text)
    set_font(r, "宋体", "Times New Roman", 10.5)
    return par

def caption(text):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(3)
    par.paragraph_format.space_after = Pt(8)
    r = par.add_run(text)
    set_font(r, "宋体", "Times New Roman", 9, False, (0x33, 0x33, 0x33))

def shade(cell, hexcolor="EFEFEF"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)

def table(headers, rows, widths=None, cap=None, font_size=9):
    if cap:
        caption(cap)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0]
    trPr = hdr._tr.get_or_add_trPr()
    tblHeader = OxmlElement("w:tblHeader")
    tblHeader.set(qn("w:val"), "true")
    trPr.append(tblHeader)
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.text = ""
        par = c.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = par.add_run(h)
        set_font(r, "黑体", "Times New Roman", font_size, True)
        shade(c)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            par = cells[i].paragraphs[0]
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT if i == 0 and len(str(v)) > 6 else WD_ALIGN_PARAGRAPH.CENTER
            r = par.add_run(str(v))
            set_font(r, "宋体", "Times New Roman", font_size)
    if widths:
        total = sum(widths)
        scale = min(1.0, 15.4 / total)
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w * scale)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t

def figure(cap, hint, height_cm=6.5):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # 虚线浅灰边框
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "dashed"); el.set(qn("w:sz"), "4"); el.set(qn("w:color"), "BFBFBF")
        borders.append(el)
    tblPr.append(borders)
    row = t.rows[0]
    row.height = Cm(height_cm)
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    cell = row.cells[0]
    cell.width = Cm(15.2)
    tcPr = cell._tc.get_or_add_tcPr()
    vAlign = OxmlElement("w:vAlign"); vAlign.set(qn("w:val"), "center"); tcPr.append(vAlign)
    par = cell.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = par.add_run("【此处插入图片】")
    set_font(r, "宋体", "Times New Roman", 9, False, (0x88, 0x88, 0x88))
    par2 = cell.add_paragraph()
    par2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = par2.add_run(hint)
    set_font(r2, "宋体", "Times New Roman", 8.5, False, (0x99, 0x99, 0x99))
    caption(cap)

# 页眉页脚
def add_header_footer():
    header = sec.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hr = hp.add_run("Microcomputers and Embedded Systems 课程设计报告")
    set_font(hr, "宋体", "Times New Roman", 8, False, (0x77, 0x77, 0x77))

    footer = sec.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = fp.add_run("第 ")
    set_font(r1, "宋体", "Times New Roman", 9)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run_el = OxmlElement("w:r")
    t_el = OxmlElement("w:t")
    t_el.text = "1"
    run_el.append(t_el)
    fld.append(run_el)
    fp._p.append(fld)
    r2 = fp.add_run(" 页")
    set_font(r2, "宋体", "Times New Roman", 9)

add_header_footer()

# ======================= 封面 =======================
for _ in range(3):
    doc.add_paragraph()
par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = par.add_run("Microcomputers and Embedded Systems")
set_font(r, "Times New Roman", "Times New Roman", 22, True)

par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
par.paragraph_format.space_before = Pt(10)
r = par.add_run("课程设计报告")
set_font(r, "黑体", "Times New Roman", 26, True)

par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
par.paragraph_format.space_before = Pt(18)
r = par.add_run("基于 STM32 的数字控制 Boost 升压恒压恒流电源")
set_font(r, "黑体", "Times New Roman", 16, False)

for _ in range(6):
    doc.add_paragraph()

info = [("小组成员", "＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿"), ("指导教师", "＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿"),
        ("学    号", "＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿"), ("院 （系）", "＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿"),
        ("专    业", "＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿")]
for k, v in info:
    par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_after = Pt(10)
    r1 = par.add_run(k + "：  "); set_font(r1, "宋体", "Times New Roman", 12)
    r2 = par.add_run(v); set_font(r2, "宋体", "Times New Roman", 12)

for _ in range(4):
    doc.add_paragraph()
par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = par.add_run("2026 年 11 月")
set_font(r, "宋体", "Times New Roman", 12)

# ======================= 目录 =======================
doc.add_page_break()
par = doc.add_paragraph(); par.alignment = WD_ALIGN_PARAGRAPH.CENTER
par.paragraph_format.space_after = Pt(12)
r = par.add_run("目  录")
set_font(r, "黑体", "Times New Roman", 16, True, (0, 0, 0))

toc_par = doc.add_paragraph()
fld = OxmlElement("w:fldSimple")
fld.set(qn("w:instr"), 'TOC \\o "1-3" \\h \\z \\u')
run_el = OxmlElement("w:r")
t_el = OxmlElement("w:t")
t_el.text = "（目录将在 Word 中自动生成：全选后按 F9 更新域）"
run_el.append(t_el)
fld.append(run_el)
toc_par._p.append(fld)

# ======================= 第一章 =======================
h1("第一章 总体介绍")

p("本课程设计的目标是设计、制作并调通一台由 STM32F103C8T6 微控制器数字控制的 Boost 升压恒压/恒流电源。"
  "系统将 5 V 直流输入升压至 12 V 输出，额定输出电流 0.5 A（6 W），开关频率 100 kHz，"
  "具备恒压（CV）与恒流（CC）自动切换、软启动、输出过压保护（OVP）与过流保护（OCP），"
  "并通过串口命令行提供运行状态查询与参数设定能力。")

h2("1.1 系统总体结构")
p("系统由六个部分组成：输入保护与滤波、Boost 功率级、输出采样链、数字控制核心、MOS 驱动与显示接口。"
  "总体结构如图 1-1 所示。")
p("（1）输入保护与滤波：F1 为 3 A 一次性保险丝（Littelfuse 0468003.NRHF），"
  "后接 C5/C6（2×22 µF 陶瓷）与 C7（220 µF/50 V 电解）组成的输入储能滤波网络；")
p("（2）Boost 功率级：L1 为 100 µH 屏蔽电感，Q1（AO3400A）为开关管，D1（SS34）为续流二极管，"
  "输出电容为 C10（220 µF/50 V 电解）与 C8/C9（2×22 µF 陶瓷）的混合方案；")
p("（3）输出采样链：电压经 R6/R7/R5/R4 分压网络（10/46）送入 ADC；"
  "电流经 0.1 Ω 分流电阻 Rs1 与电流检测放大器 U3（INA180A2，增益 50）送入 ADC；")
p("（4）数字控制核心：U1（STM32F103C8T6，72 MHz）完成 12 位 ADC 双通道 DMA 采样、"
  "10 kHz 数字 PI 控制、100 kHz PWM 生成、保护判定与串口命令行；")
p("（5）驱动：Q2（SS8050）/Q3（SS8550）组成图腾柱，经 R1、R2、R3 驱动 Q1 栅极，实现 0.7~4.3 V 快速开关；")
p("（6）接口与指示：J1 为 5 V 输入端子，J2 为 12 V 输出端子，J3 为 SWD 烧录口，J4 为串口调试口，"
  "POWER/CV/CC 三只 LED 指示电源、恒压与恒流状态，SW1 为复位键。")

figure("图 1-1  系统总体结构框图", "（建议用 01 §1 结构图或按本节文字重绘：5V→F1→滤波→Boost→输出 / 采样→MCU→驱动）")

h2("1.2 系统工作流程")
p("上电后，输出端经 L1、D1 从输入直通，输出被预充至约 Vin−VF（约 4.5~4.8 V），"
  "控制器处于待机（STANDBY），PWM 占空比为 0，三个指示灯全灭。")
p("操作者通过串口发送 on 命令后，系统进入软启动：参考电压在 50 ms 内线性爬升，"
  "输出电压跟随参考平滑上升至 12 V，无过冲；随后进入恒压（CV）环稳态。")
p("当负载加重、电流达到 0.5 A 设定值时，限幅器接管，占空比被压低，输出电流被限制在 0.5 A，"
  "系统进入恒流（CC）状态，CV 灯熄灭、CC 灯点亮。")
p("若输出越过 13.2 V（OVP）或电流超过 0.6 A 持续 5 ms（OCP），系统立即锁存故障、"
  "关断 PWM（占空比 0），POWER 指示灯以 1 Hz 慢闪；故障锁存后必须串口发送 clear（或断电重启）才能恢复。")

h2("1.3 课程指标与实现结果")
table(["指标项", "课程要求", "本设计仿真", "本设计实测"],
      [["输出电压", "12 V ± 5%", "+0.075%", "−0.17%（空载）"],
       ["输出纹波", "≤ 5%", "1.81%", "0.48%（0.12 A）"],
       ["恒流精度", "0.5 A ± 5%", "−0.18%", "−0.2% ~ +2.0%"],
       ["软启动", "无过冲、不误触发 OVP", "过冲 49 mV", "功能验证通过"],
       ["保护", "OVP / OCP 可用", "13.2 V 立即 / 0.6 A·5 ms", "OVP 实测通过"],
       ["输入适应", "5 V ± 10%", "4.75 V 时偏 20 mV", "0.1%/V"],
       ["效率", "≥ 75%", "预算 ~87%（满载）", "75.9%（0.12 A 轻载）"]],
      widths=[3.2, 4.4, 4.2, 4.2], cap="表 1-1  课程指标与实现结果对照")

h2("1.4 小组成员分工")
table(["成员", "主要工作", "贡献占比"],
      [["【填写】", "系统方案、参数计算、仿真建模与报告整理", "【填写】"],
       ["【填写】", "原理图绘制、PCB 布局布线、打样与焊接", "【填写】"],
       ["【填写】", "固件开发、烧录调试、板级实测与数据记录", "【填写】"]],
      widths=[3.0, 9.0, 3.0], cap="表 1-2  小组成员分工")

# ======================= 第二章 =======================
h1("第二章 系统总体设计智能体")

h2("2.1 智能体设计过程与需求分析")
p("本设计的总体方案阶段由 AI 设计智能体（WorkBuddy）承担，工作流为："
  "输入课程指标与约束 → 拓扑与控制方案比选 → 关键参数计算 → 建立开关级仿真模型预验证 → 输出器件参数与设计结论。"
  "智能体输出的每一条结论都用仿真复跑验证，形成\"计算—仿真—修正\"的闭环，避免拍脑袋定参数。")
p("需求分析要点如下：输入为实验室直流电源 5 V（±5%），输出 12 V/0.5 A（6 W）；"
  "要求恒压恒流双模式、软启动、过压过流保护；开关频率在 100 kHz 量级以兼顾电感体积与开关损耗；"
  "控制核心为课程指定的 STM32F103C8T6（72 MHz、12 位 ADC、高级定时器 TIM1）；"
  "整机效率不低于 75%；全部器件需在立创商城可采购，成本优先。")

h2("2.2 Boost 拓扑与控制方案选择")
p("输出电压（12 V）高于输入电压（5 V），只能选择升压类拓扑。在 Boost、反激、SEPIC 等方案中，"
  "Boost 结构最简单（单管单电感单二极管）、效率高、控制成熟，适合 6 W 小功率场合，故选定 Boost。")
p("控制方案方面，常见做法是电压外环 + 电流内环的双环平均电流模式，但其电流环对采样噪声敏感、"
  "参数整定复杂。本设计采用\"电压型 PI + 电流限幅器取小\"的架构：电压环 PI 负责稳压，"
  "限幅器根据实测电流与设定值实时压低占空比上限，两者输出取小者驱动 PWM。"
  "该结构只有一个 PI 需要整定，却同时具备恒压、恒流与过流限制能力，鲁棒性好、实现简单。")
table(["方案", "优点", "缺点", "结论"],
      [["电压型 PI + 限幅器（本设计）", "单环整定、天然限流、抗噪", "恒流动态一般", "选用"],
       ["双环平均电流模式", "恒流精度高、动态好", "需精确电感电流采样，噪声敏感、整定复杂", "不选"],
       ["峰值电流模式", "响应快", "需斜坡补偿，DCM 下模型复杂", "不选"]],
      widths=[4.6, 4.4, 4.6, 1.6], cap="表 2-1  控制方案比选")
p("开关频率取 100 kHz：电感可选用 100 µH 的贴片屏蔽电感（13.5×12.6 mm），"
  "同时 72 MHz 时钟下 PWM 计数分辨率为 1/720，占空比精度足够。")

h2("2.3 关键参数计算")
p("（1）占空比。理想 Boost 有 Vout/Vin = 1/(1−D)，即 D = 1 − Vin/Vout = 1 − 5/12 ≈ 0.583；"
  "计入二极管、电感与开关损耗后实际占空比约 0.61（实测 441/720 = 61.3%，与理论一致）。")
p("（2）输入电流与电感电流。满载时 Iin = Pout/(η·Vin) = 6/(0.87×5) ≈ 1.38 A；"
  "电感电流纹波 ΔIL = Vin·D/(L·f) = 5×0.61/(100 µH×100 kHz) ≈ 0.30 A，"
  "峰值电流约 1.55 A，所选电感饱和电流 4 A，裕量 2.5 倍。")
p("（3）输出电容。纹波由容性充电项与 ESR 项叠加。取 220 µF/50 V 电解（ESR≈0.3 Ω）与 2×22 µF 陶瓷并联，"
  "仿真得满载纹波 218 mV（1.81%），实测轻载 58 mV（0.48%），满足 ≤5% 要求。")
p("（4）电压采样链。分压电阻 3 kΩ+33 kΩ 串联对 10 kΩ 下臂，分压比 10/46 = 0.2174，"
  "12 V 对应 2.61 V；ADC 换算 269.96 counts/V，12 V 给定 3238 counts。"
  "VSENSE 节点加 1 kΩ 串联电阻与 10 nF 电容构成 RC 滤波，时间常数 τ = [1 k+(36 k∥10 k)]×10 nF = 88.3 µs，"
  "滤除开关纹波同时不破坏环路相位。")
p("（5）电流采样链。分流电阻 Rs1 = 0.1 Ω，配合 INA180A2（增益 50）得到 5 V/A 的灵敏度；"
  "0.5 A 对应 2.5 V、3102 counts，分辨率 0.161 mA/count。"
  "注意 0.1 Ω 下 0.66 A 即达 3.3 V ADC 满量程，故过流保护整定为 0.6 A（1.2 倍额定），"
  "这是量程约束下的工程取舍。")
p("（6）控制与保护参数。控制周期 10 kHz（每 10 个开关周期调节一次）；PI 参数经稳定域扫描确定为 "
  "kp = 0.06、ki = 50（kp ≤ 0.08、ki ≤ 65 全域稳定，推荐点四周留裕度）；软启动 50 ms 线性斜坡；"
  "OVP 阈值 13.2 V（12 V+10%）；OCP 阈值 0.6 A、去抖 5 ms。")
table(["参数", "数值", "依据"],
      [["输入 / 输出电压", "5 V / 12 V", "课程指标"],
       ["额定输出电流 / 功率", "0.5 A / 6 W", "课程指标"],
       ["开关频率", "100 kHz（TIM1 ARR=719，PSC=0）", "体积与损耗折中"],
       ["占空比（满载）", "0.61（441/720）", "实测与理论一致"],
       ["电感", "100 µH，ΔIL≈0.30 A，峰值 1.55 A", "饱和电流 4 A，裕量 2.5×"],
       ["输出电容", "220 µF/50 V + 2×22 µF", "纹波 ≤5%"],
       ["电流采样", "0.1 Ω × 50 = 5 V/A，3102 counts@0.5 A", "ADC 量程 0.66 A 上限"],
       ["电压采样", "10/46 分压，269.96 counts/V，τ=88.3 µs", "12 V 时 2.61 V"],
       ["控制频率 / PI", "10 kHz / kp=0.06，ki=50", "稳定域扫描"],
       ["保护", "OVP 13.2 V；OCP 0.6 A·5 ms", "仿真与量程"]],
      widths=[4.2, 7.6, 5.2], cap="表 2-2  关键参数与设计依据")

h2("2.4 主要器件参数")
table(["位号", "型号 / 参数", "作用"],
      [["U1", "STM32F103C8T6（72 MHz，64 KB Flash）", "数字控制核心"],
       ["U3", "INA180A2（增益 50，5 V/A）", "输出电流检测"],
       ["U2", "XC6206P332MR（3.3 V/200 mA）", "3.3 V 稳压"],
       ["L1", "FSA1365-101MT，100 µH，Isat 4 A，DCR 170 mΩ", "储能电感"],
       ["Q1", "AO3400A（30 V/5.7 A，Rds(on)≈30 mΩ）", "主开关管"],
       ["D1", "SS34（3 A/40 V 肖特基）", "续流二极管"],
       ["C10 / C7", "220 µF/50 V 电解（8×12 mm）", "输出/输入储能"],
       ["C5/C6/C8/C9", "22 µF/25 V X5R 1206", "高频去耦"],
       ["Rs1", "0.1 Ω ±1%（1206W4F100LT5E）", "电流分流"],
       ["F1", "0468003.NRHF，3 A/32 V，1206", "输入过流保护"],
       ["Y1", "8 MHz 贴片晶振（CL=20 pF）", "系统时钟"],
       ["J1/J2", "KF301-5.0-2P 接线端子", "5 V 输入 / 12 V 输出"]],
      widths=[2.6, 8.8, 5.4], cap="表 2-3  主要器件参数")

h2("2.5 总体方案的仿真预验证")
p("在投板前，用 Python 建立了 Boost 的开关级与平均模型（模拟器件非线性、采样保持、量化与控制环），"
  "对十个场景做了验证（S1 开环工作点、S2 软启动、S3 稳态、S4 负载阶跃、S5 恒流切换、S6 短路、"
  "S7 过压注入、S8 稳定域扫描、S9 效率预算、S10 输入跌落），结论是方案可行、参数合理。"
  "仿真结果与实测定性一致（详见第六章对照表），说明总体设计阶段的计算与建模是可靠的。")
table(["场景", "仿真结果", "指标判定"],
      [["S2 软启动", "过冲 49 mV，浪涌 1.6 A，无 OVP", "✅"],
       ["S3 稳态（0.5 A）", "12.0032 V（+0.075%），纹波 218 mV（1.81%）", "✅"],
       ["S4 负载阶跃", "卸载过冲 296 mV；加载跌落 1090 mV/6.4 ms", "✅"],
       ["S5 恒流", "0.5 A，误差 −0.18%，无振荡", "✅"],
       ["S6 短路", "OCP 5 ms 锁存", "✅"],
       ["S7 OVP 注入", "立即锁存保持", "✅"],
       ["S8 稳定域", "kp ≤ 0.08 / ki ≤ 65 全稳", "✅"],
       ["S10 输入 4.75 V", "输出偏差 20 mV", "✅"]],
      widths=[4.2, 9.4, 3.4], cap="表 2-4  仿真验证结果汇总（详见 03 号报告 §12）")

# ======================= 第三章 =======================
h1("第三章 原理图设计智能体")

h2("3.1 智能体设计过程")
p("原理图阶段采用\"AI 智能体 + 人工绘制\"的协作模式：由智能体通过嘉立创 EDA 连接器（easyeda-agent）"
  "实时读取工程网表、器件属性与几何信息，做只读核对与设计审查；人工负责在 EDA 中完成绘制与改型。"
  "智能体的审查遵循固定流程：读取网表 → 逐网核对引脚归属 → 检查悬空脚/多网线/极性 → "
  "输出问题清单 → 人工修改 → 再次回读确认，共进行三轮（设计审计、重建复核、发板前检查），"
  "每轮均留存 JSON 证据。")
p("这种方式的价值在于\"可验证\"：任何一处修改后，智能体都能在几秒内重新读出 29 个网络的逐脚归属并对比差异，"
  "避免人工肉眼核对遗漏。第三章末尾的修改记录即来自这一流程。")

h2("3.2 原理图功能模块划分")
table(["模块", "主要器件", "作用"],
      [["输入保护与滤波", "F1、C5/C6/C7", "过流保护、输入储能与高频去耦"],
       ["Boost 功率级", "L1、Q1、D1、C8/C9/C10", "升压变换与输出储能"],
       ["栅极驱动", "Q2、Q3、R1、R2、R3", "图腾柱驱动，0.7~4.3 V 快速开关"],
       ["数字控制核心", "U1、Y1、SW1、R13、R10", "最小系统、复位、BOOT0、SWD"],
       ["电压采样", "R6/R7/R5/R4、C13", "10/46 分压 + RC 滤波"],
       ["电流采样", "Rs1、U3、C14", "0.1 Ω 分流 + 50 倍放大 + RC 滤波"],
       ["3.3 V 电源", "U2、C1~C4", "XC6206 稳压与去耦"],
       ["接口与指示", "J1~J4、POWER/CV/CC、R9/R11/R12", "端子、烧录/串口、状态灯"]],
      widths=[4.2, 6.4, 6.2], cap="表 3-1  原理图功能模块划分")

h2("3.3 主要电路设计")
h3("3.3.1 输入保护与滤波")
p("F1 为 1206 封装 3 A 一次性保险丝，选取依据是满载输入电流约 1.4 A，2 倍裕量；"
  "它同时是整板唯一的输入过流屏障，因此在改版中被专门从 0 Ω 跳线恢复为保险丝。"
  "C5/C6 两片 22 µF 陶瓷就近布置在输入端，抑制开关噪声回流；C7（220 µF/50 V 电解）提供低频储能，"
  "避免输入线缆电感与变换器形成低频振荡。")
h3("3.3.2 Boost 功率级与驱动")
p("L1（100 µH）一端接输入，另一端为开关节点 SW，经 Q1 下拉到地、经 D1 送至输出。"
  "Q1 为 AO3400A，Vds 30 V 对 12.5 V 开关尖峰有 2.4 倍裕量；D1 选用 SS34 肖特基，正向压降约 0.45 V。"
  "驱动采用 SS8050/SS8550 图腾柱：MCU 的 3.3 V PWM 经 R1（1 kΩ）送入互补对，"
  "输出经 R2（10 Ω）驱动栅极，R3（100 kΩ）提供下拉，实测栅极波形为 0.7~4.3 V 方波，边沿小于 100 ns。")
h3("3.3.3 采样链")
p("电压采样为 3 kΩ + 33 kΩ 串联上臂、10 kΩ 下臂，分压比 10/46；VSENSE 经 R4（1 kΩ）与 C13（10 nF）"
  "构成低通，τ = 88.3 µs，兼顾滤除 100 kHz 纹波与环路相位裕度。")
p("电流采样把 0.1 Ω 分流电阻 Rs1 串在输出回路（VOUT→VLOAD），"
  "INA180A2 以 50 倍增益差分放大后送 ADC；C14（1 nF）滤除高频噪声。"
  "Rs1 采用 1206 封装 1% 精度电阻，250 mW 额定、实际功耗 25 mW，裕量充足。")
h3("3.3.4 数字控制核心与接口")
p("U1 最小系统含 8 MHz 贴片晶振（C11/C12 为 22 pF 负载电容）、复位按键 SW1 与 10 kΩ 上拉 R10、"
  "BOOT0 下拉 R13（100 kΩ，从 Flash 启动）、SWD 调试口 J3（3V3/SWDIO/SWCLK/GND）与串口口 J4"
  "（TX/RX/3V3/GND，与 USB-TTL 交叉连接）。三只 LED 经 1 kΩ 限流（R9/R11/R12）分别指示电源、恒压、恒流状态。")

h2("3.4 设计检查与问题修改")
p("智能体对原理图做了逐网核对：全板 46 个器件、29 个网络，逐脚比对确认无悬空（除 MCU 未用引脚）、"
  "无多网线、无网名与几何不符；极性器件（电解电容、二极管、LED）方向全部正确（极性检查 0 违规）。"
  "审查中发现并修正的问题如表 3-2。")
table(["问题", "原状", "修改", "原因"],
      [["F1 无保护能力", "0 Ω 跳线", "换 3 A 保险丝 C41342", "恢复输入唯一过流屏障"],
       ["Rs1 标定不一致", "0.05 Ω（固件按 0.05 标定）", "0.1 Ω + 固件 8 个常数同步", "提高信噪比，需配套改固件"],
       ["输出电容不足", "仅陶瓷（偏压后约 55 µF）", "补 220 µF/50 V 电解", "负载阶跃会触发 OVP 锁存"],
       ["LOAD_FF 口径错位", "0.26（按 0.05 Ω counts）", "0.13（0.1 Ω counts）", "否则前馈注入翻倍、环路限幅"],
       ["位号重复/混乱", "多处 C/R 编号冲突", "全板重新标注并建对照表", "BOM 与装配可追溯"]],
      widths=[3.6, 4.6, 4.6, 4.0], cap="表 3-2  v2→v3 主要修改记录")
table(["v3 位号", "功能", "v2 位号", "v3 位号", "功能", "v2 位号"],
      [["C5/C6", "输入 22 µF", "C5/C14", "R5", "分压下臂 10k", "R2"],
       ["C7", "输入 220 µF 电解", "新增", "R6", "分压上臂 33k", "R1"],
       ["C8/C9", "输出 22 µF", "C6/C18", "R7", "分压上臂 3k", "R13"],
       ["C10", "输出 220 µF 电解", "新增（曾用 C22）", "R8", "输出泄放 10k", "R12"],
       ["C11/C12", "晶振 22 pF", "C12/C13", "R9", "POWER 1k", "R5"],
       ["C13", "VSENSE 10 nF", "C10", "R10", "NRST 上拉 10k", "R9"],
       ["C14", "ISENSE 1 nF", "C11", "R11/R12", "CV/CC 1k", "R3/R4"],
       ["R1", "PWM 基极 1k", "R8", "R13", "BOOT0 下拉 100k", "R10"]],
      widths=[2.9, 4.3, 4.3, 2.9, 4.3, 4.3], cap="表 3-3  位号对照（节选，完整版见 08 §2.4）")

figure("图 3-1  完整原理图", "（插入嘉立创 EDA 原理图整页截图）", height_cm=10)
figure("图 3-2  采样链电路（电压分压 + 电流 INA180）", "（插入原理图采样部分局部截图）")

# ======================= 第四章 =======================
h1("第四章 PCB 设计智能体")

h2("4.1 智能体设计过程")
p("PCB 阶段同样采用\"智能体审查 + 人工布局布线\"的模式。智能体通过连接器读取 PCB 的器件坐标、"
  "焊盘网络、走线、过孔与铺铜数据，输出三类检查：布局检查（碰撞/板外/间距）、"
  "连通性检查（飞线长度、网络覆盖、网表对账）、可制造性检查（线宽、焊盘间距、丝印、死过孔等 DFM 项），"
  "并调取官方 DRC 结果。人工依据检查清单完成布局、布线与铺铜，改完再由智能体复核，"
  "形成\"读—审—改—验\"的闭环。")

h2("4.2 布局设计")
p("布局遵循\"功率回路最短、采样就近、接口靠边\"三个原则：")
p("（1）功率区集中在板左侧：J1 输入 → F1 → 输入电容 → L1 → Q1/D1 → 输出电容 → Rs1 → J2，"
  "使输入电容—开关管—二极管—输出电容构成的高频环路面积最小，降低开关尖峰与辐射；")
p("（2）控制区在板中部：U1 与晶振靠近放置，SWD/串口接口引出到板边，避免长线穿越功率区；")
p("（3）采样区紧贴被测量：分压网络与 VSENSE 滤波紧邻 U1 的 ADC 引脚；Rs1 采用开尔文接法，"
  "INA180 就近布置，采样线远离 SW 节点与电感，减少共模干扰。")
table(["项目", "设计要点", "对应约束"],
      [["功率环路", "输入电容—Q1—D1—输出电容闭合面积最小", "开关尖峰 / EMI"],
       ["采样接地", "Rs1 四线开尔文，采样地单点汇入", "电流精度"],
       ["输出电容", "C10 靠近 Rs1 与 J2，陶瓷紧邻电解", "纹波 / 瞬态"],
       ["接口位置", "J1/J2 位于板边便于接线，J3/J4 同侧", "可操作性"],
       ["去耦", "U1 每个电源脚就近 100 nF，3.3 V 主干 10 µF", "数字噪声"]],
      widths=[3.4, 8.6, 4.8], cap="表 4-1  布局设计要点")

h2("4.3 布线设计")
p("布线采用双面板：顶层走功率主干与信号，底层整片铺 GND 作为回流平面。"
  "功率主干按载流需求加宽：VIN_RAW、VIN_5V、SW、VOUT、VLOAD 采用 70 mil（约 1.78 mm），"
  "局部支路 60 mil 与 30 mil；信号线按 10~30 mil 布线，采样线（ISENSE、VSENSE）单独走、"
  "远离开关节点并包地。底层 GND 铺铜后，所有器件接地脚通过过孔或直插焊盘与地平面连通，"
  "形成低阻抗回流路径。")
p("实测的功率主干线宽与铺铜情况已通过智能体回读确认：顶层走线 37 段（其中功率主干 70 mil×11 段、"
  "60 mil×3 段、30 mil×12 段），过孔 25 个，底层 GND 铺铜 1 片覆盖整板。")

h2("4.4 设计规则检查与问题修改")
p("官方 DRC 检查结果为 0 违规；智能体的 DFM 检查共列出 77 项提示（0 项错误），主要包括："
  "板框未定义导致的丝印出界提示、7 个单层死过孔、部分去耦电容距离偏大、"
  "J3/J4 插头包络与相邻器件间距偏紧等。其中死过孔与丝印出界在最终版已清理或确认无电气影响；"
  "去耦距离与插头包络列为下一版优化项。")
table(["检查项", "结果", "处理"],
      [["官方 DRC", "0 违规", "通过"],
       ["网表对账（PCB↔原理图）", "46 器件 / 29 网一致", "通过"],
       ["功率主干线宽", "70/60 mil（载流 ≥2 A）", "满足"],
       ["死过孔（单层）", "7 处（DFM 提示）", "已确认无电气影响"],
       ["丝印出界", "板框确定后复核", "下一版优化"],
       ["去耦距离", "部分 > 5 mm", "下一版优化"]],
      widths=[5.2, 7.2, 4.4], cap="表 4-2  DRC 与 DFM 结果")

figure("图 4-1  PCB 布局图（顶层）", "（插入 EDA 顶层视图截图，标注功率区/控制区/输出区）", height_cm=7)
figure("图 4-2  PCB 布线图（底层铺铜）", "（插入底层 GND 铺铜截图）", height_cm=7)
figure("图 4-3  PCB 三维视图", "（插入 3D 渲染图）", height_cm=7)

# ======================= 第五章 =======================
h1("第五章 嵌入式程序设计智能体")

h2("5.1 智能体设计过程")
p("固件由 AI 编程智能体生成，并坚持\"仿真镜像即固件\"的原则：仿真中的控制结构（PI、限幅器、前馈、软启动、"
  "保护判定）与 C 代码逐行对应，仿真确定的参数直接写入固件常数表。"
  "生成后在本机用 STM32CubeIDE 自带工具链交叉编译、ST-Link 烧录，再用串口命令行做闭环验证"
  "（发命令—读状态—比对预期），形成\"生成—编译—烧录—验证\"的自动化链路。")

h2("5.2 程序总体结构")
table(["文件", "职责", "关键内容"],
      [["main.c", "初始化与主循环", "时钟、外设、控制初始化；循环只跑 CLI"],
       ["bsp_power.c", "板级寄存器配置", "TIM1 100 kHz PWM、TIM2 10 kHz 节拍、ADC+DMA、GPIO"],
       ["control.c", "控制算法", "状态机、PI、限幅器、前馈、软启动、保护、LED"],
       ["cli.c", "串口命令行", "命令解析与状态打印（115200 8N1）"],
       ["stm32f1xx_it.c", "中断向量", "SysTick、DMA1_CH1（TIM2 在 bsp_power 内实现）"],
       ["stm32f1xx_hal_msp.c", "时钟/引脚使能", "USART1、ADC1 时钟与 PA9/PA10 复用"]],
      widths=[3.8, 4.4, 8.6], cap="表 5-1  固件文件结构")
p("实时性划分：控制环放在 TIM2 更新中断（10 kHz），主循环只做非阻塞的命令行轮询，"
  "因此串口打印再慢也不会丢失控制拍；ADC 由 DMA 循环搬运，控制中断直接读取最新采样值。")

h2("5.3 控制逻辑实现")
p("系统状态机包含 STANDBY、SOFTSTART、RUN_CV、RUN_CC 与 FAULT_OV/OC/FB 五个状态。"
  "上电处于 STANDBY；收到 on 后进入 SOFTSTART，参考电压 50 ms 线性上升；"
  "参考到位后按\"电压环输出与限幅器输出取小\"决定占空比，由 PI 误差符号与迟滞判定 CV/CC 状态；"
  "任何保护触发即跳转对应 FAULT 状态并锁存，只有 clear 或断电才能复位。")
p("PI 采用条件积分：输出饱和时停止积分，避免积分风饱和；"
  "负载跃升前馈在电流单拍突增超过阈值时直接给积分器补一笔占空比，抵消 10 kHz 环路的响应延迟；"
  "软启动采用\"参考斜坡 + 积分器跟踪钳位\"，兼顾无过冲与快速建立。")
p("保护逻辑：OVP 判定 Vout > 13.2 V 立即锁存；OCP 判定 Iout > 0.6 A 持续 50 拍（5 ms）锁存；"
  "另有断线检测（占空比大于阈值而输出电压异常低）防止反馈开路时失控。")
table(["状态", "触发条件", "行为"],
      [["STANDBY", "上电 / off", "PWM=0，等待 on"],
       ["SOFTSTART", "收到 on", "参考 50 ms 斜坡，占空比限幅"],
       ["RUN_CV", "Vout 到达参考且未限流", "电压 PI 稳压，CV 灯亮"],
       ["RUN_CC", "电流达 0.5 A 设定", "限幅器压低占空比，CC 灯亮"],
       ["FAULT_OV / OC / FB", "过压 / 过流 / 断线", "PWM=0 锁存，POWER 灯 1 Hz 闪"]],
      widths=[4.4, 5.6, 7.0], cap="表 5-2  状态机定义")

h2("5.4 关键代码说明")
p("限幅器（节选）：比较实测电流与设定值，若超限则按 ki_i 速率压低占空比上限；"
  "欠流时按 relax 速率放松，其中深度欠流全速放松以快速脱离钳位、临界点附近慢速放松以防抖振。")
p("PI 与取小（节选）：")
p("    out_v = pi_v.kp * err_v + pi_v.integ;    // 电压环输出\n"
  "    lim   = limiter_step();                  // 限幅器输出\n"
  "    duty  = (out_v < lim) ? out_v : lim;     // 取小者驱动 PWM", indent=False, size=9)
p("前馈：di = iout − iout_prev，当 di 超过阈值且未超限流点时，integ += load_ff × di，"
  "该系数按 counts 口径标定（0.1 Ω 采样下取 0.13），换算关系必须与采样链一致，否则会过冲。")

h2("5.5 程序与硬件的配合")
p("固件与硬件的耦合点集中在三处换算：PWM 占空比（CCR 0~612 对应 0~85%）、"
  "ADC 计数（电压 269.96 counts/V、电流 6204.5 counts/A）、以及保护阈值（OVP 3562 counts、OCP 3723 counts）。"
  "这些常数与硬件采样链一一对应，一旦硬件改型（如本版 Rs1 由 0.05 Ω 改 0.1 Ω），固件必须同步修订，"
  "否则会出现\"读数翻倍、限流误动作、输出塌陷\"的连锁问题——这一点在改版中已被仿真与实测双重验证。")
table(["命令", "功能", "示例"],
      [["h", "帮助", "h"],
       ["on / off", "软启动 / 停机", "on"],
       ["st", "状态查询（状态/占空比/电压/电流/原始计数）", "st"],
       ["sv <V>", "设定输出电压（5.0~12.8 V）", "sv 12.0"],
       ["si <A>", "设定恒流值（0.05~0.7 A）", "si 0.5"],
       ["d <0-612>", "开环占空比调试", "d 200"],
       ["ovp", "过压保护注入测试", "ovp"],
       ["clear", "清除故障锁存", "clear"]],
      widths=[3.6, 8.4, 5.0], cap="表 5-3  串口命令行")
table(["常数", "数值", "说明"],
      [["ADC_VOUT_GAIN / DIV", "0.0037042 V/count / 269.96", "10/46 分压"],
       ["ADC_IOUT_GAIN / DIV", "0.00016117 A/count / 6204.5", "0.1 Ω × 50"],
       ["ISET_DEFAULT_COUNTS", "3102", "0.5 A 设定"],
       ["OCP_HARD_COUNTS", "3723（0.6 A，5 ms）", "ADC 量程约束"],
       ["OVP_COUNTS", "3562（13.2 V，立即）", "12 V+10%"],
       ["LOAD_FF / 阈值", "0.13 / 200 counts", "counts 口径"],
       ["kp_v / ki_v", "0.06 / 50", "控制环"]],
      widths=[5.0, 6.4, 5.6], cap="表 5-4  固件关键常数（v2.1）")

figure("图 5-1  程序总体流程图", "（插入流程图：初始化→待机→on→软启动→CV/CC→保护）", height_cm=8)

# ======================= 第六章 =======================
h1("第六章 系统调试与测试")

h2("6.1 测试环境与方法")
p("测试使用直流稳压电源（5 V/2 A）供电，负载采用 10 只 1 kΩ/0.25 W 电阻并联（约 100 Ω，"
  "12 V 下 0.12 A，每只功耗 0.144 W 在安全范围内）；示波器（10× 探头、短地弹簧、20 MHz 带宽限制）"
  "测纹波与开关波形；数字万用表测输出电压；串口终端（115200 8N1）与固件交互并读取状态。")
table(["项目", "设备 / 设置", "说明"],
      [["输入电源", "DC 5.0 V，限流 2 A", "J1 端子"],
       ["负载", "10×1 kΩ 并联 ≈ 100 Ω", "轻载点 0.12 A"],
       ["示波器", "10×、AC 耦合、20 MHz 限带、短地弹簧", "测 C10 两端"],
       ["串口", "115200 8N1，CH340 USB-TTL", "J4：TX/RX 交叉"],
       ["烧录", "ST-Link V2（SWD）+ STM32CubeProgrammer", "J3"]],
      widths=[3.6, 7.4, 5.0], cap="表 6-1  测试条件")

h2("6.2 串口调试输出")
p("固件启动后打印版本横幅并提供命令行。实测状态查询输出示例如下（空载 12 V 稳压）：")
p("    state=CV duty=54 Vout=11.986V Iout=0.000A raw=[3236,1]", indent=False, size=9)
p("字段含义：state 为状态机状态，duty 为占空比计数（0~612），Vout/Iout 为换算后的物理量，"
  "raw 为 ADC 原始计数（Vout/Isense）。该输出用于核对采样链标定与工作点是否正常。")
figure("图 6-1  串口终端交互截图", "（插入串口助手截图：h、on、st、ovp 的交互过程）", height_cm=5)

h2("6.3 实测数据")
p("表 6-2 汇总了 2026 年 11 月 24 日首板实测数据（数据来源：组内记录 + 串口读数 + 仪器面板，已逐项复算核对）。"
  "受实验室器材限制（无功率电阻/电子负载），满载 12 V/0.5 A 点未实测，相关指标引用仿真值并标注。")
table(["实验", "工况", "Vin", "Vout", "Iout", "占空比", "复核"],
      [["稳压精度", "空载", "4.999 V", "11.9792 V", "0", "7.5%", "−0.17%"],
       ["输入调整率", "空载", "4.5 V", "11.981 V", "0", "6.53%", "−0.16%"],
       ["输入调整率", "空载", "5.5 V", "11.969 V", "0", "10.28%", "−0.26%"],
       ["OVP", "空载", "5.5 V", "灌 14 V 锁存，撤压 5.284 V", "—", "—", "通过"],
       ["恒流", "9.0 Ω", "—", "4.589 V", "0.510 A", "0%", "+2.0%"],
       ["恒流", "19.7 Ω", "—", "9.94 V", "0.504 A", "51.53%", "+0.8%"],
       ["恒流", "20.7 Ω", "—", "10.31 V", "0.499 A", "81.00%*", "−0.2%"],
       ["纹波", "9.0 Ω", "—", "4.589 V", "0.51 A", "21.25 mV（0.46%）", "✅"],
       ["纹波", "100 Ω", "—", "11.75 V", "0.120 A", "58.00 mV（0.48%）", "100.2 kHz"],
       ["效率", "100 Ω", "4.998 V", "11.7541 V", "0.120 A", "1.859 W", "η=75.9%"]],
      widths=[2.9, 2.3, 3.0, 3.9, 2.3, 3.0, 2.2], cap="表 6-2  首板实测数据（效率行：Iin=0.372 A，Pin=V·I=1.859 W；*该格疑为软启动瞬态读数，不参与判定）", font_size=8.5)

h2("6.4 指标判定")
table(["指标", "要求", "实测", "判定"],
      [["稳压精度", "12 V ± 5%", "−0.17%（空载）", "✅"],
       ["输入调整率", "5 V±10% 内稳定", "0.1%/V（波动 12 mV）", "✅"],
       ["恒流精度", "0.5 A ± 5%", "−0.2% ~ +2.0%", "✅"],
       ["纹波", "≤ 5%", "0.46% ~ 0.48%", "✅"],
       ["效率", "≥ 75%", "75.9%（0.12 A）", "✅"],
       ["OVP", "有过压保护", "14 V 灌入即锁存，可恢复", "✅"],
       ["OCP", "有过流保护", "未实测（仿真 5 ms@0.6 A）", "⬜ 待补"],
       ["软启动", "无过冲", "未实测（仿真 49 mV）", "⬜ 可选"]],
      widths=[4.0, 5.2, 6.4, 2.8], cap="表 6-3  课程指标实测判定")

h2("6.5 波形与实物")
p("纹波波形在满载（0.51 A）与轻载（0.12 A）两种工况下测量：波形为 100 kHz 周期纹波叠加开关边沿尖峰，"
  "峰峰值分别为 21.25 mV（0.46%）与 58.00 mV（0.48%），远优于 5% 指标；"
  "开关波形为 0~12.5 V 方波，周期 9.98 µs（100.2 kHz），与设计值一致。")
figure("图 6-2  输出纹波波形（100 Ω 负载）", "（插入示波器截图：AC 耦合、20 MHz 限带、100 mV/div、10 µs/div）")
figure("图 6-3  开关节点（SW）波形", "（插入示波器截图：DC 耦合、5 V/div、5 µs/div）")
figure("图 6-4  软启动波形（on 后 0→12 V）", "（插入示波器截图：单次触发，20 ms/div）", height_cm=5)
figure("图 6-5  实物照片（首板）", "（插入整板照片 + 测试接线照片）", height_cm=6)

h2("6.6 仿真与实测对照")
table(["指标", "仿真（满载 0.5 A）", "实测（轻载 0.12 A）", "结论"],
      [["输出电压", "12.0032 V（+0.075%）", "11.98 V（−0.17%）", "同量级，均达标"],
       ["纹波", "218 mV（1.81%）", "58 mV（0.48%）", "实测更小（轻载）"],
       ["恒流精度", "−0.18%", "−0.2% ~ +2.0%", "同量级"],
       ["负载阶跃", "跌落 1090 mV/6.4 ms", "未测", "—"],
       ["效率", "预算 ~87%", "75.9%（轻载）", "轻载偏低属正常"],
       ["OVP", "立即锁存", "14 V 灌入即锁存", "一致"],
       ["开关频率", "100 kHz", "100.2 kHz", "一致"]],
      widths=[3.6, 5.4, 5.4, 4.0], cap="表 6-4  仿真与实测对照")

h2("6.7 调试问题记录")
table(["现象", "根因", "处理"],
      [["新板烧录前读 Flash 全 0xFF", "板子未烧过程序（空片）", "本机交叉编译并烧录"],
       ["烧录成功后串口完全无输出", "缺 HAL_UART_MspInit，USART1 时钟未使能，HAL 等 UE 位死循环", "补 stm32f1xx_hal_msp.c"],
       ["串口有输出但电压/电流乱码", "newlib-nano 浮点 printf 兼容问题", "改为整数定点显示"],
       ["on 被拒：fault latched", "运行中接线动作导致 OVP 瞬态锁存", "clear 后重新 on"],
       ["示波器读数异常（1.38 V）", "10× 探头被当成 1× 显示", "改探头比为 10:1"],
       ["24 Ω 电阻发热烧毁", "12 V 下 6 W，普通 1/4 W 电阻过载 24 倍", "改用 10×1 kΩ 并联 100 Ω"]],
      widths=[5.2, 7.6, 4.0], cap="表 6-5  调试问题与处理记录")

# ======================= 第七章 =======================
h1("第七章 总结")

p("本课程设计完成了一台由 STM32F103C8T6 数字控制的 Boost 升压恒压恒流电源，从方案论证、参数计算、"
  "仿真验证、原理图与 PCB 设计，到固件开发、打样焊接、板级调试与实测，走完了完整的硬件产品开发流程。")

h2("7.1 完成情况")
table(["阶段", "交付物", "状态"],
      [["方案与参数", "拓扑/控制方案、参数表、仿真验证", "完成"],
       ["原理图", "46 器件 / 29 网的完整原理图、BOM", "完成并定稿"],
       ["PCB", "双面板布局布线、底层 GND 铺铜、DRC 0 违规", "打样并收板"],
       ["固件", "10 kHz 控制环、状态机、保护、串口命令行", "烧录并验证"],
       ["实测", "稳压/调整率/恒流/纹波/效率/OVP 六项", "达标"],
       ["文档", "01~09 号文档与报告", "完成"]],
      widths=[3.6, 9.4, 3.0], cap="表 7-1  各阶段完成情况")

h2("7.2 主要结论")
p("（1）指标达成：稳压精度 −0.17%、输入调整率 0.1%/V、恒流精度 −0.2%~+2.0%、纹波 0.46%~0.48%、"
  "轻载效率 75.9%，均满足课程要求；OVP 保护在实物上验证可锁存、可恢复。")
p("（2）仿真与实测一致：开关频率、稳压点、恒流点、OVP 行为均与仿真吻合，说明设计阶段的建模与参数计算可信，"
  "仿真驱动的设计方法是有效的。")
p("（3）智能体协作有效：设计、审查、编码、测试各环节由 AI 智能体承担重复性与验证性工作，"
  "人工聚焦于决策与物理操作，显著压缩了迭代时间；但\"智能体输出必须可验证\"这一原则贯穿始终——"
  "每一处修改都有网表回读、DRC 或串口数据作为证据。")

h2("7.3 不足与改进")
p("（1）满载 12 V/0.5 A 点因缺少功率电阻/电子负载未实测，报告中满载纹波与效率引用仿真值，"
  "建议后续用电子负载补测；")
p("（2）OCP 触发时间与软启动波形未实测，可在后续实验中用电子负载缓升与示波器单次触发补充；")
p("（3）PCB 存在 7 个死过孔、部分去耦距离偏大、插头包络偏紧，下一版可优化布局与铺铜；")
p("（4）晶振负载电容 22 pF 对应等效 CL≈14 pF，略低于晶振标称 20 pF，频率偏高数十 ppm，"
  "对串口无影响，若后续使用 USB/RTC 需改为 33 pF；")
p("（5）3.3 V 由 XC6206 提供（输入上限 6 V），因此 3.3 V 只能由 5 V 口馈电，使用中需注意。")

# ======================= 附录 =======================
h1("附录")

h2("附录 A  主要元器件清单（BOM 摘要）")
table(["序号", "位号", "型号/参数", "封装", "数量"],
      [["1", "U1", "STM32F103C8T6", "LQFP-48", "1"],
       ["2", "U2", "XC6206P332MR", "SOT-23-3", "1"],
       ["3", "U3", "INA180A2IDBVR", "SOT-23-5", "1"],
       ["4", "L1", "FSA1365-101MT 100 µH", "12.6×13.5", "1"],
       ["5", "Q1", "AO3400A", "SOT-23", "1"],
       ["6", "Q2/Q3", "SS8050 / SS8550", "SOT-23", "各 1"],
       ["7", "D1", "SS34", "SMA", "1"],
       ["8", "F1", "0468003.NRHF 3 A", "1206", "1"],
       ["9", "C7/C10", "220 µF/50 V", "D8×12", "2"],
       ["10", "C5/C6/C8/C9", "22 µF/25 V X5R", "1206", "4"],
       ["11", "Rs1", "0.1 Ω ±1%", "1206", "1"],
       ["12", "J1/J2", "KF301-5.0-2P", "插件", "2"],
       ["13", "J3/J4", "2.54 mm 4P 母座", "插件", "2"],
       ["14", "Y1", "8 MHz SMD", "5032", "1"],
       ["15", "SW1", "轻触开关 5.1×5.1", "SMD", "1"],
       ["16", "LED", "POWER/CV/CC 红色", "0603", "3"]],
      widths=[1.6, 3.0, 6.6, 3.4, 1.6], cap="表 A-1  主要元器件清单（完整 29 行见 sch_work/BOM_v3.csv）")

h2("附录 B  工程文件与证据清单")
p("原理图/PCB 源文件：嘉立创 EDA 工程 boost-cccv-psu（v3 重建版，含 46 器件）；")
p("仿真模型与结果：sim/ctrl/（Python 开关级模型、场景脚本、summary_rebuild_current_sch.json）；")
p("固件源码：firmware/Core/（main/bsp_power/control/cli）与 firmware/build_min/（一键构建工程）；")
p("设计文档：01 系统设计方案、02 仿真验证计划、03 仿真验证报告、04 设计审计、05 第二版改版说明、"
  "06 固件说明、07 3D 干涉检查、08 第三版重建与发板说明、09 板级实测实验清单；")
p("证据存档：sch_work/archive_v3/（网表快照、DFM/DRC 结果、BOM）与 sch_work/rebuild_review_20261105/（审查记录）。")

h2("附录 C  串口命令速查")
table(["命令", "作用", "返回示例"],
      [["h", "帮助", "cmds: on|off|st|sv <V>|si <A>|d <0-612>|o|ovp|clear|h"],
       ["on", "启动（软启动 50 ms）", "start: softstart 50ms"],
       ["off", "停机", "stop"],
       ["st", "状态查询", "state=CV duty=441 Vout=11.994V Iout=0.129A raw=[3238,804]"],
       ["sv 12.0", "设定输出电压", "v_set=11.997V (3239 counts)"],
       ["si 0.5", "设定恒流值", "i_set=0.500A (3102 counts)"],
       ["clear", "清除故障", "fault cleared"],
       ["ovp", "OVP 注入测试", "OVP test: expect FAULT_OVP; then sv 12.0 + clear"]],
      widths=[2.6, 4.4, 9.0], cap="表 C-1  串口命令速查")

doc.save(OUT)
print("saved:", OUT)
