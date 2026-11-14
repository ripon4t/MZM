"""Draws the p-i-n rib cross-section used in the README."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

fig, ax = plt.subplots(figsize=(10, 3.8))
ax.set_aspect("auto"); ax.set_xlim(-4.4, 4.4); ax.set_ylim(-0.5, 1.25)
regions = [(-4.0, -3.4, "p$^+$\n10$^{20}$", "#c0392b"), (-3.4, -1.2, "p\n10$^{18}$", "#e67e22"),
           (-1.2, 1.2, "intrinsic\n10$^{15}$", "#bdc3c7"), (1.2, 3.4, "n\n10$^{18}$", "#5dade2"),
           (3.4, 4.0, "n$^+$\n10$^{20}$", "#2a6fbb")]
ax.add_patch(Rectangle((-4.4, -0.5), 8.8, 0.5, fc="#eaf2f8", ec="none"))
ax.text(0, -0.28, "SiO$_2$ (buried oxide)", ha="center", color="#566573")
for x0, x1, label, col in regions:
    ax.add_patch(Rectangle((x0, 0), x1 - x0, 0.09, fc=col, ec="k", lw=0.6))
    ax.text((x0 + x1) / 2, 0.55, label, ha="center", va="center", fontsize=9, color="#222")
ax.add_patch(Rectangle((-0.25, 0.09), 0.5, 0.13, fc="#bdc3c7", ec="k", lw=0.6))
ax.annotate("rib 0.50 × 0.22 µm", xy=(0, 0.22), xytext=(0.9, 0.95), arrowprops=dict(arrowstyle="-", color="gray"))
ax.annotate("slab 90 nm", xy=(-2.3, 0.09), xytext=(-2.3, 0.3), ha="center", arrowprops=dict(arrowstyle="-", color="gray"), fontsize=9)
ax.text(-4.3, 1.1, "anode", fontsize=10, weight="bold"); ax.text(3.85, 1.1, "cathode", fontsize=10, weight="bold")
ax.set_xlabel("x (µm)"); ax.set_yticks([]); ax.set_title("p-i-n rib waveguide cross-section (doping in cm$^{-3}$, not to scale vertically)")
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pin_cross_section.png"), dpi=200)
