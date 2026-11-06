from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import tracemalloc

from java_assistant.pdf import layout


def diagram(path, arrow=True):
    width, height = 1000, 650
    pixels = bytearray([255]) * (width * height)
    def line(x1, y1, x2, y2):
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                pixels[y * width + x] = 0
    for left, top, right, bottom in ((350, 50, 650, 250), (50, 350, 350, 550), (650, 350, 950, 550)):
        line(left, top, right, top + 1)
        line(left, bottom - 1, right, bottom)
        line(left, top, left + 1, bottom)
        line(right - 1, top, right, bottom)
        line(left, top + 50, right, top + 51)
        line(left, top + 120, right, top + 121)
    line(499, 251, 501, 310)
    line(200, 309, 800, 311)
    line(199, 310, 201, 350)
    line(799, 310, 801, 350)
    if arrow:
        for y in range(253, 269):
            half = (y - 253) // 2
            line(500 - half, y, 500 + half, y)
        line(500, 269, 507, 269)
    else:
        line(490, 260, 510, 261)
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode() + pixels)


class LayoutTests(unittest.TestCase):
    def test_no_boxes_skips_pixel_component_allocation(self):
        ink = bytes([1]) * 65536
        tracemalloc.start()
        try:
            self.assertEqual([], layout._connections(256, 256, ink, []))
            self.assertLess(tracemalloc.get_traced_memory()[1], 300000)
        finally:
            tracemalloc.stop()

    def test_large_connected_component_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "limite"):
            layout._connections(512, 512, bytes([1])*262144, [(0, 0, 20, 20), (490, 490, 511, 511)])

    def test_separates_side_by_side_boxes_and_follows_generalization_connector(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / "page.pgm"
            diagram(image)
            replies = iter(("Raiz\n* valor: Double\n+ Raiz(Double)\n+ total(): Double",
                            "FolhaA\n- extra: int\n+ total(): Double",
                            "FolhaB\n+ total(): Double"))
            text = layout.extract_diagram(image, lambda crop: next(replies))
            self.assertIn("CLASSE: Raiz", text)
            self.assertIn("# valor: Double", text)
            self.assertIn("CLASSE: FolhaA", text)
            self.assertIn("Raiz <|-- FolhaA", text)
            self.assertIn("Raiz <|-- FolhaB", text)

    def test_connector_without_arrow_is_not_asserted_as_inheritance(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / "page.pgm"
            diagram(image, arrow=False)
            replies = iter(("Raiz\n+ total(): Double", "FolhaA\n+ total(): Double", "FolhaB\n+ total(): Double"))
            text = layout.extract_diagram(image, lambda crop: next(replies))
            self.assertNotIn("<|--", text)
            self.assertIn("Raiz -- FolhaA", text)
