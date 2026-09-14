"""Phase 6: impeller CAD with NASA pyturbo-aero 1.3.8 (Centrif) + CadQuery (run in .venv-cad).

Inputs: data/phase6/engine_params.json (fielded impeller: r2, eye, exit width, 12 + 12 blades, -15 deg backsweep,
stress-sized thickness hub 2.24 mm -> shroud 0.8 mm, boreless hub with back-face boss). Units mm.
pyturbo usage (conventions and defects mapped in design_log D6.1 / tools_survey):
  * hub / shroud: the stress model's quarter ellipses, paired by index (same angle parameter), extended 3 mm upstream
    and 3 mm radially outward so the blade LE / TE sit strictly inside the curves (pyturbo clamps offsets at t = 0 / 1);
  * 13 profiles, one per span row (pyturbo places profiles at i/(n-1) of span);
  * camber: pyturbo's own (a 4-point Bezier per profile with ONE TE theta for all spans) could not give the 15 deg TE
    angle and the inducer throat together -- with the short shroud forced to the mid-span wrap it hooked from 43 to
    15 deg in the last 10 % of chord. Replaced (Centrif.__build_camber__ hook) by a least-squares Bezier of the stress
    model's blade: radial-fibre inducer + exducer backsweep (theta_c below); metal angles from meridional, LE = zero
    incidence at every radius, TE = 15 deg backswept at every span. The unloading exponent n = 3 (PROVISIONAL) is the
    smallest giving the Phase 3R 10 % choke margin on the fielded eye (IMP_THROAT_ONLY scan; design_log D6.3);
  * thickness: half-thickness entered as t / (2 r) at each chord station (pyturbo offsets in the conformal plane);
    the first station receives the last list value (pyturbo defect), so the last value is the thin TE;
  * splitters start at 0.5 of the main camber parameter (they reuse the main camber);
  * tip clearance: pyturbo ignores it; the casing CAD is the shroud + 0.25 mm, so the blade tip on the shroud leaves it.
Blades become smooth solids: a B-spline surface through the SS grid and one through the PS grid (hub edge embedded 0.6 mm
in the hub), filled caps, sewn (grid points on the surfaces to 1e-5 mm). A faceted variant (sewn triangles, ladder end
caps; IMP_FACETED=1) meshed into sliver tets and is kept only as a cross-check. A 30 deg sector (hub sector fused with the blade pieces that cross it; 1 main + 1 splitter in total)
is the 3D FE model (fe3d_impeller.py); the wheel is 12 copies of it (booleans on the full wheel took > 17 min).
Checks against the analysis: metal angles along the chord vs the camber law, root and tip thickness, inducer throat vs the
choke-margin requirement (TurboFlow's isentropic throat criterion reproduced by hand at the fielded dash point; the
tool-level ratio 0.75 x eye does not carry over to the larger fielded eye), grid vs solid blade volume, sector volume
closure, mass and inertia.
Outputs: cad/engine/impeller.step, cad/engine/impeller_sector.step, data/phase6/impeller_cad_checks.json
"""
import os, sys, json, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt
from pyturbo.aero.centrif import Centrif, CentrifProfile, TrailingEdgeProperties
import cadlib as cl
E = json.load(open(os.path.join(ROOT, "data", "phase6", "engine_params.json"))); v = lambda k: E["impeller"][k]["value"]
MM = 1e3; RHO_TI = 4430.0
r2, r1s, r1h, L, b2 = (v(k) * MM for k in ("r2", "r1_shroud", "r1_hub", "axial_length", "b2_physical"))
t_hub, t_tip = v("t_root_hub") * MM, v("t_tip") * MM; bsw = abs(v("backsweep_deg")); rpm = v("rpm")
bf = v("back_face"); t_rim, A_boss, p_boss = bf["t_rim"] * MM, bf["boss_A_over_r2"] * r2, bf["boss_p"]
EMBED, TE_HALF = 0.6, 0.3
THROAT_ONLY = os.environ.get("IMP_THROAT_ONLY") == "1"          # camber scan: build pyturbo blades and report the throat only
out = dict(inputs=dict(r2=r2, r1s=r1s, r1h=r1h, L=L, b2=b2, t_hub=t_hub, t_tip=t_tip, backsweep=bsw))

