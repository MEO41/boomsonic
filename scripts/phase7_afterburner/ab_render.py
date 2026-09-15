"""Phase 7: figures of the afterburner CAD (run in .venv-cad; VTK off-screen + matplotlib).
Reads the STEP files only, and reuses the Phase 6 renderer's helpers unchanged.

  plots/phase7_ab_cutaway.png   engine + afterburner, 3/4 view, static parts cut open over one quadrant
  plots/phase7_ab_section.png   meridional half-section with the stations, the plug shown in BOTH
                                positions so the 51 mm stroke is visible, and the engine envelope line

Usage: .venv-cad\\Scripts\\python scripts\\phase7_afterburner\\ab_render.py
       (this venv's processes exit non-zero at teardown; check the outputs, not the exit code)
"""
import os, sys, json, glob, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "phase6_cad"))
import cadquery as cq
import pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from render_cad import polydata, actor, render, quadrant_cut, section_xy, COL, MAT, ROTOR

PL = os.path.join(ROOT, "plots")
D7 = os.path.join(ROOT, "data", "phase7")
E = json.load(open(os.path.join(ROOT, "data", "phase6", "engine_params.json")))
CADJ = json.load(open(os.path.join(D7, "ab_cad.json")))
m = pd.read_csv(os.path.join(D7, "ab_cad_mass.csv"))
MAT7 = dict(zip(m.part, m.material))
COL7 = dict(COL); COL7["HastX"] = (0.85, 0.35, 0.10)

def load_any(nm):
    for d in ("afterburner", "engine"):
        p = os.path.join(ROOT, "cad", d, nm + ".step")
        if os.path.exists(p):
            return cq.importers.importStep(p).val()
    raise FileNotFoundError(nm)


names = [n for n in m.part if n not in ("impeller_sector",)]
shapes = {n: load_any(n) for n in names}
L = CADJ["length"]

if __name__ == "__main__":
    what = sys.argv[1].split(",") if len(sys.argv) > 1 else ["cutaway", "section"]

    if "cutaway" in what:
        acts = []
        for n, s in shapes.items():
            shp = s if n in ROTOR else quadrant_cut(s, xmin=-100, xmax=900)
            acts.append(actor(polydata(shp, tol=0.12 if n != "impeller" else 0.05), COL7[MAT7[n]]))
        render(acts, os.path.join(PL, "phase7_ab_cutaway.png"),
               cam_pos=(-620, 900, 430), focal=(390, 0, 0), up=(0, 0, 1), size=(2200, 950), zoom=2.35)

    if "section" in what:
        fig, ax = plt.subplots(figsize=(15.5, 5.0))
        for n, s in shapes.items():
            for p in section_xy(s):
                if np.all(p[:, 1] > -1e-6):
                    ax.plot(p[:, 0], p[:, 1], color=COL7[MAT7[n]], lw=0.9)
        # the plug in its DRY position, dashed, to show the stroke
        dry = cq.importers.importStep(os.path.join(ROOT, "cad", "afterburner", "nozzle_plug_DRY_POSITION.step")).val()
        for p in section_xy(dry):
            if np.all(p[:, 1] > -1e-6):
                ax.plot(p[:, 0], p[:, 1], color="0.45", lw=0.9, ls="--")

        ymax = E["envelope"]["OD_model"]["value"] * 500
        ax.axhline(ymax, color="k", lw=0.7, ls="--")
        ax.text(-28, ymax + 2.5, "engine envelope OD %.1f mm (set by the compressor diffuser)" % (2 * ymax), fontsize=7)

        st = E["stations"]
        marks = [(st["x_compressor_section_end"]["value"] * 1e3, "compressor end"),
                 (st["x_combustor_end"]["value"] * 1e3, "combustor end / NGV"),
                 (st["x_rotor_centre"]["value"] * 1e3, "turbine rotor"),
                 (L["x_turbine_exit_mm"], "turbine exit"),
                 (L["x_turbine_exit_mm"] + CADJ.get("L_diff", 270.8), "diffuser exit / flameholder"),
                 (L["x_dry_nozzle_exit_mm"], "where the DRY engine ended"),
                 (L["x_plug_tip_mm"], "plug tip")]
        for i, (xx, lab) in enumerate(marks):
            ax.axvline(xx, color="0.6", lw=0.6, ls=":")
            ax.text(xx + 2, ymax * (1.05 + 0.10 * (i % 3)), lab, fontsize=6.5, va="bottom")

        ax.annotate("", xy=(L["x_plug_tip_mm"], 8), xytext=(L["x_plug_tip_mm"] - 51.0, 8),
                    arrowprops=dict(arrowstyle="<->", color="0.25", lw=1.0))
        ax.text(L["x_plug_tip_mm"] - 25.5, 12, "51 mm\nplug stroke", fontsize=6.5, ha="center", color="0.25")

        ax.set_aspect("equal")
        ax.set_xlabel("x from impeller nose [mm]"); ax.set_ylabel("r [mm]")
        ax.set_ylim(0, ymax * 1.42); ax.set_xlim(-45, L["x_plug_tip_mm"] + 25)
        handles = [Line2D([], [], color=COL7[k], lw=2) for k in ("Ti", "Al", "SS", "IN625", "IN713", "steel", "HastX")]
        handles.append(Line2D([], [], color="0.45", lw=1.2, ls="--"))
        ax.legend(handles, ["Ti-6Al-4V", "Al alloy", "stainless", "IN625", "IN713LC", "steel",
                            "Hastelloy X", "plug, dry position"],
                  fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=8, frameon=False)
        ax.set_title("Phase 7: the frozen centrifugal engine with the afterburner and its translating-plug nozzle "
                     "(meridional half-section, plane z = 0)", fontsize=10)
        fig.tight_layout()
        fig.savefig(os.path.join(PL, "phase7_ab_section.png"), dpi=170)
        plt.close(fig)
        print("wrote plots/phase7_ab_section.png")
