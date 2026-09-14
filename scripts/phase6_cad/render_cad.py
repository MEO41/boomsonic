"""Phase 6: figures of the CAD (run in .venv-cad; VTK 9.6 off-screen + matplotlib). Reads the STEP files only.

  plots/phase6_engine_cutaway.png   engine, 3/4 view, static parts cut open over one quadrant (rotor shown whole)
  plots/phase6_engine_section.png   meridional half-section (plane z = 0) of every part, with the stations
  plots/phase6_impeller.png         impeller (12 sectors), 3/4 front view
  plots/phase6_impeller_fe.png      3D FE von Mises on the 30 deg sector (cad/fe/impeller_sector_<tag>.vtu), if present
  plots/phase6_aircraft.png         aircraft exterior, 3/4 view
  plots/phase6_aircraft_cutaway.png same view, skin / duct / jetpipe opened over one quadrant, engine inside
  plots/phase6_aircraft_section.png side section: body (with the area-rule waist), intake duct, engine section, reserved
                                    calibrated envelope, jetpipe, fuel annulus
"""
import os, sys, json, math, glob, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
import cadquery as cq
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
PL = os.path.join(ROOT, "plots"); os.makedirs(PL, exist_ok=True)
E = json.load(open(os.path.join(ROOT, "data", "phase6", "engine_params.json")))
A = json.load(open(os.path.join(ROOT, "data", "phase6", "airframe_params.json")))
MAT = dict(compressor_front_shroud="Al", compressor_front_wall="Al", diffuser_back_plate="Al", diffuser_vanes="Al", deswirl_inner_wall="Al",
           deswirl_vanes="Al", compressor_casing="Al", liner_outer="IN625", liner_inner="IN625", liner_dome="IN625", vaporisers="IN625",
           ngv_vanes="IN713", ngv_hub_ring="IN713", ngv_shroud_ring="IN713", turbine_blades="IN713", turbine_disc="IN713", turbine_shroud="IN713",
           hot_casing="SS", nozzle_outer_cone="SS", tail_cone="SS", shaft="steel", bearing_front="steel", housing_front="SS", bearing_rear="steel",
           housing_rear="SS", shaft_tunnel="SS", impeller="Ti")
COL = dict(Ti=(0.62, 0.64, 0.68), Al=(0.69, 0.77, 0.87), SS=(0.80, 0.62, 0.20), IN625=(1.0, 0.55, 0.0), IN713=(0.70, 0.13, 0.13), steel=(0.35, 0.35, 0.35))
ROTOR = {"impeller", "shaft", "turbine_disc", "turbine_blades", "bearing_front", "bearing_rear"}

def load(nm, d="engine"):
    return cq.importers.importStep(os.path.join(ROOT, "cad", d, f"{nm}.step")).val()

def polydata(shape, tol=0.08, ang=0.3):
    vs, ts = shape.tessellate(tol, ang)
    P = np.array([[v.x, v.y, v.z] for v in vs], float); T = np.array(ts, np.int64)
    pd_ = vtk.vtkPolyData(); pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(P, deep=True)); pd_.SetPoints(pts)
    cells = np.c_[np.full(len(T), 3), T].ravel(); ca = vtk.vtkCellArray(); ca.SetCells(len(T), numpy_to_vtkIdTypeArray(cells, deep=True)); pd_.SetPolys(ca)
    nrm = vtk.vtkPolyDataNormals(); nrm.SetInputData(pd_); nrm.SetFeatureAngle(35); nrm.SplittingOn(); nrm.Update()
    return nrm.GetOutput()

def actor(pd_, color, opacity=1.0, edges=False):
    mp = vtk.vtkPolyDataMapper(); mp.SetInputData(pd_); a = vtk.vtkActor(); a.SetMapper(mp)
    pr = a.GetProperty(); pr.SetColor(*color); pr.SetOpacity(opacity); pr.SetSpecular(0.25); pr.SetSpecularPower(20); pr.SetDiffuse(0.85); pr.SetAmbient(0.15)
    if edges: pr.EdgeVisibilityOn(); pr.SetEdgeColor(0.2, 0.2, 0.2); pr.SetLineWidth(0.3)
    return a

