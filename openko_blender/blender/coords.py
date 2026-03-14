"""
Coordinate-system conversion: DirectX (left-handed, Y-up) → Blender (right-handed, Z-up).

KnightOnline uses DirectX 9 with a left-handed Y-up coordinate system.
Blender uses a right-handed Z-up coordinate system.

The conversion matrix is composed from two basis-change matrices, exactly
matching the prototype's map_mtx computation:

    map_mtx = Matrix((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1))
            @ Matrix((-1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1))

For a full 4×4 matrix the correct conversion requires a conjugation
(similarity transform) so that rotation/scale axes also change:

    bl_mtx = MAP_MTX @ dx_mtx @ MAP_MTX_INV

For bone head positions only the position component is converted:

    bl_pos = MAP_MTX @ Vector(dx_pos).to_4d()

joint_local_matrix() replicates CN3Joint::ReCalcMatrix() using mathutils so
the resulting matrix can be composed with MAP_MTX for armature and animation work.
"""

from __future__ import annotations

import mathutils

from ..formats.n3joint import Joint

# ---------------------------------------------------------------------------
# Global conversion matrices (computed once at import time)
# ---------------------------------------------------------------------------

MAP_MTX: mathutils.Matrix = (
    mathutils.Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    @ mathutils.Matrix(((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
)
MAP_MTX_INV: mathutils.Matrix = MAP_MTX.inverted()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def dx_to_blender(dx_mtx: mathutils.Matrix) -> mathutils.Matrix:
    """Convert a full 4×4 DX-space matrix to Blender space via similarity transform.

    Simply multiplying MAP_MTX @ dx_mtx only converts positions; the rotation
    and scale components would remain in DX axes, producing wrong orientations.
    The conjugation MAP_MTX @ dx_mtx @ MAP_MTX_INV converts everything correctly.
    """
    return MAP_MTX @ dx_mtx @ MAP_MTX_INV


def joint_local_matrix(joint: Joint, frame: float) -> mathutils.Matrix:
    """Compute a Joint's local 4×4 transform matrix at *frame* using mathutils.

    Replicates CN3Joint::ReCalcMatrix() exactly, following the same algorithm
    as the prototype's calc_joint_matrix():

      1. Resolve animated pos/rot/scale/orient (fall back to bind-pose defaults).
      2. rot_final = m_qRot * m_qOrient  (if orient keys exist, else m_qRot only).
      3. Matrix = rot_final.to_matrix().to_4x4()
      4. If scale != (1,1,1): Matrix = scale_mtx @ Matrix   (right-multiply C++ style)
      5. Set translation column (C++ PosSet sets row 3 in row-major → column 3 here).

    Requires mathutils — only callable inside Blender.
    """
    pos = joint.key_pos.get_value(frame, joint.pos)
    rot = joint.key_rot.get_value(frame, joint.rot)
    scale = joint.key_scale.get_value(frame, joint.scale)

    if joint.key_orient.count > 0:
        orient = joint.key_orient.get_value(frame, joint.orient)
    else:
        orient = joint.orient

    # Convert KO structs → mathutils (Blender quaternion convention: w, x, y, z)
    m_vPos = mathutils.Vector([pos.x, pos.y, pos.z])
    m_qRot = mathutils.Quaternion([rot.w, rot.x, rot.y, rot.z])
    m_vScale = mathutils.Vector([scale.x, scale.y, scale.z])
    m_qOrient = mathutils.Quaternion([orient.w, orient.x, orient.y, orient.z])

    # Step 1 & 2: Determine final rotation quaternion
    if joint.key_orient.count > 0:
        rot_quat = m_qRot @ m_qOrient   # C++: m_qRot * m_qOrient
    else:
        rot_quat = m_qRot

    # Step 3: Build rotation matrix
    mtx = rot_quat.to_matrix().to_4x4()

    # Step 4: Apply scale (C++: m_Matrix *= ScaleMatrix)
    if m_vScale.x != 1.0 or m_vScale.y != 1.0 or m_vScale.z != 1.0:
        scale_mtx = mathutils.Matrix.Diagonal((*m_vScale, 1.0))
        mtx = scale_mtx @ mtx

    # Step 5: Set translation (column 3 in Blender column-major)
    mtx[0][3] = m_vPos.x
    mtx[1][3] = m_vPos.y
    mtx[2][3] = m_vPos.z

    return mtx