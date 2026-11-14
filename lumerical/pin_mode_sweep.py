"""
Optical effective-index sweep of the p-i-n waveguide in Ansys Lumerical MODE (FDE), driven by lumapi.

The carrier densities from CHARGE (data/pin_charge.mat) are loaded into an "np density" grid
attribute; an index-perturbation material (Soref-Bennett model) turns them into changes of the
silicon index and absorption. For every bias point the fundamental TE mode is solved and its
effective index and loss are written to data/neff_vs_v_<tag>.csv for analysis/modulator_analysis.py.

    python pin_mode_sweep.py [--hide] [--material "Si_index_pert"] [--electrothermal]

One-time setup of the perturbation material (done in the GUI if scripted creation is not accepted
by your version): Materials > Add > Index perturbation; name it e.g. "Si_index_pert"; base material
"Si (Silicon) - Palik"; enable the np density model "Soref and Bennett" (and, for --electrothermal,
the temperature model with a linear sensitivity ~1.8e-4 /K).
"""
import argparse
import os
import numpy as np
from lum_utils import import_lumapi, set_props, try_values

lumapi = import_lumapi()
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))

RIB_W, RIB_H, SLAB_H = 0.50e-6, 0.22e-6, 0.09e-6
X_EDGE = 4.0e-6
WAVELENGTH = 1.55e-6


def ensure_material(mode, name):
    """Best-effort scripted creation of the index-perturbation material."""
    try:
        created = mode.addmaterial("Index perturbation")
        mode.setmaterial(created, "name", name)
        mode.setmaterial(name, "base material", "Si (Silicon) - Palik")
    except Exception as exc:
        print(f"[note] could not create the index-perturbation material by script ({exc}). "
              f"Create '{name}' once in the GUI as described in the file header.")


def build(mode, material, electrothermal, create_material):
    mode.newproject()
    if create_material:
        ensure_material(mode, material)

    for name, x_span, z_min, z_max in (("slab", 2 * X_EDGE, 0.0, SLAB_H), ("rib", RIB_W, 0.0, RIB_H)):
        mode.addrect()
        set_props(mode, {"name": name, "material": material, "x": 0, "x span": x_span,
                         "y": 0, "y span": 2e-6, "z min": z_min, "z max": z_max}, name)

    mode.addgridattribute("np density")
    set_props(mode, {"name": "np", "x": 0, "x span": 2 * X_EDGE, "y": 0, "y span": 2e-6,
                     "z": RIB_H / 2, "z span": 1.0e-6}, "np density")
    mode.importdataset(os.path.join(DATA, "pin_charge.mat"))

    if electrothermal:
        mode.addgridattribute("temperature")
        set_props(mode, {"name": "temperature", "x": 0, "x span": 2 * X_EDGE, "y": 0, "y span": 2e-6,
                         "z": RIB_H / 2, "z span": 1.0e-6}, "temperature")
        mode.importdataset(os.path.join(DATA, "pin_temp.mat"))

    # fine mesh around the waveguide
    mode.addmesh()
    set_props(mode, {"name": "mesh_core", "x": 0, "x span": 1.6e-6, "z": RIB_H / 2, "z span": 0.5e-6,
                     "y": 0, "y span": 2e-6, "dx": 5e-9, "dz": 5e-9}, "mesh override")

    mode.addfde()
    set_props(mode, {"solver type": "2D Y normal", "x": 0, "x span": 2 * X_EDGE - 0.4e-6,
                     "y": 0, "z": RIB_H / 2, "z span": 2.0e-6, "wavelength": WAVELENGTH,
                     "number of trial modes": 4, "background material": "SiO2 (Glass) - Palik"}, "FDE")
    try_values(mode, "x min bc", ["PML", "Metal"], "FDE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hide", action="store_true")
    ap.add_argument("--material", default="Si_index_pert")
    ap.add_argument("--electrothermal", action="store_true")
    ap.add_argument("--try-create-material", action="store_true",
                    help="try to create the index-perturbation material by script")
    args = ap.parse_args()
    tag = "electrothermal" if args.electrothermal else "isothermal"
    volts = np.loadtxt(os.path.join(DATA, "voltages.txt"))
    rows = []

    with lumapi.MODE(hide=args.hide) as mode:
        build(mode, args.material, args.electrothermal, args.try_create_material)
        mode.save(os.path.join(DATA, f"pin_mode_{tag}.lms"))
        for k, v in enumerate(volts, start=1):
            mode.switchtolayout()
            # the grid attribute selects the bias point through its "_index" property
            for obj in ("np", "temperature"):
                try:
                    mode.setnamed(obj, "_index", k)
                except Exception:
                    pass
            n_modes = mode.findmodes()
            neff = complex(np.asarray(mode.getdata("FDE::data::mode1", "neff")).ravel()[0])
            loss = float(np.real(np.asarray(mode.getdata("FDE::data::mode1", "loss")).ravel()[0]))  # dB/m
            rows.append((v, neff.real, loss / 100.0))                                              # -> dB/cm
            print(f"V = {v:5.3f} V   neff = {neff.real:.6f}   loss = {loss/100:.3f} dB/cm")

    out = os.path.join(DATA, f"neff_vs_v_{tag}.csv")
    np.savetxt(out, np.array(rows), delimiter=",", header="V,neff,loss_dB_per_cm", comments="")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
