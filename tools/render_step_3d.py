#!/usr/bin/env python3
"""
render_step_3d.py
=================
Render an Altium **STEP** export of a PCB to a shaded isometric PNG — without
Altium and without a GUI.

The STEP file is tessellated with Open CASCADE (via the ``gmsh`` Python
package), written to a binary STL, and then drawn with a small Lambert-shaded
matplotlib 3D surface.  An optional crop removes the empty margins.

Dependencies (not part of the standard library)
-----------------------------------------------
    pip install gmsh numpy matplotlib

Usage
-----
    python3 tools/render_step_3d.py board.step images/pcb-3d.png
    python3 tools/render_step_3d.py board.step out.png --elev 40 --azim -52

Notes
-----
* The mesh size controls detail vs. render time; 1.2 mm max worked well for a
  ~57 x 41 mm board with fine-pitch parts.
* The colours shade the board (low Z) green and taller parts lighter, which
  reads like a quick mechanical render rather than a photorealistic one.
"""

from __future__ import annotations

import argparse
import struct
import sys


def step_to_stl(step_path: str, stl_path: str,
                mesh_max: float, mesh_min: float) -> None:
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_max)
    gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_min)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.option.setNumber("Mesh.Binary", 1)
    gmsh.model.occ.importShapes(step_path)
    gmsh.model.occ.synchronize()
    gmsh.model.mesh.generate(2)
    gmsh.write(stl_path)
    gmsh.finalize()


def load_stl(path: str):
    import numpy as np

    with open(path, "rb") as fh:
        fh.read(80)
        n = struct.unpack("<I", fh.read(4))[0]
        raw = np.frombuffer(fh.read(n * 50), dtype=np.uint8).reshape(n, 50)
    return raw[:, 12:48].copy().view("<f4").reshape(n, 3, 3).astype(np.float64)


def render(stl_path: str, out_png: str, elev: float = 40, azim: float = -52,
           size: tuple[int, int] = (16, 10), dpi: int = 200) -> None:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    tris = load_stl(stl_path)
    mn, mx = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    span = mx - mn

    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(nrm, axis=1)
    length[length == 0] = 1
    nrm /= length[:, None]
    nrm[nrm[:, 2] < 0] *= -1
    light = np.array([-0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    inten = 0.30 + 0.70 * np.clip(nrm @ light, 0, 1)

    zc = (tris[:, :, 2].mean(1) - mn[2]) / span[2]
    base = np.stack([0.13 + 0.55 * zc, 0.42 + 0.35 * zc, 0.20 + 0.60 * zc], 1)
    colors = np.clip(base * inten[:, None], 0, 1)

    fig = plt.figure(figsize=size, dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(Poly3DCollection(tris, facecolors=colors,
                                         edgecolors="none", shade=False))
    ax.set_xlim(mn[0], mx[0]); ax.set_ylim(mn[1], mx[1]); ax.set_zlim(mn[2], mx[2])
    ax.set_box_aspect(tuple(span))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    try:
        ax.set_proj_type("ortho")
    except Exception:
        pass
    plt.subplots_adjust(left=-0.05, right=1.05, bottom=-0.05, top=1.05)
    tmp = out_png + ".raw.png"
    plt.savefig(tmp, facecolor="white")
    plt.close(fig)

    img = plt.imread(tmp)[..., :3]
    mask = (img < 0.97).any(2)
    ys, xs = np.where(mask)
    pad = 18
    crop = img[max(0, ys.min() - pad):ys.max() + pad,
               max(0, xs.min() - pad):xs.max() + pad]
    b = 14
    framed = np.ones((crop.shape[0] + 2 * b, crop.shape[1] + 2 * b, 3))
    framed[b:-b, b:-b] = crop
    plt.imsave(out_png, framed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step")
    ap.add_argument("output")
    ap.add_argument("--mesh-max", type=float, default=1.2)
    ap.add_argument("--mesh-min", type=float, default=0.25)
    ap.add_argument("--elev", type=float, default=40)
    ap.add_argument("--azim", type=float, default=-52)
    args = ap.parse_args(argv)

    stl = args.output + ".stl"
    step_to_stl(args.step, stl, args.mesh_max, args.mesh_min)
    render(stl, args.output, args.elev, args.azim)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
