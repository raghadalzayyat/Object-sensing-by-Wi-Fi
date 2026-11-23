"""
csi_core.py  -  القلب المشترك لكل الواجهات.

بيعمل 3 حاجات:
  1) يقرا من الـ ESP32 على الـ Serial في Thread لوحده (من غير تأخير، ولو اتأخر بيلحق).
  2) يحدد الترددات الفرعية الشغالة تلقائيًا (الفاضية بتبقى صفر وبنخفيها).
  3) يحسب "الحركة": كل باكيت بنطبّعه (نقسمه على متوسطه عشان تأثير الـ AGC يروح)،
     وبعدين نحسب الانحراف المعياري على آخر WIN إطارات لكل تردد فرعي.
     لما حد يتحرك بين الـ ESP والراوتر الانحراف ده بيعلى = ألوان حارة (أحمر/أصفر).

الملفات التانية (csi_heatmap.py / csi_web.py / csi_line.py) بتعمل import للملف ده،
فلازم يكونوا كلهم في نفس الفولدر.A
"""
import threading
import time
from collections import deque

import numpy as np
import serial
from serial.tools import list_ports

# ----------------------------- الإعدادات -----------------------------------
PORT = "COM3"
BAUD = 921600        # لازم يساوي SERIAL_BAUD في كود الـ ESP32
N_SC = 64            # عدد الترددات الفرعية اللي الـ ESP بيبعتها
HEAT_COLS = 300      # عدد الإطارات الزمنية في الهيت ماب (~6 ثواني)
WIN = 8              # نافذة حساب الحركة (عدد الإطارات)
CALIB_FRAMES = 150   # عدد الإطارات للمعايرة التلقائية في البداية (~3 ثواني)
MOVE_ON = 2.5        # الحركة بتشتغل لما المؤشر يعدّي (مستوى الهدوء × 2.5)
MOVE_OFF = 1.6       # وبتقفل لما ينزل تحت (مستوى الهدوء × 1.6)
# ---------------------------------------------------------------------------

# مواضع عناصر الـ frame المخزّن
F_SEQ, F_RSSI, F_ENERGY, F_NORM, F_MOTION, F_MI = range(6)