# ---- hub / shroud curves, paired by the quarter-ellipse angle, extended at both ends ----
phi = np.linspace(0, math.pi / 2, 61)
hub = np.c_[L * np.sin(phi), r1h + (r2 - r1h) * (1 - np.cos(phi))]
shr = np.c_[(L - b2) * np.sin(phi), r1s + (r2 - r1s) * (1 - np.cos(phi))]
ext_up = np.linspace(-3.0, 0.0, 4)[:-1]; ext_out = np.linspace(0.0, 3.0, 4)[1:]
hubx = np.r_[ext_up, hub[:, 0], np.full(3, L)]; hubr = np.r_[np.full(3, r1h), hub[:, 1], r2 + ext_out]
shrx = np.r_[ext_up, shr[:, 0], np.full(3, L - b2)]; shrr = np.r_[np.full(3, r1s), shr[:, 1], r2 + ext_out]
s_hub = np.r_[0, np.cumsum(np.hypot(np.diff(hubx), np.diff(hubr)))]; s_hub /= s_hub[-1]
t_le, t_te = s_hub[3], s_hub[3 + len(phi) - 1]                                  # hub arc fractions of (0, r1h) and (L, r2)

def span_line(f):
    """quasi-streamline at span fraction f between paired hub and shroud points (as pyturbo builds it)."""
    return np.c_[hub[:, 0] + f * (shr[:, 0] - hub[:, 0]), hub[:, 1] + f * (shr[:, 1] - hub[:, 1])]

om = rpm * math.pi / 30
beta_le = dict(hub=E["impeller"]["beta1_hub_deg"]["value"], shroud=E["impeller"]["beta1_shroud_deg"]["value"])
C1 = om * (r1h / MM) / math.tan(math.radians(beta_le["hub"]))                  # recover the eye velocity used by the sheet
TH0 = om / C1 / MM                                                               # rad / mm: radial-fibre LE twist, tan b1 = r TH0

# ---- camber law: radial-fibre inducer + exducer backsweep (the stress model's blade) ----
# theta(x, r) = theta_rf(x) + theta_bs(r):
#   theta_rf' (x) = TH0 (1 - x / L)^n  -> radial fibres (theta a function of x only: no centrifugal bending of the inducer,
#       as the gate's inducer-root estimate assumed); at the LE (flow path axial) tan b = r TH0 = U / C1: zero incidence at
#       every radius at once; n (PROVISIONAL) sets how fast the inducer unloads -> the throat;
#   theta_bs' (r) = tan(b_bs(r)) / r, b_bs linear from 0 at 0.7 r2 to the 15 deg backsweep at r2 (the plate model's law).
# At r2 every span line is radial (dx/dm = 0), so the TE metal angle is 15 deg at all spans. TE rake follows from theta_rf.
RF_N = float(os.environ.get("IMP_RF_N", 3.0))         # scan (IMP_THROAT_ONLY, CFD 60): n 2 / 2.5 / 3 -> choke 1.040 / 1.072 / 1.102 x design
rr_bs = np.linspace(0.7 * r2, r2 + 3.0, 400)
th_bs_tab = np.r_[0, np.cumsum(np.diff(rr_bs) * 0.5 * ((np.tan(np.radians(bsw * np.clip((rr_bs[1:] - 0.7 * r2) / (0.3 * r2), 0, 1))) / rr_bs[1:])
                                                       + (np.tan(np.radians(bsw * np.clip((rr_bs[:-1] - 0.7 * r2) / (0.3 * r2), 0, 1))) / rr_bs[:-1])))]
def theta_c(x, r):
    return TH0 * L / (RF_N + 1) * (1 - np.clip(1 - x / L, 0, 1) ** (RF_N + 1)) + np.interp(r, rr_bs, th_bs_tab, left=0.0)

