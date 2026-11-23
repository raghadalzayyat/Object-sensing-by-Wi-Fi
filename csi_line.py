"""
csi_line.py  -  الدياجرام الأبيض (خطوط) - أبسط نسخة، من غير تأخير.

فوق:  CSI Energy (متوسط السعة)  +  RSSI
تحت:  مؤشر الحركة  +  خط العتبة (لما المؤشر يعدّيه = فيه حركة)
"""
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np

from csi_core import MOVE_ON, CSIReceiver

N = 300   # عدد النقاط الظاهرة

rx = CSIReceiver().start()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
fig.canvas.manager.set_window_title("WiFi CSI Live - Line Diagram")

(l_energy,) = ax1.plot([], [], color="tab:blue", lw=1.5, label="CSI Energy (mean amplitude)")
ax1b = ax1.twinx()
(l_rssi,) = ax1b.plot([], [], color="tab:orange", lw=1.5, label="RSSI (dBm)")
ax1.set_ylabel("CSI Energy", color="tab:blue")
ax1b.set_ylabel("RSSI (dBm)", color="tab:orange")
ax1.set_title("WiFi Human Sensing - Live CSI")
ax1.grid(True, alpha=0.4)
ax1.legend([l_energy, l_rssi], [l_energy.get_label(), l_rssi.get_label()], loc="upper right")

(l_mi,) = ax2.plot([], [], color="tab:green", lw=1.5, label="Motion index")
l_thr = ax2.axhline(0.0, color="tab:red", ls="--", lw=1, label="Motion threshold")
ax2.set_xlim(0, N - 1)
ax2.set_xlabel("Samples (newest on the right)")
ax2.set_ylabel("Motion index")
ax2.grid(True, alpha=0.4)
ax2.legend(loc="upper right")

status = ax1.text(0.01, 0.93, "Waiting for ESP32...", transform=ax1.transAxes,
                  fontsize=11, color="red")


def pad(lo, hi, frac=0.15, minspan=1.0):
    span = max(hi - lo, minspan)
    return lo - span * frac, hi + span * frac


def update(_):
    snap = rx.snapshot(N)
    n = snap["n"]
    if n < 2:
        status.set_text(snap["status"][:110])
        status.set_color("red")
        return ()

    x = np.arange(N - n, N)
    e = snap["energy"][-n:]
    r = snap["rssi"][-n:]
    m = snap["mi"][-n:]
    l_energy.set_data(x, e)
    l_rssi.set_data(x, r)
    l_mi.set_data(x, m)

    ax1.set_ylim(*pad(float(e.min()), float(e.max()), minspan=4.0))
    ax1b.set_ylim(*pad(float(r.min()), float(r.max()), minspan=6.0))

    thr = max(snap["quiet"], 1e-4) * MOVE_ON
    l_thr.set_ydata([thr, thr])
    ax2.set_ylim(0, max(float(m.max()), thr * 1.5) * 1.15)

    state = snap["state"]
    status.set_text(f"{state}  |  {snap['rate']} pkt/s  |  RSSI {snap['last_rssi']} dBm")
    status.set_color({"STILL": "green", "MOVING": "red", "CALIBRATING": "darkorange"}.get(state, "gray"))
    return ()


ani = animation.FuncAnimation(fig, update, interval=40, blit=False, cache_frame_data=False)
plt.show()
rx.stop()
