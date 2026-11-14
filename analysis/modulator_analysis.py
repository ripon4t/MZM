"""
Modulator figures of merit from the optical sweep exported by the MODE script.

Input  (data/):
    neff_vs_v_isothermal.csv      columns: V, neff, loss_dB_per_cm       (required)
    neff_vs_v_electrothermal.csv  same columns, with Joule heating        (optional)
    iv_isothermal.csv             columns: V, I   (A per simulated length) (optional)
Output : images/*.png and data/metrics.json

The phase shifter drives ONE arm of a balanced Mach-Zehnder interferometer of arm length L:

    phi(V) = 2*pi*L*(neff(V) - neff(V0)) / lambda
    T(V)   = | 0.5 * ( a_ref + a_act(V) * exp(j*phi(V)) ) |^2
    a_act  = 10^(-loss(V)*L/20),   a_ref = loss of the arm at the lowest bias

    V_pi = bias where |phi| reaches pi;  ER = T(V0)/T(V_pi);  IL = -10 log10 max(T)

    python modulator_analysis.py [--length-um 700] [--wavelength-nm 1550]
"""
import argparse
import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, ORANGE, RED = "#2a6fbb", "#e07a1f", "#c0392b"
plt.rcParams.update({"font.size": 11, "axes.grid": True, "grid.alpha": 0.3})


def load(path):
    d = np.genfromtxt(path, delimiter=",", names=True)
    order = np.argsort(d["V"])
    return {k: np.atleast_1d(d[k][order]) for k in d.dtype.names}


def mzi(d, length, lam):
    v, neff, loss = d["V"], d["neff"], d["loss_dB_per_cm"]
    phi = 2 * np.pi * length * (neff - neff[0]) / lam
    a_act = 10 ** (-(loss * 100) * length / 20)          # loss in dB/cm -> dB/m
    a_ref = 10 ** (-(loss[0] * 100) * length / 20)
    t = np.abs(0.5 * (a_ref + a_act * np.exp(1j * phi))) ** 2
    return phi, t


def vpi_of(v, phi):
    ph = np.abs(phi)
    if ph.max() < np.pi:
        return None
    k = int(np.argmax(ph >= np.pi))
    return float(np.interp(np.pi, ph[k - 1:k + 1], v[k - 1:k + 1]))


def summarize(d, length, lam):
    phi, t = mzi(d, length, lam)
    vpi = vpi_of(d["V"], phi)
    out = dict(V_pi=vpi, T_max=float(t.max()), IL_dB=float(-10 * np.log10(t.max())))
    if vpi is not None:
        t_pi = float(np.interp(vpi, d["V"], t))
        out.update(ER_dB=float(10 * np.log10(t[0] / t_pi)), VpiL_Vcm=float(vpi * length * 100))
    else:
        out.update(ER_dB=float(10 * np.log10(t.max() / t.min())), VpiL_Vcm=None)
    return out, phi, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "..", "data"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "images"))
    ap.add_argument("--length-um", type=float, default=700.0, help="modulation (arm) length")
    ap.add_argument("--wavelength-nm", type=float, default=1550.0)
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    L, lam = args.length_um * 1e-6, args.wavelength_nm * 1e-9

    runs = {"isothermal": load(os.path.join(args.data, "neff_vs_v_isothermal.csv"))}
    p_et = os.path.join(args.data, "neff_vs_v_electrothermal.csv")
    if os.path.exists(p_et):
        runs["with Joule heating"] = load(p_et)
    cols = {"isothermal": BLUE, "with Joule heating": ORANGE}

    metrics, curves = {}, {}
    for name, d in runs.items():
        metrics[name], phi, t = summarize(d, L, lam)
        curves[name] = (phi, t)

    # Fig 1: effective-index change
    fig, ax = plt.subplots(figsize=(7, 4.4))
    for name, d in runs.items():
        ax.plot(d["V"], (d["neff"] - d["neff"][0]) * 1e3, "o-", ms=3.5, color=cols[name], label=name)
    ax.set_xlabel("Forward bias (V)"); ax.set_ylabel("Δn$_{eff}$ (×10$^{-3}$)"); ax.legend()
    ax.set_title(f"Effective-index change vs bias {args.label}".strip())
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "01_neff_vs_bias.png"), dpi=200); plt.close(fig)

    # Fig 2: loss
    fig, ax = plt.subplots(figsize=(7, 4.4))
    for name, d in runs.items():
        ax.semilogy(d["V"], d["loss_dB_per_cm"], "o-", ms=3.5, color=cols[name], label=name)
    ax.set_xlabel("Forward bias (V)"); ax.set_ylabel("Propagation loss (dB/cm)"); ax.legend()
    ax.set_title(f"Loss vs bias {args.label}".strip())
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "02_loss_vs_bias.png"), dpi=200); plt.close(fig)

    # Fig 3: MZI transmission
    fig, ax = plt.subplots(figsize=(7, 4.4))
    for name, d in runs.items():
        phi, t = curves[name]
        ax.plot(d["V"], 10 * np.log10(t), "o-", ms=3.5, color=cols[name], label=name)
        vp = metrics[name]["V_pi"]
        if vp is not None:
            ax.axvline(vp, color=cols[name], ls=":", lw=1)
    ax.set_xlabel("Forward bias (V)"); ax.set_ylabel("MZI transmission (dB)"); ax.legend()
    ax.set_title(f"Modulation response, L = {args.length_um:.0f} µm {args.label}".strip())
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "03_transmission_vs_bias.png"), dpi=200); plt.close(fig)

    # Fig 4: I-V (optional)
    p_iv = os.path.join(args.data, "iv_isothermal.csv")
    if os.path.exists(p_iv):
        iv = load(p_iv)
        fig, ax = plt.subplots(figsize=(7, 4.2))
        ax.semilogy(iv["V"], np.abs(iv["I"]), "o-", ms=3.5, color=BLUE)
        ax.set_xlabel("Forward bias (V)"); ax.set_ylabel("Current (A)"); ax.set_title("Diode current")
        fig.tight_layout(); fig.savefig(os.path.join(args.out, "04_iv.png"), dpi=200); plt.close(fig)

    with open(os.path.join(args.data, "metrics.json"), "w") as f:
        json.dump(dict(length_um=args.length_um, wavelength_nm=args.wavelength_nm, results=metrics), f, indent=2)
    for name, m in metrics.items():
        vp = "n/a (pi shift not reached)" if m["V_pi"] is None else f"{m['V_pi']:.3f} V"
        print(f"{name:20s} V_pi = {vp}, ER = {m['ER_dB']:.1f} dB, IL = {m['IL_dB']:.2f} dB, V_pi*L = {m['VpiL_Vcm']}")
    if "with Joule heating" in metrics and metrics["isothermal"]["V_pi"] and metrics["with Joule heating"]["V_pi"]:
        print(f"Joule heating shifts V_pi by {metrics['with Joule heating']['V_pi'] - metrics['isothermal']['V_pi']:+.3f} V")


if __name__ == "__main__":
    main()
