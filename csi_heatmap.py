"""
csi_heatmap.py  -  هيت ماب ثيرمال (matplotlib) لكشف حركة الإنسان بين الـ ESP32 والراوتر.

الأزرار (اضغط على نافذة الرسم):
    +  أو  UP     زوّد الحساسية
    -  أو  DOWN   قلّل الحساسية
    m             بدّل بين "Motion" (الحركة) و "Raw" (الإشارة الخام)

الألوان (jet):  أزرق = ساكن   ->   أخضر/أصفر   ->   أحمر = حركة قوية
"""
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np

from csi_core import HEAT_COLS, MOVE_ON, CSIReceiver

rx = CSIReceiver().start()

sens = 5.0       # الحساسية (1..15) - أعلى = الألوان بتسخن أسرع
mode = "motion"  # "motion" أو "raw"
state_colors = {
    "STILL": "#16a34a",
    "MOVING": "#dc2626",
    "CALIBRATING": "#d97706",
    "NO DATA": "#6b7280",
}

fig, (ax, ax2) = plt.subplots(
    2, 1, figsize=(11, 7.5), sharex=True,
    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
)
fig.canvas.manager.set_window_title("WiFi CSI Thermal Heatmap")

im = ax.imshow(
    np.zeros((52, HEAT_COLS)), aspect="auto", cmap="jet", vmin=0, vmax=1,
    origin="lower", interpolation="bilinear",
    extent=(-0.5, HEAT_COLS - 0.5, -0.5, 51.5),
)
fig.colorbar(im, ax=[ax, ax2], pad=0.02,
             label="Motion intensity  (blue = still ... red = strong motion)")
ax.set_title("WiFi CSI Live Thermal Heatmap - Human Motion Sensing")
ax.set_ylabel("Subcarrier")
ax.tick_params(labelbottom=False)

status_txt = ax.text(
    0.01, 0.97, "Waiting for ESP32...", transform=ax.transAxes, fontsize=11,
    color="white", va="top",
    bbox=dict(facecolor="#6b7280", alpha=0.9, pad=5, edgecolor="none"),
)
help_txt = ax.text(
    0.99, 0.03, "+/-: sensitivity    m: motion/raw", transform=ax.transAxes,
    fontsize=9, color="white", ha="right", va="bottom",
    bbox=dict(facecolor="black", alpha=0.45, pad=3, edgecolor="none"),
)

xs = np.arange(HEAT_COLS)
(mi_line,) = ax2.plot(xs, np.zeros(HEAT_COLS), color="tab:red", lw=1.5, label="Motion index")
thr_line = ax2.axhline(0.0, color="black", ls="--", lw=1, label="Motion threshold")
ax2.set_xlim(-0.5, HEAT_COLS - 0.5)
ax2.set_ylim(0, 0.1)
ax2.set_xlabel("Time  (newest frame on the right)")
ax2.set_ylabel("Motion index")
ax2.grid(True, alpha=0.3)
ax2.legend(loc="upper left", fontsize=8)

_last_rows = [52]


def on_key(event):
    global sens, mode
    if event.key in ("+", "=", "up"):
        sens = min(sens + 1, 15)
    elif event.key in ("-", "_", "down"):
        sens = max(sens - 1, 1)
    elif event.key == "m":
        mode = "raw" if mode == "motion" else "motion"


fig.canvas.mpl_connect("key_press_event", on_key)


def update(_):
    snap = rx.snapshot(HEAT_COLS)
    n = snap["n"]
    quiet = max(snap["quiet"], 1e-4)

    if mode == "motion":
        data = snap["motion"] / (quiet * (30.0 / sens))
    else:
        data = snap["raw"].copy()
        if n >= 5:
            part = data[:, -n:]
            lo, hi = np.percentile(part, [2, 98])
            data = (data - lo) / max(hi - lo, 1e-6)
        else:
            data = np.zeros_like(data)

    rows = data.shape[0]
    if rows != _last_rows[0]:
        _last_rows[0] = rows
        im.set_extent((-0.5, HEAT_COLS - 0.5, -0.5, rows - 0.5))
        ax.set_ylim(-0.5, rows - 0.5)
    im.set_data(np.clip(data, 0.0, 1.0))

    mi = snap["mi"]
    thr = quiet * MOVE_ON
    mi_line.set_ydata(mi)
    thr_line.set_ydata([thr, thr])
    ax2.set_ylim(0, max(float(mi.max()), thr * 1.5) * 1.15)

    state = snap["state"]
    if state == "NO DATA":
        status_txt.set_text(snap["status"][:110])
    else:
        status_txt.set_text(
            f"{state}   |   {snap['rate']} pkt/s   |   RSSI {snap['last_rssi']} dBm"
            f"   |   sens {sens:.0f}   |   mode: {mode}"
        )
    status_txt.get_bbox_patch().set_facecolor(state_colors.get(state, "#6b7280"))
    return im, status_txt


ani = animation.FuncAnimation(fig, update, interval=40, blit=False, cache_frame_data=False)
plt.show()
rx.stop()