from pyturbo.helper import bezier
from scipy.special import comb
bernstein_poly = lambda n, i, t: comb(n, i) * t ** i * (1 - t) ** (n - i)
NBZ = 14                                                                         # Bezier control points (degree 13)
fit_err = {}
def rf_camber(self, profile, theta_wrap=None, use_ray_intersection=False):
    """replaces Centrif.__build_camber__ (4-point Bezier, one TE theta for all spans): least-squares Bezier in (m', theta)
    of theta_c along the profile's span line; control x equally spaced (linear precision: t = m'/Lm'); end slopes exact."""
    f = profile.percent_span; ln = span_line(f); x, r = ln[:, 0], ln[:, 1]
    mp = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(r)) / (0.5 * (r[1:] + r[:-1])))]; Lm = mp[-1]
    th = theta_c(x, r); n = NBZ - 1; t = mp / Lm
    tan_le = r[0] * TH0; tan_te = math.tan(math.radians(bsw))
    y = np.zeros(NBZ); y[-1] = th[-1]; y[1] = tan_le * Lm / n; y[-2] = th[-1] - tan_te * Lm / n
    B = np.array([bernstein_poly(n, i, t) for i in range(NBZ)]).T
    free = list(range(2, NBZ - 2)); fixed = [0, 1, NBZ - 2, NBZ - 1]
    y[free] = np.linalg.lstsq(B[:, free], th - B[:, fixed] @ y[fixed], rcond=None)[0]
    bz = bezier(np.linspace(0, Lm, NBZ), y)
    tt = np.linspace(0, 1, 400); bx, by = bz.get_point(tt); dx, dy = bz.get_point_dt(tt)
    mm = tt * Lm; xx = np.interp(mm, mp, x); rq = np.interp(mm, mp, r)
    b_fit = np.degrees(np.arctan2(dy, dx)); dmp = np.gradient(mm); b_tgt = np.degrees(np.arctan(np.gradient(theta_c(xx, rq)) / dmp))
    fit_err[round(f, 3)] = dict(max_dtheta_deg=float(np.degrees(np.abs(by - theta_c(xx, rq)).max())), max_dbeta_deg=float(np.abs(b_fit - b_tgt)[2:-2].max()),
                                LE_deg=float(b_fit[0]), TE_deg=float(b_fit[-1]), wrap_deg=float(np.degrees(th[-1])))
    return bz, th[-1]
Centrif.__build_camber__ = rf_camber                                             # (trailing __: not name-mangled)

def profile(f, splitter=False):
    ln = span_line(f); x, r = ln[:, 0], ln[:, 1]
    mp = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(r)) / (0.5 * (r[1:] + r[:-1])))]
    Lm = mp[-1]
    th_half = 0.5 * (t_hub + f * (t_tip - t_hub))
    ts, te_ = (0.5 if splitter else 0.01), 0.95
    n = 5; fr = [ts + k * (te_ - ts) / n for k in range(1, n + 1)]
    rk = [float(np.interp(q * Lm, mp, r)) for q in fr]
    thk = [th_half / rr for rr in rk[:-1]] + [TE_HALF / r2]
    b1 = math.degrees(math.atan(r[0] * TH0))                                     # (camber comes from rf_camber; angle fields unused)
    return CentrifProfile(percent_span=f, LE_Thickness=0.4 / r[0], LE_Metal_Angle=b1, TE_Metal_Angle=bsw, LE_Metal_Angle_Loc=0.1,
                          TE_Metal_Angle_Loc=0.9, ss_thickness=thk, ps_thickness=thk, wrap_angle=0.0,
                          trailing_edge_properties=TrailingEdgeProperties(), thickness_start=0.01, thickness_end=te_,
                          camber_follow_density=CFD)

NS, NC = 13, 61
CFD = int(os.environ.get("IMP_CFD", 60))     # pyturbo SS / PS are Beziers whose CONTROL points are the camber offsets; with
                                             # the default (0: ~10 points) the surfaces smooth away from camber +- t
FS =[i / (NS - 1) for i in range(NS)]                                           # one profile per span row (pyturbo: i/(n-1))
Centrif.patterns = []                                                            # pyturbo defect: shared class-level list
c = Centrif(blade_position=(t_le, t_te), use_mid_wrap_angle=False, use_ray_camber=False)
c.add_hub(hubx, hubr); c.add_shroud(shrx, shrr)
for f in FS: c.add_profile(profile(f))
c.add_splitter([profile(f, splitter=True) for f in FS], splitter_start=0.5)
c.tip_clearance = 0.0
c.build(npts_span=NS, npts_chord=NC, nblades=12, nsplitters=1)
out["camber"] = dict(law="radial-fibre inducer theta_rf'(x) = TH0 (1 - x/L)^n + exducer backsweep linear in r from 0.7 r2", n=RF_N,
                     TH0_rad_per_mm=TH0, C1=C1, bezier_points=NBZ, fit=fit_err, beta_le_target=beta_le)

