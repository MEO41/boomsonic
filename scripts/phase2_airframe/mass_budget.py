"""Phase 2 first-pass mass budget and closure against the 25 kg MTOW ceiling.

Two independent estimates of the airframe (structure + systems), both reported:
  (1) Bottom-up: component areas from the parametric geometry (airframe_model.Config) x
      areal densities built from ply counts. Carbon/epoxy woven 200 g/m2 ply, cured ~0.25 mm,
      laminate density ~1.55 g/cm3 -> 0.39 kg/m2 per ply (fibre volume ~50 %). Allowances for
      frames, joints, hatches, hinges are explicit percentages. Items: see ITEMS below.
  (2) Statistical: large RC turbine jets (data/rc_jet_airframe_database.csv, published dry
      weights) minus a database-fitted engine system for their recommended thrust -> airframe +
      systems mass vs a size proxy (length x span). Our aircraft is BELOW the database size range
      in span, so this is an extrapolation and is used only as a sanity bracket.
Engine: data/engine_envelope.json (26-engine fit) + accessories (AMT published system mass).
Fuel: mission integration with the drag polar at the iterated take-off mass (mission_drag_polar.run).
Growth/contingency: 15 % on bottom-up structure + systems (conceptual-design allowance).
Outputs: data/phase2_mass_budget.csv, plots/phase2_mass_budget.png
"""
import os, sys, json, re, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from airframe_model import Config, ROOT
import mission_drag_polar as mdp

ENV = json.load(open(os.path.join(ROOT, "data", "engine_envelope.json")))
PLY = 0.39            # kg/m2 per cured 200 g/m2 carbon ply
ACC_FRAC_NOM = 0.235  # Nike (784 N, closest size with published system mass): accessories / engine
ACC_FRAC_HI = 0.430   # Titan: highest published fraction
GROWTH = 0.15
FUEL_DENS = 0.80      # kg/L Jet-A / kerosene
UNUSABLE = 0.03

def bottom_up(c: Config):
    s = c.surfaces(); w = s["wing"]
    Sexp_w = w.exposed(c.r_fus)[0]
    Sexp_t = sum(v.exposed(c.r_fus if not v.vertical else 0.0)[0] for k, v in s.items() if k != "wing")
    duct_len = c.x_wing_frac * c.L_fus + 0.1          # inlet lip -> engine face (engine at wing root, CG)
    items = {
        # structure
        "fuselage shell (3 carbon plies + 1 glass, +40 % frames/joints/hatches)": c.body_wetted() * (3 * PLY + 0.10) * 1.40,
        "inlet duct (2 glass plies ~0.25 kg/m2, lip ring)": np.pi * np.sqrt(c.A_capture / np.pi) * 2 * duct_len * 0.25 + 0.05,
        "engine mounts + heat shield/tailpipe liner": 0.35,
        "wing (2+2 carbon plies sandwich, spar caps, ribs, +30 %; flaps/ailerons incl.)": Sexp_w * (4 * PLY + 0.10) * 1.30 + 0.10,
        "tails (2+2 plies, +30 %) + all-moving HT pivot/bearings": Sexp_t * (4 * PLY + 0.10) * 1.30 + 0.15,
        # landing / recovery
        "landing gear, tricycle retract + brakes (Raymer Table 15.2 ~4.3 % W0)": 0.043 * 25.0,
        "drag chute 0.6 m + bag + release": 0.20,
        # fuel system (tank sized later)
        "fuel tank + hopper/UAT + lines + fittings": 0.40,
        # systems
        "servos (9 x ~75 g HV: 2 ail/elevon, 2 flap, 2 HT, rudder, steering, chute/brake)": 9 * 0.075,
        "flight controller + GPS + telemetry + 2 RC receivers": 0.30,
        "flight batteries (2 x LiFe 2S) + regulators": 0.35,
        "wiring, connectors, pneumatics": 0.30,
        "prize instrumentation: calibrated pitot-static, TAT probe, sealed loggers": 0.30,
        "flight termination / fail-safe": 0.10,
    }
    return items

def statistical(c: Config):
    """RC jet database: airframe+systems = dry weight - engine system(recommended thrust)."""
    rc = pd.read_csv(os.path.join(ROOT, "data", "rc_jet_airframe_database.csv"))
    def mid(v):
        nums = [float(x) for x in re.findall(r"[\d.]+", str(v))]
        return np.mean(nums) if nums else np.nan
    rc["dry"] = rc.dry_weight_kg.map(mid); rc["F"] = rc.recommended_thrust_N.map(mid)
    rc = rc.dropna(subset=["dry", "F", "wingspan_mm", "length_mm"])
    a, b = 0.0035, 1.1638   # engine_database_fit (26 engines)
    rc["eng_sys"] = a * rc.F ** b * (1 + ACC_FRAC_NOM)
    rc["airframe_sys"] = rc.dry - rc.eng_sys
    rc["size_LxB"] = rc.length_mm / 1000 * rc.wingspan_mm / 1000
    k = np.sum(rc.airframe_sys * rc.size_LxB) / np.sum(rc.size_LxB ** 2)          # least squares through origin
    s_us = c.L_fus * c.surfaces()["wing"].span
    return k * s_us, k, rc[["model", "dry", "F", "eng_sys", "airframe_sys", "size_LxB"]], s_us

