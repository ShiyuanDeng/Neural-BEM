"""Post-outcome geometry diagnostic; no truth or forward solves are used."""
import json
import numpy as np

from qualify import HERE, LENGTH, ProjectedUpdate, scene, load_scene, write


def main():
    update = ProjectedUpdate(LENGTH)
    endpoint = json.loads((HERE / "runs/sep0.14_clean/joint/result.json").read_text())["final_state"]
    states = {"initial": scene(.14, initial=True), "joint_endpoint": load_scene(endpoint)}
    rows = []
    for label, current in states.items():
        for name, curve in zip(current.ids, current.components):
            nodes = curve.nodes(1024)
            weights = np.sqrt(nodes.arc_length_weights / nodes.perimeter)
            z = curve.values(1024)
            centre = curve.coefficients[curve.band]
            radius = nodes.perimeter / (2 * np.pi)
            rotation = 1j * (z - centre) / radius
            rigid = np.column_stack((nodes.normals,
                np.real(rotation * np.conj(nodes.normals @ np.array([1, 1j])))))
            for modes in (3, 5, 9):
                local = update.prepare(curve, modes, curve.band)
                basis = update.velocities(local, nodes) * LENGTH
                a, b = basis * weights[:, None], rigid * weights[:, None]
                coefficients = np.linalg.lstsq(a, b, rcond=1e-10)[0]
                errors = np.linalg.norm(a @ coefficients - b, axis=0) / np.linalg.norm(b, axis=0)
                rows.append(dict(state=label, component=name, modes=modes,
                                 relative_rigid_normal_span_error=errors))
    write(HERE / "rigid_span_exploratory.json", dict(
        status="geometry-only post-outcome diagnostic; not a strategy intervention",
        directions=["x translation", "y translation", "rotation about parameter mean"], rows=rows))


if __name__ == "__main__":
    main()
