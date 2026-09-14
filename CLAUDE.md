# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A conceptual design study for a 500 N-class turbojet and a ≤25 kg MTOW airframe that must reach and hold Mach 1 (the Boom Prize rules; design point M 1.02 at 5 km ISA). It is a student learning project. Explain the physics behind each result, not only the numbers, and keep the work at conceptual-study level.

The brief is `turbojet_500N_mission_brief.md`. Its ground rules are binding:
1. **No guessing.** Every decision needs a tool run or a cited handbook relation. If a tool can't answer a question, say so and propose the next-best method.
2. **Log every non-trivial decision in `design_log.md`**: tool, inputs, outputs, and why the choice won, with numbers.
3. **Verify a tool before trusting it** (see "Tool defects" below).
4. **No CAD or detailed mechanical design** until the user approves the Phase 5 `design_freeze.md`.

So far every phase and check has ended by handing the next decision to the user, and the next phase has started only on their instruction. Check the latest entry at the bottom of `design_log.md` for the current state and any decision that is waiting on the user.

**Current baseline (user decision, 2026-09-14): centrifugal compressor only.** Phase 3 was redone as Phase 3R (`docs/phase3r_centrifugal.md`). The user approved a single-stage centrifugal, OPR 4, 75 000 rpm, 15 deg backsweep (tag `ce75000_opr4_t1150_b15_cap`). Phase 4 on it is in `docs/phase4r_centrifugal.md`: shorter, radially grown combustor; 32 mm tube shaft; damped supports; TOGW 20.1 kg. The Phase 5 freeze snapshot is `docs/design_freeze.md`. Its open-risks section (surge margin, idle transient, combustor length, vane/exducer resonance, no hardware validation) must not be presented as resolved. **Phase 6 (CAD / 3D) was started on the user's instruction ("continue phase 6") with the toolchain, scope (engine + airframe + 3D impeller FE) and parametric treatment of the open items confirmed by the user (design_log D6.0).** The freeze's open decisions were not answered and remain open. Phase 6 report: `docs/phase6_cad.md` (D6.1–D6.6). The axial and axial-centrifugal work in Phases 3, 3b and 4 is kept for the record only.

## Environments (three venvs, on purpose)

Python 3.12 via `uv`. ADRpy and TurboFlow need NumPy 1; OpenMDAO/pyCycle and turbodesigner need NumPy ≥ 2. The CAD stack lives in its own venv so the frozen analysis venvs stay untouched.

| venv | NumPy | tools |
|---|---|---|
| `.venv` | 2.x | pyCycle (git), OpenMDAO, Cantera, turbo-design (git), turbodesigner, AeroSandbox, scikit-fem, ROSS |
| `.venv-np1` | 1.26 | ADRpy, TurboFlow, CoolProp |
| `.venv-cad` | 2.x | CadQuery 2.8 (OCCT 7.9), gmsh 4.15, pyturbo-aero 1.3.8, scikit-fem, meshio, pyamg, pypardiso (MKL), VTK |

```powershell
uv venv --python 3.12 .venv      ; $env:VIRTUAL_ENV="$PWD\.venv";     uv pip install -r requirements-np2.txt
uv venv --python 3.12 .venv-np1  ; $env:VIRTUAL_ENV="$PWD\.venv-np1"; uv pip install -r requirements-np1.txt
uv venv --python 3.12 .venv-cad  ; $env:VIRTUAL_ENV="$PWD\.venv-cad"; uv pip install -r requirements-cad.txt
```

`.venv-cad` has no pip; install with `uv pip` as above. Its Python processes exit non-zero at teardown after finishing (OCP quirk), so check outputs, not exit codes.

* Run scripts **from the repo root** with the venv's interpreter, e.g. `.venv\Scripts\python scripts\phase3_cycle\arch_trade.py`.
* Orchestrators hard-code `.venv-np1/Scripts/python.exe` (Windows layout) and call TurboFlow/ADRpy scripts in that venv themselves.
* After adding a package, refreeze the matching `requirements-np*.txt` and log it in `design_log.md` / `tools_survey.md`.
* The `.sh` map runners need Git Bash: `bash scripts/phase4_turbomachinery/run_turbine_map.sh <tag>`.

## Commands

There is no project test suite or linter. Correctness is established by verification scripts that check each tool against closed-form or published results. Re-run the relevant one after changing a solver:

