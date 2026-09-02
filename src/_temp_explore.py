"""Temporary exploration of primitives in 2017_67-103.dxf"""
import ezdxf
from pathlib import Path

DXF = Path(__file__).resolve().parent.parent / "data" / "dxf" / "2017_67-103.dxf"
doc = ezdxf.readfile(str(DXF))
msp = doc.modelspace()

print("=== RLE-VIGA LWPOLYLINE ===")
lwp = list(msp.query('LWPOLYLINE[layer=="RLE-VIGA"]'))
print(f"  Total: {len(lwp)}")
for i, e in enumerate(lwp[:5]):
    pts = list(e.get_points(format='xy'))
    print(f"  {i}: closed={e.closed} npts={len(pts)} pts={[(round(x,1),round(y,1)) for x,y in pts[:6]]}")
print()

print("=== RLE-VIGA LINE ===")
vl = list(msp.query('LINE[layer=="RLE-VIGA"]'))
print(f"  Total: {len(vl)}")
for i, e in enumerate(vl[:10]):
    s, end = e.dxf.start, e.dxf.end
    ln = ((end.x-s.x)**2+(end.y-s.y)**2)**0.5
    print(f"  {i}: ({s.x:.1f},{s.y:.1f})->({end.x:.1f},{end.y:.1f}) len={ln:.1f}")
print()

print("=== RLE-PILAR ARC ===")
arcs = list(msp.query('ARC[layer=="RLE-PILAR"]'))
print(f"  Total: {len(arcs)}")
for i, e in enumerate(arcs[:10]):
    c = e.dxf.center
    print(f"  {i}: center=({c.x:.1f},{c.y:.1f}) r={e.dxf.radius:.1f} a={e.dxf.start_angle:.0f}-{e.dxf.end_angle:.0f}")
print()

print("=== RLE-PILAR LINE ===")
pl = list(msp.query('LINE[layer=="RLE-PILAR"]'))
print(f"  Total: {len(pl)}")
for i, e in enumerate(pl[:15]):
    s, end = e.dxf.start, e.dxf.end
    ln = ((end.x-s.x)**2+(end.y-s.y)**2)**0.5
    print(f"  {i}: ({s.x:.1f},{s.y:.1f})->({end.x:.1f},{end.y:.1f}) len={ln:.1f}")
print()

print("=== RLE-MURO ALL ===")
ml = list(msp.query('LINE[layer=="RLE-MURO"]'))
print(f"  Total: {len(ml)}")
for i, e in enumerate(ml):
    s, end = e.dxf.start, e.dxf.end
    ln = ((end.x-s.x)**2+(end.y-s.y)**2)**0.5
    print(f"  {i}: ({s.x:.1f},{s.y:.1f})->({end.x:.1f},{end.y:.1f}) len={ln:.1f}")
print()

print("=== RLE-EJES ALL ===")
el = list(msp.query('LINE[layer=="RLE-EJES"]'))
print(f"  Total: {len(el)}")
for i, e in enumerate(el):
    s, end = e.dxf.start, e.dxf.end
    ln = ((end.x-s.x)**2+(end.y-s.y)**2)**0.5
    dx, dy = abs(end.x-s.x), abs(end.y-s.y)
    orient = "V" if dx < dy else "H"
    print(f"  {i}: ({s.x:.1f},{s.y:.1f})->({end.x:.1f},{end.y:.1f}) len={ln:.1f} {orient}")
print()

print("=== RLE-EJE MTEXT ALL ===")
mt = list(msp.query('MTEXT[layer=="RLE-EJE"]'))
print(f"  Total: {len(mt)}")
for i, e in enumerate(mt):
    txt = e.plain_text().strip()
    ins = e.dxf.insert
    h = e.dxf.char_height
    print(f'  {i}: "{txt}" at ({ins.x:.1f},{ins.y:.1f}) h={h:.1f}')
