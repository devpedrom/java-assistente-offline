"""Recover separated UML boxes and arrowed connectors from grayscale pages."""

from pathlib import Path
import re


class IncompleteLayoutError(ValueError):
    pass


def _pgm(path):
    if path.stat().st_size > 16_065_536:
        raise ValueError("Imagem fora do limite de processamento.")
    raw = path.read_bytes()
    tokens = []
    offset = 0
    while len(tokens) < 4:
        while offset < len(raw) and raw[offset] in b" \r\n\t":
            offset += 1
        if raw[offset:offset+1] == b"#":
            offset = raw.index(b"\n", offset) + 1
            continue
        match = re.match(rb"\S+", raw[offset:])
        if not match:
            raise ValueError("Imagem PGM incompleta.")
        tokens.append(match.group())
        offset += match.end()
    if tokens[0] != b"P5" or tokens[3] != b"255":
        raise ValueError("Imagem PGM não suportada.")
    width, height = int(tokens[1]), int(tokens[2])
    if not 0 < width * height <= 16_000_000:
        raise ValueError("Imagem fora do limite de processamento.")
    offset += 2 if raw[offset:offset+2] == b"\r\n" else 1
    pixels = raw[offset:]
    if len(pixels) != width * height:
        raise ValueError("Pixels PGM incompletos.")
    return width, height, pixels


def _boxes(width, height, ink):
    groups = []
    pattern = re.compile(b"\x01{" + str(max(35, width // 25)).encode() + b",}")
    for y in range(height):
        for run in pattern.finditer(ink[y*width:(y+1)*width]):
            left, right = run.start(), run.end() - 1
            group = next((g for g in groups if abs(g[0]-left) <= 3 and abs(g[1]-right) <= 3), None)
            if group is None:
                if len(groups) >= 200:
                    raise ValueError("Layout fora do limite de linhas reconhecíveis.")
                groups.append([left, right, [y]])
            else:
                group[2].append(y)
    boxes = []
    for left, right, rows in groups:
        bands = []
        for y in rows:
            if not bands or y - bands[-1][-1] > 4:
                bands.append([y])
            else:
                bands[-1].append(y)
        chain = []
        for band in bands:
            if chain:
                top, bottom = chain[-1][-1], band[0]
                continuous = all(
                    sum(any(ink[y*width+x] for x in range(max(0, edge-2), min(width, edge+3)))
                        for y in range(top, bottom+1)) >= .9 * (bottom-top+1)
                    for edge in (left, right)
                )
                if not continuous:
                    if len(chain) >= 3:
                        boxes.append((left, chain[0][0], right, chain[-1][-1]))
                    chain = []
            chain.append(band)
        if len(chain) >= 3:
            boxes.append((left, chain[0][0], right, chain[-1][-1]))
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def _connections(width, height, ink, boxes):
    if len(boxes) < 2:
        return []
    remaining = bytearray(ink)
    for left, top, right, bottom in boxes:
        for y in range(max(0, top-2), min(height, bottom+3)):
            start, end = y*width+max(0, left-2), y*width+min(width, right+3)
            remaining[start:end] = bytes(end-start)
    links = []
    for start in range(len(remaining)):
        if not remaining[start]:
            continue
        remaining[start] = 0
        stack, points = [start], []
        while stack:
            index = stack.pop()
            y, x = divmod(index, width)
            points.append((x, y))
            if len(points) > 100000 or len(stack) > 100000:
                raise ValueError("Conectores fora do limite de processamento; confirme o diagrama.")
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        neighbor = ny*width+nx
                        if remaining[neighbor]:
                            remaining[neighbor] = 0
                            stack.append(neighbor)
        if len(points) < 20:
            continue
        parents = [i for i, (l, t, r, b) in enumerate(boxes)
                   if any(l <= x <= r and b < y <= b+7 for x, y in points)]
        children = [i for i, (l, t, r, b) in enumerate(boxes)
                    if any(l <= x <= r and t-7 <= y < t for x, y in points)]
        if len(parents) != 1 or not children:
            continue
        parent = parents[0]
        bottom = boxes[parent][3]
        near = [(x, y) for x, y in points if bottom < y < bottom+22]
        spans = [(y, max(xs)-min(xs)+1) for y in sorted({y for x, y in near})
                 for xs in [[x for x, yy in near if yy == y]]]
        head = []
        for y, span in spans:
            if 4 <= span <= 35:
                if head and y > head[-1][0] + 2:
                    break
                head.append((y, span))
            elif head:
                break
        widths = [span for _, span in head]
        if widths:
            peak = widths.index(max(widths))
            tail = len(widths) - peak - 1
            widths = widths[:peak+1] if tail <= 2 else []
        arrow = (len(widths) >= 4 and max(widths) >= 7 and max(widths)-min(widths) >= 4
                 and sum(b > a for a, b in zip(widths, widths[1:])) >= 2
                 and all(b >= a-1 for a, b in zip(widths, widths[1:])))
        links.extend((parent, child, arrow) for child in children if child != parent)
    return links


def extract_diagram(path: Path, recognize) -> str:
    width, height, pixels = _pgm(path)
    ink = pixels.translate(bytes(1 if value < 160 else 0 for value in range(256)))
    boxes = _boxes(width, height, ink)
    if len(boxes) > 30:
        raise ValueError("Diagrama excede o limite de trinta caixas por página.")
    lines, names = [], {}
    for index, (left, top, right, bottom) in enumerate(boxes):
        crop_width, crop_height = right-left-5, bottom-top-5
        if crop_width <= 0 or crop_height <= 0:
            continue
        rows = []
        for y in range(top+3, bottom-2):
            row = bytearray(pixels[y*width+left+3:y*width+right-2])
            if any(len(run.group()) > crop_width * .8 for run in re.finditer(b"\x01+", ink[y*width+left+3:y*width+right-2])):
                row[:] = bytes([255]) * crop_width
            rows.append(row)
        crop = path.with_name(f"{path.stem}-classe-{index}.pgm")
        crop.write_bytes(f"P5\n{crop_width} {crop_height}\n255\n".encode() + b"".join(rows))
        text = recognize(crop)
        content = [line.strip() for line in text.splitlines() if line.strip()]
        if not content or not re.fullmatch(r"[A-Za-z_$À-ÿ][\w$À-ÿ]*", content[0]):
            continue
        names[index] = content[0]
        lines.append("CLASSE: " + content[0])
        for line in content[1:]:
            # shortcut: OCR commonly confuses UML # with *, confirm flagged OCR contracts.
            line = re.sub(r"^\*\s*(?=\w+\s*[:(])", "# ", line)
            lines.append(line)
    if len(names) != len(boxes):
        raise IncompleteLayoutError(
            f"OCR de caixas incompleto: {len(names)} de {len(boxes)} classes reconhecidas; forneça o diagrama em texto para confirmar."
        )
    for parent, child, arrow in _connections(width, height, ink, boxes):
        if parent in names and child in names:
            lines.append(f"{names[parent]} {'<|--' if arrow else '--'} {names[child]}")
    return "\n".join(lines)
