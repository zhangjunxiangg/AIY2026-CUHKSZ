#!/usr/bin/env python3
"""key_debug.py — 键盘原始字节调试：按什么键就打印什么字节。按 q 退出。"""
import os
import select
import sys
import termios
import tty

fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
tty.setcbreak(fd)
print("按任意键看字节（方向键/A/D/W），q 退出：")
try:
    while True:
        r, _, _ = select.select([fd], [], [], 0.5)
        if not r:
            continue
        data = os.read(fd, 8)
        for b in data:
            print(f"  byte: 0x{b:02x} ({chr(b) if 32 <= b < 127 else '?'})")
        if b"q" in data:
            break
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print("退出")
