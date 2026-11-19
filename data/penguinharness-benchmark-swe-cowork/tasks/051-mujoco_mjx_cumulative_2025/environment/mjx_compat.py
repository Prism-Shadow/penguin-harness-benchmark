"""Compatibility for the 2025 MJX Python snapshots and frozen MuJoCo 3.3.1 runtime.

Only aliases for native names removed or renamed between the source snapshot
and the pinned wheel are installed.  No solver-facing behavior is implemented
here; all behavior remains in the archived MJX production modules.
"""
import mujoco

if not hasattr(mujoco.MjModel, "light_directional") and hasattr(mujoco.MjModel, "light_type"):
    mujoco.MjModel.light_directional = property(
        lambda model: model.light_type == mujoco.mjtLightType.mjLIGHT_DIRECTIONAL
    )

if not hasattr(mujoco.mjtDisableBit, "mjDSBL_PASSIVE") and hasattr(mujoco.mjtDisableBit, "mjDSBL_SPRING"):
    mujoco.mjtDisableBit.mjDSBL_PASSIVE = mujoco.mjtDisableBit.mjDSBL_SPRING

_sparse_aliases = {
    "C_rownnz": "M_rownnz",
    "C_rowadr": "M_rowadr",
    "C_colind": "M_colind",
    "mapM2C": "mapM2M",
}
for _name, _source in _sparse_aliases.items():
    if not hasattr(mujoco.MjData, _name) and hasattr(mujoco.MjData, _source):
        setattr(mujoco.MjData, _name, property(lambda data, source=_source: getattr(data, source)))