```powershell
.venv\Scripts\python scripts\phase0_tools\smoke_pycycle.py          # also smoke_cantera / smoke_turbodesign / smoke_turbodesigner
.venv-np1\Scripts\python scripts\phase0_tools\smoke_turboflow.py    # also smoke_adrpy
.venv\Scripts\python scripts\phase2_airframe\verify_aero_tools.py   # wave-drag integral vs Sears-Haack / parabolic body
.venv\Scripts\python scripts\phase3_cycle\validate_mass_model.py    # engine mass model vs JetCat P400 / AMT Nike
.venv\Scripts\python scripts\phase4_turbomachinery\verify_axisym_fe.py      # rotating-disc FE vs Timoshenko
.venv\Scripts\python scripts\phase4_turbomachinery\rotordynamics_verify.py  # ROSS / own eigen-solver vs closed forms
.venv\Scripts\python scripts\phase4_turbomachinery\cc_benchmark.py          # full operability chain on the P400 (idles at 31 %)
```

Phase 6: `.venv-cad\Scripts\python scripts\phase6_cad\smoke_cad.py` (CAD primitives) and `fe3d_impeller.py A,B,BT` (3D FE vs rotating-disc theory and the axisymmetric FE).

Also `.venv-np1\Scripts\python scripts\phase3_cycle\verify_turboflow_slip.py` (TurboFlow slip fix) and `.venv\Scripts\python scripts\phase3_cycle\impeller_stress.py` (regression against the Phase 4 impeller gate). For the Phase 3R calibration and benchmark runs, set `P3_DATA=phase3r` and `MAP_DIR=data/phase3r/maps` (see README).

Pipeline entry points:

```powershell
python scripts/phase2_airframe/run_phase2.py        # every Phase 2 table and plot (calls both venvs)
.venv\Scripts\python scripts\phase3_cycle\cc_trade.py run 4.0:75000:-15     # Phase 3R full-chain case (OPR:rpm:backsweep)
.venv\Scripts\python scripts\phase3_cycle\cc_trade.py compile               # data/phase3r_cc_trade.csv
.venv\Scripts\python scripts\phase3_cycle\cc_mission.py ce75000_opr4_t1150_b15_cap   # running lines, deck, sortie on real maps
```

`README.md` has the full per-phase command list. Add each new phase's commands there.

## Architecture

### Phases chain through files, not a package
`scripts/phaseN_*/` are flat script directories. Later phases import earlier ones with `sys.path.insert`:
* Phase 3 imports `phase2_airframe` (`airframe_model`, `mass_budget`) to recompute dash drag with the real engine diameter.
* Phase 4 imports `phase3_cycle` (`cycle_model`, `dash_cycle`, `arch_trade.scaled_comp`, `engine_mass`).

Changing a Phase 2 or 3 module can therefore silently change downstream results.

### Cross-venv calls go through JSON
`arch_trade.run_np1` (and the same pattern in `axicent_design`, `centrifugal_sweep`, `operability`) works like this:
1. write `data/phase3/<tag>_in.json`;
2. run the script under `.venv-np1` as `script.py <in.json> <out.json>`;
3. read `<tag>_out.json`.

The NumPy-1 scripts are `centrifugal_design.py`, `turbine_design.py`, `centrifugal_map.py`, `turbine_map.py` and `constraint_diagram.py`. Keep them standalone: file in, file out, no imports from the `.venv` side.

### Case tags name every artefact
`arch_trade.py` builds each tag as `{kind[:2]}{rpm}_opr{OPR}_t{T4}[_ax{n_ax}_pa{pi_axial}][_cap]{P3_TAG_SUFFIX}`:
* `ce` = centrifugal;
* `ax` = both the pure axial and the axial-centrifugal. The axial-centrifugal is the one with `_ax{n}_pa{pr}`;
* rpm `0` = the best axial speed over the grid;
* `_cap` = turbine tip capped at the engine envelope;
* `_blk` = a run after the TurboDesigner blockage fix. Pre-`_blk` axial results are superseded (design_log F4.2).

Each case is evaluated at two technology levels:
* `tool`: the efficiencies the design tools predict;
* `fielded`: debited to reproduce commercial micro-turbojet TSFC, eta_c 0.70 (centrifugal), eta_t 0.75. The axial is debited by the same ratio via `P3_CC_REF`.

The outputs are `data/phase3/trade_<tag>_{tool,fielded}.json` and `data/phase3_arch_trade_*.csv`. Phase 4 scripts take a tag as their argument and read `trade_<tag>_fielded.json` plus `<tag>_tt_out.json` (turbine) or `<tag>_ac_out.json` (axial-centrifugal).