def blade_solid(bl):
    """faceted solid from pyturbo SS / PS grids (span x chord x 3; x, y = r sin th, z = r cos th); hub row embedded."""
    ss, ps = np.array(bl.ss_cart_pts, float), np.array(bl.ps_cart_pts, float)
    def embed(a):
        d = a[0] - a[1]; d /= np.linalg.norm(d, axis=1, keepdims=True); return a[0] + EMBED * d
    ss = np.concatenate([embed(ss)[None], ss]); ps = np.concatenate([embed(ps)[None], ps])
    ns, nc, _ = ss.shape
    loops = [np.vstack([ss[i], ps[i][::-1][1:-1]]) for i in range(ns)]           # closed loop per span (SS and PS share LE / TE)
    sew = BRepBuilderAPI_Sewing(1e-3)
    tri = lambda a, b, d: BRepBuilderAPI_MakeFace(cl.polygon_wire([a, b, d]), True).Face()
    for i in range(ns - 1):
        A, B = loops[i], loops[i + 1]; m = len(A)
        for j in range(m):
            j2 = (j + 1) % m
            sew.Add(tri(A[j], A[j2], B[j2])); sew.Add(tri(A[j], B[j2], B[j]))
    # end caps: ladder between SS[j] and PS[j] (LE / TE points shared). A fan from the loop centroid overlaps itself on a
    # thin cambered section: BRepCheck still passes, but every boolean returned empty (found building the FE sector)
    for i, flip in ((0, True), (ns - 1, False)):
        for j in range(nc - 1):
            quad = [(ss[i, j], ss[i, j + 1], ps[i, j + 1])] if j == 0 else [(ss[i, j], ss[i, j + 1], ps[i, j + 1]), (ss[i, j], ps[i, j + 1], ps[i, j])]
            if j == nc - 2: quad = [(ss[i, j], ss[i, j + 1], ps[i, j])]
            for a, b, d in quad:
                sew.Add(tri(a, d, b) if flip else tri(a, b, d))
    sew.Perform()
    ms = BRepBuilderAPI_MakeSolid(); ms.Add(TopoDS.Shell_s(sew.SewedShape())); so = ms.Solid()
    from OCP.BRepLib import BRepLib
    BRepLib.OrientClosedSolid_s(so)                                                # outward normals
    s = cq.Solid(so)
    if s.Volume() < 0: s = cq.Solid(so.Reversed())
    return s, ss, ps

def blade_solid_smooth(bl):
    """smooth solid: one B-spline surface through the SS grid and one through the PS grid (with the embedded hub row), the
    shared LE / TE lines as their V-boundaries, filled caps at the embedded root and at the tip, sewn. The faceted solid
    (blade_solid) meshed into 15 % sliver tets (gmsh had to honour ~3000 facet edges per blade) -> spurious 1e6 MPa peaks."""
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
    from OCP.GeomAbs import GeomAbs_Shape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeFilling
    from OCP.BRepLib import BRepLib
    ss, ps = np.array(bl.ss_cart_pts, float), np.array(bl.ps_cart_pts, float)
    def embed(a):
        d = a[0] - a[1]; d /= np.linalg.norm(d, axis=1, keepdims=True); return a[0] + EMBED * d
    ss = np.concatenate([embed(ss)[None], ss]); ps = np.concatenate([embed(ps)[None], ps])
    ns, nc, _ = ss.shape
    def surf(g):
        A = TColgp_Array2OfPnt(1, ns, 1, nc)
        for i in range(ns):
            for j in range(nc): A.SetValue(i + 1, j + 1, gp_Pnt(*map(float, g[i, j])))
        return GeomAPI_PointsToBSplineSurface(A, 3, 8, GeomAbs_Shape.GeomAbs_C2, 1e-3).Surface()
    S_ss, S_ps = surf(ss), surf(ps)
    faces = [BRepBuilderAPI_MakeFace(S, 1e-6).Face() for S in (S_ss, S_ps)]
    def iso_edge(S, first):
        u1, u2, v1, v2 = S.Bounds(); return BRepBuilderAPI_MakeEdge(S.UIso(u1 if first else u2)).Edge()
    for first in (True, False):                                                  # caps: embedded root row and tip row
        fl = BRepOffsetAPI_MakeFilling()
        fl.Add(iso_edge(S_ss, first), GeomAbs_Shape.GeomAbs_C0); fl.Add(iso_edge(S_ps, first), GeomAbs_Shape.GeomAbs_C0)
        fl.Build(); faces.append(fl.Shape())
    sew = BRepBuilderAPI_Sewing(2e-2)
    for f in faces: sew.Add(f)
    sew.Perform()
    ms = BRepBuilderAPI_MakeSolid(); ms.Add(TopoDS.Shell_s(sew.SewedShape())); so = ms.Solid()
    BRepLib.OrientClosedSolid_s(so); s = cq.Solid(so)
    if s.Volume() < 0: s = cq.Solid(so.Reversed())
    return s, ss, ps