def render(actors, path, cam_pos, focal, up=(0, 0, 1), size=(1800, 1200), zoom=1.0, bg=(1, 1, 1), extra=None):
    ren = vtk.vtkRenderer(); ren.SetBackground(*bg)
    for a in actors: ren.AddActor(a)
    if extra: extra(ren)
    rw = vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.AddRenderer(ren); rw.SetSize(*size); rw.SetMultiSamples(8)
    ren.SetUseDepthPeeling(1); ren.SetMaximumNumberOfPeels(8); rw.SetAlphaBitPlanes(1)
    cam = ren.GetActiveCamera(); cam.SetPosition(*cam_pos); cam.SetFocalPoint(*focal); cam.SetViewUp(*up); ren.ResetCamera(); cam.Zoom(zoom)
    lk = vtk.vtkLightKit(); lk.AddLightsToRenderer(ren)
    rw.Render(); w = vtk.vtkWindowToImageFilter(); w.SetInput(rw); w.Update()
    pw = vtk.vtkPNGWriter(); pw.SetFileName(path); pw.SetInputConnection(w.GetOutputPort()); pw.Write(); print("wrote", os.path.relpath(path, ROOT))

def quadrant_cut(shape, xmin=-100, xmax=500):
    box = cq.Solid.makeBox(xmax - xmin, 300, 300, cq.Vector(xmin, 0, 0))       # removes y > 0, z > 0
    try:
        r = shape.cut(box)
        return r if r.Volume() > 1e-6 else shape
    except Exception:
        return shape

def section_xy(shape, n=80):
    """edges of the section of a shape with the plane z = 0, as (x, y) polylines."""
    op = BRepAlgoAPI_Section(shape.wrapped, gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))); op.Build()
    out = []
    for e in cq.Shape.cast(op.Shape()).Edges():
        p = np.array([[q.x, q.y] for q in e.positions(np.linspace(0, 1, n if e.geomType() != "LINE" else 2))]); out.append(p)
    return out

