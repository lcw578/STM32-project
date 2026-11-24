# -*- coding: utf-8 -*-
"""把实测串口交互记录渲染为终端风格图片（数据为真实收发内容）"""
from PIL import Image, ImageDraw, ImageFont

lines = [
    ("=== Boost CCCV PSU fw v1.0 ===", "#6A9955"),
    ("type h for help, on to start", "#6A9955"),
    ("state=STANDBY duty=0 Vout=4.793V Iout=0.000A raw=[1294,0]", "#D4D4D4"),
    ("> h", "#4EC9B0"),
    ("cmds: on|off|st|sv <V>|si <A>|d <0-612>|o|ovp|clear|h", "#D4D4D4"),
    ("> on", "#4EC9B0"),
    ("start: softstart 50ms", "#DCDCAA"),
    ("> st", "#4EC9B0"),
    ("state=CV duty=54 Vout=11.986V Iout=0.000A raw=[3236,1]", "#D4D4D4"),
    ("> st", "#4EC9B0"),
    ("state=CV duty=441 Vout=11.994V Iout=0.129A raw=[3238,804]", "#D4D4D4"),
    ("> ovp", "#4EC9B0"),
    ("OVP test: expect FAULT_OVP; then sv 12.0 + clear", "#DCDCAA"),
    ("> st", "#4EC9B0"),
    ("state=FAULT_OVP duty=0 Vout=5.637V Iout=0.000A raw=[1522,0]", "#F48771"),
    ("> clear", "#4EC9B0"),
    ("fault cleared", "#DCDCAA"),
    ("> st", "#4EC9B0"),
    ("state=STANDBY duty=0 Vout=4.289V Iout=0.000A raw=[1158,2]", "#D4D4D4"),
]

W, H = 1180, 620
img = Image.new("RGB", (W, H), "#0C0C0C")
d = ImageDraw.Draw(img)
font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 19)
y = 26
for text, color in lines:
    d.text((26, y), text, font=font, fill=color)
    y += 29
img.save("img/term.png")
print("terminal image ok")
