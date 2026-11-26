"""Scene export for the MATLAB cross-check: PLY round trip to STL and receiver sampling."""

import struct

import numpy as np

from bns.geospatial.osm_scene import write_ply
from bns.validation.matlab_case import merge, read_ply, sample_cells, write_stl


def test_ply_is_read_back_exactly_and_written_as_stl(tmp_path):
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    f = np.array([[0, 1, 2], [0, 1, 3]])
    write_ply(tmp_path / "m.ply", v, f)
    rv, rf = read_ply(tmp_path / "m.ply")
    assert np.allclose(rv, v) and rf.tolist() == f.tolist()
    write_stl(tmp_path / "m.stl", *merge([(rv, rf), (rv + 10, rf)]))
    data = (tmp_path / "m.stl").read_bytes()
    count = struct.unpack("<I", data[80:84])[0]
    assert count == 4 and len(data) == 84 + 50 * 4
    normal = struct.unpack("<3f", data[84:96])
    assert np.allclose(normal, [0, 0, 1])                       # first face lies in z = 0, counter-clockwise


def test_cell_sampling_is_reproducible_and_balanced():
    mask = np.ones((10, 10), dtype=bool)
    classes = np.zeros((10, 10), dtype=int)
    classes[:3] = 1
    a = sample_cells(mask, classes, 5, seed=1)
    assert a == sample_cells(mask, classes, 5, seed=1)
    assert sum(classes[c] == 1 for c in a) == 5 and len(a) == 10
