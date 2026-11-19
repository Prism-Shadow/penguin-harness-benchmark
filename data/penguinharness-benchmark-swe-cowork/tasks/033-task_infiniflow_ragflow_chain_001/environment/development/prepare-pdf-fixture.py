"""Deterministic, actual PDF input for the frozen public parser integration."""
from pathlib import Path
import argparse
import hashlib

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
content = (b'BT /F1 18 Tf 60 735 Td (A simple English document) Tj ET\n'
           b'BT /F1 12 Tf 60 690 Td (This page contains searchable source text.) Tj ET\n'
           b'BT /F1 12 Tf 60 665 Td (Rivers flow through valleys and forests.) Tj ET\n'
           b'BT /F1 12 Tf 60 640 Td (A second paragraph preserves its own words.) Tj ET\n')
objects = [
    b'<< /Type /Catalog /Pages 2 0 R >>',
    b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
    b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'endstream',
]
data = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
offsets = [0]
for number, obj in enumerate(objects, 1):
    offsets.append(len(data))
    data.extend(str(number).encode() + b' 0 obj\n' + obj + b'\nendobj\n')
xref = len(data)
data.extend(b'xref\n0 6\n0000000000 65535 f \n')
for offset in offsets[1:]:
    data.extend(f'{offset:010d} 00000 n \n'.encode())
data.extend(b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n')
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(data)
print('Generated real public PDF fixture:', len(data), hashlib.sha256(data).hexdigest())
