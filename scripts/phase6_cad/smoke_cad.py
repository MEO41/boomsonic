"""Phase 6 tool verification (run in .venv-cad): does the proposed CAD toolchain do what it claims?

Only primitives with analytic answers are built here; no engine geometry (the brief: toolchain confirmed with the user
before any geometry is generated).
  1. CadQuery 2.8 / OCCT 7.9: box volume exact; STEP export + re-import keeps the volume; STL export.
  2. Point cloud -> B-spline surface (the route pyturbo-aero's blade point clouds need): points sampled on a cylinder
     patch (r 50 mm, 60 deg, 20 mm high) -> GeomAPI_PointsToBSplineSurface -> face area vs r * theta * h.
  3. Loft of closed spline sections -> solid (the route for blades built section by section): circles r 5 mm at
     z = 0 and 10 mm sampled as points -> closed B-spline wires -> ThruSections -> volume vs pi r^2 h.
  4. gmsh 4.15: tetra mesh of the STEP box -> summed element volume vs 6000 mm3.
  5. pyturbo-aero 1.3.8 imports in this environment (Centrif API present).
Usage: .venv-cad/Scripts/python scripts/phase6_cad/smoke_cad.py
"""
import os, math, tempfile, numpy as np
import cadquery as cq
from OCP.TColgp import TColgp_Array2OfPnt, TColgp_Array1OfPnt
from OCP.gp import gp_Pnt
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface, GeomAPI_PointsToBSpline
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
TMP = tempfile.mkdtemp(prefix="cad_smoke_")
res = {}

# 1. box, STEP round trip, STL
box = cq.Workplane("XY").box(10, 20, 30)
v0 = box.val().Volume(); step = os.path.join(TMP, "box.step"); stl = os.path.join(TMP, "box.stl")
cq.exporters.export(box, step); cq.exporters.export(box, stl)
v1 = cq.importers.importStep(step).val().Volume()
res["box"] = (v0, v1, os.path.getsize(stl))
print(f"1. box volume {v0:.6f} (exact 6000), after STEP round trip {v1:.6f}; STL {os.path.getsize(stl)} bytes")

# 2. cylinder patch from points
r, th, h = 50.0, math.radians(60), 20.0
nu, nv = 25, 9; arr = TColgp_Array2OfPnt(1, nu, 1, nv)
for i in range(nu):
    for j in range(nv):
        t = th * i / (nu - 1); z = h * j / (nv - 1)
        arr.SetValue(i + 1, j + 1, gp_Pnt(r * math.cos(t), r * math.sin(t), z))
from OCP.GeomAbs import GeomAbs_Shape
surf = GeomAPI_PointsToBSplineSurface(arr, 3, 8, GeomAbs_Shape.GeomAbs_C2, 1e-6).Surface()
face = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
gp = GProp_GProps(); BRepGProp.SurfaceProperties_s(face, gp); A = gp.Mass(); A0 = r * th * h
res["patch"] = (A, A0)
print(f"2. B-spline surface through {nu}x{nv} points on a cylinder patch: area {A:.4f} vs analytic {A0:.4f} ({100*(A/A0-1):+.4f} %)")

# 3. loft of closed spline sections
def closed_section(z, rr=5.0, n=40):
    pts = TColgp_Array1OfPnt(1, n + 1)
    for k in range(n + 1):
        a = 2 * math.pi * k / n; pts.SetValue(k + 1, gp_Pnt(rr * math.cos(a), rr * math.sin(a), z))
    c = GeomAPI_PointsToBSpline(pts, 3, 8, GeomAbs_Shape.GeomAbs_C2, 1e-6).Curve()
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(c).Edge()).Wire()
loft = BRepOffsetAPI_ThruSections(True, False, 1e-6)
for z in (0.0, 5.0, 10.0): loft.AddWire(closed_section(z))
loft.Build(); sol = cq.Solid(loft.Shape())
V = sol.Volume(); V0 = math.pi * 25 * 10
res["loft"] = (V, V0, sol.isValid())
print(f"3. loft of 3 closed spline sections: volume {V:.4f} vs analytic {V0:.4f} ({100*(V/V0-1):+.4f} %), valid solid {sol.isValid()}")

# 4. gmsh tetra mesh of the STEP box
import gmsh
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
gmsh.option.setNumber("Mesh.MeshSizeMax", 3.0); gmsh.model.mesh.generate(3)
et, tags, nodes = gmsh.model.mesh.getElements(3)
ntet = sum(len(t) for t in tags)
ntags, coords, _ = gmsh.model.mesh.getNodes(); X = coords.reshape(-1, 3); idx = {int(t): i for i, t in enumerate(ntags)}
vol = 0.0
for typ, nd in zip(et, nodes):
    if typ != 4: continue
    q = np.array([idx[int(n)] for n in nd]).reshape(-1, 4); P = X[q]
    vol += np.abs(np.einsum("ij,ij->i", P[:, 1] - P[:, 0], np.cross(P[:, 2] - P[:, 0], P[:, 3] - P[:, 0]))).sum() / 6
gmsh.finalize()
res["gmsh"] = (ntet, vol)
print(f"4. gmsh tetra mesh of the STEP box: {ntet} tets, summed volume {vol:.6f} (exact 6000)")

# 5. pyturbo
from pyturbo.aero.centrif import Centrif, CentrifProfile, TrailingEdgeProperties
print("5. pyturbo-aero imports in .venv-cad: Centrif.build / add_splitter / tip_clearance present:",
      all(hasattr(Centrif, a) for a in ("build", "add_splitter", "tip_clearance", "add_hub", "add_shroud")))
ok = abs(v0 - 6000) < 1e-6 and abs(v1 - 6000) < 1e-3 and abs(A / A0 - 1) < 1e-3 and abs(V / V0 - 1) < 5e-3 and res["loft"][2] and abs(vol - 6000) < 1e-3
print("ALL CHECKS PASS" if ok else "SOME CHECK FAILED", "| temp files in", TMP)