if __name__ == "__main__":
    what = sys.argv[1].split(",") if len(sys.argv) > 1 else ["engine", "section", "impeller", "fe", "aircraft", "asection"]
    names = [os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "cad", "engine", "*.step"))]
    names = [n for n in names if n in MAT]
    shapes = {n: load(n) for n in names}
    if "engine" in what:
        acts = []
        for n, s in shapes.items():
            shp = s if n in ROTOR else quadrant_cut(s)
            acts.append(actor(polydata(shp, tol=0.1 if n != "impeller" else 0.05), COL[MAT[n]]))
        render(acts, os.path.join(PL, "phase6_engine_cutaway.png"), cam_pos=(-250, 420, 330), focal=(170, 0, 0), up=(0, 0, 1), zoom=1.35)
    if "section" in what:
        fig, ax = plt.subplots(figsize=(13, 5.2))
        for n, s in shapes.items():
            for p in section_xy(s):
                if np.all(p[:, 1] > -1e-6): ax.plot(p[:, 0], p[:, 1], color=COL[MAT[n]], lw=0.9)
        st = E["stations"]; ymax = E["envelope"]["OD_model"]["value"] * 500
        for i, (k, lab) in enumerate((("x_compressor_section_end", "compressor section end"), ("x_combustor_end", "combustor end / NGV LE"),
                                      ("x_rotor_centre", "turbine rotor"), ("x_nozzle_exit", "nozzle exit"))):
            if k in st:
                xx = st[k]["value"] * 1e3; ax.axvline(xx, color="0.6", lw=0.6, ls=":")
                ax.text(xx + 2, ymax * (1.03 + 0.07 * (i % 2)), lab, fontsize=7, va="bottom")
        ax.axhline(ymax, color="k", lw=0.6, ls="--"); ax.text(-28, ymax + 1.5, f"envelope OD {2*ymax:.1f} mm", fontsize=7)
        ax.set_aspect("equal"); ax.set_xlabel("x from impeller nose [mm]"); ax.set_ylabel("r [mm]"); ax.set_ylim(0, ymax * 1.22); ax.set_xlim(-40, 370)
        from matplotlib.lines import Line2D
        ax.legend([Line2D([], [], color=c, lw=2) for c in COL.values()], ["Ti-6Al-4V", "Al alloy", "stainless", "IN625", "IN713LC", "steel"], fontsize=7,
                  loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=6, frameon=False)
        ax.set_title("Phase 6 engine CAD: meridional half-section (plane z = 0; blade rows cut where they cross the plane)", fontsize=10)
        fig.tight_layout(); fig.savefig(os.path.join(PL, "phase6_engine_section.png"), dpi=170); plt.close(fig); print("wrote plots/phase6_engine_section.png")
    if "impeller" in what:                           # axis vertical, nose up, looking down onto the inducer
        render([actor(polydata(shapes["impeller"], tol=0.03, ang=0.2), COL["Ti"])], os.path.join(PL, "phase6_impeller.png"),
               cam_pos=(-110, 120, 40), focal=(25, 0, 0), up=(-1, 0, 0), size=(1400, 1300), zoom=1.3)
        sec = cq.importers.importStep(os.path.join(ROOT, "cad", "engine", "impeller_sector.step")).val()
        render([actor(polydata(sec, tol=0.02, ang=0.15), COL["Ti"], edges=False)], os.path.join(PL, "phase6_impeller_sector.png"),
               cam_pos=(-90, 110, 90), focal=(25, 25, 25), up=(-1, 0, 0), size=(1300, 1200), zoom=1.2)
    if "fe" in what:
        vt = sorted(glob.glob(os.path.join(ROOT, "cad", "fe", "impeller_sector_*.vtu")))
        vt = [p for p in vt if p.endswith("baseline.vtu")] or vt
        if vt:
            rd = vtk.vtkXMLUnstructuredGridReader(); rd.SetFileName(vt[0]); rd.Update()
            sf = vtk.vtkDataSetSurfaceFilter(); sf.SetInputConnection(rd.GetOutputPort()); sf.Update()
            surf = sf.GetOutput(); surf.GetCellData().SetActiveScalars("vm_MPa")
            Fty = round(json.load(open(os.path.join(ROOT, "data", "phase6", "fe3d_impeller.json")))["reference_phase3r"]["Fty_MPa"])
            lut = vtk.vtkLookupTable(); lut.SetHueRange(0.667, 0.0); lut.SetTableRange(0, Fty); lut.SetAboveRangeColor(0.6, 0.0, 0.6, 1.0); lut.UseAboveRangeColorOn(); lut.Build()
            mp = vtk.vtkDataSetMapper(); mp.SetInputData(surf); mp.SetScalarModeToUseCellData(); mp.SetLookupTable(lut); mp.SetScalarRange(0, Fty); mp.UseLookupTableScalarRangeOn()
            a = vtk.vtkActor(); a.SetMapper(mp); a.GetProperty().SetAmbient(0.45); a.GetProperty().SetDiffuse(0.65)
            def bar(ren):
                sb = vtk.vtkScalarBarActor(); sb.SetLookupTable(lut); sb.SetTitle(f"von Mises [MPa]\nmagenta > Fty {Fty}"); sb.SetNumberOfLabels(5)
                sb.GetTitleTextProperty().SetColor(0, 0, 0); sb.GetLabelTextProperty().SetColor(0, 0, 0)
                sb.UnconstrainedFontSizeOn(); sb.GetTitleTextProperty().SetFontSize(26); sb.GetLabelTextProperty().SetFontSize(24)
                sb.GetTitleTextProperty().ItalicOff(); sb.GetLabelTextProperty().ItalicOff(); sb.SetTextPad(8)
                sb.SetPosition(0.78, 0.1); sb.SetWidth(0.2); sb.SetHeight(0.8); ren.AddActor2D(sb)
            render([a], os.path.join(PL, "phase6_impeller_fe.png"), cam_pos=(-60, 150, 120), focal=(25, 20, 30), up=(1, 0, 0), size=(1500, 1200), zoom=1.2, extra=bar)
    if "aircraft" in what or "asection" in what:
        an = [os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "cad", "airframe", "*.step"))]
        ash = {n: load(n, "airframe") for n in an}
        xf = A["engine_face_x"] * 1e3
    if "aircraft" in what:
        L_b = A["body_x"][-1] * 1e3
        skin = polydata(ash["fuselage_skin"], tol=0.5, ang=0.3)
        surf = {n: polydata(s, tol=0.4, ang=0.3) for n, s in ash.items() if n != "fuselage_skin"}
        eng = {n: polydata(s.translate((xf, 0, 0)), tol=0.3, ang=0.4) for n, s in shapes.items()}
        cam = dict(cam_pos=(-0.25 * L_b, -1.05 * L_b, 0.55 * L_b), focal=(0.5 * L_b, 0, 0), up=(0, 0, 1), size=(2000, 1150), zoom=1.5)
        ext = [actor(skin, (0.80, 0.82, 0.86))] + [actor(p, (0.45, 0.55, 0.75)) for n, p in surf.items() if n not in ("jetpipe", "intake_duct")]
        render(ext, os.path.join(PL, "phase6_aircraft.png"), bg=(0.93, 0.94, 0.96), **cam)
        # cutaway (off-screen VTK dropped translucent actors): skin opened over the quadrant facing the camera (y < 0, z > 0)
        box = cq.Solid.makeBox(L_b + 200, 400, 400, cq.Vector(-100, -400, 0))
        cut = lambda s: s.cut(box)
        ph = [actor(polydata(cut(ash["fuselage_skin"]), tol=0.5, ang=0.3), (0.80, 0.82, 0.86))]
        for n, s in ash.items():
            if n == "fuselage_skin": continue
            col = (0.72, 0.53, 0.04) if n == "jetpipe" else ((0.35, 0.65, 0.35) if n == "intake_duct" else (0.45, 0.55, 0.75))
            ph.append(actor(polydata(cut(s) if n in ("jetpipe", "intake_duct") else s, tol=0.4, ang=0.3), col))
        ph += [actor(p, COL[MAT[n]]) for n, p in eng.items()]
        render(ph, os.path.join(PL, "phase6_aircraft_cutaway.png"), bg=(0.93, 0.94, 0.96), **cam)
    if "asection" in what:
        x = np.array(A["body_x"]) * 1e3; r = np.array(A["body_r"]) * 1e3; rw = np.array(A["body_r_waisted"]) * 1e3
        chk = json.load(open(os.path.join(ROOT, "data", "phase6", "airframe_cad_checks.json")))
        fig, ax = plt.subplots(figsize=(15, 4.6))
        ax.plot(x, r, color="0.7", lw=0.8, ls="--", label="body without the area-rule waist")
        ax.plot(x, rw, color="k", lw=1.2, label="fuselage OML (waisted, as built)"); ax.plot(x, -rw, color="k", lw=1.2)
        for n in ("intake_duct", "jetpipe"):
            for p in section_xy(ash[n]): ax.plot(p[:, 0], p[:, 1], color=(0.3, 0.6, 0.3) if n == "intake_duct" else (0.72, 0.53, 0.04), lw=0.9)
        for n, s in shapes.items():
            for p in section_xy(s): ax.plot(p[:, 0] + xf, p[:, 1], color=COL[MAT[n]], lw=0.6)
        ev = chk["engine_clearance"]; Re = ev["envelope_r_mm"]; x0, x1 = ev["envelope_x_mm"]
        ax.add_patch(plt.Rectangle((x0, -Re), x1 - x0, 2 * Re, fill=False, ls="--", ec="r", lw=0.8, label="reserved calibrated engine envelope"))
        fv = chk["fuel_volume"]; xa = np.linspace(*fv["annulus_x_mm"], 50)
        ax.fill_between(xa, np.interp(xa, x, rw) - 6.5, np.interp(xa, [0, x0 - 30], [chk["intake"]["capture_r_mm"] + 6, chk["intake"]["face_r_mm"] + 6]),
                        color="C0", alpha=0.15, label=f"fuel annulus (gross {fv['annulus_volume_L']:.1f} L; {fv['fuel_required_L']:.2f} L needed)")
        yb = -rw.max() - 12
        for sf in A["surfaces"].values():
            if not sf["vertical"]:
                xl = sf["x_root_le"] * 1e3; ax.plot([xl, xl + sf["c_root"] * 1e3], [yb, yb], color="C3", lw=3, alpha=0.6, solid_capstyle="butt")
        ax.plot([], [], color="C3", lw=3, alpha=0.6, label="wing / tail root chord (x extent)")
        ax.set_aspect("equal"); ax.set_xlabel("x from the nose [mm]"); ax.set_ylabel("r [mm]"); ax.set_ylim(yb - 10, rw.max() + 10)
        ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=4, frameon=False)
        ax.set_title(f"Phase 6 aircraft section (plane z = 0): engine gap to the waisted skin {ev['radial_gap_mm']:.1f} mm at x = {ev['at_x_mm']:.0f} mm", fontsize=10)
        fig.tight_layout(); fig.savefig(os.path.join(PL, "phase6_aircraft_section.png"), dpi=160); plt.close(fig); print("wrote plots/phase6_aircraft_section.png")
