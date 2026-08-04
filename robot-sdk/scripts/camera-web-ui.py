#!/usr/bin/env python3
"""Small dependency-free web UI for ROS camera topics.

The HTTP layer only reads image topics. It never publishes motor or arm commands.
"""

import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image


PORT = int(rospy.get_param("/camera_web/port", 8088)) if rospy.core.is_initialized() else 8088


PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RK3588S 小车视觉</title>
<style>
  :root { color-scheme: dark; --bg:#11151b; --card:#1b222c; --line:#344152; --ok:#52d273; }
  * { box-sizing:border-box; }
  body { margin:0; padding:18px; background:var(--bg); color:#edf2f7; font-family:system-ui,"Microsoft YaHei",sans-serif; }
  header { display:flex; gap:16px; align-items:center; justify-content:space-between; margin-bottom:14px; }
  h1 { font-size:20px; margin:0; }
  #status { color:#ffca58; font-size:14px; }
  #status.ok { color:var(--ok); }
  nav { display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; }
  button { border:1px solid var(--line); border-radius:7px; padding:8px 13px; color:#eaf0f6; background:#222b37; cursor:pointer; }
  button.active { background:#1969a6; border-color:#4ba3e3; }
  main { max-width:1100px; margin:auto; }
  .viewer { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; }
  .image-wrap { position:relative; line-height:0; min-height:240px; display:flex; justify-content:center; align-items:center; }
  #stream { display:block; max-width:100%; max-height:72vh; border-radius:6px; cursor:crosshair; }
  #marker { display:none; position:absolute; width:18px; height:18px; border:2px solid #ff3b30; border-radius:50%; pointer-events:none; transform:translate(-50%,-50%); }
  #marker:before,#marker:after { content:""; position:absolute; background:#ff3b30; }
  #marker:before { width:24px; height:2px; left:-5px; top:6px; }
  #marker:after { width:2px; height:24px; left:6px; top:-5px; }
  .info { display:flex; gap:18px; flex-wrap:wrap; padding:10px 2px 2px; color:#b9c6d4; font-size:14px; }
  code { color:#8bd5ff; }
  .hint { margin-top:12px; color:#9eabb8; font-size:13px; line-height:1.6; }
</style>
</head>
<body><main>
<header><h1>RK3588S 小车视觉界面</h1><span id="status">正在连接……</span></header>
<nav>
  <button data-view="rgb" class="active">彩色画面</button>
  <button data-view="detections">识别结果</button>
  <button data-view="depth">深度伪彩色</button>
  <button id="snapshot">打开当前快照</button>
</nav>
<section class="viewer">
  <div class="image-wrap"><img id="stream" src="/stream/rgb.mjpg"><i id="marker"></i></div>
  <div class="info"><span>画面：<code id="viewName">RGB</code></span><span>点击坐标：<code id="coord">未选择</code></span><span>分辨率：<code id="size">等待画面</code></span></div>
</section>
<p class="hint">点击画面可读取像素坐标。此页面只读取相机数据，不会控制轮子或机械臂。深度图颜色表示相对距离，精确距离后续可通过深度像素接口读取。</p>
</main>
<script>
const img=document.querySelector('#stream'), marker=document.querySelector('#marker');
const coord=document.querySelector('#coord'), size=document.querySelector('#size');
const names={rgb:'RGB',detections:'OpenCV检测',depth:'深度'}; let view='rgb';
document.querySelectorAll('button[data-view]').forEach(b=>b.onclick=()=>{
  view=b.dataset.view; img.src='/stream/'+view+'.mjpg?t='+Date.now();
  document.querySelectorAll('button[data-view]').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelector('#viewName').textContent=names[view]; marker.style.display='none'; coord.textContent='未选择';
});
img.onload=()=>size.textContent=img.naturalWidth+'×'+img.naturalHeight;
img.onclick=e=>{
  const r=img.getBoundingClientRect();
  const x=Math.round((e.clientX-r.left)*img.naturalWidth/r.width), y=Math.round((e.clientY-r.top)*img.naturalHeight/r.height);
  coord.textContent='x='+x+', y='+y;
  marker.style.display='block'; marker.style.left=(e.clientX-r.left+r.left-img.parentElement.getBoundingClientRect().left)+'px'; marker.style.top=(e.clientY-r.top+r.top-img.parentElement.getBoundingClientRect().top)+'px';
};
document.querySelector('#snapshot').onclick=()=>window.open('/snapshot/'+view+'.jpg?t='+Date.now(),'_blank');
async function poll(){try{const s=await (await fetch('/api/status',{cache:'no-store'})).json();const ok=s.rgb&&s.depth;const el=document.querySelector('#status');el.textContent=ok?'相机在线｜RGB '+s.rgb_fps.toFixed(1)+' FPS｜Depth '+s.depth_fps.toFixed(1)+' FPS':'等待相机数据';el.className=ok?'ok':'';}catch(e){document.querySelector('#status').textContent='网页服务连接失败';}setTimeout(poll,1500)}poll();
</script></body></html>"""


class FrameSlot:
    def __init__(self):
        self.jpeg = None
        self.updated = 0.0
        self.frames = 0
        self.first = 0.0
        self.condition = threading.Condition()

    def put(self, image):
        now = time.time()
        # Ten browser frames per second are smooth enough and leave CPU time
        # for perception, ROS and arm control.
        if now - self.updated < 0.09:
            return
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            return
        with self.condition:
            self.jpeg = encoded.tobytes()
            self.updated = now
            if not self.first:
                self.first = now
            self.frames += 1
            self.condition.notify_all()

    def fps(self):
        elapsed = self.updated - self.first
        return float(self.frames - 1) / elapsed if elapsed > 0 and self.frames > 1 else 0.0


bridge = CvBridge()
slots = {name: FrameSlot() for name in ("rgb", "detections", "depth")}


def color_callback(message, name):
    try:
        frame = bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
        slots[name].put(frame)
    except Exception as error:
        rospy.logwarn_throttle(10.0, "camera web %s conversion failed: %s", name, error)


def depth_callback(message):
    try:
        depth = bridge.imgmsg_to_cv2(message, desired_encoding="passthrough")
        depth = np.asarray(depth, dtype=np.float32)
        valid = depth[np.isfinite(depth) & (depth > 0)]
        if valid.size:
            near, far = np.percentile(valid, (3, 97))
            if far <= near:
                far = near + 1.0
            gray = np.clip((depth - near) * 255.0 / (far - near), 0, 255).astype(np.uint8)
            gray[~np.isfinite(depth) | (depth <= 0)] = 0
        else:
            gray = np.zeros(depth.shape, dtype=np.uint8)
        slots["depth"].put(cv2.applyColorMap(255 - gray, cv2.COLORMAP_TURBO))
    except Exception as error:
        rospy.logwarn_throttle(10.0, "camera web depth conversion failed: %s", error)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def send_bytes(self, payload, content_type, status=HTTPStatus.OK):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/status":
            now = time.time()
            body = {
                name: bool(slot.jpeg and now - slot.updated < 3.0)
                for name, slot in slots.items()
            }
            body.update({name + "_fps": slot.fps() for name, slot in slots.items()})
            return self.send_bytes(json.dumps(body).encode(), "application/json")
        for name in slots:
            if path == "/snapshot/%s.jpg" % name:
                frame = slots[name].jpeg
                if frame is None:
                    return self.send_bytes(b"frame unavailable\n", "text/plain", HTTPStatus.SERVICE_UNAVAILABLE)
                return self.send_bytes(frame, "image/jpeg")
            if path == "/stream/%s.mjpg" % name:
                return self.stream(name)
        return self.send_bytes(b"not found\n", "text/plain", HTTPStatus.NOT_FOUND)

    def stream(self, name):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        slot = slots[name]
        last = 0.0
        try:
            while not rospy.is_shutdown():
                with slot.condition:
                    slot.condition.wait_for(lambda: slot.updated > last, timeout=2.0)
                    frame, last = slot.jpeg, slot.updated
                if frame is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n")
                self.wfile.write(frame + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    rospy.init_node("camera_web_ui", anonymous=False, disable_signals=True)
    rospy.Subscriber("/astra_camera/rgb/image_raw", Image, color_callback, callback_args="rgb", queue_size=1, buff_size=2 ** 24)
    rospy.Subscriber("/detections/image", Image, color_callback, callback_args="detections", queue_size=1, buff_size=2 ** 24)
    rospy.Subscriber("/astra_camera/depth/image_raw", Image, depth_callback, queue_size=1, buff_size=2 ** 24)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    rospy.loginfo("camera web UI listening on 0.0.0.0:%d", PORT)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
