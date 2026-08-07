"""Generate test DXF fixture files for qcad-mcp tests."""

import os

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def make_simple_floorplan():
    """A 10x8m floor plan with 4 rooms, 1 door, 1 window."""
    import ezdxf

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Outer walls
    walls = [
        ((0, 0), (10000, 0)),
        ((10000, 0), (10000, 8000)),
        ((10000, 8000), (0, 8000)),
        ((0, 8000), (0, 0)),
        # Inner walls
        ((5000, 0), (5000, 4000)),
        ((5000, 4000), (10000, 4000)),
        ((0, 4000), (5000, 4000)),
    ]
    for (x1, y1), (x2, y2) in walls:
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "Walls"})

    # Door block
    doc.blocks.new("DOOR")
    msp.add_blockref("DOOR", (5000, 0), dxfattribs={"layer": "Doors"})

    # Window block
    doc.blocks.new("WINDOW")
    msp.add_blockref("WINDOW", (2000, 8000), dxfattribs={"layer": "Windows"})

    # Furniture
    msp.add_lwpolyline(
        [(100, 100), (2000, 100), (2000, 500), (100, 500), (100, 100)], dxfattribs={"layer": "Furniture"}
    )

    doc.layers.add("Walls", color=7)
    doc.layers.add("Doors", color=3)
    doc.layers.add("Windows", color=4)
    doc.layers.add("Furniture", color=6)

    path = os.path.join(FIXTURE_DIR, "simple_floorplan.dxf")
    doc.saveas(path)
    return path


def make_office_layout():
    """A 20x15m open office layout with cubicles."""
    import ezdxf

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Outer shell
    msp.add_lwpolyline([(0, 0), (20000, 0), (20000, 15000), (0, 15000), (0, 0)], dxfattribs={"layer": "Walls"})
    # Interior partitions
    for x in range(4000, 20000, 4000):
        msp.add_line((x, 0), (x, 12000), dxfattribs={"layer": "Partitions"})
    for y in range(3000, 12000, 3000):
        msp.add_line((0, y), (20000, y), dxfattribs={"layer": "Partitions"})
    # Reception desk
    msp.add_circle((18000, 13500), 1500, dxfattribs={"layer": "Furniture"})
    # Plants
    for pos in [(1000, 14000), (19000, 1000), (500, 500)]:
        msp.add_circle(pos, 300, dxfattribs={"layer": "Plants"})

    doc.layers.add("Walls", color=7)
    doc.layers.add("Partitions", color=5)
    doc.layers.add("Furniture", color=6)
    doc.layers.add("Plants", color=3)

    path = os.path.join(FIXTURE_DIR, "office_layout.dxf")
    doc.saveas(path)
    return path


def make_mechanical_part():
    """Simple mechanical bracket."""
    import ezdxf

    doc = ezdxf.new("R2000")
    msp = doc.modelspace()

    msp.add_lwpolyline(
        [(0, 0), (100, 0), (100, 50), (80, 50), (80, 20), (20, 20), (20, 50), (0, 50), (0, 0)],
        dxfattribs={"layer": "Profile"},
    )
    msp.add_circle((50, 25), 8, dxfattribs={"layer": "Holes"})
    msp.add_circle((50, 25), 4, dxfattribs={"layer": "Holes"})
    msp.add_text("MCP-001", height=5, dxfattribs={"layer": "Labels", "insert": (10, 55)})

    doc.layers.add("Profile", color=7)
    doc.layers.add("Holes", color=1)
    doc.layers.add("Labels", color=2)

    path = os.path.join(FIXTURE_DIR, "mechanical_bracket.dxf")
    doc.saveas(path)
    return path


def make_annotation_only():
    """DXF with text and dimensions only (no geometry)."""
    import ezdxf

    doc = ezdxf.new("R2000")
    msp = doc.modelspace()
    msp.add_text("TEST PLAN - NOT FOR CONSTRUCTION", height=50, dxfattribs={"layer": "Text", "insert": (1000, 5000)})
    msp.add_text("Scale: 1:100", height=25, dxfattribs={"layer": "Text", "insert": (1000, 4800)})
    msp.add_text("Date: 2026-05-12", height=25, dxfattribs={"layer": "Text", "insert": (1000, 4600)})
    doc.layers.add("Text", color=7)
    path = os.path.join(FIXTURE_DIR, "annotation_only.dxf")
    doc.saveas(path)
    return path


if __name__ == "__main__":
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    print(f"Fixture dir: {FIXTURE_DIR}")
    for fn in os.listdir(FIXTURE_DIR):
        os.remove(os.path.join(FIXTURE_DIR, fn))
    for maker in [make_simple_floorplan, make_office_layout, make_mechanical_part, make_annotation_only]:
        p = maker()
        sz = os.path.getsize(p)
        print(f"  {os.path.basename(p):40s} {sz:>8,} bytes")
    print(f"\n{len(os.listdir(FIXTURE_DIR))} fixture files created.")
