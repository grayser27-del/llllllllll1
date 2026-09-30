#!/usr/bin/env python3
"""Build the Russian logical ER diagram PDF from native ImageMagick drawing commands."""
from __future__ import annotations

import struct
import subprocess
import tempfile
import textwrap
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "ER-диаграмма.pdf"
W, H = 2400, 1697
SCALE = 2.5
PIX_W, PIX_H = round(W * SCALE), round(H * SCALE)
MM_TO_PT = 72 / 25.4
PAGE_W_PT, PAGE_H_PT = 594 * MM_TO_PT, 420 * MM_TO_PT  # A2 landscape
FONT = "DejaVu-Sans"
FONT_BOLD = "DejaVu-Sans-Bold"

INK = "#203047"
MUTED = "#607086"
PAPER = "#F3F6FA"
BORDER = "#C7D2DF"
ROW_A = "#FFFFFF"
ROW_B = "#F7F9FC"
FOOT = "#EFF4F8"
COLORS = {
    "master": "#167783",
    "catalog": "#287E8C",
    "price": "#625DA8",
    "spec": "#5364A9",
    "sales": "#C4772F",
    "production": "#2F826D",
    "counterparty": "#9B6482",
    "unit": "#AE8429",
    "nomenclature": "#3B8292",
}
BADGE_COLORS = {
    "PK": "#155E75",
    "FK": "#287052",
    "PK,FK": "#5B4BA5",
    "UQ": "#A86B13",
    "CHECK": "#64748B",
}


def n(value: float) -> str:
    return str(round(value * SCALE, 2))


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def text_cmd(x: float, y: float, text: str, size: float = 18,
             color: str = INK, bold: bool = False) -> str:
    font = FONT_BOLD if bold else FONT
    return (
        f'font "{font}" font-size {n(size)} fill "{color}" stroke none '
        f'text {n(x)},{n(y)} "{esc(text)}"'
    )


def line_cmd(x1: float, y1: float, x2: float, y2: float,
             color: str, width: float = 2.4) -> str:
    return (f'fill none stroke "{color}" stroke-width {n(width)} '
            f'stroke-linecap round stroke-linejoin round line '
            f'{n(x1)},{n(y1)} {n(x2)},{n(y2)}')


def path_cmd(points: list[tuple[float, float]], color: str,
             width: float = 2.4, arrow: bool = True) -> list[str]:
    cmds = [line_cmd(*a, *b, color, width) for a, b in zip(points, points[1:])]
    if arrow and len(points) >= 2:
        x0, y0 = points[-2]
        x1, y1 = points[-1]
        length, half = 15, 8
        if abs(x1 - x0) >= abs(y1 - y0):
            direction = 1 if x1 > x0 else -1
            bx = x1 - direction * length
            pts = [(x1, y1), (bx, y1 - half), (bx, y1 + half)]
        else:
            direction = 1 if y1 > y0 else -1
            by = y1 - direction * length
            pts = [(x1, y1), (x1 - half, by), (x1 + half, by)]
        flat = " ".join(f"{n(x)},{n(y)}" for x, y in pts)
        cmds.append(f'fill "{color}" stroke none polygon {flat}')
    return cmds


