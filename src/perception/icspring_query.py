#!/usr/bin/env python3
"""Enumerate V4L2 controls, formats and frame sizes for a UVC camera."""
import fcntl, struct, os, sys

DEV = sys.argv[1] if len(sys.argv) > 1 else "/dev/video20"

VIDIOC_QUERYCAP      = 0x80685600
VIDIOC_ENUM_FMT      = 0xc0405602
VIDIOC_ENUM_FRAMESIZES = 0xc02c564a
VIDIOC_ENUM_FRAMEINTERVALS = 0xc034564b
VIDIOC_QUERYCTRL     = 0xc0445624
VIDIOC_G_CTRL        = 0xc008561b
VIDIOC_QUERYMENU     = 0xc02c5625
NEXT_CTRL            = 0x80000000

TNAME = {1: "int", 2: "bool", 3: "menu", 4: "button", 5: "bitmask", 6: "string", 7: "int64"}
DISABLED, GRABBED, INACTIVE = 1, 2, 0x10

def cstr(b):
    return b.split(bytes([0]))[0].decode(errors="replace")

fd = os.open(DEV, os.O_RDWR)

cap = bytearray(104)
fcntl.ioctl(fd, VIDIOC_QUERYCAP, cap, True)
print(f"== Device: {cstr(cap[16:48])} | driver={cstr(cap[0:16])} | bus={cstr(cap[48:80])}")

print("== Formats ==")
i = 0
while True:
    b = bytearray(64)
    struct.pack_into("II", b, 0, i, 1)
    try:
        fcntl.ioctl(fd, VIDIOC_ENUM_FMT, b, True)
    except OSError:
        break
    pixfmt = struct.unpack_from("I", b, 12)[0]
    fourcc = struct.pack("I", pixfmt).decode(errors="replace")
    desc = cstr(b[16:48])
    print(f"- {fourcc} ({desc})")
    j = 0
    while True:
        sb = bytearray(48)
        struct.pack_into("II", sb, 0, j, pixfmt)
        try:
            fcntl.ioctl(fd, VIDIOC_ENUM_FRAMESIZES, sb, True)
        except OSError:
            break
        stype = struct.unpack_from("I", sb, 8)[0]
        if stype == 1:
            w, h = struct.unpack_from("II", sb, 12)
            k = 0
            fpsl = []
            while True:
                fb = bytearray(56)
                struct.pack_into("IIII", fb, 0, k, pixfmt, w, h)
                try:
                    fcntl.ioctl(fd, VIDIOC_ENUM_FRAMEINTERVALS, fb, True)
                except OSError:
                    break
                itype = struct.unpack_from("I", fb, 16)[0]
                if itype == 1:
                    n, d = struct.unpack_from("II", fb, 20)
                    fpsl.append(f"{d//n if n else 0}fps")
                k += 1
            print(f"    {w}x{h} @ {', '.join(fpsl) if fpsl else '?'}")
        else:
            minw, maxw, stepw, minh, maxh, steph = struct.unpack_from("IIIIII", sb, 12)
            print(f"    stepwise {minw}..{maxw} (step {stepw}) x {minh}..{maxh} (step {steph})")
        j += 1
    i += 1

print("== Controls ==")
cid = NEXT_CTRL
for _ in range(64):
    buf = bytearray(80)
    struct.pack_into("I", buf, 0, cid)
    try:
        fcntl.ioctl(fd, VIDIOC_QUERYCTRL, buf, True)
    except OSError:
        break
    cid_out = struct.unpack_from("I", buf, 0)[0]
    typ = struct.unpack_from("I", buf, 4)[0]
    name = cstr(buf[8:40])
    mn, mx, step, default = struct.unpack_from("iiii", buf, 40)
    flags = struct.unpack_from("I", buf, 56)[0]
    cur = "-"
    if not (flags & DISABLED) and typ != 4:
        g = bytearray(16)
        struct.pack_into("II", g, 0, cid_out, 0)
        try:
            fcntl.ioctl(fd, VIDIOC_G_CTRL, g, True)
            cur = str(struct.unpack_from("i", g, 4)[0])
        except OSError:
            cur = "<read-err>"
    stat = " ".join(s for f, s in ((DISABLED, "DISABLED"), (GRABBED, "GRABBED"), (INACTIVE, "INACTIVE")) if flags & f)
    print(f"- {name} [{TNAME.get(typ, typ)}] range={mn}..{mx} step={step} default={default} current={cur} {stat}")
    if typ == 3:
        opts = []
        for mi in range(mn, min(mx, 64) + 1):
            mb = bytearray(80)
            struct.pack_into("II", mb, 0, cid_out, mi)
            try:
                fcntl.ioctl(fd, VIDIOC_QUERYMENU, mb, True)
                opts.append(f"{mi}={cstr(mb[8:40])}")
            except OSError:
                pass
        if opts:
            print("    options: " + ", ".join(opts))
    cid = (cid_out + 1) | NEXT_CTRL

os.close(fd)
