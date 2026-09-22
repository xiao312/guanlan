"""Metadata-only readiness screen; a successful ParaView read is still required."""
import math
import re
import time
from pathlib import Path


def partition_paths(case):
    paths = sorted((p for p in Path(case).iterdir() if p.is_dir() and re.fullmatch(r"processor\d+", p.name)),
                   key=lambda p: int(p.name[9:]))
    if not paths or [p.name for p in paths] != ["processor" + str(i) for i in range(len(paths))]:
        raise ValueError("expected contiguous uncollated processor directories starting with processor0")
    return paths


def latest_candidate(case, fields, settle_seconds=10, time_name=None):
    partitions = partition_paths(case)
    times = None
    for partition in partitions:
        available = {}
        for path in partition.iterdir():
            try:
                value = float(path.name)
            except ValueError:
                continue
            if math.isfinite(value) and value > 0 and path.is_dir():
                available[path.name] = value
        times = available if times is None else {k: v for k, v in times.items() if k in available}
    for name in sorted(times or {}, key=times.get, reverse=True):
        if time_name is not None and name != time_name:
            continue
        signature = []
        try:
            for partition in partitions:
                for mesh_name in ('points', 'faces', 'owner', 'neighbour', 'boundary'):
                    mesh = partition / 'constant' / 'polyMesh' / mesh_name
                    if not mesh.is_file():
                        mesh = mesh.with_suffix('.gz')
                    # Dynamic meshes need a separate qualified reader policy.
                    if (partition / name / 'polyMesh').exists():
                        raise ValueError('time-varying mesh is not qualified by this static-mesh reader')
                    if mesh.exists():
                        mesh_stat = mesh.stat()
                        signature.append((str(mesh), mesh_stat.st_size, mesh_stat.st_mtime_ns))
                for field in fields:
                    path = partition / name / field
                    if not path.is_file():
                        path = path.with_suffix(".gz")
                    stat = path.stat()
                    if stat.st_size == 0 or time.time() - stat.st_mtime < settle_seconds:
                        raise OSError("output still being written")
                    signature.append((str(path), stat.st_size, stat.st_mtime_ns))
            return name, signature
        except OSError:
            continue
    raise ValueError("waiting for a settled timestep with all requested fields on every partition")


def unchanged(signature):
    for name, size, stamp in signature:
        stat = Path(name).stat()
        if (stat.st_size, stat.st_mtime_ns) != (size, stamp):
            return False
    return True


def field_units(case, time_name, fields):
    import gzip
    known = {"0 1 -1 0 0 0 0": "m/s", "1 -1 -2 0 0 0 0": "Pa",
             "0 2 -2 0 0 0 0": "m²/s²", "0 0 0 1 0 0 0": "K", "0 0 0 0 0 0 0": "1"}
    result = {}
    for field in fields:
        path = Path(case) / "processor0" / time_name / field
        opener = open
        if not path.exists():
            path = path.with_suffix(".gz")
            opener = gzip.open
        with opener(path, "rb") as stream:
            header = stream.read(4096).decode("ascii", errors="ignore")
        match = re.search(r"dimensions\s*\[([^]]+)\]", header)
        dimensions = " ".join(match.group(1).split()) if match else "unknown"
        result[field] = {"units": known.get(dimensions, "dimensions [" + dimensions + "]"),
                         "dimensions": dimensions, "association": "cell"}
    return result