def table_card(x: int, y: int, w: int, title: str, group: str,
               rows: list[tuple[str, str]], footer: str = "") -> list[str]:
    header_h, row_h, footer_h = 54, 31, (30 if footer else 0)
    h = header_h + len(rows) * row_h + footer_h
    c = COLORS[group]
    x2, y2 = x + w, y + h
    cmds = [
        f'fill "#DCE4EC" stroke none roundrectangle {n(x+5)},{n(y+7)} {n(x2+5)},{n(y2+7)} 16,16',
        f'fill "#FFFFFF" stroke none roundrectangle {n(x)},{n(y)} {n(x2)},{n(y2)} 16,16',
        f'fill "{c}" stroke none roundrectangle {n(x)},{n(y)} {n(x2)},{n(y+header_h)} 16,16',
        f'fill "{c}" stroke none rectangle {n(x)},{n(y+18)} {n(x2)},{n(y+header_h)}',
        text_cmd(x + 20, y + 35, title, 23, "#FFFFFF", True),
    ]
    for i, (tag, label) in enumerate(rows):
        row_y = y + header_h + i * row_h
        fill = ROW_A if i % 2 == 0 else ROW_B
        cmds.append(f'fill "{fill}" stroke none rectangle {n(x+2)},{n(row_y)} {n(x2-2)},{n(row_y+row_h)}')
        cmds.append(line_cmd(x + 2, row_y + row_h, x2 - 2, row_y + row_h, "#E4EAF0", 0.8))
        if tag:
            badge_c = BADGE_COLORS.get(tag, "#64748B")
            badge_w = 70 if tag not in ("PK,FK", "CHECK") else 78
            bx, by = x + 13, row_y + 5
            cmds.append(f'fill "{badge_c}" stroke none roundrectangle {n(bx)},{n(by)} {n(bx+badge_w)},{n(by+22)} 8,8')
            cmds.append(text_cmd(bx + 8, by + 16, tag, 13.5, "#FFFFFF", True))
        label_size = 17.5
        if len(label) > 46:
            label_size = 14.5
        elif len(label) > 34:
            label_size = 15.5
        cmds.append(text_cmd(x + 103, row_y + 21, label, label_size, INK, False))
    if footer:
        fy = y + header_h + len(rows) * row_h
        cmds.append(f'fill "{FOOT}" stroke none rectangle {n(x+2)},{n(fy)} {n(x2-2)},{n(y2-2)}')
        cmds.append(text_cmd(x + 15, fy + 20, footer, 14.5, MUTED, False))
    cmds.extend([
        f'fill none stroke "{BORDER}" stroke-width {n(1.6)} roundrectangle {n(x)},{n(y)} {n(x2)},{n(y2)} 16,16',
        line_cmd(x, y + header_h, x2, y + header_h, "#FFFFFF", 0.8),
    ])
    return cmds


def note_card(x: int, y: int, w: int, h: int, title: str,
              lines: list[str], accent: str, font_size: float = 17.5,
              line_height: float = 31) -> list[str]:
    cmds = [
        f'fill "#DCE4EC" stroke none roundrectangle {n(x+5)},{n(y+6)} {n(x+w+5)},{n(y+h+6)} 16,16',
        f'fill "#FFFFFF" stroke none roundrectangle {n(x)},{n(y)} {n(x+w)},{n(y+h)} 16,16',
        f'fill "{accent}" stroke none roundrectangle {n(x)},{n(y)} {n(x+w)},{n(y+52)} 16,16',
        f'fill "{accent}" stroke none rectangle {n(x)},{n(y+18)} {n(x+w)},{n(y+52)}',
        text_cmd(x + 20, y + 34, title, 20, "#FFFFFF", True),
    ]
    baseline = y + 87
    max_chars = max(38, int((w - 92) / (font_size * 0.54)))
    for bullet in lines:
        wrapped = textwrap.wrap(bullet, width=max_chars, break_long_words=False,
                                break_on_hyphens=False) or [""]
        for idx, line in enumerate(wrapped):
            yy = baseline
            if idx == 0:
                cmds.append(f'fill "{accent}" stroke none circle {n(x+25)},{n(yy-6)} {n(x+31)},{n(yy)}')
            cmds.append(text_cmd(x + 47, yy, line, font_size, INK, False))
            baseline += line_height
    cmds.append(f'fill none stroke "{BORDER}" stroke-width {n(1.6)} roundrectangle {n(x)},{n(y)} {n(x+w)},{n(y+h)} 16,16')
    return cmds


def relationship_card(x: int, y: int, w: int, title: str,
                      rows: list[tuple[str, str, str, str]], accent: str) -> list[str]:
    header_h, row_h = 54, 42
    h = header_h + len(rows) * row_h
    x2 = x + w
    cmds = [
        f'fill "#DCE4EC" stroke none roundrectangle {n(x+5)},{n(y+6)} {n(x2+5)},{n(y+h+6)} 16,16',
        f'fill "#FFFFFF" stroke none roundrectangle {n(x)},{n(y)} {n(x2)},{n(y+h)} 16,16',
        f'fill "{accent}" stroke none roundrectangle {n(x)},{n(y)} {n(x2)},{n(y+header_h)} 16,16',
        f'fill "{accent}" stroke none rectangle {n(x)},{n(y+18)} {n(x2)},{n(y+header_h)}',
        text_cmd(x + 20, y + 35, title, 22, "#FFFFFF", True),
    ]
    for i, (parent, cardinality, child, fk) in enumerate(rows):
        yy = y + header_h + i * row_h
        fill = ROW_A if i % 2 == 0 else ROW_B
        cmds.append(f'fill "{fill}" stroke none rectangle {n(x+2)},{n(yy)} {n(x2-2)},{n(yy+row_h)}')
        cmds.append(line_cmd(x+4, yy+row_h, x2-4, yy+row_h, "#E7ECF2", 0.7))
        cmds.append(text_cmd(x+18, yy+27, parent, 16.5, INK, False))
        cmds.append(text_cmd(x+390, yy+27, cardinality, 16.5, accent, True))
        cmds.append(text_cmd(x+500, yy+27, child, 16.5, INK, False))
        cmds.append(text_cmd(x+w-315, yy+27, f"FK: {fk}", 14.5, MUTED, False))
    cmds.append(f'fill none stroke "{BORDER}" stroke-width {n(1.6)} roundrectangle {n(x)},{n(y)} {n(x2)},{n(y+h)} 16,16')
    return cmds