def grids(bl):
    ss, ps = np.array(bl.ss_cart_pts, float), np.array(bl.ps_cart_pts, float)
    return np.concatenate([ss[:1], ss]), np.concatenate([ps[:1], ps])            # row 0 duplicated: same indexing as blade_solid

def throat(ss_m, ps_m):
    """inducer throat: per span, the smallest distance between the LE region of the next main blade (rotated 30 deg) and
    this blade's front half (either way round), integrated over the LE span; 12 main-blade passages (splitters start later)."""
    R = np.array([[1, 0, 0], [0, math.cos(math.radians(30)), math.sin(math.radians(30))], [0, -math.sin(math.radians(30)), math.cos(math.radians(30))]])
    rot = lambda p: p @ R.T
    o = []
    for i in range(1, NS + 1):
        nb = np.vstack([rot(ss_m[i]), rot(ps_m[i])]); front = np.vstack([ss_m[i, : NC // 2], ps_m[i, : NC // 2]])
        le = np.vstack([ss_m[i, :8], ps_m[i, :8]])
        d = min(np.min(np.linalg.norm(front - q, axis=1)) for q in rot(le))
        d2 = min(np.min(np.linalg.norm(nb - q, axis=1)) for q in le)
        o.append(min(d, d2))
    sl = [np.linalg.norm(ss_m[i + 1, 0] - ss_m[i, 0]) for i in range(1, NS)]
    o = np.array(o); A_th = 12 * float(np.sum(0.5 * (o[1:] + o[:-1]) * np.array(sl)))
    A_eye = math.pi * (r1s ** 2 - r1h ** 2)
    return dict(throat_widths_mm=o.tolist(), A_throat_mm2=A_th, A_eye_mm2=A_eye, ratio=A_th / A_eye,
                tool_level_ratio=E["impeller"]["throat_area_ratio_design"]["value"], choke_flow_over_design=choke_ratio(A_th * 1e-6))

def choke_ratio(A_th):
    """TurboFlow's impeller throat criterion (choking_criterion.evaluate_throat, 'evaluate_throat'): isentropic, relative
    flow through A_throat normal to w, rothalpy = h01 (axial inflow), throat at the arithmetic-mean eye radius. Choked mass
    flow / design flow at the fielded dash point (100 % speed). Reproduces Phase 3R's tool-level result by hand: ATR 0.70 ->
    1.086 (choked at +10 %), 0.75 -> 1.164."""
    cyc = json.load(open(os.path.join(ROOT, "data", "phase3r", "cct_ce75000_opr4_t1150_b15_cap.json")))["levels"]["fielded"]["eval"]["cycle"]
    g, R, cp_ = 1.4, 287.05, cyc["c_in_Cp"]; m, T01, P01 = cyc["W_kgps"], cyc["Tt2_K"], cyc["Pt2_kPa"] * 1e3
    u = om * 0.5 * (r1s + r1h) / MM; T0r = T01 + u * u / (2 * cp_); P0r = P01 * (T0r / T01) ** (g / (g - 1))
    return A_th * P0r / math.sqrt(T0r) * math.sqrt(g / R) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1))) / m

if THROAT_ONLY:
    t = throat(*grids(c.mainblade))
    print(json.dumps(dict(n=RF_N, fit_max_dbeta=max(e["max_dbeta_deg"] for e in fit_err.values()), throat_ratio=t["ratio"], A_throat=t["A_throat_mm2"], choke=t["choke_flow_over_design"])), flush=True); sys.exit(0)

BS = blade_solid if os.environ.get("IMP_FACETED") == "1" else blade_solid_smooth
main, ss_m, ps_m = BS(c.mainblade); split, ss_s, ps_s = BS(c.splitterblade)
# pyturbo's c.splitterblade sits at the MAIN blade's theta: the half-pitch offset (+15 deg in theta) is applied only in
# __create_fullwheel__. theta = atan2(y, z), so +15 deg in theta is -15 deg about +x in CadQuery's sense.
split = split.rotate((0, 0, 0), (1, 0, 0), -15.0)
out["blade_solids"] = dict(main_valid=cl.valid(main), main_volume_mm3=main.Volume(), splitter_valid=cl.valid(split), splitter_volume_mm3=split.Volume(),
                           main_splitter_overlap_mm3=main.intersect(split).Volume())
