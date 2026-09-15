# `axial/` — the axial and axial-centrifugal compressor work

Everything in this directory belongs to engine architectures that are **not** the project baseline.
It is kept for the record and is separated from the repo root so that continued development of the
**centrifugal** engine cannot pick up an axial number by accident.

| | |
|---|---|
| **Status** | Not the baseline. Which engine goes forward is still an open decision of `docs/design_freeze.md`. |
| **Pure axial** | 6 stages, OPR 5, 80 000 rpm, tag `ax80000_opr5_t1150_n6_cap_3r`. Taken to its own freeze: `axial/docs/design_freeze_axial.md`. |
| **Axial-centrifugal ("option B")** | 1–2 axial stages + 1 centrifugal, Phase 3b / Phase 4. Superseded; kept for the record only. |
| **Open risks** | Unchanged by this reorganisation. The axial freeze's open risks (unvalidated stacking model R4.1, idle 77.5 % forcing an engine-off descent, unsourced variable-geometry hardware, start not analysed, blade roots at 96 % of Fty, blade resonances) and the Phase 6A risks R6A.1–R6A.6 must not be presented as resolved. |

## Layout

```
axial/
  scripts/
    phase3_cycle/           ax_trade.py, axial_sweep.py, axicent_sensitivity.py
    phase4_turbomachinery/  ax_*.py (Phase 4A), operability.py + sweeps (Phase 4 axial),
                            ac_operability.py / impeller_check_ac.py / plot_optionB.py (option B),
                            axial_blockage_screen.py, check_turbodesigner_blockage.py
    phase6a_axial_cad/      packaging and mass CAD of the axial core + variable geometry
  data/
    phase3ax/   phase3ax_trade.csv        Phase 3A-R cycle/compressor designs
    phase4ax/                             Phase 4A operability, rotor, mission, closure
    phase4/                               Phase 4 axial + option-B maps (TurboFlow), map parts
    phase6a/                              Phase 6A parameters, clash, mass
    phase4_*.csv|json                     Phase 4 axial running lines, sweeps, rotordynamics
    phase3_axicent_*.csv                  option-B screens and sensitivity
  docs/                     phase4a_axial.md, design_freeze_axial.md, phase4_operability.md,
                            phase4_rotordynamics.md, phase4_optionB_checks.md, phase6a_axial_cad.md
  plots/                    phase4a_*.png, phase4_operability.png, phase4_optionB_operability.png,
                            phase4_campbell.png, phase4_critical_speed_map.png, phase4_rotor_*.png
  cad/
    parts/                  axial core + variable-geometry STEP solids
    axial_core_assembly.step, axial_vg_assembly.step
```

## How the split works

Scripts here keep **two** roots:

* `ROOT` — the repo root, unchanged in meaning. Shared modules (`cycle_model`, `arch_trade`,
  `engine_mass`, `rotor_model`, `cadlib`, …) and shared data (`data/phase3/`, `data/phase3r/`) are
  still reached through it, so nothing was duplicated.
* `AXROOT` — this directory. Every axial artefact (data, plots, cad) is written and read through it.

Each script inserts its original shared directory on `sys.path`, so its imports resolve exactly as
before the move.

### Five axial-named modules deliberately stayed in the shared tree

They could not move: the live **centrifugal** entry points import them.

| module (still in `scripts/`) | imported by | what is used |
|---|---|---|
| `phase3_cycle/axial_design.py` | `arch_trade.py` (module level) → `cc_trade.py` | axial meanline design, for the architecture trade |
| `phase3_cycle/axicent_design.py` | `arch_trade.py` (module level) → `cc_trade.py` | axial-centrifugal design, for the architecture trade |
| `phase4_turbomachinery/axial_map.py` | `cc_mission.py`, `cc_benchmark.py` | `build_compressor_lines`, `compressor_mapdata`, `turbine_mapdata` — generic map → pyCycle helpers, not axial-specific |
| `phase4_turbomachinery/axial_offdesign.py` | `cc_mission.py`, `cc_benchmark.py`, `ac_offdesign.py` | the `Choked` exception; `Compressor` only on the axial path |
| `phase4_turbomachinery/ac_offdesign.py` | `cc_mission.py`, `cc_benchmark.py` | `PureCC` and `CentrifugalMap` — the **pure centrifugal** off-design model lives in this file |

`rotordynamics.py`, `rotordynamics_damped.py`, `rotordynamics_stiffening.py` and `rotor_model.py`
also stayed, because `cc_rotor.py` imports them. Their `__main__` studies are the pure-axial rotor,
so those scripts write their results here, into `axial/data/` and `axial/plots/`.

## Commands

Run from the **repo root**, as before.

### Phase 3A-R / 4A (pure axial, taken to its freeze)

