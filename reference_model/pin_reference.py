"""
Illustrative Python model of a forward-biased p-i-n rib phase shifter (no Lumerical needed).

 diode (series resistance) -> injected carrier density -> Soref-Bennett index/absorption
 -> optional Joule-heating thermo-optic counter-effect

The parameters are illustrative and NOT calibrated against any CHARGE/MODE result. The model is
there to exercise the analysis code and to show the qualitative physics: exponential carrier
injection, index decrease with absorption increase, and heating that works against the index change.
It writes the same CSV files as the MODE sweep and runs the same analysis.

    python pin_reference.py
"""
import os
import subprocess
import sys
import numpy as np
from scipy.optimize import brentq

HERE = os.path.dirname(os.path.abspath(__file__))
Q, KB, T0 = 1.602176634e-19, 1.380649e-23, 300.0
VT = KB * T0 / Q

LENGTH = 700e-6          # m
AREA_I = 2.8e-9          # cm^2, intrinsic-region cross-section
LIFETIME = 1.5e-9        # s, effective carrier lifetime (surface recombination included)
I_SAT_PER_M = 5e-7     # A/m, diode saturation current per length
IDEALITY = 2.0
R_SERIES = 5.0           # ohm
GAMMA = 0.55             # mode overlap with the injected region
NEFF0, LOSS0 = 2.45, 1.0 # passive effective index, passive loss (dB/cm)
DNEFF_DT = 1.9e-4        # 1/K
R_TH = 120.0             # K/W (illustrative, for the full length)
V = np.linspace(0.4, 1.2, 21)


def diode_current(v):
    i_s = I_SAT_PER_M * LENGTH
    f = lambda i: i - i_s * np.exp((v - i * R_SERIES) / (IDEALITY * VT))
    return brentq(f, 0.0, 5.0)


def carriers_cm3(i_total):
    per_len_cm = i_total / (LENGTH * 100)                   # A/cm
    return per_len_cm * LIFETIME / (Q * AREA_I)             # cm^-3


def soref_bennett(n):
    dn = -(8.8e-22 * n + 8.5e-18 * n ** 0.8)
    da = (8.5e-18 * n + 6.0e-18 * n) * 4.343                # dB/cm
    return dn, da


def sweep(heating):
    rows, iv = [], []
    for v in V:
        i = diode_current(v)
        n = carriers_cm3(i)
        dn, da = soref_bennett(n)
        neff = NEFF0 + GAMMA * dn
        if heating:
            neff += DNEFF_DT * R_TH * i * v
        rows.append((v, neff, LOSS0 + GAMMA * da))
        iv.append((v, i))
    return np.array(rows), np.array(iv)


def save(path, arr, header):
    np.savetxt(path, arr, delimiter=",", header=header, comments="")


def main():
    data = os.path.join(HERE, "data")
    os.makedirs(data, exist_ok=True)
    hdr = "V,neff,loss_dB_per_cm"
    iso, iv = sweep(False)
    et, _ = sweep(True)
    save(os.path.join(data, "neff_vs_v_isothermal.csv"), iso, hdr)
    save(os.path.join(data, "neff_vs_v_electrothermal.csv"), et, hdr)
    save(os.path.join(data, "iv_isothermal.csv"), iv, "V,I")
    ana = os.path.join(HERE, "..", "analysis", "modulator_analysis.py")
    subprocess.run([sys.executable, ana, "--data", data, "--out", os.path.join(HERE, "images"),
                    "--label", "(Python reference)"], check=True)


if __name__ == "__main__":
    main()
