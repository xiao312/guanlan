"""Equivalent VTP datasets for Glance. No CFD read and no new approximation."""
import base64
import struct
from xml.etree import ElementTree as ET
from guanlan.portable.assets import original_edges


def binary_array(parent, name, dtype, raw, components=1):
    node = ET.SubElement(parent, 'DataArray', type=dtype, Name=name,
                         NumberOfComponents=str(components), format='binary')
    # Float64 payloads need an 8-byte aligned start for vtk.js XML readers.
    node.text = base64.b64encode(struct.pack('<Q', len(raw)) + raw).decode('ascii')


def vtp_bytes(dataset, edges=False):
    topology = base64.b64decode(dataset['polys'])
    if edges:
        topology = original_edges(topology)
    cells = [v[0] for v in struct.iter_unpack('<I', topology)]
    indices, offsets = [], []
    cursor = 0
    while cursor < len(cells):
        count = cells[cursor]
        indices.extend(cells[cursor+1:cursor+count+1])
        offsets.append(len(indices))
        cursor += count+1
    root = ET.Element('VTKFile', type='PolyData', version='0.1', byte_order='LittleEndian', header_type='UInt64')
    piece = ET.SubElement(ET.SubElement(root, 'PolyData'), 'Piece', NumberOfPoints=str(dataset['point_count']),
                          NumberOfVerts='0', NumberOfLines=str(len(offsets) if edges else 0), NumberOfStrips='0',
                          NumberOfPolys=str(0 if edges else len(offsets)))
    cell_data = ET.SubElement(piece, 'CellData')
    if not edges:
        for name, field in dataset['fields'].items():
            binary_array(cell_data, name, 'Float64', base64.b64decode(field['values']))
    ET.SubElement(piece, 'PointData')
    binary_array(ET.SubElement(piece, 'Points'), 'Points', 'Float32', base64.b64decode(dataset['points']), 3)
    topology_node = ET.SubElement(piece, 'Lines' if edges else 'Polys')
    binary_array(topology_node, 'connectivity', 'UInt32', struct.pack('<' + 'I'*len(indices), *indices))
    binary_array(topology_node, 'offsets', 'UInt32', struct.pack('<' + 'I'*len(offsets), *offsets))
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)
