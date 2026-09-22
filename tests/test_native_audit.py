"""Optional NumPy tests; ParaView supplies NumPy on the extraction worker."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from guanlan.worker.audit import native_scalar, compare_scalar_values

STATE=Path(__file__).resolve().parents[1]/'state'/'tests'
STATE.mkdir(parents=True,exist_ok=True)


@unittest.skipUnless(importlib.util.find_spec('numpy'),'NumPy is supplied by the optional ParaView worker')
class NativeAuditTests(unittest.TestCase):
    def test_histogram_is_not_ordering(self):
        import numpy as np
        native = np.array([1.123456789, 2.0, 3.0], dtype=np.float64)
        actual = native.astype(np.float32)
        result = compare_scalar_values(actual, native)
        self.assertTrue(result['native_cast_reader_ordered_equal'])
        self.assertFalse(result['native_reader_multiset_equal'])
        result = compare_scalar_values(actual[::-1], native)
        self.assertTrue(result['native_cast_reader_multiset_equal'])
        self.assertFalse(result['native_cast_reader_ordered_equal'])
        with self.assertRaisesRegex(ValueError, 'multiset'):
            compare_scalar_values(actual + 1, native)

    def test_ascii_and_legacy_binary(self):
        with tempfile.TemporaryDirectory(dir=STATE) as temp:
            path=Path(temp)/'p'
            path.write_bytes(b'FoamFile { format ascii; }\ninternalField nonuniform List<scalar>\n2\n(1 2);')
            self.assertEqual(list(native_scalar(path)),[1,2])
            path.write_bytes(b'FoamFile { format binary; }\ninternalField nonuniform List<scalar>\n2\n('
                             +struct.pack('<dd',1,2)+b');')
            with self.assertRaisesRegex(ValueError,'profile'):native_scalar(path)
            self.assertEqual(list(native_scalar(path,True)),[1,2])
            path.write_bytes(path.read_bytes().replace(b'\n2\n(',b'\n3\n('))
            with self.assertRaisesRegex(ValueError,'count'):native_scalar(path,True)

    def test_uniform_uses_mesh_count(self):
        with tempfile.TemporaryDirectory(dir=STATE) as temp:
            root=Path(temp);field=root/'1'/'T';field.parent.mkdir()
            owner=root/'constant'/'polyMesh'/'owner';owner.parent.mkdir(parents=True)
            owner.write_bytes(b'note "nPoints:4 nCells:2 nFaces:5";')
            field.write_bytes(b'internalField uniform 300;')
            self.assertEqual(list(native_scalar(field)),[300,300])


if __name__=='__main__':unittest.main()
