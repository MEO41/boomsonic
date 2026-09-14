# Phase 6: CAD / 3D toolchain proposal (for confirmation before any geometry is generated) (2026-09-14)

The brief's Phase 6: "propose the CAD/3D toolchain (e.g. CadQuery/FreeCAD scripting) and confirm it with me before
generating any geometry". The user said "continue phase 6" after the Phase 5 snapshot (`docs/design_freeze.md`). The
freeze's open decisions (surge margin, diffuser vane count, combustor length) are **still open**. As the freeze
section 5 warns, geometry that depends on them may need to change. The proposal below builds those parts from
parameters so they can be regenerated rather than redrawn.

## 1. Proposed toolchain (installed and verified in `.venv-cad`)

| tool | role | verification |
|---|---|---|
| **CadQuery 2.8.0** (OCCT 7.9.3 via OCP, Apache-2.0) | scripted solid modelling, assembly, STEP and STL export; direct OCCT calls for B-spline surfaces through point clouds and lofts | `scripts/phase6_cad/smoke_cad.py`: exact box volume and STEP round trip; B-spline surface through cylinder points at the exact analytic area; spline-section loft at the exact analytic volume, valid solid |
| **pyturbo-aero 1.3.8** (NASA, held for Phase 6 since D0.7) | impeller blade geometry: main and splitter blades from the meridional hub / shroud, camber (metal angles, wrap) and thickness distributions, tip clearance, full wheel; point clouds only | imports; API present. A functional check on a generic case is the first step after confirmation. Known defect: shared class-level `patterns` list (build one wheel per process) |
| **gmsh 4.15.2** | tetra meshing of CAD solids for 3D FE (the freeze's open "3D impeller FE") | STEP box meshed, summed volume exact |
| scikit-fem 12.0.2 (existing, `.venv`) | 3D elasticity on the gmsh mesh, if the 3D impeller FE is pursued | would need its own 3D verification (rotating solid disc and cantilever) before use |

Environment: a separate `.venv-cad` (`requirements-cad.txt`), so the frozen analysis environments are untouched.
Geometry data passes from the analysis to CAD as JSON, as between the two existing venvs.

**Alternatives considered:**
* **build123d 0.11** has the same kernel, but its OCP build differs from CadQuery's (novtk), so it cannot share the env.
  CadQuery is the one the brief names.
* **FreeCAD scripting** needs a full application install and its own Python, and is harder to run headless and
  reproducibly.
* **OpenVSP** is not needed unless the airframe is modelled.

## 2. Proposed modelling plan (nothing below is generated until confirmed)

1. **Parameter sheet** `data/phase6/engine_params.json`, generated from the Phase 3R / 4R data files, so every CAD
   dimension is traceable. Each parameter is tagged *frozen* or *provisional*. Provisional, per the freeze:
   * diffuser vane count and type, R4/R2, vaneless gap;
   * combustor length and radius;
   * bearing span, shaft tube, bearing housings;
   * start-bleed provision (space reserved only).
2. **2D meridional layout** of the whole engine: flow path, stations, bearing positions, envelope. Checked against the
   mass-model envelope (426 × 187 mm).
3. **Impeller 3D** (pyturbo-aero → CadQuery solid): hub body with boreless back-face boss, 12 + 12 blades, -15°
   backsweep, the stress-sized root thickness distribution, tip clearance.

   Checks against the analysis:
   * blade count and exit angle;
   * eye and exit radii and widths;
   * inducer throat area against the design's 0.75 of the eye area;
   * mass and inertia against the axisymmetric FE body (1.13 kg, Ip 1.44e-3 kg m² before the 10 % allowance).
4. **Other components as conceptual solids:**
   * vaned diffuser and deswirl (parametric vane count);
   * combustor casing and liners;
   * NGV and turbine from the TurboFlow blade geometry;
   * shaft, bearings and damper housings;
   * outer casing and nozzle.

   Assembled into one STEP file.
5. **Optional further analysis on the CAD:** 3D FE of the impeller blades (gmsh + scikit-fem, verified first) to replace
   the 2D plate model of the exducer root; CAD mass properties against the models.

Not proposed unless asked:
* airframe CAD;
* detail or manufacturing drawings, tolerances, fillets beyond the root fillet the stress sizing assumes.

## 3. What the user is asked to confirm
* the toolchain (section 1);
* the scope and order (section 2), in particular engine only or also the airframe, and whether the optional 3D FE is
  in;
* that provisional parts are modelled parametrically, while their decisions stay open in `docs/design_freeze.md`.