class CSIReceiver:
    def __init__(self, port=PORT, baud=BAUD):
        self.port = port
        self.baud = baud
        self.lock = threading.Lock()
        self._stop = threading.Event()

        self.status = "Starting..."
        self.esp_msg = ""

        self.frames = deque(maxlen=2000)      # آخر الإطارات (للرسم)
        self.recent = deque(maxlen=WIN)       # نافذة حساب الحركة
        self.arrivals = deque(maxlen=600)     # أوقات وصول الباكيتات (لحساب المعدل)
        self.mi_hist = deque(maxlen=1800)     # تاريخ مؤشر الحركة (لتقدير الهدوء)

        self.valid = None                     # قناع الترددات الشغالة (بعد ~60 إطار)
        self._sum_amp = np.zeros(N_SC, dtype=np.float64)
        self._warm = 0

        self.seq = 0
        self.quiet = 0.02                     # مستوى مؤشر الحركة وقت الهدوء (بيتعدّل تلقائيًا)
        self.mi_smooth = 0.0
        self.moving = False
        self.last_rssi = 0
        self.last_frame_time = 0.0

    # ------------------------------------------------------------------ تشغيل
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def stop(self):
        self._stop.set()

    def _set_status(self, text):
        with self.lock:
            self.status = text

    # --------------------------------------------------------- القراءة من البورت
    def _run(self):
        while not self._stop.is_set():
            ser = None
            try:
                ser = serial.Serial()
                ser.port = self.port
                ser.baudrate = self.baud
                ser.timeout = 0.05
                # نمنع الـ DTR/RTS من عمل reset للـ ESP أول ما البورت يتفتح
                ser.dtr = False
                ser.rts = False
                ser.open()
                self._set_status(f"Connected to {self.port} - waiting for ESP32 data...")

                buf = bytearray()
                while not self._stop.is_set():
                    n = ser.in_waiting
                    chunk = ser.read(n if n > 0 else 1)   # بيستنى 50ms بس لو مفيش بيانات
                    if not chunk:
                        continue
                    buf += chunk
                    if len(buf) > 200000:                 # حماية: لو تراكم كبير نرمي القديم
                        buf = bytearray(buf[-5000:])
                    *lines, rest = buf.split(b"\n")
                    buf = rest
                    for ln in lines:
                        self._handle_line(ln)
            except Exception as e:
                ports = ", ".join(p.device for p in list_ports.comports()) or "none"
                self._set_status(
                    f"Cannot use {self.port}: {e} | available ports: {ports} "
                    f"| (close Arduino Serial Monitor) retrying..."
                )
                time.sleep(2)
            finally:
                try:
                    if ser is not None and ser.is_open:
                        ser.close()
                except Exception:
                    pass

    # -------------------------------------------------------------- تحليل سطر
    def _handle_line(self, raw):
        try:
            line = raw.decode("ascii", errors="ignore").strip()
        except Exception:
            return
        if not line:
            return

        if line.startswith("#"):                      # رسالة معلومات من الـ ESP
            self.esp_msg = line.lstrip("# ").strip()
            if time.time() - self.last_frame_time > 2.0:
                self._set_status("ESP32: " + self.esp_msg)
            return

        if not line.startswith("CSI,"):
            return
        parts = line.split(",")
        if len(parts) != 3 + N_SC:                    # سطر ناقص/مقطوع: نتجاهله
            return
        try:
            rssi = int(parts[2])
            amp = np.array([float(x) for x in parts[3:]], dtype=np.float32)
        except ValueError:
            return
        self._process(rssi, amp)

    # ----------------------------------------------------------- حساب الحركة
    def _process(self, rssi, amp):
        now = time.time()

        # 1) نتعلم أنهي ترددات فرعية شغالة (الفاضية/الحراس بتبقى صفر)
        if self.valid is None:
            self._sum_amp += amp
            self._warm += 1
            if self._warm >= 60:
                mean_amp = self._sum_amp / self._warm
                nz = mean_amp[mean_amp > 0]
                if nz.size:
                    ref = float(np.median(nz))
                    mask = mean_amp > 0.25 * ref
                    if int(mask.sum()) >= 8:
                        self.valid = mask
        use = self.valid if self.valid is not None else (amp > 0)
        if not use.any():
            return

        # 2) تطبيع: نقسم على متوسط الإطار (بيشيل تأثير تغيّر الـ gain)
        energy = float(amp[use].mean())
        if energy <= 0:
            return
        norm = (amp / energy).astype(np.float32)

        # 3) الحركة = الانحراف المعياري لكل تردد على آخر WIN إطارات
        self.recent.append(norm)
        have_window = len(self.recent) >= WIN
        if have_window:
            motion = np.std(np.stack(self.recent), axis=0).astype(np.float32)
            mi = float(motion[use].mean())
            self.mi_smooth = mi if not self.mi_hist else (0.8 * self.mi_smooth + 0.2 * mi)
            self.mi_hist.append(self.mi_smooth)
        else:
            motion = np.zeros(N_SC, dtype=np.float32)

        self.seq += 1

        # 4) مستوى الهدوء = الشريحة الربعية الدنيا من آخر ~30 ثانية (بيتظبط لوحده)
        if have_window and self.seq % 10 == 0 and len(self.mi_hist) >= 30:
            self.quiet = max(float(np.percentile(self.mi_hist, 25)), 1e-4)

        # 5) حالة حركة / سكون (مع hysteresis عشان ما تهتزش)
        if len(self.mi_hist) >= CALIB_FRAMES:
            ratio = self.mi_smooth / self.quiet
            if self.moving and ratio < MOVE_OFF:
                self.moving = False
            elif (not self.moving) and ratio > MOVE_ON:
                self.moving = True
        else:
            self.moving = False

        with self.lock:
            self.frames.append((self.seq, rssi, energy, norm, motion, self.mi_smooth))
            self.arrivals.append(now)
            self.last_frame_time = now
            self.last_rssi = rssi
            self.status = "Receiving live CSI"

    # ------------------------------------------------------------- للواجهات
    def state(self):
        if time.time() - self.last_frame_time > 2.0:
            return "NO DATA"
        if len(self.mi_hist) < CALIB_FRAMES:
            return "CALIBRATING"
        return "MOVING" if self.moving else "STILL"

    def packet_rate(self):
        now = time.time()
        with self.lock:
            return sum(1 for t in self.arrivals if now - t <= 1.0)

    def valid_indices(self):
        v = self.valid
        return np.flatnonzero(v) if v is not None else np.arange(N_SC)

    def snapshot(self, cols=HEAT_COLS):
        """آخر cols إطار جاهزين للرسم (الأحدث على اليمين). الصفوف = الترددات الشغالة."""
        with self.lock:
            frames = list(self.frames)[-cols:]
            status = self.status
        idx = self.valid_indices()
        n = len(frames)

        motion = np.zeros((cols, N_SC), dtype=np.float32)
        raw = np.zeros((cols, N_SC), dtype=np.float32)
        mi = np.zeros(cols, dtype=np.float32)
        rssi = np.zeros(cols, dtype=np.float32)
        energy = np.zeros(cols, dtype=np.float32)
        if n:
            motion[-n:] = np.stack([f[F_MOTION] for f in frames])
            raw[-n:] = np.stack([f[F_NORM] for f in frames])
            mi[-n:] = [f[F_MI] for f in frames]
            rssi[-n:] = [f[F_RSSI] for f in frames]
            energy[-n:] = [f[F_ENERGY] for f in frames]

        return {
            "motion": motion[:, idx].T,   # (صفوف الترددات × cols)
            "raw": raw[:, idx].T,
            "mi": mi,
            "rssi": rssi,
            "energy": energy,
            "n": n,
            "quiet": self.quiet,
            "state": self.state(),
            "rate": self.packet_rate(),
            "status": status,
            "last_rssi": self.last_rssi,
        }

    def frames_since(self, last_seq, limit=300):
        """الإطارات الجديدة بعد last_seq (للويب)."""
        out = []
        with self.lock:
            for f in reversed(self.frames):
                if f[F_SEQ] <= last_seq:
                    break
                out.append(f)
                if len(out) >= limit:
                    break
        out.reverse()
        return out
