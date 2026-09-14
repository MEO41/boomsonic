"""Run-time fix for a TurboFlow 0.1.18 defect (import BEFORE running any centrifugal-compressor case; .venv-np1).

Defect (found Phase 3R, 2026-09-14): turboflow/centrifugal_compressor/slip_model.py, get_slip_weisner:
    return u_out*np.sqrt(np.cos(theta_out))/(z**0.7)
theta_out (geometry 'trailing_edge_angle') is in DEGREES everywhere else in the model (flow_model.py uses
math.tand(theta_out) in the slip-velocity residual; the upstream example gives -24.5), but np.cos takes radians.
Wiesner (1967): sigma = 1 - sqrt(cos beta2b) / Z^0.7 with beta2b the blade angle from meridional.
Effect of the bug on the slip velocity term sqrt(cos): -24.5 deg 0.898 vs 0.955 (-6 %, why the upstream example
looked fine); -30 deg 0.393 vs 0.931 (-58 %); -10 / -40 deg: cos < 0 -> NaN.
Evidence: verify_turboflow_slip.py.
"""
import numpy as np
from turboflow.centrifugal_compressor import slip_model as _sm

def _get_slip_wiesner_deg(input, geometry):
    return input["u_out"] * np.sqrt(np.cos(np.radians(geometry["trailing_edge_angle"]))) / (geometry["number_of_blades"] ** 0.7)

_STOCK = _sm.get_slip_weisner

def apply():
    _sm.get_slip_weisner = _get_slip_wiesner_deg      # evaluate_slip looks the name up at call time

def revert():
    _sm.get_slip_weisner = _STOCK

apply()