def close(S, engine_case="nom", E_WD=None):
    c = Config(S_wing=S)
    eng = ENV["engine_mass_kg"] if engine_case == "nom" else ENV["engine_mass_hi_kg"]
    acc = eng * (ACC_FRAC_NOM if engine_case == "nom" else ACC_FRAC_HI)
    items = bottom_up(c)
    af = sum(items.values())
    empty = eng + acc + af * (1 + GROWTH)
    M = 25.0
    for _ in range(6):                                     # iterate take-off mass <-> mission fuel
        r = mdp.run(S, E_WD=E_WD, M0=M)
        if r is None: return None
        fuel = r[0]["fuel_total_kg"] * (1 + UNUSABLE)
        M_new = empty + fuel
        if abs(M_new - M) < 0.01: break
        M = M_new
    st, k, rc, size = statistical(c)
    return dict(S_wing=S, engine_case=engine_case, E_case="nom" if E_WD is None else "hi", engine_kg=eng, accessories_kg=acc,
                airframe_systems_bottomup_kg=af, growth_kg=af * GROWTH, fuel_kg=fuel, fuel_volume_L=fuel / FUEL_DENS,
                TOGW_kg=M_new, margin_to_25kg=25.0 - M_new, dash_throttle=r[0]["dash_throttle"], V_LOF=r[0]["V_LOF_mps"],
                airframe_systems_statistical_kg=st, size_proxy=size, fuselage_volume_L=c.body_volume() * 1000), items, rc, k

if __name__ == "__main__":
    rows = []
    for S in [0.25, 0.30, 0.35]:
        for ec in ("nom", "hi"):
            for E in (None, "hi"):
                Ev = max(3.0, max(1.8, Config(S_wing=S).E_geom())) if E == "hi" else None
                out = close(S, ec, Ev)
                if out is None:
                    rows.append(dict(S_wing=S, engine_case=ec, E_case=E, note="dash infeasible")); continue
                d, items, rc, k = out; rows.append(d)
                if S == 0.30 and ec == "nom" and E is None:
                    base_items, base = items, d
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ROOT, "data", "phase2_mass_budget.csv"), index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_colwidth", 90)
    print(df.round(3).to_string(index=False))
    print("\nBottom-up items (S = 0.30 m2):")
    for kk, v in base_items.items(): print(f"  {v:6.3f} kg  {kk}")
    print(f"  sum {sum(base_items.values()):.3f} kg  (+{GROWTH*100:.0f} % growth = {sum(base_items.values())*GROWTH:.3f} kg)")
    print(f"\nStatistical cross-check (RC jets, airframe+systems per unit length x span = {k:.2f} kg/m2):")
    print(rc.round(2).to_string(index=False))
    print(f"  our size proxy {base['size_proxy']:.2f} m2 -> {base['airframe_systems_statistical_kg']:.2f} kg (extrapolated below database range)")
    # summary table for the budget (S = 0.30, nominal)
    summ = {"engine (dry, database fit)": base["engine_kg"], "engine accessories": base["accessories_kg"]}
    grp = {"structure": ["fuselage", "inlet", "engine mounts", "wing", "tails"], "landing gear + chute": ["landing gear", "drag chute"],
           "fuel system": ["fuel tank"], "systems + avionics + instrumentation": ["servos", "flight controller", "flight batteries", "wiring", "prize", "flight termination"]}
    for g, keys in grp.items():
        summ[g] = sum(v for kk, v in base_items.items() if any(kk.startswith(x) for x in keys))
    summ["growth allowance 15 %"] = base["growth_kg"]; summ["fuel (mission + reserve + 3 % unusable)"] = base["fuel_kg"]
    summ["margin to 25 kg"] = base["margin_to_25kg"]
    sm = pd.Series(summ); sm.to_csv(os.path.join(ROOT, "data", "phase2_mass_budget_summary_S030.csv"), header=["kg"])
    print("\nBudget summary, S = 0.30 m2, nominal engine and drag:\n", sm.round(2).to_string(), f"\n  TOGW = {base['TOGW_kg']:.2f} kg")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    left = 0
    for (lab, v), col in zip(sm.items(), plt.cm.tab10.colors):
        ax.barh([0], [v], left=left, color=col if lab != "margin to 25 kg" else "lightgray", edgecolor="k", label=f"{lab}: {v:.2f} kg")
        left += v
    ax.axvline(25, c="r", lw=2); ax.set_xlim(0, 26); ax.set_yticks([]); ax.set_xlabel("mass [kg]")
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    ax.set_title(f"Phase 2 mass budget, S = 0.30 m2 (nominal): TOGW {base['TOGW_kg']:.1f} kg vs 25 kg ceiling", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots", "phase2_mass_budget.png"), dpi=130)
    print("saved")
