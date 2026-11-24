# -*- coding: utf-8 -*-
"""生成报告用示意图：系统结构框图、程序流程图、串口交互记录"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager
import os

FONT = "C:/Windows/Fonts/msyh.ttc"
fp = font_manager.FontProperties(fname=FONT)
matplotlib.rcParams["axes.unicode_minus"] = False

# ---------- 图 1-1 系统总体结构框图 ----------
fig, ax = plt.subplots(figsize=(10.6, 5.9), dpi=240)
ax.set_xlim(0, 100); ax.set_ylim(0, 58); ax.axis("off")

def box(x, y, w, h, text, fc="#EAF2FB", ec="#3B6EA5", fs=11.0, lw=1.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.35,rounding_size=0.8",
                                fc=fc, ec=ec, lw=lw))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontproperties=fp, fontsize=fs)

def arrow(x1, y1, x2, y2, style="-|>", lw=1.4, color="#333333", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                                 lw=lw, color=color, linestyle=ls, shrinkA=2, shrinkB=2))

# 功率通道（上排）
box(1, 44, 10, 7, "J1\n5 V 输入", fc="#FDF3E3", ec="#C8842A")
box(13.5, 44, 11, 7, "F1\n3 A 保险丝", fc="#FDF3E3", ec="#C8842A")
box(27, 44, 13, 7, "输入滤波\nC5/C6/C7", fc="#FDF3E3", ec="#C8842A")
box(42.5, 43, 20, 9, "Boost 功率级\nL1/Q1/D1\nC8/C9/C10", fc="#FBE7E7", ec="#B03A3A", fs=10.8)
box(65, 44, 13, 7, "Rs1 0.1 Ω\n电流分流", fc="#FDF3E3", ec="#C8842A")
box(80.5, 44, 12, 7, "J2 输出\n12 V / 0.5 A", fc="#FDF3E3", ec="#C8842A")
for x1, x2 in [(11, 13.5), (24.5, 27), (40, 42.5), (62.5, 65), (78, 80.5)]:
    arrow(x1, 47.5, x2, 47.5)

# 采样（中排）
box(46, 31, 17, 7, "电压分压 10/46\n+ RC 滤波 (τ=88.3 µs)", fc="#EAF7EE", ec="#3E7B54", fs=11.2)
box(66, 31, 17, 7, "U3 INA180A2 ×50\n(5 V/A)", fc="#EAF7EE", ec="#3E7B54", fs=11.2)
arrow(52.5, 43, 52.5, 38.2, ls="--")   # 从 VOUT 采样
arrow(71.5, 43.9, 74.5, 38.2, ls="--") # 从 Rs1 采样
ax.text(53.6, 40.6, "VOUT", fontproperties=fp, fontsize=8.5, color="#666666")
ax.text(63.0, 39.4, "VOUT→VLOAD", fontproperties=fp, fontsize=7.5, color="#777777")

# 控制（中下排）
box(36, 17.5, 24, 9, "U1 STM32F103C8T6\n12-bit ADC + DMA 采样\n10 kHz 数字 PI + 限幅器", fc="#EDF0FA", ec="#4A55A2", fs=11.2)
box(64, 17.5, 15, 9, "TIM1 PWM\n100 kHz\n(1/720 分辨率)", fc="#EDF0FA", ec="#4A55A2", fs=11.2)
box(81.5, 17.5, 13, 9, "图腾柱驱动\nQ2/Q3", fc="#EDF0FA", ec="#4A55A2", fs=10.8)
arrow(48.5, 34.6, 48.5, 26.8)  # 分压 → MCU
arrow(74.5, 34.6, 60.5, 26.8)  # INA → MCU
arrow(60.2, 22, 64, 22)
arrow(79.2, 22, 81.5, 22)
arrow(87.5, 26.8, 87.5, 43.2)  # 驱动 → Q1 栅极
ax.text(88.4, 34.8, "栅极驱动\n0.7~4.3 V", fontproperties=fp, fontsize=8.0, color="#666666")

# 辅助（下排）
box(1, 4.5, 13, 7, "U2 XC6206\n3.3 V/200 mA", fc="#F2F2F2", ec="#777777", fs=10.2)
box(15.5, 4.5, 13, 7, "Y1 8 MHz\n复位/BOOT0", fc="#F2F2F2", ec="#777777", fs=10.2)
box(30, 4.5, 11, 7, "J3 SWD\n烧录调试", fc="#F2F2F2", ec="#777777", fs=10.2)
box(42.5, 4.5, 13, 7, "J4 串口\n115200 8N1", fc="#F2F2F2", ec="#777777", fs=10.2)
box(57, 4.5, 15, 7, "LED 指示\nPOWER/CV/CC", fc="#F2F2F2", ec="#777777", fs=10.2)
box(73.5, 4.5, 15, 7, "故障保护\nOVP 13.2 V\nOCP 0.6 A", fc="#FBEDED", ec="#B03A3A", fs=10.0)


ax.text(50, 55.6, "功率通道：5 V → 12 V / 0.5 A", ha="center", fontproperties=fp, fontsize=13, color="#444444")
ax.text(50, 1.2, "采样 → 数字控制 → 驱动 闭环；保护与接口作为旁路", ha="center", fontproperties=fp, fontsize=11, color="#777777")

plt.tight_layout()
plt.savefig("img/fig_struct.png", bbox_inches="tight", facecolor="white")
plt.close()

# ---------- 图 5-1 程序流程图 ----------
fig, ax = plt.subplots(figsize=(8.0, 10.6), dpi=240)
ax.set_xlim(0, 60); ax.set_ylim(0, 96); ax.axis("off")

def rbox(cx, cy, w, h, text, fc="#EAF2FB", ec="#3B6EA5", fs=10.5):
    ax.add_patch(FancyBboxPatch((cx - w/2, cy - h/2), w, h, boxstyle="round,pad=0.3,rounding_size=0.7",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(cx, cy, text, ha="center", va="center", fontproperties=fp, fontsize=fs)

def diamond(cx, cy, w, h, text, fs=10.2):
    ax.add_patch(plt.Polygon([[cx, cy + h/2], [cx + w/2, cy], [cx, cy - h/2], [cx - w/2, cy]],
                             closed=True, fc="#FFF6E5", ec="#C8842A", lw=1.2))
    ax.text(cx, cy, text, ha="center", va="center", fontproperties=fp, fontsize=fs)

def arr(x1, y1, x2, y2, label=None, lx=0, ly=0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                                 lw=1.2, color="#333333", shrinkA=1, shrinkB=1))
    if label:
        ax.text((x1 + x2)/2 + lx, (y1 + y2)/2 + ly, label, fontproperties=fp, fontsize=8.5, color="#555555")

rbox(30, 92, 22, 5.5, "上电复位", fc="#F2F2F2", ec="#777777")
arr(30, 89.2, 30, 85.8)
rbox(30, 82.5, 34, 6.5, "初始化：时钟 72 MHz / GPIO / TIM1 PWM /\nTIM2 10 kHz / ADC+DMA / 串口 / 状态机", fs=9)
arr(30, 79.2, 30, 75.8)
rbox(30, 72.5, 26, 5.8, "STANDBY（PWM=0，三灯灭）", fc="#F7F7F7", ec="#888888")
diamond(30, 64, 20, 8, "收到 on ?", fs=9.5)
arr(30, 69.6, 30, 68.2)
arr(30, 60, 30, 55.6, "是", 2.5, 0)
rbox(30, 52, 30, 6.2, "SOFTSTART：参考 50 ms 线性斜坡\n积分器跟踪钳位", fc="#EAF7EE", ec="#3E7B54")
arr(30, 48.8, 30, 45.2)
rbox(30, 41.5, 34, 6.5, "10 kHz 控制中断（TIM2）\nADC 采样 → 保护判定 → PI / 限幅器取小 → PWM", fc="#EDF0FA", ec="#4A55A2", fs=9)
arr(30, 38.2, 30, 34.2)

diamond(30, 29, 22, 9, "OVP / OCP /\n反馈断线 ?", fs=8.5)
arr(30, 24.4, 30, 20.2, "否", 2.5, 0)
rbox(30, 16.5, 40, 7, "按电压环与限幅器取小值输出占空比\nCV / CC 状态判定（迟滞）→ 对应 LED 点亮", fs=8.8)
arr(30, 12.9, 30, 9.2, "循环执行（每 100 µs）", 14.5, -1.5)
rbox(30, 6.2, 26, 5.2, "继续运行（返回控制中断）", fc="#EAF7EE", ec="#3E7B54", fs=9)

# 右侧：故障分支
arr(41, 29, 47, 29, "是", 0, 1.2)
rbox(52, 29, 15, 12, "FAULT 锁存\nPWM=0\nPOWER 灯 1 Hz 闪\n（OV/OC/FB）", fc="#FBEDED", ec="#B03A3A", fs=8.8)
ax.add_patch(FancyArrowPatch((50, 23), (44.5, 16.2), arrowstyle="-|>", mutation_scale=13, lw=1.1,
                             color="#333333", linestyle="--", shrinkA=1, shrinkB=1))
ax.text(46.5, 20.6, "clear / 断电复位", fontproperties=fp, fontsize=8.5, color="#555555")

# 左侧：CLI 分支
arr(19, 64, 13, 64, "否", 0, 1.2)
rbox(7, 64, 11, 9, "主循环\nCLI 轮询\n(on/off/st/sv…)", fc="#F2F2F2", ec="#777777", fs=8.5)
ax.text(30, 1.0, "控制环在 TIM2 更新中断中运行；主循环只做非阻塞命令行", ha="center",
        fontproperties=fp, fontsize=8.5, color="#777777")

plt.tight_layout()
plt.savefig("img/fig_flow.png", bbox_inches="tight", facecolor="white")
plt.close()
print("figs ok")