```powershell
.venv\Scripts\python axial\scripts\phase3_cycle\ax_trade.py grid                     # fielded compressor grid (P3_DATA=phase3ax set inside)
.venv\Scripts\python axial\scripts\phase3_cycle\ax_trade.py run 80000                # full chain at one speed (omit rpm: all speeds)
.venv\Scripts\python axial\scripts\phase3_cycle\ax_trade.py compile                  # axial/data/phase3ax_trade.csv
$t = "ax80000_opr5_t1150_n6_cap_3r"
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_rotor_stress.py $t       # blade roots, discs, blade modes (+ FE verification)
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_operability.py $t one 15 0.10 1.6   # one VG configuration per process (parallel)
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_operability_summary.py $t          # idle per configuration (AXOP_SM_MIN)
$env:AXOP_A8_N = "0.80"; .venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_operability.py $t final 15 0.10 2.0   # adopted VG
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_rotor.py $t 80           # rotor-dynamics sweep (ROSS); 2nd arg = idle % for the API check
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_transient.py $t          # acceleration (~45 min; AXTR_NS=0.8,0.775 re-runs a subset)
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_mission.py $t            # engine deck + idle (AXM_REUSE_DECK=1 reuses the deck)
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_closure.py $t            # engine update + closure (incl. engine-off descent)
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ax_plots.py $t              # axial/plots/phase4a_*.png
```

### Phase 6A (axial packaging and mass CAD; exploratory only)

```powershell
.venv\Scripts\python axial\scripts\phase6a_axial_cad\make_params_axial.py    # parameter sheet + VG actuation loads
.venv\Scripts\python axial\scripts\phase6a_axial_cad\ax_flowpath_check.py    # flow-path area / choking capacity per station
.venv-cad\Scripts\python axial\scripts\phase6a_axial_cad\ax_engine_cad.py    # core engine solids -> axial/cad/parts/
.venv-cad\Scripts\python axial\scripts\phase6a_axial_cad\ax_vg_cad.py        # VIGV, stage-3 bleed, variable nozzle mechanisms
.venv-cad\Scripts\python axial\scripts\phase6a_axial_cad\ax_clash.py         # envelope, interference, clearances (~3 min)
.venv-cad\Scripts\python axial\scripts\phase6a_axial_cad\ax_mass_compare.py  # CAD vs the raw bottom-up mass model
```

### Phase 4 on the early pure axial (operability, rotor dynamics)

The map runners live in the shared tree and are steered by environment variables; point `MAP_DIR`
at `axial/data/phase4` for axial tags.

```powershell
.venv\Scripts\python axial\scripts\phase4_turbomachinery\check_turbodesigner_blockage.py   # evidence for the Phase 3 blockage error
$env:P3_OPR=5; $env:P3_CASES="axial:0"; $env:P3_TURB_CAP=1; $env:P3_CC_REF=0.794; $env:P3_TAG_SUFFIX="_blk"; .venv\Scripts\python scripts\phase3_cycle\arch_trade.py
$env:MAP_DIR="axial/data/phase4"; bash scripts/phase4_turbomachinery/run_turbine_map.sh ax0_opr5_t1150_cap_blk
.venv\Scripts\python axial\scripts\phase4_turbomachinery\operability.py ax0_opr5_t1150_cap_blk      # stacking map, running lines, variable IGV
.venv\Scripts\python axial\scripts\phase4_turbomachinery\nozzle_sweep.py ax0_opr5_t1150_cap_blk 1.3,1.6,2.0
.venv\Scripts\python axial\scripts\phase4_turbomachinery\bleed_sweep.py ax0_opr5_t1150_cap_blk 0.1,0.2,0.3
.venv\Scripts\python axial\scripts\phase4_turbomachinery\running_line_axi5.py                      # bracket with the NPSS AXI5 map
.venv\Scripts\python axial\scripts\phase4_turbomachinery\plot_operability.py
.venv\Scripts\python scripts\phase4_turbomachinery\rotordynamics_verify.py   # shared: ROSS verification (writes data/phase4_rotordynamics_verification.json)
.venv\Scripts\python scripts\phase4_turbomachinery\rotordynamics.py          # shared module, axial study -> axial/data, axial/plots
```

### Option B checks (axial-centrifugal) and method benchmark

```powershell
.venv\Scripts\python axial\scripts\phase4_turbomachinery\impeller_check_ac.py    # check 1: impeller stress, both AC variants
$env:MAP_DIR="axial/data/phase4"; bash scripts/phase4_turbomachinery/run_centrifugal_map.sh ax90000_opr4_t1150_ax2_pa2_cap_blk
.venv\Scripts\python axial\scripts\phase4_turbomachinery\ac_operability.py ax90000_opr4_t1150_ax2_pa2_cap_blk [neg_width] [cc map]
.venv\Scripts\python axial\scripts\phase4_turbomachinery\plot_optionB.py
```

`cc_benchmark.py` (the same chain on the JetCat P400 model) stayed in the shared tree — it is the
method verification for the centrifugal too. Its pre-Phase-3R P400 maps stayed in `data/phase4/`.
