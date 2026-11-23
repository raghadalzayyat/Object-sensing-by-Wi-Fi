"""
csi_web.py  -  لوحة ثيرمال على localhost لكشف حركة الإنسان.

شغّله وافتح:  http://127.0.0.1:5000   (بيفتح لوحده بعد ثانية ونص)
مفيش اعتماد على الإنترنت (من غير Chart.js ولا CDN) - الرسم كله Canvas.
"""
import logging
import threading
import webbrowser

import numpy as np
from flask import Flask, Response, jsonify, request

from csi_core import F_ENERGY, F_MI, F_MOTION, F_NORM, F_SEQ, HEAT_COLS, MOVE_ON, CSIReceiver

HOST = "127.0.0.1"
WEB_PORT = 5000

app = Flask(__name__)
rx = CSIReceiver().start()

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WiFi CSI Thermal</title>
<style>
  body { font-family: Tahoma, Arial, sans-serif; background:#0f172a; color:#f8fafc; margin:0; padding:16px; text-align:center; }
  .card { background:#1e293b; border-radius:12px; padding:16px; max-width:1100px; margin:auto; box-shadow:0 4px 15px rgba(0,0,0,.5); }
  h2 { margin:4px 0 12px; font-size:20px; }
  .bar { display:flex; gap:10px; justify-content:center; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  .badge { padding:8px 18px; border-radius:8px; font-weight:bold; min-width:120px; }
  .info { background:#0b1220; padding:8px 14px; border-radius:8px; font-size:14px; color:#cbd5e1; }
  .still { background:#16a34a; } .moving { background:#dc2626; } .calib { background:#d97706; } .nodata { background:#6b7280; }
  canvas { width:100%; display:block; border-radius:8px; background:#000; }
  #tl { margin-top:10px; height:130px; }
  label { font-size:14px; color:#cbd5e1; }
  button { background:#334155; color:#f8fafc; border:0; padding:8px 14px; border-radius:8px; cursor:pointer; font-size:14px; }
  button:hover { background:#475569; }
  .legend { display:flex; align-items:center; gap:8px; justify-content:center; margin-top:10px; font-size:13px; color:#94a3b8; direction:ltr; }
  #grad { width:260px; height:12px; border-radius:6px; }
  #msg { font-size:12px; color:#94a3b8; margin-top:8px; word-break:break-word; }
</style>
</head>
<body>
<div class="card">
  <h2>لوحة Wi-Fi CSI الثيرمال المباشرة - كشف حركة الإنسان</h2>
  <div class="bar">
    <div id="badge" class="badge nodata">جاري الاتصال...</div>
    <div class="info">الباكيتات: <b id="rate">0</b> / ثانية</div>
    <div class="info">RSSI: <b id="rssi">--</b> dBm</div>
    <label>الحساسية <input id="sens" type="range" min="1" max="15" step="1" value="5"> <b id="sensv">5</b></label>
    <button id="modeBtn">الوضع: حركة</button>
  </div>
  <canvas id="heat" width="1000" height="420"></canvas>
  <canvas id="tl" width="1000" height="130"></canvas>
  <div class="legend"><span>ساكن</span><canvas id="grad" width="260" height="12"></canvas><span>حركة قوية</span></div>
  <div id="msg"></div>
</div>

<script>
const COLS = __COLS__;
const MOVE_ON = __MOVE_ON__;
const NSC = 64;

const $ = id => document.getElementById(id);
const heat = $('heat'), hctx = heat.getContext('2d');
const tl = $('tl'), tctx = tl.getContext('2d');
const off = document.createElement('canvas');
off.width = COLS; off.height = 52;
const octx = off.getContext('2d');

// ---- jet colormap (256 درجة) ----
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const LUT = new Uint8ClampedArray(256 * 3);
for (let i = 0; i < 256; i++) {
  const v = i / 255;
  LUT[i*3]   = clamp(1.5 - Math.abs(4*v - 3), 0, 1) * 255;
  LUT[i*3+1] = clamp(1.5 - Math.abs(4*v - 2), 0, 1) * 255;
  LUT[i*3+2] = clamp(1.5 - Math.abs(4*v - 1), 0, 1) * 255;
}
(function drawGrad() {
  const g = $('grad').getContext('2d');
  for (let x = 0; x < 260; x++) {
    const i = Math.round(x / 259 * 255);
    g.fillStyle = `rgb(${LUT[i*3]},${LUT[i*3+1]},${LUT[i*3+2]})`;
    g.fillRect(x, 0, 1, 12);
  }
})();

let history = [];     // كل عنصر: {m:[64], r:[64], i:mi}
let valid = null;     // أرقام الترددات الشغالة
let lastSeq = 0;
let quiet = 0.02;
let sens = 5;
let mode = 'motion';
let rawLo = 0, rawHi = 1, rawTick = 0;

$('sens').addEventListener('input', e => { sens = +e.target.value; $('sensv').textContent = sens; });
$('modeBtn').addEventListener('click', () => {
  mode = (mode === 'motion') ? 'raw' : 'motion';
  $('modeBtn').textContent = 'الوضع: ' + (mode === 'motion' ? 'حركة' : 'إشارة خام');
});

function drawHeat() {
  const rows = valid ? valid : Array.from({length: NSC}, (_, i) => i);
  const nR = rows.length;
  if (off.height !== nR) off.height = nR;
  const img = octx.createImageData(COLS, nR);
  const d = img.data;
  const n = history.length;

  let lo = 0, hi = 1;
  if (mode === 'motion') {
    hi = Math.max(quiet, 1e-4) * (30 / sens);
  } else {
    if (rawTick++ % 15 === 0 && n > 5) {
      const vals = [];
      for (let c = Math.max(0, n - COLS); c < n; c++) for (let r = 0; r < nR; r++) vals.push(history[c].r[rows[r]]);
      vals.sort((a, b) => a - b);
      rawLo = vals[Math.floor(vals.length * 0.02)];
      rawHi = vals[Math.floor(vals.length * 0.98)];
    }
    lo = rawLo; hi = Math.max(rawHi, rawLo + 1e-6);
  }
  const span = hi - lo;

  for (let c = 0; c < COLS; c++) {
    const h = history[n - COLS + c];
    for (let r = 0; r < nR; r++) {
      let v = 0;
      if (h) v = ((mode === 'motion' ? h.m[rows[r]] : h.r[rows[r]]) - lo) / span;
      const li = Math.round(clamp(v, 0, 1) * 255);
      const p = ((nR - 1 - r) * COLS + c) * 4;   // الصف 0 تحت
      d[p] = LUT[li*3]; d[p+1] = LUT[li*3+1]; d[p+2] = LUT[li*3+2]; d[p+3] = 255;
    }
  }
  octx.putImageData(img, 0, 0);
  hctx.imageSmoothingEnabled = true;
  hctx.drawImage(off, 0, 0, heat.width, heat.height);
}

function drawTimeline() {
  const W = tl.width, H = tl.height, n = history.length;
  tctx.clearRect(0, 0, W, H);
  tctx.fillStyle = '#0b1220'; tctx.fillRect(0, 0, W, H);
  const thr = Math.max(quiet, 1e-4) * MOVE_ON;
  let mx = thr * 1.5;
  for (let c = Math.max(0, n - COLS); c < n; c++) mx = Math.max(mx, history[c].i);
  mx *= 1.15;
  const Y = v => H - 8 - (v / mx) * (H - 16);

  tctx.strokeStyle = '#ef4444'; tctx.setLineDash([6, 5]); tctx.lineWidth = 1;
  tctx.beginPath(); tctx.moveTo(0, Y(thr)); tctx.lineTo(W, Y(thr)); tctx.stroke();
  tctx.setLineDash([]);

  tctx.strokeStyle = '#22c55e'; tctx.lineWidth = 2; tctx.beginPath();
  let started = false;
  for (let c = 0; c < COLS; c++) {
    const h = history[n - COLS + c];
    if (!h) continue;
    const x = c / (COLS - 1) * W, y = Y(h.i);
    if (!started) { tctx.moveTo(x, y); started = true; } else tctx.lineTo(x, y);
  }
  tctx.stroke();
  tctx.fillStyle = '#94a3b8'; tctx.font = '13px sans-serif'; tctx.textAlign = 'left';
  tctx.fillText('Motion index  (dashed = threshold)', 8, 16);
}

const STATE_TXT = {STILL:['سكون','still'], MOVING:['حركة!','moving'], CALIBRATING:['معايرة... (ما تتحركش 3 ثواني)','calib'], 'NO DATA':['مفيش بيانات','nodata']};

async function poll() {
  try {
    const res = await fetch('/data?since=' + lastSeq, {cache: 'no-store'});
    const d = await res.json();
    if (d.seq < lastSeq) history = [];       // السيرفر اتعمله restart
    lastSeq = d.seq;
    valid = d.valid;
    quiet = d.quiet;
    for (const f of d.frames) history.push({m: f.m, r: f.r, i: f.i});
    if (history.length > COLS * 2) history.splice(0, history.length - COLS * 2);

    const st = STATE_TXT[d.state] || [d.state, 'nodata'];
    const b = $('badge'); b.textContent = st[0]; b.className = 'badge ' + st[1];
    $('rate').textContent = d.rate;
    $('rssi').textContent = d.state === 'NO DATA' ? '--' : d.rssi;
    $('msg').textContent = d.state === 'NO DATA' ? d.status : '';
  } catch (err) {
    $('msg').textContent = 'السيرفر مش بيرد: ' + err;
  }
  setTimeout(poll, 30);
}

function loop() { drawHeat(); drawTimeline(); requestAnimationFrame(loop); }
poll();
requestAnimationFrame(loop);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    page = HTML_PAGE.replace("__COLS__", str(HEAT_COLS)).replace("__MOVE_ON__", str(MOVE_ON))
    return Response(page, mimetype="text/html")


@app.route("/data")
def data():
    since = request.args.get("since", default=0, type=int)
    frames = rx.frames_since(since)
    valid = rx.valid
    return jsonify(
        seq=int(rx.seq),
        status=rx.status,
        state=rx.state(),
        rate=int(rx.packet_rate()),
        quiet=float(rx.quiet),
        rssi=int(rx.last_rssi),
        valid=None if valid is None else np.flatnonzero(valid).tolist(),
        frames=[
            {
                "s": int(f[F_SEQ]),
                "m": np.round(f[F_MOTION].astype(np.float64), 4).tolist(),
                "r": np.round(f[F_NORM].astype(np.float64), 4).tolist(),
                "i": round(float(f[F_MI]), 5),
                "e": round(float(f[F_ENERGY]), 2),
            }
            for f in frames
        ],
    )


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)   # من غير spam في التيرمنال
    url = f"http://{HOST}:{WEB_PORT}"
    print(f"Open {url}   (Ctrl+C to stop)")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=WEB_PORT, debug=False, threaded=True, use_reloader=False)