### Phase 3R chain (centrifugal, current)
`cc_trade.py` reuses `arch_trade.design_case` (with `P3_DATA=phase3r`, so files go to `data/phase3r/`) but evaluates differently. Its tags add the backsweep, e.g. `ce75000_opr4_t1150_b15_cap`, and each case goes to one `data/phase3r/cct_<tag>.json`.
* **Stress.** The impeller is sized inside the loop (`impeller_stress.py`, which sets the Phase 4 gate module's globals).
* **Fielded compressor geometry** is work-based (`cc_screen.fielded_scales`), not √W.
* **Fielded turbine** is re-designed by TurboFlow at the fielded cycle. The result is cached in `<tag>_ttf70_out.json` / `_ttf66_` and reused when its input is unchanged.
* **Mass and length calibrations** come from `data/phase3_mass_model_validation_3r.csv` and are applied before the drag and TOGW.

`arch_trade.evaluate` and `compile_trade.py` are the Phase 3 path and do none of this.

The centrifugal design options are `Z_split`, `split_frac`, `effective_width` and `choke_margin`. When `Z_eff` is present, `engine_mass` reads `Z_eff`, `t_blade_mean` and `b2_geo_ratio`; old designs keep the Phase 3 blade assumptions.

Map runs write into `data/phase3r/maps/`. Map generation is memory-bound: more than about two maps at once on this 14 GB machine produced `MemoryError` crashes. Re-run a failed compressor group under its original `_g<i>` part number, because the runner numbers parts from 0.

### Cycle model (`scripts/phase3_cycle/cycle_model.py`)
It is a pyCycle `Turbojet` using TABULAR Jet-A thermo, with combustion efficiency applied in post-processing.

Its options are:
* `design_W` (`Fn` to size to thrust, `fixed` for vendor calibration);
* `od_mode` (`T4`, `N`, or `NT4` for transient excess power);
* `nozz_type`;
* `comp_map` / `turb_map`: `None` uses the placeholder NPSS AXI5 / LPT2269 maps;
* `comp_bleed`.

The Phase 4 options default to off. Phase 3 results must reproduce unchanged: centrifugal dash W 1.32575 kg/s, TSFC 0.16416.

### Maps and caches
* TurboFlow maps are generated one speed line (or speed group) per process, because a failed point poisons every later point in the same call. The parts go to `data/phase4/{tmap,cmap}_parts/` and are merged into `data/phase4/{turbine,centrifugal}_map_<tag>.json`.
* `operability.py` reuses `comp_lines_<tag>_nw*.json` and `turbine_map_<tag>.json` if they exist. **Delete them to force regeneration** after changing the compressor or turbine model.
* `airframe_model.Config` loads `data/engine_envelope.json` if present, and that overrides the default engine size.

### Environment-variable knobs
| variable | effect |
|---|---|
| `P3_OPR`, `P3_T4` | cycle OPR and T4 |
| `P3_CASES` | cases as `kind:rpm[:n_ax:pi_a]`, comma-separated |
| `P3_TURB_CAP` | cap the turbine tip at the engine envelope |
| `P3_CC_REF` | centrifugal tool eta_c used to debit the axial |
| `P3_TAG_SUFFIX`, `P3_OUT_SUFFIX` | suffixes on the case tag and the output CSV |
| `CC_RPMS`, `CC_R4R2` | centrifugal sweep grid |
| `CC_ATR` | impeller throat area ratio |
| `P4_TRADE` | rotor-model source trade file |
| `TMAP_NS`, `TMAP_PAR` | turbine-map speed lines; run them in parallel |
| `P3_DATA` | data subdirectory for `arch_trade` / `validate_mass_model` / `cc_benchmark` (`phase3r` for Phase 3R) |
| `P3_CC_OPTS` | JSON of centrifugal design options for `validate_mass_model` |
| `CC_SRC`, `TT_SRC`, `MAP_DIR`, `CC_GROUPS` | map-runner source design, output dir, compressor speed groups |
| `CCS_OPR`, `CCS_RPM`, `CCS_BETA` | `cc_screen.py` grid |

Phase 6 knobs: `IMP_THROAT_ONLY=1` (impeller camber / throat scan only), `IMP_RF_N` (radial-fibre unloading exponent, default 3), `IMP_CFD` (pyturbo camber-follow density, default 60), `IMP_FACETED=1` (faceted blades, cross-check only).

### Phase 6 CAD chain
`make_params.py` (`.venv`) writes `data/phase6/engine_params.json` / `airframe_params.json`, with status frozen / derived / provisional. `impeller_cad.py` builds the impeller and the passage-bounded FE sector. `engine_cad.py` imports `cad/engine/impeller.step`. `airframe_cad.py` imports `cad/engine_assembly.step`. Re-run downstream steps after changing an upstream one. Shared CAD helpers are in `cadlib.py`. Every boolean result is checked by volume (a silent boolean failure returns a plausible-looking shape).

`OPENMDAO_REPORTS=0` is set inside the scripts. `ross_shim.py` must be imported before ROSS: it sets `NUMBA_DISABLE_JIT=1` and patches the plotly theme.

## Tool defects already found (don't re-hit or "fix" back)
Details are in `tools_survey.md` and `design_log.md`.
* **pyCycle** must come from git. PyPI `pycycle` is an unrelated package.
* **turbo-design** must come from git main. PyPI 1.4.2 imports `turtle`. It also cannot predict axial-compressor efficiency (empty loss models).
* **TurboDesigner** blockage is a *fraction added* to the area (`physical = flow * (1 + blockage)`): pass 0.02 / 0.04, never 0.98 / 0.96. Efficiency is an input. Its rotor diffusion factor is wrong, so it is recomputed.
* **TurboFlow**:
  * the centrifugal Wiesner slip model takes `np.cos` of the blade angle in degrees (`slip_model.py`). Every TurboFlow centrifugal script must `import turboflow_fixes` (`scripts/phase3_cycle/`), which patches it. Evidence: `verify_turboflow_slip.py`. Centrifugal results made before Phase 3R used the defective slip;
  * design optimisation ignores the requested omega, so an equality constraint was added;
  * it has no stress limit, so a 350 MPa blade-root tip-radius constraint was added;
  * a performance-analysis failure cascades to later points in the same call;
  * `print_simulation_summary` crashes with `stop_on_failure=False`.
* **ADRpy** fails under NumPy 2 and has a default-sweep precedence bug. **AeroSandbox**'s Sears-Haack function returns CD on frontal area, so it isn't used.
* **Axial-stage efficiency and stall** come from an own Howell cascade and stage-stacking model that is unvalidated at micro scale (open risk R4.1). Any result that depends on the axial model inherits that caveat.
* **The peak-PR surge surrogate fails on vaned-diffuser stages** (NASA HECC: real surge margin 8.4 %, surrogate ≥ 73 %; `hecc_surge_check.py`). Never present a peak-PR surge margin as validated.
* **NASA turbo-design centrifugal:** the solver needs `x_le` strictly inside the flow path, and it chokes if the throat is estimated from blade angles (use the design's `area_throat_ratio`). Its vaned-diffuser loss cannot size a diffuser.
* **TurboFlow `area_throat_ratio`** is a fraction of the *tool-level* eye area. What carries to the fielded impeller is the 10 % choke margin (`impeller_cad.choke_ratio`), not the 0.75.
* **pyturbo-aero `Centrif`** (tools_survey section 9):
  * `Centrif.patterns` is class-level (reset it);
  * the first thickness station takes the last list value;
  * profiles are placed at i/(n-1) of span;
  * `build()` runs once per instance; theta shifts crash;
  * SS / PS are Beziers through control points (set `camber_follow_density`);
  * `splitterblade` sits at the main blade's θ (rotate it half a pitch);
  * its own camber (one TE θ for all spans) is replaced by the `__build_camber__` hook.
* **OCCT / gmsh:**
  * faceted solids with fan end caps pass BRepCheck but fail every boolean;
  * the `common()` result of an uncut faceted solid fused to zero volume once;
  * gmsh `setPeriodic` needs matching face topology, so the cyclic tie in `fe3d_impeller.py` is used instead;
  * off-screen VTK drops translucent actors.
* **Solvers:** AMG stalls with the interpolated cyclic tie; SciPy SuperLU pages at ~220 k DOF on this 14 GB machine. Use pypardiso.

## Documentation conventions
* `design_log.md`: newest entries at the bottom, grouped by phase, IDs `Dx.y` (decision), `Ax.y` (assumption), `Fx.y` (finding), `Rx.y` (risk). When a result turns out wrong, add an erratum entry rather than rewriting history, and bannerise the affected doc (as `docs/phase3_engine.md` section 14 does).
* One report per phase or check in `docs/`, plots as `plots/phaseN_*.png`, tables as `data/phaseN_*.csv|json`. Generated data is committed.
* Commit messages start with the phase, e.g. `Phase 4: ...`.
