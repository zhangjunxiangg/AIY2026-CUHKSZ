import cv2, glob, sys

for dev in sorted(glob.glob('/dev/video*')):
    idx = int(dev.replace('/dev/video', ''))
    try:
        name = open(f'/sys/class/video4linux/video{idx}/name').read().strip()
    except Exception:
        name = ''
    if 'USB 2.0 Camera' not in name:
        continue
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap.isOpened():
        continue
    ret, frame = cap.read()
    cap.release()
    if ret and frame is not None and frame.size > 0:
        print(idx)
        sys.exit(0)
print('Astra UVC not found', file=sys.stderr)
sys.exit(1)
