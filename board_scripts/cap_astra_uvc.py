import cv2, sys

dev = int(open('/cap/astra_dev.txt').read())
cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
if not cap.isOpened():
    raise SystemExit(f'cannot open /dev/video{dev}')
for _ in range(5):
    cap.read()
ret, frame = cap.read()
cap.release()
if not ret or frame is None:
    raise SystemExit('capture failed')
cv2.imwrite('/out/astra_uvc_latest.jpg', frame)
print('captured', frame.shape)