print("blades:", out["blade_solids"], flush=True)

# ---- hub body (stress-model geometry, boreless) ----
rr = np.linspace(r2, 0, 40)
back = [(L + t_rim + A_boss * ((r2 - r) / r2) ** p_boss, r) for r in rr]
prof = [(0.0, 0.0), (0.0, r1h)] + [(float(x), float(r)) for x, r in hub[1:]] + [(L + t_rim, r2)] + [(float(x), float(r)) for x, r in back[1:]]
hub_body = cl.revolve(prof)
# ---- 30 deg sector (FE model and building block of the wheel), bounded THROUGH THE PASSAGES ----
# Flat cut planes (first attempt) cross the blades (each wraps > 50 deg): they left blade slivers joined only through the
# cyclic faces, and the FE stiffness became near-singular (AMG stalled at 3 % residual). The sector is bounded instead by
# the surfaces psi = psi_main(x) + d, psi_main(x) = 90 deg - theta_rf(x) (the main blade's radial-fibre line; psi =
# atan2(z, y) = 90 deg - pyturbo theta), d = -22.5 and +7.5 deg: the backsweep adds <= 2.7 deg and the half-thickness
# <= 1 deg, so the main blade (d ~ 0..-3.7) and the splitter (d ~ -14..-18.7) sit wholly inside and nothing is cut. The
# boundary is ruled by radial lines (theta_rf depends on x only); built as a ruled loft of triangles at NB stations, the
# slave side is the master side rotated by exactly 30 deg.
NB = 120; xb_ = np.linspace(-20.0, L + t_rim + A_boss + 20.0, NB)
psi_main = 90.0 - np.degrees(TH0 * L / (RF_N + 1) * (1 - np.clip(1 - xb_ / L, 0, 1) ** (RF_N + 1)))
D0, D1, RW = -22.5, 7.5, 250.0
def twisted_wedge():
    ws = []
    for x_, p_ in zip(xb_, psi_main):
        a0, a1 = math.radians(p_ + D0), math.radians(p_ + D1)
        ws.append(cl.polygon_wire([(x_, 0, 0), (x_, RW * math.cos(a0), RW * math.sin(a0)), (x_, RW * math.cos(a1), RW * math.sin(a1))]))
    return cl.loft(ws, ruled=True)
wedge = twisted_wedge()
body = hub_body.fuse(main).fuse(split)
inside = dict(main=main.intersect(wedge).Volume() / main.Volume(), splitter=split.intersect(wedge).Volume() / split.Volume())
sector = body.intersect(wedge).clean()
hub_sec = hub_body.intersect(wedge)
V_expect = hub_sec.Volume() + main.Volume() + split.Volume() - main.intersect(hub_body).Volume() - split.intersect(hub_body).Volume()
out["sector"] = dict(valid=cl.valid(sector), wedge_valid=cl.valid(wedge), n_solids=len(sector.Solids()), volume_mm3=sector.Volume(), volume_expected_mm3=V_expect,
                     closure=sector.Volume() / V_expect - 1, hub_sector_x12_over_hub=12 * hub_sec.Volume() / hub_body.Volume(), blades_inside_fraction=inside,
                     boundary=dict(x_mm=xb_.tolist(), psi_master_deg=(psi_main + D0).tolist(), note="slave = master + 30 deg; psi = atan2(z, y)"))
# closure tolerance 1e-4: OCCT's volume integration on B-spline faces is good to ~1e-5 relative (a lost part would be
# >= 4 %: the smallest blade piece is 840 mm3 of 20 350)
assert abs(out["sector"]["closure"]) < 1e-4 and out["sector"]["n_solids"] == 1 and min(inside.values()) > 1 - 1e-6, \
    {k: v for k, v in out["sector"].items() if k != "boundary"}
