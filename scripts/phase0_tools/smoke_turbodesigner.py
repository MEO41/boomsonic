"""Phase 0 smoke test: turbodesigner (OpenOrion) axial-compressor meanline at micro-turbojet scale.
NOTE: turbodesigner takes isentropic efficiency as an INPUT (no loss model) - it is a
geometry/velocity-triangle generator, not a performance predictor. Axial only."""
from turbodesigner.turbomachinery import Turbomachinery
from turbodesigner.stage import StageBladeProperty
tm = Turbomachinery(gamma=1.4, axial_velocity=150.0, rpm=70000, gas_constant=287.05, mass_flow_rate=0.9,
    pressure_ratio=3.0, inlet_total_pressure=101325, inlet_total_temperature=288.15, isentropic_efficiency=0.82,
    num_stages=2, inlet_blockage=1.0, outlet_blockage=1.0, hub_to_tip_ratio=0.6, num_streams=3,
    stage_temperature_rise="equal", stage_reaction=0.5, row_gap_to_chord=0.25, stage_gap_to_chord=0.25,
    aspect_ratio=StageBladeProperty(rotor=1.5, stator=1.5), spacing_to_chord=StageBladeProperty(rotor=0.8, stator=0.8),
    max_thickness_to_chord=StageBladeProperty(rotor=0.08, stator=0.08))
print(f"inlet mean radius = {tm.inlet_mean_radius*1000:.1f} mm, tip radius = {tm.inlet_tip_radius*1000:.1f} mm, "
      f"inlet Mach = {tm.inlet_mach_number:.3f}, stages = {len(tm.stages)}")
for i, s in enumerate(tm.stages):
    print(f"stage {i}: PR={s.pressure_ratio:.3f} psi(loading)={s.loading_coefficient:.3f} phi(flow)={s.flow_coefficient:.3f}")
print("TURBODESIGNER SMOKE TEST: PASS")
