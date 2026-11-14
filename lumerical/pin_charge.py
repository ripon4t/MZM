"""
Electrical simulation of a forward-biased p-i-n silicon rib waveguide in Ansys Lumerical
CHARGE (DEVICE), driven by lumapi.

Cross-section (x horizontal, z vertical, 2D y-normal):
    rib 0.50 um wide, 0.22 um tall;  slab 0.09 um thick, spanning +-4 um
    p+ | p | intrinsic (+-1.2 um) | n | n+ ,  contacts on the simulation-region edges

The charge monitor saves the electron/hole densities to ../data/pin_charge.mat for each bias
point; with --electrothermal the solver runs in coupled (CHARGE + HEAT) mode and a temperature
profile is saved to ../data/pin_temp.mat as well.

    python pin_charge.py [--hide] [--v-start 0.4 --v-stop 1.2 --n-points 21] [--electrothermal]

Run lumerical/pin_mode_sweep.py afterwards.
"""
import argparse
import os
import numpy as np
from lum_utils import import_lumapi, set_props

lumapi = import_lumapi()
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))

# ---- geometry and doping (m, cm^-3) ----
RIB_W, RIB_H, SLAB_H = 0.50e-6, 0.22e-6, 0.09e-6
X_EDGE = 4.0e-6
DOPING = [  # (name, x_min, x_max, type, concentration)
    ("p_plus",  -X_EDGE, -3.4e-6, "p", 1e20),
    ("p_slab",  -3.4e-6, -1.2e-6, "p", 1e18),
    ("intrinsic", -1.2e-6, 1.2e-6, "p", 1e15),
    ("n_slab",   1.2e-6,  3.4e-6, "n", 1e18),
    ("n_plus",   3.4e-6,  X_EDGE, "n", 1e20),
]


def build(dev, args):
    dev.newproject()
    dev.addsimulationregion(name="SimRegion", dimension="2D Y-Normal",
                            x_span=2 * X_EDGE, z_span=1.2e-6)
    dev.addchargesolver(name="CHARGE", simulation_region="SimRegion")
    set_props(dev, {"z": RIB_H / 2}, "SimRegion position")

    # model materials for the electrical solver
    for name, base in (("Silicon", "Si (Silicon)"), ("Oxide", "SiO2 (Glass) - Palik")):
        try:
            dev.addmodelmaterial(name=name)
            dev.addmaterialproperties("CT", base)
        except Exception as exc:
            print(f"[warning] model material {name}: {exc}")

    # geometry: oxide first (lowest priority), then slab, then rib
    for name, mat, x_span, z_min, z_max in (
        ("oxide", "Oxide", 2 * X_EDGE, -1.0e-6, 1.0e-6),
        ("slab", "Silicon", 2 * X_EDGE, 0.0, SLAB_H),
        ("rib", "Silicon", RIB_W, 0.0, RIB_H),
    ):
        dev.addrect()
        set_props(dev, {"name": name, "material": mat, "x": 0, "x span": x_span,
                        "y": 0, "y span": 1.0e-6, "z min": z_min, "z max": z_max}, name)

    # doping (non-overlapping segments, restricted to the silicon layer)
    for name, x0, x1, kind, conc in DOPING:
        try:
            dev.adddope(name=name, x_min=x0, x_max=x1, dopant_type=kind, concentration=conc)
            set_props(dev, {"z min": 0.0, "z max": RIB_H}, name)
        except Exception as exc:
            print(f"[warning] doping {name}: {exc}")

    # contacts on the left (anode, p side) and right (cathode, n side) edges of the region
    dev.addelectricalcontact(properties={"name": "anode", "surface type": "simulation region", "x min": True})
    set_props(dev, {"sweep type": "range", "range start": args.v_start, "range stop": args.v_stop,
                    "range num points": args.n_points}, "anode sweep")
    dev.addelectricalcontact(properties={"name": "cathode", "surface type": "simulation region", "x max": True})
    set_props(dev, {"voltage": 0.0}, "cathode")

    # charge monitor over the waveguide + slab, saving the carrier densities for MODE
    dev.addchargemonitor()
    set_props(dev, {"name": "monitor_wg", "x min": -X_EDGE, "x max": X_EDGE,
                    "z min": -0.05e-6, "z max": RIB_H + 0.05e-6,
                    "save data": True, "filename": os.path.join(DATA, "pin_charge.mat")}, "charge monitor")

    if args.electrothermal:
        dev.select("CHARGE")
        set_props(dev, {"temperature dependence": "coupled"}, "CHARGE solver")
        # Thermal side: heat solver, thermal boundary and temperature monitor (best effort)
        try:
            dev.addheatsolver(name="HEAT", simulation_region="SimRegion")
        except Exception as exc:
            print(f"[warning] heat solver: {exc}. Add a HEAT solver, thermal contacts and thermal "
                  "conductivities in the GUI, then re-run.")
        try:
            dev.addtemperaturemonitor()
            set_props(dev, {"name": "monitor_T", "x min": -X_EDGE, "x max": X_EDGE,
                            "z min": -0.05e-6, "z max": RIB_H + 0.05e-6,
                            "save data": True, "filename": os.path.join(DATA, "pin_temp.mat")}, "temperature monitor")
        except Exception as exc:
            print(f"[warning] temperature monitor: {exc}")


def export_iv(dev, tag):
    """Best-effort export of the anode current vs bias."""
    try:
        res = dev.getresult("CHARGE", "anode")
        keys = [k for k in res.keys() if not str(k).startswith("Lumerical")]
        vk = next(k for k in keys if k.upper().startswith("V"))
        ik = next(k for k in keys if k.upper().startswith("I"))
        v = np.asarray(res[vk]).ravel(); i = np.asarray(res[ik]).ravel()
        np.savetxt(os.path.join(DATA, f"iv_{tag}.csv"), np.c_[v, i], delimiter=",", header="V,I", comments="")
        print(f"saved iv_{tag}.csv")
    except Exception as exc:
        print(f"[warning] could not export the I-V curve ({exc}); view it from the CHARGE object in the GUI")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hide", action="store_true")
    ap.add_argument("--v-start", type=float, default=0.4)
    ap.add_argument("--v-stop", type=float, default=1.2)
    ap.add_argument("--n-points", type=int, default=21)
    ap.add_argument("--electrothermal", action="store_true", help="coupled CHARGE + HEAT run")
    args = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)

    with lumapi.DEVICE(hide=args.hide) as dev:
        build(dev, args)
        tag = "electrothermal" if args.electrothermal else "isothermal"
        dev.save(os.path.join(DATA, f"pin_{tag}.ldev"))
        dev.run()
        export_iv(dev, tag)
    np.savetxt(os.path.join(DATA, "voltages.txt"), np.linspace(args.v_start, args.v_stop, args.n_points))
    print("done: carrier data in data/pin_charge.mat" + (", temperature in data/pin_temp.mat" if args.electrothermal else ""))


if __name__ == "__main__":
    main()