def title_block(title: str, subtitle: str, page_label: str) -> list[str]:
    cmds = [
        text_cmd(50, 56, title, 39, INK, True),
        text_cmd(52, 91, subtitle, 20, MUTED, False),
        text_cmd(2110, 58, page_label, 17, MUTED, True),
    ]
    return cmds


def render_png(groups: list[str], out: Path) -> None:
    args = [
        "convert", "-limit", "memory", "220MiB", "-limit", "map", "512MiB",
        "-size", f"{PIX_W}x{PIX_H}", f"xc:{PAPER}",
        "-font", FONT,
    ]
    for group in groups:
        if group.strip():
            args.extend(["-draw", group])
    args.extend(["-depth", "8", "-type", "TrueColor", f"PNG24:{out}"])
    subprocess.run(args, check=True, cwd=ROOT)


def extract_png_rgb(path: Path) -> tuple[int, int, bytes]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("ImageMagick did not produce PNG")
    pos = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos:pos+4])[0]
        kind = raw[pos+4:pos+8]
        data = raw[pos+8:pos+8+length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filt, interlace = struct.unpack(">IIBBBBB", data)
            if (bit_depth, color_type, compression, filt, interlace) != (8, 2, 0, 0, 0):
                raise ValueError(f"Expected non-interlaced RGB8 PNG, got {bit_depth=}, {color_type=}")
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break
    if width != PIX_W or height != PIX_H:
        raise ValueError(f"Unexpected PNG dimensions: {width}x{height}")
    # A cheap integrity check also catches a truncated image before writing the PDF.
    decompressed = zlib.decompress(compressed)
    expected = height * (1 + width * 3)
    if len(decompressed) != expected:
        raise ValueError(f"Unexpected PNG raster data length {len(decompressed)} != {expected}")
    return width, height, bytes(compressed)


def utf16_hex(value: str) -> str:
    return "<FEFF" + value.encode("utf-16-be").hex().upper() + ">"


def write_pdf(pages: list[tuple[int, int, bytes]]) -> None:
    objects: list[bytes] = [b""]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R /PageLayout /SinglePage >>")
    page_ids = [3, 6]
    objects.append(f"<< /Type /Pages /Kids [{page_ids[0]} 0 R {page_ids[1]} 0 R] /Count 2 >>".encode())
    for i, (width, height, compressed) in enumerate(pages):
        page_id = page_ids[i]
        image_id = page_id + 1
        content_id = page_id + 2
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W_PT:.4f} {PAGE_H_PT:.4f}] "
                        f"/Resources << /ProcSet [/PDF /ImageC] /XObject << /Im0 {image_id} 0 R >> >> "
                        f"/Contents {content_id} 0 R >>").encode())
        image_dict = (f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
                      f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
                      f"/DecodeParms << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns {width} >> "
                      f"/Length {len(compressed)} >>\nstream\n").encode()
        objects.append(image_dict + compressed + b"\nendstream")
        content = (f"q\n{PAGE_W_PT:.4f} 0 0 {PAGE_H_PT:.4f} 0 0 cm\n/Im0 Do\nQ\n").encode()
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"endstream")
    info_id = len(objects)
    objects.append((f"<< /Title {utf16_hex('ER-диаграмма — производство и продажи')} "
                    f"/Subject {utf16_hex('Логическая ER-модель в третьей нормальной форме')} "
                    f"/Producer {utf16_hex('ER diagram generator')} >>").encode())

    pdf = bytearray(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = [0]
    for i, obj in enumerate(objects[1:], start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend((f"trailer\n<< /Size {len(objects)} /Root 1 0 R /Info {info_id} 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n").encode())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(pdf)


def page1() -> list[str]:
    connectors: list[str] = []
    def edge(points, color, arrow=True, width=2.4):
        connectors.extend(path_cmd(points, color, width, arrow))

    # Контрагентские роли и документы.
    edge([(312, 470), (312, 500)], COLORS["counterparty"])
    edge([(576, 350), (590, 350), (590, 860), (640, 860)], COLORS["counterparty"])
    edge([(168, 230), (168, 180), (2220, 180), (2220, 230)], COLORS["counterparty"])
    edge([(440, 230), (440, 198), (1900, 198), (1900, 230)], COLORS["counterparty"])
    # Подразделение обходит схему по внешнему контуру и ведёт к производственному заказу.
    edge([(48, 938), (25, 938), (25, 166), (2375, 166), (2375, 920), (2352, 920)], COLORS["production"])

    # Номенклатура, коды, единицы и цены.
    edge([(640, 380), (610, 380), (610, 1174), (576, 1174)], COLORS["nomenclature"])
    edge([(576, 700), (606, 700), (606, 360), (640, 360)], COLORS["unit"])
    edge([(576, 744), (640, 744)], COLORS["unit"])
    edge([(900, 408), (900, 440)], COLORS["nomenclature"])
    edge([(640, 390), (625, 390), (625, 960), (640, 960)], COLORS["nomenclature"])
    edge([(1168, 360), (1180, 360), (1180, 780), (1496, 780), (1496, 800)], COLORS["nomenclature"])
    edge([(1168, 390), (1200, 390), (1200, 1020), (1500, 1020), (1500, 1040)], COLORS["nomenclature"])
    edge([(1168, 390), (1215, 390), (1215, 630), (1824, 630)], COLORS["nomenclature"])

    # Спецификация → её строки и технологические операции.
    edge([(1168, 875), (1232, 875)], COLORS["spec"])
    edge([(1168, 1030), (1205, 1030), (1205, 1150), (1232, 1150)], COLORS["spec"])
    # Привязка производственной строки к выбранной версии спецификации.
    edge([(1050, 1070), (1050, 1330), (1780, 1330), (1780, 1170), (1824, 1170)], COLORS["spec"])

    # Единицы измерения: общий маршрут и ответвления к строкам документов/нормативов.
    edge([(576, 790), (600, 790), (600, 1360), (1804, 1360)], COLORS["unit"], arrow=False)
    edge([(1400, 1360), (1400, 1009)], COLORS["unit"])
    edge([(1530, 1360), (1530, 1311)], COLORS["unit"])
    edge([(1640, 1360), (1640, 1311)], COLORS["unit"])
    edge([(1804, 1360), (1804, 1279), (2180, 1279)], COLORS["unit"])
    edge([(1804, 1279), (1804, 771), (2060, 771)], COLORS["unit"])

    # Заголовки документов и строки.
    edge([(2088, 469), (2088, 500)], COLORS["sales"])
    edge([(2090, 1039), (2090, 1070)], COLORS["production"])

    cmds = [" ".join(connectors)]
    cmds.extend(title_block(
        "ER-ДИАГРАММА · ПРОИЗВОДСТВО И ПРОДАЖИ",
        "Логическая модель • третья нормальная форма • типы данных опущены • лист 1 из 2",
        "A2  |  МОДЕЛЬ ДАННЫХ",
    ))
    cmds.extend([
        f'fill "#FFFFFF" stroke "{BORDER}" stroke-width {n(1)} roundrectangle {n(48)},{n(105)} {n(2352)},{n(137)} 10,10',
        f'fill "{BADGE_COLORS["PK"]}" stroke none roundrectangle {n(62)},{n(111)} {n(120)},{n(132)} 7,7',
        text_cmd(70, 127, "PK", 12.5, "#FFFFFF", True),
        text_cmd(130, 127, "первичный ключ", 14.5, MUTED),
        f'fill "{BADGE_COLORS["FK"]}" stroke none roundrectangle {n(310)},{n(111)} {n(368)},{n(132)} 7,7',
        text_cmd(318, 127, "FK", 12.5, "#FFFFFF", True),
        text_cmd(378, 127, "внешний ключ", 14.5, MUTED),
        f'fill "{BADGE_COLORS["UQ"]}" stroke none roundrectangle {n(550)},{n(111)} {n(608)},{n(132)} 7,7',
        text_cmd(558, 127, "UQ", 12.5, "#FFFFFF", True),
        text_cmd(618, 127, "уникальность", 14.5, MUTED),
        text_cmd(830, 127, "Стрелки: 1 → N; точные FK и кратности приведены на листе 2.", 14.5, MUTED),
        text_cmd(48, 150, "СПРАВОЧНИКИ", 16.5, COLORS["master"], True),
        text_cmd(640, 150, "НОМЕНКЛАТУРА / ЦЕНЫ / СПЕЦИФИКАЦИЯ", 16.5, COLORS["catalog"], True),
        text_cmd(1232, 150, "СОСТАВ И ОПЕРАЦИИ", 16.5, COLORS["spec"], True),
        text_cmd(1824, 150, "ЗАКАЗЫ", 16.5, COLORS["sales"], True),
    ])

    # Все сущности и атрибуты.
    cards = [
        (48, 230, 528, "контрагент", "master", [
            ("PK", "контрагент_id"),
            ("UQ", "внешний_id (JSON id), допускает NULL"),
            ("UQ", "ИНН, NULL допустим"),
            ("", "наименование"), ("", "адрес"), ("", "телефон"),
        ], ""),
        (48, 500, 528, "контрагент_роль", "master", [
            ("PK,FK", "контрагент_id → контрагент"),
            ("PK", "роль (несколько значений на контрагента)"),
        ], ""),
        (48, 670, 528, "единица_измерения", "master", [
            ("PK", "единица_id"), ("UQ", "обозначение"), ("", "наименование"),
        ], ""),
        (48, 880, 528, "подразделение", "master", [
            ("PK", "подразделение_id"), ("UQ", "наименование"),
        ], ""),
        (48, 1070, 528, "код_номенклатуры", "master", [
            ("PK", "код_id"),
            ("FK", "номенклатура_id → номенклатура"),
            ("", "источник"),
            ("UQ", "код (уникален вместе с источником)"),
        ], "UQ (источник, код)"),
        (640, 230, 528, "номенклатура", "catalog", [
            ("PK", "номенклатура_id"),
            ("CHECK", "вид: продукция / материал / операция"),
            ("", "наименование"),
            ("FK", "базовая_единица_id → единица_измерения"),
        ], ""),
        (640, 440, 528, "цена_номенклатуры", "price", [
            ("PK", "цена_id"),
            ("FK", "номенклатура_id → номенклатура"),
            ("CHECK", "вид_цены: закупочная / тариф / отпускная"),
            ("FK", "единица_id → единица_измерения"),
            ("", "значение"), ("", "валюта"), ("", "действует_с"), ("", "действует_по"),
        ], "UQ (номенклатура, вид_цены, единица, действует_с)"),
        (640, 800, 528, "спецификация", "spec", [
            ("PK", "спецификация_id"),
            ("FK", "продукция_id → номенклатура"),
            ("FK", "изготовитель_id → контрагент"),
            ("", "версия"), ("", "действует_с"), ("", "действует_по"),
        ], "UQ (продукция_id, версия)"),
        (1232, 800, 528, "спецификация_материал", "spec", [
            ("PK,FK", "спецификация_id → спецификация"),
            ("PK", "номер_строки"),
            ("FK", "материал_id → номенклатура"),
            ("", "количество_на_изделие"),
            ("FK", "единица_id → единица_измерения"),
        ], ""),
        (1232, 1040, 528, "спецификация_операция", "spec", [
            ("PK,FK", "спецификация_id → спецификация"),
            ("PK", "номер_строки"),
            ("FK", "операция_id → номенклатура"),
            ("", "норма_времени"),
            ("FK", "единица_времени_id → единица_измерения"),
            ("", "количество_на_изделие"),
            ("FK", "единица_количества_id → единица_измерения"),
        ], ""),
        (1824, 230, 528, "заказ_покупателя", "sales", [
            ("PK", "заказ_покупателя_id"), ("", "номер"), ("", "дата"),
            ("FK", "покупатель_id → контрагент"),
            ("FK", "продавец_id → контрагент"),
        ], "UQ (номер, дата)"),
        (1824, 500, 528, "строка_заказа_покупателя", "sales", [
            ("PK,FK", "заказ_покупателя_id → заказ_покупателя"),
            ("PK", "номер_строки"),
            ("FK", "продукция_id → номенклатура"),
            ("", "количество"),
            ("FK", "единица_id → единица_измерения"),
            ("", "цена_за_единицу (снимок)"),
            ("", "скидка_сумма"),
        ], ""),
        (1824, 800, 528, "заказ_производства", "production", [
            ("PK", "заказ_производства_id"), ("", "номер"), ("", "дата"),
            ("", "дата_запуска"),
            ("FK", "подразделение_id → подразделение"),
        ], "UQ (номер, дата)"),
        (1824, 1070, 528, "строка_заказа_производства", "production", [
            ("PK,FK", "заказ_производства_id → заказ_производства"),
            ("PK", "номер_строки"),
            ("FK", "спецификация_id → спецификация"),
            ("", "количество"),
            ("FK", "единица_id → единица_измерения"),
        ], ""),
    ]
    for x, y, w, name, group, rows, footer in cards:
        cmds.append(" ".join(table_card(x, y, w, name, group, rows, footer)))

    # Вычисляемая часть модели.
    cmds.extend(note_card(48, 1415, 1120, 225, "РАСЧЁТНЫЕ ДАННЫЕ НЕ ДУБЛИРУЮТСЯ",
        [
            "Себестоимость = материалы по спецификации × закупочные цены + операции × тарифы.",
            "Потребность заказа производства выводится из его количества и закреплённой версии спецификации.",
            "Итоги заказов и суммы строк вычисляются; в модели хранятся исходные факты и ставки.",
        ], COLORS["spec"], 16.5, 31))
    cmds.extend(note_card(1200, 1415, 1152, 225, "ЦЕНА И ИСТОРИЯ",
        [
            "Цена_номенклатуры хранит тарифы/прайс по единице измерения и периоду действия.",
            "Продажная цена в строке заказа — снимок на момент сделки; скидка хранится отдельно.",
            "Формула наценки в источниках не задана: отпускную цену утверждают отдельным правилом.",
        ], COLORS["price"], 16.5, 31))
    return cmds


def page2() -> list[str]:
    cmds = title_block(
        "СВЯЗИ, ЦЕЛОСТНОСТЬ И ДОПУЩЕНИЯ",
        "Все связи заданы внешними ключами; UQ/CHECK — альтернативные ограничения • типы данных не фиксируются",
        "A2  |  ПРАВИЛА МОДЕЛИ",
    )
    left = [
        ("контрагент", "1 → 0..N", "контрагент_роль", "контрагент_id"),
        ("контрагент", "1 → 0..N", "спецификация", "изготовитель_id"),
        ("контрагент", "1 → 0..N", "заказ_покупателя", "покупатель_id"),
        ("контрагент", "1 → 0..N", "заказ_покупателя", "продавец_id"),
        ("номенклатура", "1 → 0..N", "код_номенклатуры", "номенклатура_id"),
        ("единица_измерения", "1 → 0..N", "номенклатура", "базовая_единица_id"),
        ("номенклатура", "1 → 0..N", "цена_номенклатуры", "номенклатура_id"),
        ("единица_измерения", "1 → 0..N", "цена_номенклатуры", "единица_id"),
        ("номенклатура", "1 → 0..N", "спецификация", "продукция_id"),
        ("спецификация", "1 → 0..N", "спецификация_материал", "спецификация_id"),
        ("номенклатура", "1 → 0..N", "спецификация_материал", "материал_id"),
        ("единица_измерения", "1 → 0..N", "спецификация_материал", "единица_id"),
    ]
    right = [
        ("спецификация", "1 → 0..N", "спецификация_операция", "спецификация_id"),
        ("номенклатура", "1 → 0..N", "спецификация_операция", "операция_id"),
        ("единица_измерения", "1 → 0..N", "спецификация_операция", "единица_времени_id"),
        ("единица_измерения", "1 → 0..N", "спецификация_операция", "единица_количества_id"),
        ("заказ_покупателя", "1 → 1..N", "строка_заказа_покупателя", "заказ_покупателя_id"),
        ("номенклатура", "1 → 0..N", "строка_заказа_покупателя", "продукция_id"),
        ("единица_измерения", "1 → 0..N", "строка_заказа_покупателя", "единица_id"),
        ("подразделение", "1 → 0..N", "заказ_производства", "подразделение_id"),
        ("заказ_производства", "1 → 1..N", "строка_заказа_производства", "заказ_производства_id"),
        ("спецификация", "1 → 0..N", "строка_заказа_производства", "спецификация_id"),
        ("единица_измерения", "1 → 0..N", "строка_заказа_производства", "единица_id"),
    ]
    cmds.append(" ".join(relationship_card(48, 190, 1120, "СПРАВОЧНИКИ И НОРМАТИВНЫЕ ДАННЫЕ", left, COLORS["catalog"])))
    cmds.append(" ".join(relationship_card(1232, 190, 1120, "ЗАКАЗЫ И ИХ СТРОКИ", right, COLORS["sales"])))

    cmds.extend(note_card(48, 790, 730, 820, "ССЫЛОЧНАЯ ЦЕЛОСТНОСТЬ",
        [
            "Каждая строка ссылается на существующий родительский PK.",
            "Удаление используемых контрагентов, единиц, товаров и спецификаций запрещено.",
            "PK строк документа составной: (документ_id, номер_строки).",
            "UQ: код (источник, код); спецификация (продукция, версия).",
            "UQ: цена (номенклатура, вид, единица, начало действия).",
            "UQ: номер + дата документа; обозначение единицы; название подразделения.",
            "ИНН уникален, но может отсутствовать; внешний_id допускает NULL для компании.",
            "Количество > 0; цена ≥ 0; период действия не должен быть перевёрнут.",
            "FK на номенклатуру проверяет вид: продукция / материал / операция.",
            "Роли покупателя/поставщика/продавца/изготовителя проверяются по контрагент_роль.",
        ], COLORS["master"], 16.2, 34))
    cmds.extend(note_card(810, 790, 730, 820, "3НФ И ЦЕНООБРАЗОВАНИЕ",
        [
            "Наименование товара, материала и операции хранится в одном справочнике.",
            "Строки спецификации содержат только состав/нормы и FK на сущности.",
            "Себестоимость единицы продукции рассчитывается по выбранной версии:",
            "Σ(количество материала × закупочная цена) + Σ(норма операции × тариф).",
            "Для тарифа учитываются его единица измерения и период действия.",
            "Продажная цена хранится в прайсе, если утверждена; заказ сохраняет снимок.",
            "Скидка — атрибут строки; сумма строки и итог заказа вычисляются.",
            "Потребность материалов и операций заказа производства — запрос по спецификации.",
            "У заказа производства хранится FK на версию спецификации для истории.",
            "Итоги и расчёт стоимости — представление/запрос, не копии в таблицах.",
        ], COLORS["price"], 16.2, 34))
    cmds.extend(note_card(1572, 790, 780, 820, "ЗАМЕЧАНИЯ ПО ИСТОЧНИКАМ",
        [
            "«Самобранка»: НФ-00000006 в производственном заказе и ФР-00000034 в заказе покупателя; сохранить коды по источникам и объединять номенклатуру только после подтверждения.",
            "«Опора»: спецификация указывает «шт», производственный заказ — «тыс. шт»; проверить и пересчитать единицы, чтобы исключить ошибку масштаба.",
            "В «Цены.xlsx» не указаны единицы измерения и сроки действия тарифов; согласовать их при загрузке.",
            "ООО ТД «Вершина» указано как продавец/изготовитель, но отсутствует в JSON; завести контрагента с нужными ролями.",
            "Ключ JSON «addres» нормализуется в атрибут «адрес».",
            "Основание: 5 XLSX-документов и Заказчики.json из репозитория.",
        ], COLORS["production"], 16.2, 34))
    cmds.append(text_cmd(52, 1658,
        "Модель содержит логические атрибуты и ключи; физические типы данных, правила конвертации единиц и коэффициент наценки согласуются при внедрении.",
        15.5, MUTED, False))
    return cmds


def main() -> None:
    if not shutil_which("convert"):
        raise SystemExit("ImageMagick `convert` is required to render the ER diagram.")
    with tempfile.TemporaryDirectory(prefix="er-diagram-") as temp:
        temp_path = Path(temp)
        page_images = []
        for idx, commands in enumerate((page1(), page2()), start=1):
            png_path = temp_path / f"page-{idx}.png"
            render_png(commands, png_path)
            page_images.append(extract_png_rgb(png_path))
        write_pdf(page_images)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


def shutil_which(name: str) -> str | None:
    from shutil import which
    return which(name)


if __name__ == "__main__":
    main()
