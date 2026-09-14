"""Phase 6 CAD helpers shared by engine_cad.py, impeller_cad.py and airframe_cad.py (run in .venv-cad).
Coordinates: x = axis (engine: from the impeller nose rearward; airframe: from the nose rearward); units mm."""
import math, numpy as np
import cadquery as cq
from OCP.TColgp import TColgp_Array1OfPnt, TColgp_HArray1OfPnt
from OCP.gp import gp_Pnt
from OCP.GeomAPI import GeomAPI_PointsToBSpline, GeomAPI_Interpolate
from OCP.GeomAbs import GeomAbs_Shape
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.ShapeFix import ShapeFix_Shape

def revolve(pts):
    """closed profile [(x, r), ...] in mm revolved 360 deg about the x axis."""
    return cq.Workplane("XY").polyline([(float(a), float(b)) for a, b in pts]).close().revolve(360, (0, 0, 0), (1, 0, 0)).val()

def spline_wire(pts, closed=True):
    p = list(pts) + ([pts[0]] if closed else [])
    arr = TColgp_Array1OfPnt(1, len(p))
    for i, q in enumerate(p): arr.SetValue(i + 1, gp_Pnt(*map(float, q)))
    c = GeomAPI_PointsToBSpline(arr, 3, 8, GeomAbs_Shape.GeomAbs_C2, 1e-4).Curve()
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(c).Edge()).Wire()

def periodic_wire(pts):
    """closed, smooth (periodic interpolating) B-spline wire through the points (no duplicate end point)."""
    arr = TColgp_HArray1OfPnt(1, len(pts))
    for i, q in enumerate(pts): arr.SetValue(i + 1, gp_Pnt(*map(float, q)))
    it = GeomAPI_Interpolate(arr, True, 1e-6); it.Perform()
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(it.Curve()).Edge()).Wire()

def polygon_wire(pts):
    """closed polygonal wire through the points (faceted). Used for blade sections: a periodic spline through a sharp
    trailing-edge cusp overshoots into a self-intersecting loop (found in Phase 6: the volume of a straight prism of the
    section came out 19 % off), a polygon cannot."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    mp = BRepBuilderAPI_MakePolygon()
    for q in pts: mp.Add(gp_Pnt(*map(float, q)))
    mp.Close(); return mp.Wire()

def loft(wires, ruled=False):
    t = BRepOffsetAPI_ThruSections(True, ruled, 1e-4)
    for w in wires: t.AddWire(w)
    t.CheckCompatibility(True); t.Build()
    return cq.Solid(t.Shape())

def valid(shape):
    return bool(BRepCheck_Analyzer(shape.wrapped).IsValid())

def fix(shape):
    sf = ShapeFix_Shape(shape.wrapped); sf.Perform(); return type(shape)(sf.Shape()) if hasattr(shape, "wrapped") else sf.Shape()

def pattern(solid, n):
    return cq.Compound.makeCompound([solid.rotate((0, 0, 0), (1, 0, 0), 360.0 * i / n) for i in range(n)])

def section2d(chord, b_in, b_out, tmax, n=36):
    """blade section in the (axial, tangential) plane: camber with the angle from axial linear along the chord, NACA
    4-digit thickness form (closed trailing edge) scaled to tmax. Open point list LE -> upper -> TE -> lower (no duplicate)."""
    s = np.linspace(0, 1, 400); b = np.radians(b_in + (b_out - b_in) * s)
    xc = np.concatenate([[0], np.cumsum(np.cos(b[:-1]) * np.diff(s))]); yc = np.concatenate([[0], np.cumsum(np.sin(b[:-1]) * np.diff(s))])
    sc = chord / math.hypot(xc[-1], yc[-1]); xc, yc = xc * sc, yc * sc
    u = 0.5 * (1 - np.cos(np.linspace(0, math.pi, n)))
    xs, ys, bs = np.interp(u, s, xc), np.interp(u, s, yc), np.interp(u, s, b)
    th = 5 * tmax * (0.2969 * np.sqrt(u) - 0.1260 * u - 0.3516 * u ** 2 + 0.2843 * u ** 3 - 0.1036 * u ** 4)
    nx, ny = -np.sin(bs), np.cos(bs)
    up = np.c_[xs + th * nx, ys + th * ny]; lo = np.c_[xs - th * nx, ys - th * ny]
    return np.vstack([up, lo[::-1][1:-1]])

def blade_row(x_le, r_hub, r_tip, chord, b_in, b_out, tmax, n, embed=0.6, nsec=3, embed_tip=None):
    """blade lofted through PLANAR sections (planes parallel to the axis at height r, i.e. tangent to the cylinder at the
    blade's mean line) from r_hub - embed to r_tip + embed. Planar end sections give proper cap faces (sections wrapped on
    cylinders gave non-planar end wires and invalid solids). Curvature error ~ r (1 - cos(half the angular extent)),
    < 0.4 mm here; conceptual."""
    wires = []
    for r in np.linspace(r_hub - embed, r_tip + (embed if embed_tip is None else embed_tip), nsec):
        p2 = section2d(chord, b_in, b_out, tmax); p2[:, 0] -= p2[:, 0].min(); p2[:, 1] -= p2[:, 1].mean()
        wires.append(polygon_wire(np.c_[x_le + p2[:, 0], p2[:, 1], np.full(len(p2), r)]))
    blade = loft(wires, ruled=True)
    return pattern(blade, n), blade