cq.exporters.export(cq.Workplane().add(sector), os.path.join(ROOT, "cad", "engine", "impeller_sector.step"))
json.dump(out["sector"]["boundary"], open(os.path.join(ROOT, "data", "phase6", "impeller_sector_boundary.json"), "w"))
# ---- full wheel = 12 copies of the sector (touching at the cut surfaces): exact union mass properties, no double counting ----
wheel = cq.Compound.makeCompound([sector.rotate((0, 0, 0), (1, 0, 0), 30.0 * k) for k in range(12)])
Vw = wheel.Volume()
out["wheel"] = dict(valid_parts=cl.valid(sector), volume_mm3=Vw, mass_kg=Vw * 1e-9 * RHO_TI, hub_mass_kg=hub_body.Volume() * 1e-9 * RHO_TI,
                    blades_mass_kg=(Vw - hub_body.Volume()) * 1e-9 * RHO_TI, note="12 sectors; blade mass = the part outside the hub body")
I = cq.Shape.matrixOfInertia(wheel); cm = cq.Shape.centerOfMass(wheel)            # unit density about the centre of mass, mm^5
out["wheel"].update(Ip_kgm2=I[0][0] * RHO_TI * 1e-15, Id_cg_kgm2=0.5 * (I[1][1] + I[2][2]) * RHO_TI * 1e-15, x_cg_mm=cm.x,
                    cg_radial_offset_mm=math.hypot(cm.y, cm.z))
cq.exporters.export(cq.Workplane().add(wheel), os.path.join(ROOT, "cad", "engine", "impeller.step"))
print("wheel:", out["wheel"], flush=True)

# ---- checks: angles, thickness, throat ----
def cyl(p): x, y, z = p[..., 0], p[..., 1], p[..., 2]; return x, np.hypot(y, z), np.arctan2(y, z)
def camber_angles(ss, ps, i, fr=(0.03, 0.1, 0.3, 0.5, 0.7, 0.9, 0.97)):
    """blade (camber = SS / PS mid-points) metal angle from the CAD grid vs the target law at the same (x, r)."""
    x, r, th = cyl(0.5 * (ss[i] + ps[i])); th = np.unwrap(th)
    dm = np.hypot(np.diff(x), np.diff(r)); rm, xm = 0.5 * (r[1:] + r[:-1]), 0.5 * (x[1:] + x[:-1])
    b = np.degrees(np.arctan(rm * np.diff(th) / dm))
    bt = np.degrees(np.arctan(rm * np.diff(theta_c(x, r)) / dm))
    j = [int(q * (len(b) - 1)) for q in fr]
    return dict(chord_frac=list(fr), cad_deg=[float(b[k]) for k in j], target_deg=[float(bt[k]) for k in j], max_abs_dev_deg=float(np.abs(b - bt)[1:-1].max()),
                TE_deg=float(b[-1]), TE_target_deg=float(bt[-1]))
spans = {"hub (first grid row)": 1, "mid": 1 + (NS - 1) // 2, "shroud": NS}
out["angles"] = {k: camber_angles(ss_m, ps_m, i) for k, i in spans.items()}
def grid_volume(ss, ps):
    """blade volume from the grids alone (mid-surface cell area x mean SS-PS distance) -- checks the sewn solids."""
    cm = 0.5 * (ss + ps); tk = np.linalg.norm(ss - ps, axis=2); V = 0.0
    for i in range(ss.shape[0] - 1):
        for j in range(ss.shape[1] - 1):
            a, b, c_, d = cm[i, j], cm[i, j + 1], cm[i + 1, j + 1], cm[i + 1, j]
            A = 0.5 * np.linalg.norm(np.cross(c_ - a, d - b)); V += A * tk[i:i + 2, j:j + 2].mean()
    return float(V)
out["blade_solids"].update(main_grid_volume_mm3=grid_volume(ss_m, ps_m), splitter_grid_volume_mm3=grid_volume(ss_s, ps_s))
def thickness(ss, ps, i, frac):
    j = int(frac * (ss.shape[1] - 1)); return float(np.min(np.linalg.norm(ps[i] - ss[i, j], axis=1)))
out["thickness_mm"] = {f"hub row at {q:.0%} chord": thickness(ss_m, ps_m, 1, q) for q in (0.3, 0.6, 0.85)}
out["thickness_mm"].update({f"tip at {q:.0%} chord": thickness(ss_m, ps_m, NS, q) for q in (0.3, 0.6, 0.85)})
out["throat"] = throat(ss_m, ps_m)
json.dump(out, open(os.path.join(ROOT, "data", "phase6", "impeller_cad_checks.json"), "w"), indent=1, default=float)
print(json.dumps({k: out[k] for k in ("wheel", "angles", "thickness_mm", "throat", "sector")}, indent=1, default=lambda x: round(float(x), 4)))
