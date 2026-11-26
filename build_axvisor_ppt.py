#!/usr/bin/env python3
"""Generate the AxVisor PPTX presentation and its Markdown notes."""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PPTX = os.path.join(REPO_ROOT, "1128beijing-temp.pptx")
V4_PPTX = os.path.join(REPO_ROOT, "TGOSKits_Presentation_v4.pptx")
OUT_PPTX = os.path.join(REPO_ROOT, "AxVisor_组件化轻量虚拟机.pptx")
OUT_NOTES_MD = os.path.join(REPO_ROOT, "AxVisor_组件化轻量虚拟机_演讲备注.md")

# Fonts: Times New Roman for English/Latin/code, Microsoft YaHei for CJK
FONT_CJK = "微软雅黑"
FONT_LATIN = "Times New Roman"
FONT_MONO = "Times New Roman"
FONT_COVER = "Microsoft YaHei"

# Palette aligned with 1128 Beijing template
BRAND_BLUE = RGBColor(0x08, 0x61, 0xFF)
DARK_NAVY = RGBColor(0x0E, 0x2A, 0x5C)
MID_BLUE = RGBColor(0x1D, 0x4E, 0xD8)
BODY_TEXT = RGBColor(0x26, 0x35, 0x4D)
MUTED_TEXT = RGBColor(0x5A, 0x6B, 0x85)
ICE_FILL = RGBColor(0xEE, 0xF4, 0xFF)
BORDER_BLU = RGBColor(0xC2, 0xD7, 0xF5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF5, 0xF7, 0xFB)
GRAY_BORDER = RGBColor(0xD4, 0xDC, 0xE8)
SLATE_DARK = RGBColor(0x47, 0x55, 0x69)

SAFE_GREEN = RGBColor(0x0B, 0x8F, 0x63)
SAFE_BG = RGBColor(0xEA, 0xF9, 0xF3)
SAFE_BORDER = RGBColor(0x9E, 0xE2, 0xC8)

AMBER_ORG = RGBColor(0xD9, 0x5D, 0x0A)
AMBER_BG = RGBColor(0xFF, 0xF4, 0xEA)
AMBER_BORDER = RGBColor(0xFA, 0xCB, 0xA0)

ALERT_RED = RGBColor(0xCF, 0x2F, 0x3F)
RED_BG = RGBColor(0xFE, 0xEE, 0xF0)
RED_BORDER = RGBColor(0xF5, 0xB8, 0xBF)

PURPLE = RGBColor(0x63, 0x44, 0xEC)
PURP_BG = RGBColor(0xF3, 0xF0, 0xFF)
PURP_BORDER = RGBColor(0xC9, 0xBD, 0xFA)

CODE_BG = RGBColor(0x13, 0x1E, 0x34)
CODE_FG = RGBColor(0xE5, 0xED, 0xF8)
CODE_CMT = RGBColor(0x7E, 0x97, 0xB8)
CODE_KW = RGBColor(0x7D, 0xD3, 0xFC)
CODE_STR = RGBColor(0x86, 0xEF, 0xAC)
CODE_TYPE = RGBColor(0xFD, 0xD4, 0x63)

TOTAL_SLIDES = 18


@dataclass
class PicStamp:
    blob: bytes
    left: int
    top: int
    width: int
    height: int


def extract_template_stamps(prs: Presentation) -> dict[str, list[PicStamp]]:
    """Capture background and logo picture stamps from template slides before clearing."""
    def grab(slide_idx: int, order: list[str]) -> list[PicStamp]:
        slide = prs.slides[slide_idx]
        by_name = {sh.name: sh for sh in slide.shapes if sh.shape_type == 13}
        out = []
        for nm in order:
            sh = by_name[nm]
            out.append(PicStamp(sh.image.blob, sh.left, sh.top, sh.width, sh.height))
        return out

    return {
        "gradient": grab(2, ["图片 3", "图片 1", "图片 2", "图片 4", "图片 6"]),
        "white": grab(4, ["图片 1", "图片 2", "图片 4", "图片 6"]),
    }


def extract_v4_media() -> dict[str, bytes]:
    """Extract verified real screenshots & QR code from TGOSKits_Presentation_v4.pptx."""
    targets = {
        "web_ui": "ppt/media/image6.png",
        "web_term": "ppt/media/image7.png",
        "ostool_boards": "ppt/media/image10.png",
        "ostool_overview": "ppt/media/image11.png",
        "wechat_qr": "ppt/media/image12.jpeg",
    }
    blobs: dict[str, bytes] = {}
    with zipfile.ZipFile(V4_PPTX) as z:
        for key, member in targets.items():
            blobs[key] = z.read(member)
    return blobs


def remove_middle_slides(prs: Presentation) -> None:
    """Keep the event cover and closing slides, and remove the sample pages."""
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst)[1:-1]:
        rId = sldId.rId
        prs.part.drop_rel(rId)
        sldIdLst.remove(sldId)
    prs.part.rename_slide_parts(slide_id.rId for slide_id in sldIdLst)


def new_styled_slide(prs: Presentation, stamps: list[PicStamp]):
    """Use the template's content layout and reproduce its background and logos."""
    slide = prs.slides.add_slide(prs.slides[0].slide_layout)
    for ph in list(slide.placeholders):
        sp = ph._element
        sp.getparent().remove(sp)
    for st in stamps:
        slide.shapes.add_picture(
            io.BytesIO(st.blob), st.left, st.top, st.width, st.height
        )
    return slide


def set_run(
    run,
    text: str,
    size: float,
    color: RGBColor = BODY_TEXT,
    bold: bool = False,
    font_name: str = FONT_CJK,
):
    run.text = text
    f = run.font
    f.name = FONT_LATIN
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    latin = rPr.find(qn("a:latin"))
    for tag in ("a:ea", "a:cs"):
        old = rPr.find(qn(tag))
        if old is not None:
            rPr.remove(old)
    ea = OxmlElement("a:ea")
    ea.set("typeface", FONT_CJK)
    cs = OxmlElement("a:cs")
    cs.set("typeface", FONT_LATIN)
    if latin is not None:
        latin.addnext(ea)
        ea.addnext(cs)
    else:
        rPr.append(ea)
        rPr.append(cs)


def add_textbox(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str = "",
    size: float = 22,
    color: RGBColor = BODY_TEXT,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    font_name: str = FONT_CJK,
    line_spacing: float = 1.2,
    margin: tuple[float, float, float, float] = (0.04, 0.04, 0.02, 0.02),
):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(margin[0])
    tf.margin_right = Inches(margin[1])
    tf.margin_top = Inches(margin[2])
    tf.margin_bottom = Inches(margin[3])
    if text:
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = line_spacing
            r = p.add_run()
            set_run(r, line, size=size, color=color, bold=bold, font_name=font_name)
    return tb


def add_rich_paragraphs(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    paras: list[tuple[list[tuple[str, float, RGBColor, bool, str]], float, PP_ALIGN]],
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    line_spacing: float = 1.22,
    margin: tuple[float, float, float, float] = (0.06, 0.06, 0.04, 0.04),
):
    """Add multi-paragraph, multi-run formatted text box."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(margin[0])
    tf.margin_right = Inches(margin[1])
    tf.margin_top = Inches(margin[2])
    tf.margin_bottom = Inches(margin[3])
    for idx, (runs_spec, space_after, align) in enumerate(paras):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        for txt, sz, col, bld, fn in runs_spec:
            r = p.add_run()
            set_run(r, txt, size=sz, color=col, bold=bld, font_name=fn)
    return tb


def add_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: RGBColor | None = WHITE,
    border: RGBColor | None = BORDER_BLU,
    border_pt: float = 1.2,
    rounded: bool = True,
    radius: float = 0.05,
    dash: MSO_LINE_DASH_STYLE | None = None,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        sh.adjustments[0] = radius
    if fill is not None:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    else:
        sh.fill.background()
    if border is not None:
        sh.line.color.rgb = border
        sh.line.width = Pt(border_pt)
        if dash is not None:
            sh.line.dash_style = dash
    else:
        sh.line.fill.background()
    return sh


def add_card(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str = "",
    accent: RGBColor = BRAND_BLUE,
    fill: RGBColor = WHITE,
    border: RGBColor = BORDER_BLU,
    title_size: float = 26,
    header_band: bool = False,
    header_band_h: float = 0.68,
    radius: float = 0.04,
):
    """Add a crisp card with optional colored top header band or thin top accent bar."""
    add_rect(slide, x, y, w, h, fill=fill, border=border, border_pt=1.5, rounded=True, radius=radius)
    if header_band and title:
        band_h = header_band_h
        add_rect(slide, x + 0.02, y + 0.02, w - 0.04, band_h, fill=accent, border=None, rounded=True, radius=0.06)
        add_rect(slide, x + 0.02, y + band_h * 0.55, w - 0.04, band_h * 0.48, fill=accent, border=None, rounded=False)
        add_textbox(
            slide, x + 0.22, y + 0.04, w - 0.44, band_h - 0.04,
            title, size=title_size, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.12
        )
    else:
        add_rect(slide, x + 0.14, y + 0.03, w - 0.28, 0.08, fill=accent, border=None, rounded=False)
        if title:
            add_textbox(
                slide, x + 0.24, y + 0.16, w - 0.48, 0.54,
                title, size=title_size, color=accent, bold=True, valign=MSO_ANCHOR.MIDDLE
            )


def add_arrow(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    direction: str = "right",
    color: RGBColor = BRAND_BLUE,
):
    mapping = {
        "right": MSO_SHAPE.RIGHT_ARROW,
        "left": MSO_SHAPE.LEFT_ARROW,
        "down": MSO_SHAPE.DOWN_ARROW,
        "up": MSO_SHAPE.UP_ARROW,
        "lr": MSO_SHAPE.LEFT_RIGHT_ARROW,
        "ud": MSO_SHAPE.UP_DOWN_ARROW,
    }
    sh = slide.shapes.add_shape(mapping[direction], Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    return sh


def add_picture_fit(
    slide,
    blob: bytes,
    box_x: float,
    box_y: float,
    box_w: float,
    box_h: float,
    frame_border: RGBColor | None = BORDER_BLU,
    pad: float = 0.06,
):
    """Insert image preserving exact aspect ratio, centered inside target box."""
    im = Image.open(io.BytesIO(blob))
    iw, ih = im.size
    avail_w = box_w - 2 * pad
    avail_h = box_h - 2 * pad
    scale = min(avail_w / iw, avail_h / ih)
    draw_w = iw * scale
    draw_h = ih * scale
    px = box_x + (box_w - draw_w) / 2
    py = box_y + (box_h - draw_h) / 2
    if frame_border is not None:
        add_rect(
            slide, px - pad, py - pad, draw_w + 2 * pad, draw_h + 2 * pad,
            fill=WHITE, border=frame_border, border_pt=1.4, rounded=True, radius=0.02
        )
    slide.shapes.add_picture(io.BytesIO(blob), Inches(px), Inches(py), Inches(draw_w), Inches(draw_h))
    return px, py, draw_w, draw_h


def add_content_chrome(
    slide,
    is_gradient: bool,
    section_label: str,
    section_color: RGBColor,
    title_text: str,
    eli5_text: str,
    page_num: int,
    takeaway_label: str,
    takeaway_text: str,
):
    """Consistent header, ELI5 strip, takeaway footer, and page indicator."""
    add_rect(slide, 1.12, 1.32, 3.10, 0.56, fill=section_color, border=None, rounded=True, radius=0.22)
    add_textbox(
        slide, 1.12, 1.32, 3.10, 0.56,
        section_label, size=21, color=WHITE, bold=True,
        align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, margin=(0.04, 0.04, 0.02, 0.02)
    )
    add_textbox(
        slide, 4.40, 1.24, 21.15, 0.72,
        title_text, size=40, color=DARK_NAVY, bold=True,
        valign=MSO_ANCHOR.MIDDLE, margin=(0.04, 0.04, 0.0, 0.0)
    )
    strip_fill = WHITE if is_gradient else ICE_FILL
    add_rect(slide, 1.12, 2.04, 0.11, 0.56, fill=section_color, border=None, rounded=False)
    add_rect(slide, 1.23, 2.04, 24.32, 0.56, fill=strip_fill, border=BORDER_BLU, border_pt=1.0, rounded=False)
    add_textbox(
        slide, 1.38, 2.05, 24.00, 0.54,
        eli5_text, size=22, color=DARK_NAVY, bold=False,
        valign=MSO_ANCHOR.MIDDLE, line_spacing=1.05, margin=(0.06, 0.04, 0.02, 0.02)
    )
    bar_fill = WHITE if is_gradient else LIGHT_GRAY
    add_rect(slide, 3.55, 11.98, 17.15, 1.06, fill=bar_fill, border=BORDER_BLU, border_pt=1.4, rounded=True, radius=0.08)
    add_rect(slide, 3.75, 12.21, 2.40, 0.60, fill=section_color, border=None, rounded=True, radius=0.18)
    add_textbox(
        slide, 3.75, 12.21, 2.40, 0.60,
        takeaway_label, size=20, color=WHITE, bold=True,
        align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE
    )
    add_textbox(
        slide, 6.32, 12.04, 14.20, 0.94,
        takeaway_text, size=22, color=DARK_NAVY, bold=True,
        valign=MSO_ANCHOR.MIDDLE, line_spacing=1.15
    )
    add_textbox(
        slide, 10.60, 13.48, 3.00, 0.48,
        f"{page_num} / {TOTAL_SLIDES}", size=20, color=MUTED_TEXT, bold=True,
        align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE
    )


def replace_cover_title(cover) -> None:
    """Replace the sample topic artwork in its original boxes."""
    by_name = {shape.name: shape for shape in cover.shapes}
    title = by_name["图片 6"]
    banner = by_name["图片 9"]
    title_box = add_rich_paragraphs(
        cover, title.left.inches, title.top.inches, title.width.inches, title.height.inches,
        [([("AxVisor: ", 104, DARK_NAVY, True, FONT_COVER),
           ("组件化轻量虚拟机", 78, BRAND_BLUE, True, FONT_COVER)], 0, PP_ALIGN.LEFT)],
        valign=MSO_ANCHOR.MIDDLE, line_spacing=1.0, margin=(0, 0, 0, 0)
    )
    banner_bounds = (banner.left.inches, banner.top.inches, banner.width.inches, banner.height.inches)
    add_rect(cover, *banner_bounds, fill=BRAND_BLUE, border=None, rounded=False)
    subtitle_box = add_textbox(
        cover, *banner_bounds, "基于 Rust 的 Type-1 虚拟机管理器",
        size=42, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE,
        line_spacing=1.0, margin=(0.26, 0.26, 0, 0)
    )
    for textbox in (title_box, subtitle_box):
        textbox.text_frame.word_wrap = False
        textbox.text_frame.auto_size = MSO_AUTO_SIZE.NONE
        paragraph = textbox.text_frame.paragraphs[0]
        paragraph._p.get_or_add_pPr().set("marL", "0")
        for run in paragraph.runs:
            run.font.name = FONT_COVER
            run._r.get_or_add_rPr().find(qn("a:ea")).set("typeface", FONT_COVER)
    for picture in (title, banner):
        rid = picture._pic.blip_rId
        picture._element.getparent().remove(picture._element)
        cover.part.drop_rel(rid)


def build_slides(prs: Presentation, stamps: dict[str, list[PicStamp]], media: dict[str, bytes]) -> list[tuple[str, str, float, str]]:
    """Build the slides and return [(title, section, minutes, notes), ...]."""
    notes_records: list[tuple[str, str, float, str]] = []
    cover, ending = prs.slides[0], prs.slides[1]
    ending_id = prs.slides._sldIdLst[1]

    def add_notes(slide, title: str, section: str, minutes: float, text: str):
        clean = text.strip()
        ns = slide.notes_slide
        ns.notes_text_frame.text = clean
        notes_records.append((title, section, minutes, clean))

    # =========================================================================
    # SLIDE 1: 封面 (Cover Style)
    # =========================================================================
    replace_cover_title(cover)
    add_notes(
        cover,
        "AxVisor: 组件化轻量虚拟机",
        "开场介绍",
        1.0,
        """大家好，非常荣幸能在这里向大家分享 AxVisor。AxVisor 由清华大学和泉城实验室联合开发，是一款用 Rust 编写的轻量级 Type-1 虚拟机管理器。

Type-1 是指虚拟机管理器直接跑在硬件上，不像 KVM 运行虚拟机需要 Linux 内核的支持。AxVisor 直接作为内核管理硬件资源，给各台虚拟机分配 CPU、内存和设备，让不同的操作系统在同一台机器上隔离运行。

拿机器人举个例子，一块板子上可以同时跑 Linux 和实时系统。Linux 处理摄像头画面，实时系统控制电机和底盘，两边需要配合时再交换数据。车载和工业控制也有类似的需求。"""
    )

    # =========================================================================
    # SLIDE 2: 背景——单颗多核芯片上的多系统隔离需求
    # =========================================================================
    s2 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s2, True, "01 背景与取舍", BRAND_BLUE,
        "背景：单颗多核芯片上的多系统隔离需求",
        "机器人、车载与工业控制常需在同一颗芯片上同时运行硬实时控制与复杂 Linux 应用",
        2, "问题定义",
        "能否同时获得 Type-1 硬件隔离的轻量性，以及可运行实时任务与标准库服务的宿主内核？"
    )
    housing_cards = [
        (
            "方案一：单系统混跑（OS / 容器）", ALERT_RED, RED_BG, RED_BORDER,
            "实时控制、外设驱动、UI 与 AI 推理共用同一个操作系统内核",
            [
                "优势：开发与部署成本最低，任务间可直接共享内存。",
                "隔离局限：容器共享宿主机内核，外设驱动故障或内核调度抖动会直接波及关键控制任务。",
                "典型约束：缺少硬件级故障域边界，难以满足混合关键性系统的安全隔离要求。"
            ],
            "权衡：开发简单，但缺少硬件故障隔离"
        ),
        (
            "方案二：Linux 宿主（KVM / QEMU）", AMBER_ORG, AMBER_BG, AMBER_BORDER,
            "先在裸机启动完整 Linux 作为宿主机，再在其上创建虚拟客户机",
            [
                "优势：复用成熟 Linux 内核与工具链，云端及通用服务器生态完善。",
                "资源开销：运行 Linux 宿主和 QEMU 设备模拟进程，需要预留内存。",
                "实时任务：客户机的 vCPU 由 Linux 宿主调度，时延需要按部署场景验证。"
            ],
            "权衡：生态成熟，但宿主底座偏重"
        ),
        (
            "方案三：静态分区（Jailhouse / Bao）", BRAND_BLUE, ICE_FILL, BORDER_BLU,
            "按静态分区划分 CPU 核、内存与外设，Jailhouse 由 Linux 加载",
            [
                "优势：资源事先划给各个分区，运行时的归属清楚。",
                "宿主局限：监控器本身没有任务调度与标准库运行时，实时控制仍需另开客户机承载。",
                "运维成本：缺少网络、文件系统与标准库支持，动态管控和调试能力扩展受限。"
            ],
            "权衡：足够轻量，但缺少宿主运行时与生态"
        ),
    ]
    for idx, (ctitle, accent, bg, bd, desc, bullets, foot) in enumerate(housing_cards):
        cx = 1.12 + idx * 8.28
        cw = 7.86
        add_card(s2, cx, 2.84, cw, 8.65, title=ctitle, accent=accent, fill=WHITE, border=bd, title_size=26, header_band=True)
        add_rect(s2, cx + 0.28, 3.74, cw - 0.56, 1.05, fill=bg, border=bd, border_pt=1.0, rounded=True, radius=0.06)
        add_textbox(s2, cx + 0.42, 3.80, cw - 0.84, 0.94, desc, size=22, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE)
        paras = []
        for b in bullets:
            head, rest = b.split("：", 1)
            paras.append((
                [("• " + head + "：", 22, accent, True, FONT_CJK), (rest, 22, BODY_TEXT, False, FONT_CJK)],
                12, PP_ALIGN.LEFT
            ))
        add_rich_paragraphs(s2, cx + 0.30, 5.00, cw - 0.60, 5.30, paras, line_spacing=1.28)
        add_rect(s2, cx + 0.28, 10.50, cw - 0.56, 0.72, fill=bg, border=bd, border_pt=1.2, rounded=True, radius=0.10)
        add_textbox(s2, cx + 0.36, 10.50, cw - 0.72, 0.72, foot, size=22, color=accent, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s2,
        "背景：单颗多核芯片上的多系统隔离需求",
        "01 背景与取舍",
        2.0,
        """但真要把这两类负载装进同一颗多核芯片，马上就会遇到隔离和性能的矛盾：一边是跑视觉和 AI 推理的复杂 Linux 应用，另一边是按固定周期控制电机的硬实时任务。目前常见的做法主要有三种，落到嵌入式板卡上，各自都有明显的局限。

左边第一种是单系统混跑。实时控制、驱动和复杂应用共用一个内核，开发最省事，但就算使用容器隔离，底下还是共享宿主机内核，没有硬件级的故障边界。一旦外设驱动出错，或者视觉、AI 重负载引起内核调度抖动，就会直接波及底盘控制，很难满足混合关键性系统的安全隔离要求。

中间第二种是在裸机启动完整 Linux 做宿主，再用 KVM 和 QEMU 跑客户机。这套生态在服务器上很成熟，放到资源受限的嵌入式板卡上就有两个问题：一是宿主底座偏重，光运行 Linux 宿主和 QEMU 设备模拟进程就要预留不少内存；二是客户机的 vCPU 归通用 Linux 宿主调度，实时任务的时延受宿主影响，需要按部署场景逐一验证。

右边第三种是 Jailhouse、Bao 这类静态分区方案，事先按分区划好 CPU 核、内存和外设，其中 Jailhouse 还要靠 Linux 加载。它足够轻量，资源归属也清楚，代价是宿主本身的功能过于精简：监控器自己没有任务调度和标准库运行时，跑实时控制还得另开一台客户机承载；宿主也缺少网络、文件系统和标准库支持，动态管控和调试很难扩展，拉高了运维成本。

把这三种方案摆在一起，我们要补齐的缺口就很清楚了：能不能既保留 Type-1 硬件隔离的轻量底座，又让宿主内核自己就能跑实时任务和标准库服务？AxVisor 给出的解法，是按需组装一个专用的 Type-1 宿主内核。一方面直接跑在硬件上，把复杂 Linux 应用放进硬件隔离的客户机，建立硬件故障边界，也省掉厚重的通用 Linux 宿主；另一方面宿主自带实时调度，并支持 Rust 标准库、网络和文件系统，实时控制与网页管控都能直接跑在宿主态。"""
    )

    # =========================================================================
    # SLIDE 3: AxVisor 的四项设计特点
    # =========================================================================
    s3 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s3, False, "01 背景与取舍", BRAND_BLUE,
        "AxVisor 的四项设计特点",
        "Type-1 宿主负责管理硬件和客户机，也能直接运行实时应用和管理服务",
        3, "组件底座",
        "从 TGOSKits 选用内核组件，再加入虚拟化组件，组装成 AxVisor。"
    )
    quads = [
        (
            "01 · 按需组装专用内核", BRAND_BLUE, ICE_FILL, BORDER_BLU,
            "Type-1 直接跑在硬件上，需要调度、内存管理和驱动等内核能力。",
            "从 TGOSKits 选用底层组件，再加入虚拟化组件，组装成专门做虚拟化的宿主内核。"
        ),
        (
            "02 · 内核态支持 Rust 标准库", SAFE_GREEN, SAFE_BG, SAFE_BORDER,
            "网页管理服务需要线程、网络等标准库能力。",
            "宿主内核提供 Rust std，管理线程可直接使用 Tokio、Axum 等通常用于应用层的库。"
        ),
        (
            "03 · 宿主内核也是实时内核", AMBER_ORG, AMBER_BG, AMBER_BORDER,
            "电机控制要按时运行，也要及时处理设备中断。",
            "实时应用可由宿主直接调度。控制设备由宿主管理时，可省掉向客户机转发中断的开销。"
        ),
        (
            "04 · 声明式设备图简化配置", PURPLE, PURP_BG, PURP_BORDER,
            "给客户机加虚拟串口或磁盘时，地址、中断号和固件描述得对得上。",
            "配置只需写要用哪些虚拟设备。设备图统一分配地址和中断号，并生成客户机固件描述。"
        ),
    ]
    for i, (qtitle, accent, bg, bd, pain, sol) in enumerate(quads):
        col = i % 2
        row = i // 2
        qx = 1.12 + col * 12.42
        qy = 2.86 + row * 4.44
        qw, qh = 12.00, 4.14
        add_card(s3, qx, qy, qw, qh, title=qtitle, accent=accent, fill=WHITE, border=bd, title_size=26, header_band=True)
        add_rect(s3, qx + 0.28, qy + 0.88, qw - 0.56, 1.02, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.0, rounded=True, radius=0.06)
        add_textbox(s3, qx + 0.42, qy + 0.92, qw - 0.84, 0.94, pain, size=21, color=MUTED_TEXT, bold=False, valign=MSO_ANCHOR.MIDDLE)
        add_rect(s3, qx + 0.28, qy + 2.04, qw - 0.56, 1.84, fill=bg, border=bd, border_pt=1.2, rounded=True, radius=0.06)
        add_textbox(s3, qx + 0.42, qy + 2.10, qw - 0.84, 1.72, sol, size=22.5, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24)

    add_notes(
        s3,
        "AxVisor 的四项设计特点",
        "01 背景与取舍",
        1.5,
        """围绕这个思路，AxVisor 在架构上做了四项关键设计。

第一，按需组装专用内核。AxVisor 是 Type-1 虚拟机管理器，直接跑在硬件上，自己就得有调度、内存管理和设备驱动。这些能力来自 TGOSKits，它是一个用 Rust 开发操作系统和虚拟化软件的开源项目。我们从里面选出需要的内核组件，再加上虚拟化组件，组装成专门做虚拟化的宿主内核。

第二，在内核态支持 Rust 标准库。像 Tokio 和 Axum 这类平时用来写应用服务的库，也可以直接在宿主内核的管理线程里运行。板子上的网页管理台就是这么实现的。

第三，宿主内核也是实时内核。比如电机控制，可以直接交给宿主调度，省掉客户机这一层。如果控制设备由宿主直接管理，中断也由宿主直接处理，少一次虚拟化转发。

第四，用声明式设备图简化配置。比如给客户机加个虚拟串口，配置里写要用什么设备，AxVisor 就会分配地址和中断号，再用同一份设备图生成供客户机识别的硬件描述清单。

这四项设计里，最基础的是第一条：一个不依赖 Linux 托底的 Type-1 宿主内核，到底怎么低成本地搭建出来？"""
    )

    # =========================================================================
    # SLIDE 4: 组件化底座——214 个 crate 组装三种内核形态
    # =========================================================================
    s4 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s4, True, "02 专用内核", BRAND_BLUE,
        "组件化底座：214 个 crate 组装三种内核形态",
        "TGOSKits 统一工作区维护 214 个 Rust crate，底层核心均为 #![no_std]，按特性组合为三类系统",
        4, "底座复用",
        "底层驱动、调度器与内存管理只维护一套，AxVisor 通过叠加虚拟化 crate 直接继承全套能力。"
    )
    add_card(s4, 1.12, 2.84, 10.35, 8.65, title="TGOSKits 工作区：214 个 Crate 分布", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=25, header_band=True)
    bars = [
        ("drivers/ 跨内核设备驱动", 81, 81, SAFE_GREEN, "网卡 / 块设备 / USB / PCIe / NPU"),
        ("components/ 通用内核核心", 39, 81, BRAND_BLUE, "ax-task / axcpu / trait-ffi / percpu"),
        ("os/ 系统装配与运行时", 23, 81, MID_BLUE, "ax-runtime / ax-std / 三套系统成品"),
        ("virtualization/ 虚拟化组件", 17, 81, AMBER_ORG, "axvm / axdevice / arm_vgic / axvirtio-*"),
        ("memory/ 内存与硬件封装", 8, 81, PURPLE, "mmio-api / dma-api / 通用页表 / 分配器"),
        ("platforms/ fs/ net/ 等其他", 46, 81, SLATE_DARK, "someboot / axplat-dyn / 文件系统 / 测试套件"),
    ]
    for bi, (bname, count, maxc, bcol, bsub) in enumerate(bars):
        by = 3.78 + bi * 1.24
        add_textbox(s4, 1.40, by, 6.20, 0.42, bname, size=22, color=DARK_NAVY, bold=True)
        add_textbox(s4, 8.95, by, 2.20, 0.42, f"{count} 个", size=24, color=bcol, bold=True, align=PP_ALIGN.RIGHT)
        track_w = 9.75
        add_rect(s4, 1.40, by + 0.44, track_w, 0.30, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=0.8, rounded=True, radius=0.35)
        fill_w = max(0.55, track_w * (count / maxc))
        add_rect(s4, 1.40, by + 0.44, fill_w, 0.30, fill=bcol, border=None, rounded=True, radius=0.35)
        add_textbox(s4, 1.44, by + 0.78, 9.70, 0.34, bsub, size=19, color=MUTED_TEXT, bold=False)

    add_arrow(s4, 11.65, 6.60, 1.05, 0.90, "right", AMBER_ORG)
    add_textbox(s4, 11.48, 7.62, 1.40, 0.95, "Cargo\n特性组合", size=20, color=AMBER_ORG, bold=True, align=PP_ALIGN.CENTER)

    add_card(s4, 12.90, 2.84, 12.65, 8.65, title="基于同一套组件组装的三种内核形态", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=25, header_band=True)
    morphs = [
        ("ArceOS\n单内核", BRAND_BLUE, ICE_FILL, BORDER_BLU,
         "应用层\nRust std / C App", "直接函数调用\n无系统调用开销", "公共底座\n调度 / 内存 / 驱动", "EL1 / S-Mode / Ring 0", False),
        ("StarryOS\n通用宏内核", SAFE_GREEN, SAFE_BG, SAFE_BORDER,
         "用户态进程\n原生 Linux ELF", "Linux Syscall\n(~300 系统调用)", "ArceOS 底座 +\n3 个宏内核增量包", "EL0 用户 + EL1 内核", False),
        ("AxVisor\nType-1 虚拟机", AMBER_ORG, AMBER_BG, AMBER_ORG,
         "多客户机隔离\nLinux / RTOS / Zephyr", "二阶段页表 + vGIC\n宿主直跑实时+std", "ArceOS 底座 +\n17 个虚拟化 crate", "EL2 / HS / VMX / LVZ", True),
    ]
    for mi, (mtitle, maccent, mbg, mbd, top_t, mid_t, bot_t, priv_t, is_hi) in enumerate(morphs):
        mx = 13.18 + mi * 4.10
        mw = 3.86
        border_w = 3.0 if is_hi else 1.4
        add_rect(s4, mx, 3.78, mw, 7.42, fill=mbg if is_hi else WHITE, border=mbd, border_pt=border_w, rounded=True, radius=0.05)
        add_rect(s4, mx + 0.14, 3.92, mw - 0.28, 0.96, fill=maccent, border=None, rounded=True, radius=0.08)
        add_textbox(s4, mx + 0.18, 3.94, mw - 0.36, 0.92, mtitle, size=23, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_rect(s4, mx + 0.22, 5.06, mw - 0.44, 1.48, fill=WHITE, border=maccent, border_pt=1.2, rounded=True, radius=0.06)
        add_textbox(s4, mx + 0.26, 5.10, mw - 0.52, 1.40, top_t, size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s4, mx + 0.22, 6.66, mw - 0.44, 1.12, mid_t, size=19, color=maccent, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_rect(s4, mx + 0.22, 7.90, mw - 0.44, 1.60, fill=maccent if not is_hi else DARK_NAVY, border=None, rounded=True, radius=0.06)
        add_textbox(s4, mx + 0.26, 7.94, mw - 0.52, 1.52, bot_t, size=20, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_rect(s4, mx + 0.22, 9.72, mw - 0.44, 1.24, fill=LIGHT_GRAY if not is_hi else WHITE, border=GRAY_BORDER, border_pt=1.0, rounded=True, radius=0.06)
        add_textbox(s4, mx + 0.26, 9.76, mw - 0.52, 1.16, priv_t, size=19, color=BODY_TEXT, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s4,
        "组件化底座：214 个 crate 组装三种内核形态",
        "02 专用内核",
        2.0,
        """Type-1 直接跑在硬件上，从上电引导、多核调度、内存管理，到网卡和存储驱动，宿主自己都必须具备。如果为了做虚拟化再去单独写一整套内核和驱动，维护两套底层代码成本太高；而这些基础能力，本来就和操作系统内核高度重合。

所以我们没有单独维护一套孤立代码，直接在 TGOSKits 工作区里构建 AxVisor。TGOSKits 是我们维护的一体化开源 Rust 操作系统与虚拟化工作区。看左边的分布图，它把原本紧耦合的内核拆成 214 个职责独立的 Rust crate，底层核心统一保持 no_std，不与某一种特定内核绑定。数量最多的是 81 个跨内核设备驱动，涵盖网卡、块设备、USB、PCIe 和 NPU；其余是 39 个通用内核核心包、内存与页表封装、平台引导、文件系统和网络栈，以及 17 个虚拟化专用组件。

有了左边这个公共组件池，构建时通过 Cargo 特性开关按需组合，就能组装出右边三种不同形态的内核：把公共底座和应用编译进同一地址空间，是轻量单内核 ArceOS；在 ArceOS 底座上加多进程独立虚存和约 300 个 Linux 系统调用组件，就是能跑原生 Linux 应用的宏内核 StarryOS。

最右边高亮的就是 AxVisor 的组成方式。它直接复用 ArceOS 底座里的平台引导、实时调度、内存管理、设备驱动，以及提供内核态标准库的 ax-runtime 与 ax-std，让这套底座运行在硬件虚拟化特权级上，比如 ARM64 的 EL2、RISC-V 的 HS 模式、x86 的 VMX 或龙芯的 LVZ；再在这个宿主底座之上，叠加左边那 17 个虚拟化 crate，用 axvm 管理客户机与 vCPU，配上二阶段页表、虚拟中断控制器 vGIC、设备框架 axdevice 和 VirtIO 组件，就组装成了 AxVisor。这样底层的驱动、调度器和内存管理全工作区只维护一套，AxVisor 直接继承了实时内核与标准库能力，修好一处驱动问题，三套系统也同时受益。组件选齐之后，进到系统内部是怎么协同运行起来的？"""
    )

    # =========================================================================
    # SLIDE 5: 整体架构——五层职责划分与两条执行主线
    # =========================================================================
    s5 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s5, False, "02 专用内核", BRAND_BLUE,
        "整体架构：五层职责划分与两条执行主线",
        "从引导与硬件层到客户机共分五层，各层通过明确边界解耦，板级与客户机配置均外置为 TOML",
        5, "分层边界",
        "驱动层不感知虚拟化，虚拟化核不耦合控制面，编排层不直接读写硬件寄存器。"
    )
    layers = [
        ("L5 客户机与配置", "Linux · ArceOS · StarryOS · Zephyr · FreeRTOS · RT-Thread（6 种 Guest / 62 份配置）", SAFE_GREEN, SAFE_BG, SAFE_BORDER),
        ("L4 AxVisor 编排层", "os/axvisor/src：main.rs · AxvmManager 生命周期 · ConsoleMux · Shell · Web 控制面", PURPLE, PURP_BG, PURP_BORDER),
        ("L3 虚拟化核心层", "virtualization/（17 个 crate）：axvm · axaddrspace（二阶段页表）· axdevice · vGIC/vPLIC/vLAPIC · VirtIO · axivc", AMBER_ORG, AMBER_BG, AMBER_BORDER),
        ("L2 宿主实时底座", "ax-runtime / ax-task / ax-std / ax-sync / rdrive：PREEMPT_RT 风格实时调度、PI 锁、网络/文件系统、81 个驱动、Rust std", BRAND_BLUE, ICE_FILL, BORDER_BLU),
        ("L1 最小硬件层", "someboot / axplat-dyn / axcpu：四架构统一引导、FDT/ACPI 硬件动态探测、特权级与硬件陷入封装", ALERT_RED, RED_BG, RED_BORDER),
    ]
    for li, (lname, ldesc, laccent, lbg, lbd) in enumerate(layers):
        ly = 2.86 + li * 1.74
        add_rect(s5, 1.12, ly, 18.00, 1.54, fill=lbg, border=lbd, border_pt=1.8, rounded=True, radius=0.06)
        add_rect(s5, 1.26, ly + 0.16, 3.60, 1.22, fill=laccent, border=None, rounded=True, radius=0.08)
        add_textbox(s5, 1.32, ly + 0.18, 3.48, 1.18, lname, size=24, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s5, 5.08, ly + 0.14, 13.80, 1.26, ldesc, size=21, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22)

    add_card(s5, 19.42, 2.86, 6.13, 8.54, title="两条执行与配置主线", accent=DARK_NAVY, fill=LIGHT_GRAY, border=BORDER_BLU, title_size=24, header_band=True)
    add_rect(s5, 19.68, 3.78, 5.61, 3.55, fill=WHITE, border=BRAND_BLUE, border_pt=1.5, rounded=True, radius=0.06)
    add_textbox(s5, 19.86, 3.88, 5.25, 0.46, "主线一：启动与运行流", size=22, color=BRAND_BLUE, bold=True)
    add_textbox(
        s5, 19.86, 4.40, 5.25, 2.75,
        "① someboot 上电使能虚拟化\n"
        "② axvm::host 注入宿主服务能力\n"
        "③ AxvmManager 创建选中客户机\n"
        "④ 后台启 Web/HTTP + 前台 Shell\n"
        "⑤ vCPU 作为 Task 进入调度循环",
        size=20, color=BODY_TEXT, bold=False, line_spacing=1.28
    )
    add_rect(s5, 19.68, 7.56, 5.61, 3.60, fill=WHITE, border=AMBER_ORG, border_pt=1.5, rounded=True, radius=0.06)
    add_textbox(s5, 19.86, 7.66, 5.25, 0.46, "主线二：两层外置配置流", size=22, color=AMBER_ORG, bold=True)
    add_textbox(
        s5, 19.86, 8.18, 5.25, 2.84,
        "• 板级配置 configs/board/*.toml\n"
        "  决定目标板卡与启用的驱动特性\n"
        "• 客户机配置 configs/vms/*.toml\n"
        "  声明每个 Guest 的内存、镜像与设备\n"
        "• 启动先索引 /guest/builtin 与\n"
        "  /guest 动态池，按需延迟创建",
        size=20, color=BODY_TEXT, bold=False, line_spacing=1.25
    )

    add_notes(
        s5,
        "整体架构：五层职责划分与两条执行主线",
        "02 专用内核",
        1.6,
        """比如我们在开发板上启动一台 Linux 客户机。开发板要先完成上电初始化，宿主要有自己的线程和驱动，还得给 Linux 划分一块内存，最后才能通过命令行或网页把它启动起来。这些工作分在哪几层？

看左图，最底层启动板卡、启用硬件虚拟化。往上是 ArceOS 底座，负责宿主的调度、内存和驱动。再往上，虚拟化层给客户机建立自己的内存映射。比如 Linux 看到的物理地址，还要经过 CPU 的第二次地址转换，才会落到板子上的实际内存。管理层把创建、启动和停止这些操作接到命令行和网页上，顶上就是运行中的客户机。

右图把这条启动流程串了起来。板级配置选目标板和驱动，客户机配置写镜像、内存和设备。宿主启动后先建立客户机配置清单，再按启动参数或管理命令创建客户机。这个过程用到的驱动也可以被别的系统复用，前提是驱动能从不同的内核拿到它需要的能力。"""
    )

    # =========================================================================
    # SLIDE 6: 依赖解耦
    # =========================================================================
    s6 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s6, False, "02 专用内核", BRAND_BLUE,
        "依赖解耦：通过过程宏与 FFI 实现跨 crate 链接",
        "借鉴 C 语言外部函数链接机制，由过程宏将标准 trait 自动展开为配对的 FFI 声明与导出符号",
        6, "解耦收益",
        "既打破循环依赖，又省去泛型传染与虚表跳转开销；更换一套实现即可跨内核复用或运行宿主机单测。"
    )
    add_rect(s6, 1.12, 2.86, 24.43, 3.85, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.5, rounded=True, radius=0.05)
    add_textbox(s6, 1.45, 3.03, 23.77, 0.42, "编译期单向依赖关系（箭头同向流动，无反向引用环）", size=22, color=DARK_NAVY, bold=True)
    dependencies = [
        ("操作系统运行层", "向下选用网卡等硬件驱动\n提供内存映射等底层能力实现", BRAND_BLUE),
        ("跨内核网卡驱动", "只调公共接口请求地址映射\n不反向依赖任何具体内核", AMBER_ORG),
        ("中立接口包 + 过程宏", "只声明统一的能力契约\n编译期自动展开 FFI 调用与导出", SAFE_GREEN),
    ]
    for index, (title, detail, color) in enumerate(dependencies):
        x = 1.45 + index * 8.55
        add_card(s6, x, 3.62, 6.67, 2.76, title=title, accent=color, fill=WHITE, border=color, title_size=24, header_band=True)
        add_textbox(s6, x + 0.18, 4.38, 6.31, 1.72, detail, size=21, color=DARK_NAVY, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        if index < len(dependencies) - 1:
            add_arrow(s6, x + 7.02, 4.82, 1.22, 0.62, "right", color)

    add_card(s6, 1.12, 6.96, 11.40, 4.52, title="一处定义契约、过程宏展开 FFI、链接期合拢", accent=DARK_NAVY, fill=WHITE, border=BORDER_BLU, title_size=24, header_band=True)
    binding_steps = [
        ("1. 生成 FFI 两端", "过程宏按一份 trait 契约，同时生成外部函数调用封装与导出规则。"),
        ("2. 校验并导出", "内核提供实现时先由编译器校验签名，再自动生成同名 FFI 导出函数。"),
        ("3. 跨包静态链接", "链接器按符号名将两端跨 crate 直连，无虚表跳转，支持跨包内联。"),
    ]
    for index, (label, detail) in enumerate(binding_steps):
        y = 7.82 + index * 1.18
        add_rect(s6, 1.38, y, 10.88, 1.02, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.0, rounded=True, radius=0.06)
        add_textbox(s6, 1.54, y, 2.52, 1.02, label, size=21, color=BRAND_BLUE, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s6, 4.14, y, 7.90, 1.02, detail, size=19.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s6, 12.82, 6.96, 12.73, 4.52, fill=CODE_BG, border=DARK_NAVY, border_pt=1.5, rounded=True, radius=0.05)
    add_textbox(s6, 13.10, 7.10, 12.15, 0.44, "三方角色示意（契约声明 · 驱动调用 · 内核实现）", size=21.5, color=CODE_KW, bold=True)
    add_rich_paragraphs(
        s6, 13.06, 7.62, 12.25, 3.68,
        [
            ([("// 1. 接口包 (axklib): 一处声明契约，过程宏生成两端 FFI 胶水", 19, CODE_CMT, False, FONT_MONO)], 3, PP_ALIGN.LEFT),
            ([("#[def_extern_trait]", 19.5, CODE_TYPE, True, FONT_MONO)], 2, PP_ALIGN.LEFT),
            ([("pub trait ", 19.5, CODE_KW, True, FONT_MONO), ("Klib ", 19.5, CODE_TYPE, True, FONT_MONO), ("{ fn mem_iomap(pa: PhysAddr, sz: usize) -> KlibResult<VirtAddr>; }", 18.5, CODE_FG, False, FONT_MONO)], 10, PP_ALIGN.LEFT),
            ([("// 2. 驱动侧: 像调用本地普通函数一样直接请求映射", 19, CODE_CMT, False, FONT_MONO)], 3, PP_ALIGN.LEFT),
            ([("let vaddr = axklib::mem::iomap(paddr, size)?;", 19.5, CODE_STR, True, FONT_MONO)], 10, PP_ALIGN.LEFT),
            ([("// 3. 内核或单测桩: 编译器校验签名后导出符号，链接期跨 crate 直连", 19, CODE_CMT, False, FONT_MONO)], 3, PP_ALIGN.LEFT),
            ([("impl_trait! { ", 19.5, CODE_TYPE, True, FONT_MONO), ("impl ", 19.5, CODE_KW, True, FONT_MONO), ("Klib ", 19.5, CODE_TYPE, True, FONT_MONO), ("for KlibImpl { ... } }", 19.5, CODE_FG, False, FONT_MONO)], 0, PP_ALIGN.LEFT),
        ],
        line_spacing=1.15
    )

    add_notes(
        s6,
        "依赖解耦：通过过程宏与 FFI 实现跨 crate 链接",
        "02 专用内核",
        1.9,
        """拿网卡驱动举例。驱动初始化时要读写硬件寄存器，必须请操作系统把设备的物理地址映射成虚拟地址。但从包依赖关系看，是操作系统往下选用网卡驱动；如果驱动反过来再去依赖具体内核的内存模块，两边就会形成循环依赖，这份驱动也无法给其他系统复用。

要解决这个反向依赖问题，常规做法要么逐层传递泛型参数，结果泛型约束会传染到驱动的每一层数据结构；要么传递虚表指针做运行时动态分发，又会带来间接跳转开销和初始化顺序问题。我们的思路，是借助类似 C 语言外部函数接口（FFI）的链接机制：由 Rust 过程宏把标准 trait 自动展开成配对的 FFI 外部函数声明与导出符号，在最终链接阶段完成跨 crate 绑定。

对照右下角的示例，操作系统和驱动都只单向依赖中间的纯接口包，整套机制分三步完成。第一步，在接口包里只写一份能力声明，过程宏在编译期自动展开出互相匹配的两端 FFI 代码：对驱动这一侧，把外部函数声明封装成普通的安全函数入口，驱动就像调用本地函数一样发起请求，既不需要接触底层裸指针，也不用背负层层传递泛型的负担；对操作系统这一侧，同时生成配套的导出规则，将符号名称、调用约定与参数类型统一固定在同一份契约里。

第二步，当操作系统提供自己的内存映射实现时，编译器会先按这份契约做严格的类型检查，参数或返回值稍有不一致就会在编译阶段直接报错；检查通过后，过程宏自动生成同名的 FFI 导出函数，省去了手工编写 C FFI 时两边签名容易脱节的隐患。第三步，在最终生成系统镜像时，链接器直接按符号名把驱动侧的调用和内核侧的实现跨 crate 静态链接到一起，漏提供实现或者重复提供实现都会在链接阶段报错拦截。整条调用路径没有虚表跳转开销，开启链接期优化后还能跨包直接内联；平时在开发机上测试驱动，只要链接一套测试桩实现，不用改动一行驱动代码就能直接运行单元测试。"""
    )

    # =========================================================================
    # SLIDE 7: 多架构共用流程
    # =========================================================================
    s7 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s7, False, "02 专用内核", BRAND_BLUE,
        "多架构复用：四种架构共用一套 vCPU 流程",
        "把通用流程写在 AxVM，硬件操作由构建时选定的架构后端提供",
        7, "共用流程",
        "修正 vCPU 的通用执行顺序时，只需要改一处。"
    )
    add_card(s7, 1.12, 2.84, 11.15, 8.65, title="从 QEMU 的多架构场景看起", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=27, header_band=True)
    add_textbox(
        s7, 1.46, 3.82, 10.46, 1.42,
        "QEMU 的 ARM 和 x86 整机目标要分别处理 CPU 与中断控制器。AxVisor 在硬件上运行客户机，也面对这类差异。",
        size=24, color=BODY_TEXT, line_spacing=1.2
    )
    add_rect(s7, 1.46, 5.40, 10.46, 2.13, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.2)
    add_textbox(s7, 1.71, 5.57, 9.96, 0.46, "各架构都要完成的工作", size=24, color=BRAND_BLUE, bold=True)
    add_textbox(s7, 1.71, 6.16, 9.96, 0.96, "调度 vCPU、进入客户机、退出后恢复宿主，再处理设备访问。", size=23, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)
    add_rect(s7, 1.46, 7.78, 10.46, 2.76, fill=AMBER_BG, border=AMBER_BORDER, border_pt=1.2)
    add_textbox(s7, 1.71, 7.98, 9.96, 0.46, "AxVM 怎么复用", size=24, color=AMBER_ORG, bold=True)
    add_textbox(s7, 1.71, 8.59, 9.96, 1.55, "通用执行器规定先后顺序。ArchOps 定义准备、写回和退出等硬件操作，编译时接到对应的后端。", size=23, color=DARK_NAVY, line_spacing=1.2)

    add_card(s7, 12.60, 2.84, 12.95, 8.65, title="一个 vCPU 跑一轮", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=27, header_band=True)
    vcpu_steps = [
        ("调度 vCPU", "把 vCPU 当宿主任务，由 ArceOS 调度。", BRAND_BLUE, ICE_FILL),
        ("进入客户机", "run_once 安排进入顺序，后端装载 CPU 状态。", AMBER_ORG, AMBER_BG),
        ("发生 VM-Exit", "卸载客户机硬件状态，恢复宿主执行环境。", ALERT_RED, RED_BG),
        ("处理退出", "ExitHandler 在任务上下文处理虚拟设备访问。", SAFE_GREEN, SAFE_BG),
    ]
    for index, (label, description, color, fill) in enumerate(vcpu_steps):
        y = 3.77 + index * 1.87
        add_rect(s7, 12.92, y, 12.31, 1.47, fill=fill, border=color, border_pt=1.3)
        add_textbox(s7, 13.13, y + 0.11, 11.89, 0.45, label, size=25, color=color, bold=True)
        add_textbox(s7, 13.13, y + 0.62, 11.89, 0.66, description, size=22, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)
        if index < len(vcpu_steps) - 1:
            add_arrow(s7, 18.88, y + 1.49, 0.38, 0.29, "down", color)

    add_notes(
        s7,
        "多架构复用：四种架构共用一套 vCPU 流程",
        "02 专用内核",
        1.6,
        """解决了驱动在不同内核之间的复用，到了虚拟化核心层 AxVM，还要面对另一重差异：跨处理器架构复用，同时支持 ARM64、x86-64、RISC-V 和 LoongArch。看左上角，就像 QEMU 整机模拟要分别处理各架构的 CPU 和中断控制器一样，AxVisor 直接跑在硬件上，各家的特权寄存器、页表和中断硬件也完全不同。要是四种架构各自写一套 vCPU 循环，改一次执行顺序就得同步改四处。

往上一层看，不管底层是什么芯片，让一个 vCPU 跑一轮，宿主在任务层要走的顺序其实是一样的。看右边四步：先由 ArceOS 把 vCPU 作为宿主任务调度到物理核上运行。接着通用执行器的 run_once 完成进入前准备、写回上次退出结果并注入待处理中断，再让后端装入客户机状态，进入物理 CPU 执行客户机指令。发生 VM-Exit 后，比如客户机写虚拟串口触发陷入，先卸载客户机硬件状态、恢复宿主环境。最后回到普通任务上下文，由 ExitHandler 调用虚拟设备完成处理。

左下角的 ArchOps 就是这一层找出来的最小共同接口。进出顺序只在通用执行器里维护一份，具体读写哪些寄存器由各架构实现，编译时直接绑定到目标后端。那再往下一层看，中断投递和 CPU 切换能不能也照这个办法合成一个统一接口？"""
    )

    # =========================================================================
    # SLIDE 8: 保留架构差异
    # =========================================================================
    s8 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s8, True, "02 专用内核", AMBER_ORG,
        "多架构差异：中断和 CPU 为什么要分开处理",
        "用同一套运行流程管理 vCPU，各后端按自己的硬件规则投递中断和切换状态",
        8, "架构调优",
        "中断的确认、完成与重新投递由后端掌握，按各自硬件的规则调优。"
    )
    irq_backends = [
        (1.12, "ARM64：GIC", BRAND_BLUE, ICE_FILL, BORDER_BLU, [
            ("中断投递", "用 GIC 的列表寄存器记录要交给客户机的虚拟中断。"),
            ("处理完成", "物理中断直通要区分应答、优先级下降和去激活。"),
            ("CPU 切换", "在 EL2 管理客户机寄存器和执行上下文。"),
        ]),
        (13.60, "x86-64：LAPIC / I/O APIC", AMBER_ORG, AMBER_BG, AMBER_BORDER, [
            ("中断投递", "I/O APIC 负责外设路由，目标 vCPU 的虚拟 LAPIC 接收向量。"),
            ("处理完成", "电平中断收到客户机 EOI 后，才决定是否继续投递。"),
            ("CPU 切换", "Intel VMX 和 AMD SVM 各有自己的控制状态和进出路径。"),
        ]),
    ]
    for x, title, color, fill, border, details in irq_backends:
        add_card(s8, x, 2.84, 11.95, 7.15, title=title, accent=color, fill=WHITE, border=border, title_size=27, header_band=True)
        for index, (label, description) in enumerate(details):
            y = 3.84 + index * 1.91
            add_rect(s8, x + 0.28, y, 11.39, 1.58, fill=fill, border=border, border_pt=1.0)
            add_textbox(s8, x + 0.49, y + 0.13, 10.97, 0.43, label, size=23, color=color, bold=True)
            add_textbox(s8, x + 0.49, y + 0.63, 10.97, 0.76, description, size=22, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s8, 1.12, 10.27, 24.43, 1.15, fill=DARK_NAVY, border=None)
    add_textbox(s8, 1.40, 10.36, 23.87, 0.97, "如果只留「向某个 vCPU 注入中断」这一句，控制器何时确认、何时可以再次投递，仍得由各架构自己处理。", size=23, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s8,
        "多架构差异：中断和 CPU 为什么要分开处理",
        "02 专用内核",
        1.7,
        """做多架构适配时很容易有个直觉：既然两边都要给客户机发中断，干脆在底层定一个统一接口，就叫「向某个 vCPU 注入中断」。对比左右两张卡片，就能看出为什么这一个简单接口无法覆盖底层的真实硬件行为。

先看左边 ARM64。宿主在 EL2 管理客户机上下文，虚拟中断要写进 GIC 的列表寄存器交给客户机；做物理中断直通时，一次中断还要区分宿主应答、优先级下降和客户机去激活三个阶段，状态一直由 GIC 这一侧维护。

再看右边 x86-64。外设中断先由 I/O APIC 路由成向量，再送给目标 vCPU 的虚拟 LAPIC；比如一条电平触发中断，必须等客户机写 EOI 通知处理结束，控制器才能决定要不要继续投递。单在 x86 内部，Intel VMX 和 AMD SVM 的控制状态和进出路径也是分开的。

这就是底下深色框说的意思：表面都叫发中断，但状态归谁管、什么时候确认完成、什么时候允许再次投递，底层硬件规则并不等价。如果在底层强行合并成一套状态机，要么迁就共同点、丢掉硬件原有的直通和加速能力，要么在通用代码里到处补架构分支。所以这一层我们保留差异，让各后端管好自己的中断状态机和 CPU 切换，按各自硬件独立调优。底层既然不能强行合并，那公共接口到底该定在哪一层？"""
    )

    # =========================================================================
    # SLIDE 9: 求同存异
    # =========================================================================
    s9 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s9, False, "02 专用内核", SAFE_GREEN,
        "求同存异：往上找共同的行为",
        "底层保留硬件规则，往上找到行为一致的一层，再把共用流程提出来",
        9, "分层边界",
        "共用层负责等与唤醒，后端判断本架构的事件是否就绪。"
    )
    add_card(s9, 1.12, 2.84, 11.72, 8.65, title="从硬件差异往上找", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=27, header_band=True)
    layers = [
        ("所有架构需要", "Architecture 组合运行、机器资源、客户机启动和镜像装载。", BRAND_BLUE, ICE_FILL),
        ("行为相同就共用", "vCPU 进入与退出的顺序共用一份，等待通知也共用一份。", SAFE_GREEN, SAFE_BG),
        ("只有部分架构需要", "ARM64 与 RISC-V 单独实现 CpuOn，并由编译器检查调用。", PURPLE, PURP_BG),
        ("硬件规则不同", "寄存器、GIC、APIC 等状态和操作留在架构后端。", AMBER_ORG, AMBER_BG),
    ]
    for index, (label, description, color, fill) in enumerate(layers):
        y = 3.86 + index * 1.78
        add_rect(s9, 1.48, y, 10.55, 1.49, fill=fill, border=color, border_pt=1.25)
        add_textbox(s9, 1.70, y + 0.10, 10.11, 0.45, label, size=24, color=color, bold=True)
        add_textbox(s9, 1.70, y + 0.61, 10.11, 0.72, description, size=21, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)
        if index < len(layers) - 1:
            add_arrow(s9, 12.22, y + 1.30, 0.34, 0.62, "up", DARK_NAVY)

    add_card(s9, 13.12, 2.84, 12.43, 8.65, title="例子：vCPU 刚要休眠时，中断到了", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=25, header_band=True)
    wait_parts = [
        ("各自判断事件", "ARM64 检查虚拟中断和计时器。x86 检查自己有没有待处理事件。", AMBER_ORG, AMBER_BG),
        ("共用等待和唤醒", "VcpuWait 把后端的检查接到宿主等待队列。通知会保留，唤醒后重新检查。", SAFE_GREEN, SAFE_BG),
        ("上层只看 vCPU 是否该继续", "调度和执行流程走共用路径，硬件怎么判断事件仍由后端决定。", BRAND_BLUE, ICE_FILL),
    ]
    for index, (label, description, color, fill) in enumerate(wait_parts):
        y = 3.86 + index * 2.36
        add_rect(s9, 13.45, y, 11.77, 2.01, fill=fill, border=color, border_pt=1.3)
        add_textbox(s9, 13.67, y + 0.13, 11.33, 0.46, label, size=24, color=color, bold=True)
        add_textbox(s9, 13.67, y + 0.66, 11.33, 1.12, description, size=22, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.16)

    add_notes(
        s9,
        "求同存异：往上找共同的行为",
        "02 专用内核",
        1.9,
        """如果先在顶层定一个大而全的接口让各个架构勉强适配，底下很容易塞满空实现和架构特判。我们的「求同存异」反过来做：从底层的硬件差异出发，一层一层往上找最小共同接口，走到哪一层行为真正一致了，才在哪一层提取共用逻辑。

先看左图，顺着箭头从下往上走。最底下，寄存器、GIC、APIC 这些规则不同的操作留在架构后端。往上一层，遇到只有部分架构才有的能力，比如响应客户机唤醒从核的 CpuOn，只有 ARM64 和 RISC-V 需要处理；我们就单独拆成最小接口 CpuOn，只由具备能力的后端实现，其他架构不需要编写空实现来凑齐接口，发生误调用时编译期会直接报错。再往上，进出顺序、等待唤醒这些行为一致的流程只维护一份，后端只暴露最小的配合接口。到了最顶层，Architecture 组合所有架构都具备的运行、机器资源、客户机启动和镜像装载四组最小接口，编译时绑定后端，通用代码不再写架构分支。

右边的 VcpuWait 就是具体例子。vCPU 正要休眠时，如果刚检查完没有待处理事件、还没真正进入休眠时中断恰好到达，一旦漏掉这次唤醒通知，vCPU 就会一直卡在休眠状态。看右上第一格，ARM64 查虚拟中断和计时器，x86 查自己的待处理事件，底层的判断逻辑无法直接统一；但往上提一步，后端只需暴露一个最小接口，回答当前有没有事件就绪。中间的 VcpuWait 把这项检查接到宿主等待队列，保留休眠前后的唤醒通知，醒来再复查，这套防丢唤醒流程四种架构共用一份。最下面的调度和执行层只看 vCPU 该不该继续运行。到这里，跨架构的裸机宿主底座就搭稳了。但平时在板卡上管理多台虚拟机，总不能只靠一根串口线敲命令；要想直接在板卡上跑起网页管理台和远程终端，裸机宿主就得能用上成熟的应用层网络生态。"""
    )

    # =========================================================================
    # SLIDE 10: Rust 标准库与 Web 实拍
    # =========================================================================
    s10 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s10, True, "03 内核态 std", BRAND_BLUE,
        "宿主运行 Rust 标准库：Web 管理台与终端",
        "ax-std 将宿主的线程和网络能力接到 Rust 标准库，管理服务直接跑在板卡上",
        10, "管理服务",
        "宿主运行 Tokio 和 Axum，客户机拥有各自的系统与串口。"
    )
    service_steps = [
        ("宿主能力", "ArceOS 底座提供线程和网络。", BRAND_BLUE),
        ("接上 Rust 标准库", "ax-std 给标准库提供所需的宿主接口。", SAFE_GREEN),
        ("网页与终端", "Tokio 和 Axum 在宿主线程里处理请求。", PURPLE),
    ]
    for index, (label, description, color) in enumerate(service_steps):
        x = 1.12 + index * 8.28
        add_card(s10, x, 2.82, 7.86, 1.85, title=label, accent=color, fill=WHITE, border=BORDER_BLU, title_size=23)
        add_textbox(s10, x + 0.24, 3.50, 7.38, 0.89, description, size=21, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    screenshots = [
        (1.12, media["web_ui"], "Web 管理台：查看客户机状态、内存和 vCPU", BRAND_BLUE),
        (13.68, media["web_term"], "浏览器终端：通过 WebSocket 连接客户机串口", SAFE_GREEN),
    ]
    for x, blob, caption, color in screenshots:
        add_rect(s10, x, 4.86, 11.87, 6.68, fill=WHITE, border=color, border_pt=1.6, rounded=True, radius=0.03)
        add_picture_fit(s10, blob, x + 0.14, 4.95, 11.59, 5.75, frame_border=None, pad=0.04)
        add_textbox(s10, x + 0.12, 10.80, 11.63, 0.62, caption, size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s10,
        "宿主运行 Rust 标准库：Web 管理台与终端",
        "03 内核态 std",
        1.5,
        """比如在浏览器点一下「启动客户机」，AxVisor 要接收网络请求、找到客户机配置，再把结果返回给浏览器。我们希望能直接复用 Tokio 和 Axum，它们所需的线程和网络接口在这里由宿主内核直接提供。

上方三格展示了接入方式。ArceOS 底座提供线程和网络，ax-std 把这些能力对接到 Rust 标准库，Tokio 和 Axum 就能在宿主的管理线程里运行。左边的实拍可以查看 Linux 客户机状态、内存和虚拟核，右边通过 WebSocket 连接客户机串口，实时查看启动输出。

处理网页请求的也是宿主线程。如果把电机控制任务也放到宿主里，这两类任务对调度的要求就完全不同了。"""
    )

    # =========================================================================
    # SLIDE 11: 宿主即实时内核——实时调度与四级显式锁
    # =========================================================================
    s11 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s11, True, "04 实时内核", AMBER_ORG,
        "宿主即实时内核：实时调度与四级显式锁",
        "AxVisor 宿主机本身基于 ArceOS 实时内核构建，对延迟敏感的任务可直接运行在宿主态，免去虚拟化转发",
        11, "实时调度",
        "Hypervisor 自带 Deadline/RT 调度与 PI 锁，与硬件隔离 Linux 客户机协同部署。"
    )
    add_card(s11, 1.12, 2.84, 12.60, 8.65, title="混合关键性部署：实时任务的位置差异", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=26, header_band=True)

    add_rect(s11, 1.42, 3.76, 12.00, 3.00, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.5, rounded=True, radius=0.06)
    add_textbox(s11, 1.62, 3.84, 11.60, 0.44, "部署位置一：在 RTOS 客户机里运行实时任务", size=22, color=SLATE_DARK, bold=True)
    add_rect(s11, 1.72, 4.40, 5.20, 1.05, fill=WHITE, border=GRAY_BORDER, border_pt=1.2, rounded=True, radius=0.06)
    add_textbox(s11, 1.82, 4.44, 5.00, 0.96, "Guest A：复杂 Linux\n（AI / 视觉 / 界面）", size=21, color=BODY_TEXT, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_rect(s11, 7.62, 4.40, 5.50, 1.05, fill=RED_BG, border=ALERT_RED, border_pt=1.4, rounded=True, radius=0.06)
    add_textbox(s11, 7.72, 4.44, 5.30, 0.96, "Guest B：实时 RTOS\n由客户机接收设备中断", size=21, color=ALERT_RED, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_rect(s11, 1.72, 5.64, 11.40, 0.90, fill=SLATE_DARK, border=None, rounded=True, radius=0.06)
    add_textbox(s11, 1.82, 5.68, 11.20, 0.82, "虚拟机管理器负责分配硬件资源和处理客户机中断", size=21, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s11, 1.42, 7.00, 12.00, 4.24, fill=AMBER_BG, border=AMBER_ORG, border_pt=2.2, rounded=True, radius=0.06)
    add_textbox(s11, 1.62, 7.08, 11.60, 0.44, "AxVisor 混合部署：宿主运行实时任务 + 硬件隔离 Linux 客户机", size=23, color=AMBER_ORG, bold=True)
    add_rect(s11, 1.72, 7.66, 5.45, 1.68, fill=WHITE, border=SAFE_GREEN, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(s11, 1.84, 7.72, 5.21, 1.56, "硬件隔离客户机（Guest）\nLinux / StarryOS / Zephyr\n按各自配置分配和使用资源", size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)
    add_rect(s11, 7.42, 7.66, 5.70, 1.68, fill=SAFE_GREEN, border=None, rounded=True, radius=0.06)
    add_textbox(s11, 7.54, 7.72, 5.46, 1.56, "宿主内核直接运行实时任务\n硬件中断直达、无虚拟化转发\n可直接使用 Rust std 与网络栈", size=21, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.20)
    add_rect(s11, 1.72, 9.54, 11.40, 1.44, fill=DARK_NAVY, border=None, rounded=True, radius=0.06)
    add_textbox(s11, 1.84, 9.60, 11.16, 1.32, "AxVisor 宿主 = ArceOS 实时底座（实时调度 + std）+ 17 个虚拟化 crate\n实时控制与管控面运行在宿主态  ·  复杂通用负载运行在隔离客户机", size=20, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.26)

    add_card(s11, 14.04, 2.84, 11.51, 4.10, title="调度策略：三类实时与通用调度（components/ax-task）", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=24, header_band=True)
    sched_rows = [
        ("Deadline 调度（EDF / CBS）", "最高优先级（Rank 1），按绝对截止期与时间预算调度周期性实时任务", ALERT_RED, RED_BG),
        ("Real-Time 调度（POSIX 1..99）", "优先级 Rank 2，支持 FIFO 与时间片轮转（RR）抢占式调度", AMBER_ORG, AMBER_BG),
        ("Fair 公平调度（Nice -20..19）", "支持 Normal / Batch / Idle 模式，承接管理服务与普通 vCPU 负载", BRAND_BLUE, ICE_FILL),
    ]
    for si, (st, sd, sc, sb) in enumerate(sched_rows):
        sy = 3.74 + si * 1.02
        add_rect(s11, 14.32, sy, 10.95, 0.88, fill=sb, border=sc, border_pt=1.2, rounded=True, radius=0.06)
        add_textbox(s11, 14.48, sy + 0.04, 4.15, 0.80, st, size=19.5, color=sc, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s11, 18.68, sy + 0.04, 6.46, 0.80, sd, size=18.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE)

    add_card(s11, 14.04, 7.14, 11.51, 4.35, title="锁机制：对标 Linux PREEMPT_RT 的四级显式锁", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=24, header_band=True)
    lock_rows = [
        ("Mutex / RwSem（优先级继承）", "等待锁时，持锁任务可临时继承等待者的优先级"),
        ("RtSpinLock / RtSpinRwLock", "竞争时允许睡眠并约束持锁迁移，避免关抢占拖长响应延迟"),
        ("RawSpinLock（lock / irqsave）", "用于不可睡眠短临界区，禁抢占或保存并恢复局部中断状态"),
        ("LocalLock + 内置 lockdep", "每核本地隔离，配合 lockdep 在运行期检测锁依赖环"),
    ]
    for li, (lt, ld) in enumerate(lock_rows):
        ly = 8.02 + li * 0.84
        add_rect(s11, 14.32, ly, 10.95, 0.72, fill=LIGHT_GRAY if li % 2 else SAFE_BG, border=GRAY_BORDER, border_pt=1.0, rounded=True, radius=0.05)
        add_textbox(s11, 14.48, ly + 0.04, 4.25, 0.64, lt, size=18.5, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s11, 18.78, ly + 0.04, 6.36, 0.64, ld, size=18.5, color=BODY_TEXT, bold=False, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s11,
        "宿主即实时内核：实时调度与四级显式锁",
        "04 实时内核",
        1.7,
        """网页晚一点响应，用户多等一会儿。电机控制晚一个周期，就可能错过发指令的时机。视觉识别可以在 Linux 客户机里跑，电机控制放在哪儿，才能按时拿到 CPU 和设备中断？

看左图，上方做法是让实时客户机来运行电机控制，由它接收设备中断、调度控制任务。下方则是 AxVisor 支持的混合部署方式：视觉应用继续在隔离的 Linux 客户机里运行，电机控制直接交给宿主。如果控制设备由宿主直接管理，宿主就能直接处理硬件中断，省掉向客户机转发这一步。

右上角是 ArceOS 的调度器。像周期性的电机控制，可以用 Deadline 按截止时间和运行预算安排。需要固定优先级的任务用 RT，网页管理和普通 vCPU 可以用公平调度。

排上 CPU 之后，任务也可能卡在锁上。比如控制任务要用的锁还在低优先级任务手里，右下角的优先级继承会临时提高持锁任务的优先级，让它尽快运行并释放锁。普通线程、中断处理和只访问本核数据的代码，各用适合的锁。控制任务和客户机的 vCPU 都由宿主调度。至于串口、网卡这些设备该归宿主还是客户机，还要把资源和访问权限划清楚。"""
    )

    # =========================================================================
    # SLIDE 12: 安全边界——三级隔离与最小 unsafe 边界
    # =========================================================================
    s12 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s12, True, "05 声明式设备图", SAFE_GREEN,
        "安全边界：硬件操作与上层逻辑",
        "将页表、寄存器和硬件切换操作封装在底层接口，上层组件通过接口访问资源",
        12, "审计边界",
        "集中检查硬件访问所用的地址、长度与权限，并在上层校验配置和设备请求。"
    )
    add_card(s12, 1.12, 2.84, 12.60, 8.65, title="AxVisor 安全边界分层", accent=DARK_NAVY, fill=WHITE, border=BORDER_BLU, title_size=26, header_band=True)

    add_rect(s12, 1.44, 3.80, 11.96, 2.15, fill=SAFE_BG, border=SAFE_GREEN, border_pt=2.0, rounded=True, radius=0.06)
    add_rect(s12, 1.66, 4.02, 3.60, 1.71, fill=SAFE_GREEN, border=None, rounded=True, radius=0.08)
    add_textbox(s12, 1.72, 4.06, 3.48, 1.63, "第三层\n宿主服务\n（内核态 ax-std）", size=22, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s12, 5.46, 3.96, 7.72, 1.84,
        "• Web 控制面（Axum / Tokio）、Shell、配置池、ConsoleMux\n"
        "• 宿主业务基于 Safe Rust 与标准库 std::sync 编写\n"
        "• 不直接触碰硬件寄存器或裸页表指针",
        size=21, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    add_rect(s12, 1.44, 6.20, 11.96, 2.25, fill=ICE_FILL, border=BRAND_BLUE, border_pt=2.0, rounded=True, radius=0.06)
    add_rect(s12, 1.66, 6.42, 3.60, 1.81, fill=BRAND_BLUE, border=None, rounded=True, radius=0.08)
    add_textbox(s12, 1.72, 6.46, 3.48, 1.73, "第二层\n内核组件\n（虚拟化与驱动）", size=22, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s12, 5.46, 6.34, 7.72, 1.98,
        "• ax-runtime、ax-task 实时调度与锁，81 个跨内核驱动\n"
        "• axdevice 设备图与运行时、VirtIO 设备、vGIC / vPLIC\n"
        "• 由借用检查器与强类型物理/虚拟地址类型约束边界",
        size=21, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    add_rect(s12, 1.44, 8.60, 11.96, 0.44, fill=ALERT_RED, border=None, rounded=True, radius=0.25)
    add_textbox(
        s12, 1.54, 8.60, 11.76, 0.44,
        "▲  上层使用类型化接口   |   ▼  底层封装硬件访问",
        size=20, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE
    )

    add_rect(s12, 1.44, 9.18, 11.96, 2.02, fill=RED_BG, border=ALERT_RED, border_pt=2.0, rounded=True, radius=0.06)
    add_rect(s12, 1.66, 9.38, 3.60, 1.62, fill=ALERT_RED, border=None, rounded=True, radius=0.08)
    add_textbox(s12, 1.72, 9.42, 3.48, 1.54, "第一层\n硬件访问层", size=22, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s12, 5.46, 9.32, 7.72, 1.74,
        "• axcpu / someboot：汇编上下文切换与硬件虚拟化陷入\n"
        "• mmio-api / dma-api / axaddrspace：寄存器与二阶段页表\n"
        "• 集中检查硬件访问与接口约定",
        size=21, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    add_card(s12, 14.04, 2.84, 11.51, 8.65, title="虚拟化实现包的 src 源码统计", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=26, header_band=True)

    add_rect(s12, 14.34, 3.78, 10.91, 1.48, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(s12, 14.54, 3.86, 4.10, 1.32, "9 / 16", size=60, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s12, 18.70, 3.90, 6.35, 1.24,
        "16 个虚拟化实现包中，9 个\n在 src 源码里使用 0 处 unsafe",
        size=24, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    audit_rows = [
        ("axdevice + axdevice_base\n(设备图 / 运行期 / 授权)", "27,636 行", "0 处 unsafe", "设备模拟与授权", SAFE_GREEN),
        ("aarch64_sysreg\n(ARM64 虚拟系统寄存器)", "12,735 行", "0 处 unsafe", "寄存器解码", SAFE_GREEN),
        ("axvirtio-common / blk / net\n(VirtIO 块与网络协议)", "12,646 行", "0 处 unsafe", "队列与协议解析", SAFE_GREEN),
        ("axvmconfig / axvm-types\n+ riscv_vplic", "2,792 行", "0 处 unsafe", "配置与虚拟中断", SAFE_GREEN),
        ("axvm / axaddrspace / riscv-h 等\n(7 个含 unsafe 的实现包)", "底层接口", "含 unsafe", "包括页表和进出客户机", ALERT_RED),
    ]
    for ai, (aname, aloc, abadge, adesc, acol) in enumerate(audit_rows):
        ay = 5.44 + ai * 1.16
        add_rect(s12, 14.34, ay, 10.91, 1.02, fill=LIGHT_GRAY if ai < 4 else RED_BG, border=GRAY_BORDER if ai < 4 else RED_BORDER, border_pt=1.0, rounded=True, radius=0.05)
        add_textbox(s12, 14.52, ay + 0.06, 4.55, 0.90, aname, size=20, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s12, 19.05, ay + 0.12, 1.65, 0.78, aloc, size=20, color=MUTED_TEXT, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_rect(s12, 20.80, ay + 0.22, 2.05, 0.56, fill=acol, border=None, rounded=True, radius=0.16)
        add_textbox(s12, 20.80, ay + 0.22, 2.05, 0.56, abadge, size=20, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s12, 22.95, ay + 0.08, 2.22, 0.86, adesc, size=18, color=BODY_TEXT, bold=False, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s12,
        "安全边界：硬件操作与上层逻辑",
        "05 声明式设备图",
        1.1,
        """客户机一旦开始访问外设，就会碰到宿主的权限边界。比如客户机往虚拟串口写一个字节，CPU 把控制权交回宿主。底层负责切换寄存器和执行上下文，上层负责找到串口、判断这次访问允许做什么。

左图从下往上看。寄存器操作和地址转换封装在底层硬件接口，虚拟化组件通过接口管理资源，网页和命令行再通过管理接口操作客户机。右边是这版源码的统计，设备图、VirtIO 队列和配置校验等 9 个实现包的 src 里没有 unsafe。

设备能访问哪些地址，在处理请求之前就得定好。就拿这个虚拟串口来说，给宿主和客户机的地址要对得上。"""
    )

    # =========================================================================
    # SLIDE 13: 设备规划与授权
    # =========================================================================
    s13 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s13, False, "05 声明式设备图", PURPLE,
        "声明式设备图：地址怎么分，权限怎么给",
        "设备图统一分配地址和中断号，设备在运行时按请求获得访问权限",
        13, "设备边界",
        "客户机和宿主使用同一份资源分配结果，设备按次访问获准的资源。"
    )
    device_steps = [
        ("为客户机分配设备", "配置声明虚拟串口、磁盘等设备。设备规划器分配地址和中断号，并检查资源冲突。", "设备配置\n↓\nResolvedDeviceGraph", BRAND_BLUE, ICE_FILL, BORDER_BLU),
        ("一份设备图，两种输出", "宿主按地址查模拟设备。客户机从设备树或 ACPI 表读取地址和中断号。", "一份设备图\n↓\n宿主路由表 + 客户机固件", PURPLE, PURP_BG, PURP_BORDER),
        ("按请求给设备权限", "虚拟磁盘写回数据时，只能在回调期间按已登记的权限借用客户机内存。", "设备请求\n↓\nGrant 与临时访问入口", SAFE_GREEN, SAFE_BG, SAFE_BORDER),
    ]
    for index, (label, description, flow, color, fill, border) in enumerate(device_steps):
        x = 1.12 + index * 8.28
        add_card(s13, x, 2.84, 7.86, 6.29, title=label, accent=color, fill=WHITE, border=border, title_size=25, header_band=True)
        add_textbox(s13, x + 0.29, 3.86, 7.28, 1.94, description, size=23, color=BODY_TEXT, line_spacing=1.2)
        add_rect(s13, x + 0.29, 6.02, 7.28, 2.76, fill=fill, border=border, border_pt=1.1)
        add_textbox(s13, x + 0.43, 6.30, 7.00, 2.20, flow, size=23, color=color, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s13, 1.12, 9.41, 24.43, 1.97, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.2)
    add_textbox(s13, 1.43, 9.52, 23.81, 0.43, "需要直通或协作时", size=23, color=BRAND_BLUE, bold=True)
    add_textbox(s13, 1.43, 10.05, 23.81, 1.02, "设备中断可直通给客户机。客户机之间也可以通过共享内存交换数据，再通知对方读取。", size=22, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s13,
        "声明式设备图：地址怎么分，权限怎么给",
        "05 声明式设备图",
        1.6,
        """给 Linux 客户机加一个虚拟串口，Linux 启动时要从设备树或 ACPI 表拿到地址和中断号。要是宿主改了地址，客户机拿到的清单却没改，串口就可能找不到。

看左边和中间。配置里声明需要哪些设备，AxVisor 统一分配地址和中断号并检查资源冲突，再用同一份设备图生成宿主查找模拟设备所用的路由表，以及客户机的固件描述。Linux 往这个地址写入数据时，宿主就能把请求准确分发给对应的虚拟串口。

右边是运行时的权限。比如虚拟磁盘要把读到的数据写回客户机内存，AxVisor 按这次请求借给它一个入口，回调结束就收回来。需要客户机直接接收设备中断时，可以走中断直通。机器人里的视觉和控制系统要交换结果，也可以用共享内存加通知。到了实机上，除了虚拟设备，还要安排摄像头、串口和管理网卡这些物理设备。"""
    )

    # =========================================================================
    # SLIDE 14: 实机部署——RK3588 多客户机混合运行案例
    # =========================================================================
    s14 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s14, False, "06 实机与验证", AMBER_ORG,
        "实机部署：RK3588 多客户机混合运行案例",
        "基于 Orange Pi 5 Plus (RK3588) 的两套实机部署验证：大小核设备直通双系统与全虚拟化三系统",
        14, "实机部署",
        "大核承载视觉与 AI 推理，小核承载实时底盘控制，宿主管理物理网络与多路终端，按硬件边界隔离外设。"
    )
    add_card(s14, 1.12, 2.84, 11.95, 6.72, title="案例一：大小核设备直通双客户机（dual-linux-zephyr / dual-starry-zephyr）", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=22.5, header_band=True)
    add_textbox(s14, 1.38, 3.64, 11.43, 0.42, "目标板卡：Orange Pi 5 Plus (RK3588)，大核负责视觉感知，小核负责实时底盘控制", size=20, color=AMBER_ORG, bold=True)

    add_rect(s14, 1.38, 4.18, 5.10, 2.66, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.6, rounded=True, radius=0.06)
    add_textbox(s14, 1.54, 4.26, 4.78, 0.46, "A76 大核 · Linux / StarryOS", size=21, color=BRAND_BLUE, bold=True, align=PP_ALIGN.CENTER)
    add_textbox(
        s14, 1.52, 4.76, 4.82, 1.98,
        "• 直通 USB3 摄像头（/usbdrd3_1）\n"
        "• 调用 RKNPU 运行视觉推理\n"
        "• 剔除宿主 PCIe PHY 与 USB0\n"
        "  避免误复位宿主管理网卡",
        size=18.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18
    )

    add_arrow(s14, 6.62, 5.16, 0.96, 0.56, "lr", SAFE_GREEN)
    add_textbox(s14, 6.42, 5.76, 1.36, 0.72, "robot-ivc\n共享通道", size=18, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER)

    add_rect(s14, 7.72, 4.18, 5.08, 2.66, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.6, rounded=True, radius=0.06)
    add_textbox(s14, 7.88, 4.26, 4.76, 0.46, "A55 小核 · Zephyr 实时控制", size=21, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER)
    add_textbox(
        s14, 7.86, 4.76, 4.80, 1.98,
        "• 独占物理 UART6 (/serial@feb90000)\n"
        "• 驱动底盘、机械臂与看门狗\n"
        "• 与 Linux 视觉系统硬件隔离，\n"
        "  外设所有权边界清晰",
        size=18.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18
    )

    add_rect(s14, 1.38, 7.00, 11.42, 2.30, fill=DARK_NAVY, border=None, rounded=True, radius=0.06)
    add_textbox(
        s14, 1.58, 7.08, 11.02, 2.14,
        "AxVisor 宿主（持有共享硬件与管控通道）\n"
        "• 保留物理管理串口与 RTL8125 物理网卡（经 PCIe 接入管理网络）\n"
        "• 对外输出三路独立 WebSocket 终端：同时观察 AxVisor + Linux + Zephyr",
        size=20, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.26
    )

    add_card(s14, 13.60, 2.84, 11.95, 6.72, title="案例二：单芯三客户机全虚拟化（triple-guest-functional）", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=22.5, header_band=True)
    add_textbox(s14, 13.86, 3.64, 11.43, 0.42, "目标板卡：Orange Pi 5 Plus (RK3588)，同时启动三个全虚拟化 Guest（无外设直通）", size=20, color=BRAND_BLUE, bold=True)

    guests3 = [
        ("Guest 1：Linux 6.1.99", "virtio-blk 独立根盘\nvirtio-net 接入交换机\n完成离线 apt-get 安装", SAFE_GREEN, SAFE_BG),
        ("Guest 2：StarryOS", "本仓构建 Rust 宏内核\n独立 ext4 根盘 + virtio-net\n同样通过 apt-get 校验", BRAND_BLUE, ICE_FILL),
        ("Guest 3：Zephyr", "合成 vGIC + 虚拟串口\n独立 Shell 交互校验\n三客户机并发在线", PURPLE, PURP_BG),
    ]
    for gi, (gt, gd, gc, gb) in enumerate(guests3):
        gx = 13.86 + gi * 3.84
        add_rect(s14, gx, 4.18, 3.66, 2.66, fill=gb, border=gc, border_pt=1.6, rounded=True, radius=0.06)
        add_rect(s14, gx + 0.12, 4.30, 3.42, 0.54, fill=gc, border=None, rounded=True, radius=0.10)
        add_textbox(s14, gx + 0.16, 4.30, 3.34, 0.54, gt, size=19, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s14, gx + 0.14, 4.96, 3.38, 1.76, gd, size=19, color=DARK_NAVY, bold=False, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.20)

    add_rect(s14, 13.86, 7.00, 11.42, 2.30, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(
        s14, 14.06, 7.08, 11.02, 2.14,
        "AxVisor 宿主内建二层虚拟交换机 + 统一存储/网络归属\n"
        "• 宿主独占 eMMC 根文件系统与物理 RTL8125 网卡\n"
        "• Linux 与 StarryOS 的 virtio-net 经宿主二层交换机统一接入局域网并互通",
        size=20, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.26
    )

    add_rect(s14, 1.12, 9.76, 12.10, 1.72, fill=AMBER_BG, border=AMBER_BORDER, border_pt=1.4, rounded=True, radius=0.06)
    add_textbox(s14, 1.34, 9.84, 11.66, 0.44, "已覆盖 7 款实体板卡/主机 + 4 架构 QEMU（configs/board/）", size=21, color=AMBER_ORG, bold=True)
    add_textbox(s14, 1.34, 10.30, 11.66, 1.08, "Orange Pi 5 Plus (RK3588) · 飞腾派 (E2000) · ROC-RK3568-PC · RDK-S100 · Rock 4D · TAC-E400 · ASUS NUC15CRH (x86_64)", size=20, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22)

    add_rect(s14, 13.45, 9.76, 12.10, 1.72, fill=SAFE_BG, border=SAFE_BORDER, border_pt=1.4, rounded=True, radius=0.06)
    add_textbox(s14, 13.67, 9.84, 11.66, 0.44, "已适配 6 种客户机系统 · 共 62 份 VM 配置（configs/vms/）", size=21, color=SAFE_GREEN, bold=True)
    add_textbox(s14, 13.67, 10.30, 11.66, 1.08, "Linux · ArceOS · StarryOS · Zephyr · FreeRTOS · RT-Thread\n支持单核 / SMP 多核 · 全虚拟化与设备直通混合配置", size=20, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22)

    add_notes(
        s14,
        "实机部署：RK3588 多客户机混合运行案例",
        "06 实机与验证",
        1.6,
        """把视觉和控制装到同一块 Orange Pi 5 Plus 上，摄像头要给视觉系统，控制串口要给实时系统，管理网卡还得留给宿主。设备之间有共享的硬件依赖，分配时得一起看。

左图里，Linux 或 StarryOS 客户机用摄像头和 NPU 做感知，再通过共享内存把结果发给 Zephyr。Zephyr 独占一个串口，用它给底盘和机械臂发指令。管理网卡依赖的 PCIe PHY 如果也暴露给客户机，客户机重置它时，宿主网页就可能断线。所以配置把管理网卡和它依赖的那部分硬件都留给宿主。

右边是同一款板子的另一种配置。Linux、StarryOS 和 Zephyr 同时运行，实体网卡和存储归宿主。Linux 和 StarryOS 各用自己的虚拟磁盘，通过宿主里的虚拟交换机联网。左边检验直通设备和跨机通信，右边检验多台客户机一起运行时的存储、网络和串口。机器人这组用例上板以后，具体跑到了哪一步？"""
    )

    # =========================================================================
    # SLIDE 15: 机器人实板结果
    # =========================================================================
    s15 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s15, True, "06 实机与验证", AMBER_ORG,
        "实机结果：机器人双客户机验证",
        "Orange Pi 5 Plus（RK3588） · 2026 年 9 月 21 日实板记录",
        15, "验证结果",
        "两组配置都完成了真实感知负载、跨客户机传输和受控反馈检查。"
    )

    add_card(s15, 1.12, 2.84, 12.12, 8.65, title="板子上实际跑了什么", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=26, header_band=True)
    stages = [
        ("摄像头和 NPU", "Linux 或 StarryOS 客户机采集画面并运行推理。", BRAND_BLUE, ICE_FILL),
        ("跨客户机通信", "感知和控制系统通过共享内存通道交换数据。", SAFE_GREEN, SAFE_BG),
        ("控制反馈", "Zephyr 处理受控动作并返回结果，测试结束后清理资源。", AMBER_ORG, AMBER_BG),
    ]
    for index, (label, detail, color, fill) in enumerate(stages):
        y = 3.84 + index * 2.36
        add_rect(s15, 1.44, y, 11.48, 1.86, fill=fill, border=color, border_pt=1.4)
        add_textbox(s15, 1.69, y + 0.17, 10.98, 0.53, label, size=24, color=color, bold=True)
        add_textbox(s15, 1.69, y + 0.77, 10.98, 0.87, detail, size=23, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)
        if index < len(stages) - 1:
            add_arrow(s15, 6.95, y + 1.92, 0.46, 0.35, "down", color)

    add_card(s15, 13.60, 2.84, 11.95, 8.65, title="两段采样的感知帧率", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=26, header_band=True)
    measurements = [
        ("Linux + Zephyr", "29.94 / 29.99 FPS", BRAND_BLUE, ICE_FILL),
        ("StarryOS + Zephyr", "29.47 / 30.02 FPS", SAFE_GREEN, SAFE_BG),
    ]
    for index, (label, values, color, fill) in enumerate(measurements):
        y = 3.89 + index * 1.75
        add_rect(s15, 13.94, y, 11.27, 1.46, fill=fill, border=color, border_pt=1.4)
        add_textbox(s15, 14.14, y + 0.10, 5.50, 1.26, label, size=26, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s15, 19.62, y + 0.10, 5.34, 1.26, values, size=29, color=color, bold=True, align=PP_ALIGN.RIGHT, valign=MSO_ANCHOR.MIDDLE)

    add_textbox(s15, 14.15, 7.53, 10.78, 0.82, "两组均记录 IVC 丢帧 0，并完成控制反馈与清理。", size=22, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE)
    add_rect(s15, 13.94, 8.49, 11.27, 1.61, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.0)
    add_textbox(s15, 14.15, 8.62, 10.78, 1.34, "控制阶段使用预设识别结果，夹持反馈允许模拟。", size=22, color=BODY_TEXT, valign=MSO_ANCHOR.MIDDLE)
    source = add_textbox(s15, 14.13, 10.43, 10.88, 0.55, "来源：TGOSKits 2026 年 9 月月报 §2.7（PR #2314）", size=19, color=BRAND_BLUE, valign=MSO_ANCHOR.MIDDLE)
    source.text_frame.paragraphs[0].runs[0].hyperlink.address = (
        "https://github.com/rcore-os/tgoskits/blob/a28226c70077f5120b9ab05ed44e2bf498811e6a/"
        "docs/blog/2026/10-01-september-2026-retrospective/september-2026-retrospective.md#L125-L134"
    )

    add_notes(
        s15,
        "实机结果：机器人双客户机验证",
        "06 实机与验证",
        1.5,
        """9 月 21 日，我们用两种配置在 RK3588 板子上跑了测试。前半段用真实的摄像头和 NPU 跑感知负载，后半段经共享内存给 Zephyr 送预设的识别结果，检查控制端能不能处理并返回反馈。

看右边的感知帧率。用 Linux 时，两段采样分别是 29.94 和 29.99 帧每秒。换成 StarryOS，分别是 29.47 和 30.02 帧每秒。两组都记录到跨客户机通道没有丢帧，最后完成了控制反馈和清理。控制阶段允许模拟夹持，所以这里测的是两个系统能不能交换结果、走完控制流程。

这是当时的实测记录，双客户机机器人用例之后曾暂停自动检查。单次上板跑通只是第一步，日常改完代码怎么防止把已有的多客户机功能改坏，还得靠自动化测试持续回归。"""
    )

    # =========================================================================
    # SLIDE 16: 测试与验证——宿主机单测与实机测试集群
    # =========================================================================
    s16 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s16, True, "06 实机与验证", SAFE_GREEN,
        "测试与验证：宿主机单测与实机测试集群",
        "先在开发机通过 Rust std 单元测试拦截逻辑错误，再由 QEMU 与远程实体板卡集群执行自动回归",
        16, "测试体系",
        "开发机先检查组件逻辑，QEMU 和板卡再验证启动、设备与多客户机协作。"
    )
    add_card(s16, 1.12, 2.84, 12.25, 3.00, title="第一级 · 宿主机 std 单元测试（cargo xtask test）", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=24, header_band=True)
    add_textbox(
        s16, 1.40, 3.70, 11.70, 1.98,
        "• 17 个虚拟化 crate 中已有 13 个接入 scripts/test/std_crates.csv（全仓共 78 个）\n"
        "• 无需启动 QEMU 或烧录板卡，开发机直接验证：设备资源冲突、VirtIO 队列状态机、vGIC 中断生命周期与锁边界\n"
        "• 在进入硬件测试前检查组件逻辑",
        size=20, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    add_card(s16, 1.12, 6.08, 12.25, 3.30, title="第二级 · QEMU 与 ostool-server 自动化实机回归", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=24, header_band=True)
    add_textbox(
        s16, 1.40, 6.94, 11.70, 2.28,
        "• test-suit/axvisor 维护 46 个常规 QEMU / 板卡测试 TOML（覆盖 AArch64 / x86_64 VMX & SVM / RISC-V / LoongArch）\n"
        "• 自研开源 ostool-server：网络继电器断电冷重启破除内核死锁，配合 TFTP / HTTP 无盘内存引导（无 SD 卡插拔与闪存磨损）\n"
        "• WebSocket 双向转发串口输出，按正则规则自动判定通过或超时失败",
        size=20, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    kpis = [
        ("13 / 17", "虚拟化 crate\n宿主机 std 单测", BRAND_BLUE, ICE_FILL),
        ("46 个", "AxVisor 常规\nQEMU / 实机用例", AMBER_ORG, AMBER_BG),
        ("19 台", "截图中的四架构\n实体开发板", SAFE_GREEN, SAFE_BG),
    ]
    for ki, (knum, klbl, kcol, kbg) in enumerate(kpis):
        kx = 1.12 + ki * 4.16
        add_rect(s16, kx, 9.64, 3.92, 1.84, fill=kbg, border=kcol, border_pt=1.8, rounded=True, radius=0.06)
        add_textbox(s16, kx + 0.14, 9.74, 3.64, 0.86, knum, size=42, color=kcol, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s16, kx + 0.14, 10.60, 3.64, 0.78, klbl, size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s16, 13.70, 2.84, 11.85, 4.30, fill=WHITE, border=BRAND_BLUE, border_pt=1.5, rounded=True, radius=0.04)
    add_picture_fit(s16, media["ostool_boards"], 13.86, 2.94, 11.53, 3.56, frame_border=GRAY_BORDER, pad=0.04)
    add_textbox(s16, 13.84, 6.56, 11.57, 0.48, "ostool-server 开发板列表：支持 U-Boot / HTTP Boot 自动分配租约与串口控制", size=18.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s16, 13.70, 7.34, 11.85, 4.14, fill=WHITE, border=PURPLE, border_pt=1.5, rounded=True, radius=0.04)
    add_picture_fit(s16, media["ostool_overview"], 13.86, 7.44, 11.53, 3.42, frame_border=GRAY_BORDER, pad=0.04)
    add_textbox(s16, 13.84, 10.92, 11.57, 0.48, "资源总览截图：19 台实体开发板（RK3588 / 飞腾派 / 龙芯 / x86 / SG2002）", size=18.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s16,
        "测试与验证：宿主机单测与实机测试集群",
        "06 实机与验证",
        1.5,
        """比如改了设备分配代码，Linux 还能启动，StarryOS 的网卡却可能用不了。三台客户机要一起跑，网络、存储和串口这些检查就得写成能反复执行的用例。

左上是开发机上的单元测试。有些逻辑，比如两个设备的地址有没有冲突、虚拟队列能不能按顺序处理，可以给组件接上测试用的宿主接口，在电脑上直接验证。涉及客户机启动和虚拟设备配合的用例，再拿到 QEMU 里跑。

真板子由右边的 ostool-server 分配。测试占用一块板子，启动镜像后收集串口输出，按用例要求的标记逐项判断。三客户机用例会分别检查各台客户机，所有约定的检查都通过，这次运行才算通过。"""
    )

    # =========================================================================
    # SLIDE 17: 总结与开源交流
    # =========================================================================
    s17 = new_styled_slide(prs, stamps["white"])
    add_textbox(
        s17, 1.12, 1.24, 24.43, 0.72, "总结与开源交流",
        size=40, color=DARK_NAVY, bold=True,
        valign=MSO_ANCHOR.MIDDLE, margin=(0.04, 0.04, 0, 0)
    )
    add_textbox(
        s17, 10.60, 13.48, 3.00, 0.48, f"17 / {TOTAL_SLIDES}",
        size=20, color=MUTED_TEXT, bold=True, align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE
    )

    add_card(s17, 1.50, 3.66, 15.20, 7.28, title="小结与开源仓库", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=27, header_band=True)
    takeaways = [
        ("1. 专用内核：", "按需选用 TGOSKits 组件。多架构共用流程，各后端处理自己的硬件。", BRAND_BLUE),
        ("2. 内核态 std：", "宿主通过 Tokio 和 Axum 提供网页管理和串口终端。", SAFE_GREEN),
        ("3. 实时宿主：", "控制任务可由宿主调度，视觉应用可留在隔离客户机里。", AMBER_ORG),
        ("4. 声明式设备图：", "用一份资源规划生成宿主的设备表和客户机的硬件清单。", PURPLE),
    ]
    for ti, (thead, tbody, tcol) in enumerate(takeaways):
        ty = 4.48 + ti * 0.79
        add_rect(s17, 1.82, ty, 14.56, 0.68, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.0, rounded=True, radius=0.06)
        add_rich_paragraphs(
            s17, 2.00, ty + 0.02, 14.20, 0.64,
            [([(thead, 22, tcol, True, FONT_CJK), (tbody, 21.5, DARK_NAVY, True, FONT_CJK)], 0, PP_ALIGN.LEFT)],
            valign=MSO_ANCHOR.MIDDLE
        )

    add_rect(s17, 1.82, 7.82, 14.56, 2.86, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.2, rounded=True, radius=0.06)
    add_textbox(s17, 2.06, 8.02, 14.08, 0.48, "开源仓库（欢迎试用、反馈 Issue 与提交 PR · Apache-2.0 等协议）：", size=22, color=DARK_NAVY, bold=True)
    repos = [
        ("TGOSKits 主仓库（含 ArceOS / StarryOS / AxVisor 与 214 组件）：", "https://github.com/rcore-os/tgoskits"),
        ("ostool 硬件自动化测试工具：", "https://github.com/drivercraft/ostool"),
    ]
    repo_paras = [
        ([("• " + rl + "\n   ", 21, BODY_TEXT, True, FONT_CJK), (ru, 22, BRAND_BLUE, True, FONT_MONO)], 12, PP_ALIGN.LEFT)
        for rl, ru in repos
    ]
    add_rich_paragraphs(s17, 2.06, 8.58, 14.08, 1.98, repo_paras, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)

    add_card(s17, 17.30, 3.66, 7.86, 7.28, title="扫码加微信 · 交流讨论", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=26, header_band=True)
    add_picture_fit(s17, media["wechat_qr"], 17.85, 4.50, 6.76, 5.76, frame_border=None, pad=0.04)
    add_textbox(s17, 17.50, 10.34, 7.46, 0.46, "备注“AxVisor”或“北京沙龙”，欢迎交流技术细节", size=20, color=MUTED_TEXT, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s17,
        "总结与开源交流",
        "总结与交流",
        0.9,
        """回到开场那台机器人。AxVisor 基于 TGOSKits 组件组装宿主内核，不同架构共用执行流程，各自处理底层硬件差异。内核态的 Rust 标准库支撑起网页管理台，宿主的实时调度可以直接承载控制任务，声明式设备图则把客户机所需的设备与权限配置清楚。板卡上的双客户机用例也验证了另一种部署形态，由独立的 Zephyr 客户机负责控制，再与视觉客户机通过共享内存交换结果。

左边是代码仓库地址。AxVisor 集成在 TGOSKits 工作区里，可以通过 cargo xtask 命令先在 QEMU 环境里体验运行。右边是我的微信，想交流板卡适配或者手头有类似应用场景，欢迎会后深入交流。"""
    )

    # SLIDE 18: 模板致谢页
    thanks = next(shape.text_frame for shape in ending.shapes if shape.has_text_frame)
    thanks.word_wrap = False
    thanks.auto_size = MSO_AUTO_SIZE.NONE
    thanks.paragraphs[0].runs[0].font.size = Pt(165)
    add_notes(ending, "THANKS", "致谢", 0.1, "谢谢大家。大家有什么问题，我们现场聊。")
    slide_ids = prs.slides._sldIdLst
    slide_ids.append(ending_id)
    prs.part.rename_slide_parts(slide_id.rId for slide_id in slide_ids)

    return notes_records


def write_notes_markdown(records: list[tuple[str, str, float, str]]) -> None:
    total_chars = sum(len(re.sub(r"\s+", "", r[3])) for r in records)
    total_mins = sum(r[2] for r in records)
    lines = [
        "# AxVisor: 组件化轻量虚拟机 演讲文稿",
        "",
        f"- **幻灯片页数**：{len(records)} 页",
        f"- **预计演讲时长**：约 {total_mins:.1f} 分钟",
        f"- **文稿字数**：{total_chars} 字",
        "",
        "## 章节与时长规划",
        "",
        "| 页码 | 章节 | 页面标题 | 建议时长 | 字数 |",
        "| ---: | --- | --- | ---: | ---: |",
    ]
    for idx, (title, sec, mins, body) in enumerate(records, 1):
        cnum = len(re.sub(r"\s+", "", body))
        lines.append(f"| {idx} | {sec} | {title} | {mins:.1f} 分钟 | {cnum} 字 |")
    lines.append("")
    for idx, (title, sec, mins, body) in enumerate(records, 1):
        cnum = len(re.sub(r"\s+", "", body))
        lines.extend([
            f"## 第 {idx} 页：{title}（{sec} · 约 {mins:.1f} 分钟 · {cnum} 字）",
            "",
            body,
            "",
        ])
    md_text = "\n".join(lines)
    with open(OUT_NOTES_MD, "w", encoding="utf-8") as f:
        f.write(md_text)


def main() -> None:
    prs = Presentation(TEMPLATE_PPTX)
    stamps = extract_template_stamps(prs)
    media = extract_v4_media()
    remove_middle_slides(prs)
    records = build_slides(prs, stamps, media)
    prs.save(OUT_PPTX)
    write_notes_markdown(records)

    reopened = Presentation(OUT_PPTX)
    assert len(reopened.slides) == TOTAL_SLIDES, f"Expected {TOTAL_SLIDES} slides, got {len(reopened.slides)}"
    total_chars = 0
    forbidden_words = [
        "赋能", "里程碑", "开创性", "凸显", "至关重要", "错综复杂", "深入探讨", "格局", "充满活力", "底蕴深厚",
        "合租房", "楼中楼", "毛坯", "大通铺", "保险柜", "墙上插座", "市政水电", "急诊抢救台", "驾照", "战袍",
        "保洁阿姨", "临时房卡", "传菜窗", "风洞", "硬核", "独门特色", "生态跃升", "眼见为实", "三句话带走", "乐高",
    ]
    forbidden_meta = ["大白话", "ELI5", "没有半点虚构", "不空谈跑分", "实事求是", "AxVisor 独立仓库", "arceos-hypervisor/axvisor", "不懂本领域", "懂 Rust 但", "仅 1 处", "仅剩 1 处", "含 1 处"]
    for idx, s in enumerate(reopened.slides, 1):
        latin_font, cjk_font = FONT_LATIN, FONT_CJK
        if idx == 1:
            latin_font = cjk_font = FONT_COVER
        elif idx == TOTAL_SLIDES:
            latin_font = cjk_font = "HarmonyOS Sans SC"
        for sh in s.shapes:
            if sh.has_text_frame:
                stxt = sh.text_frame.text
                assert "！" not in stxt, f"Slide {idx} shape text contains exclamation mark: {stxt!r}"
                for fm in forbidden_meta + forbidden_words:
                    assert fm not in stxt, f"Slide {idx} shape text contains forbidden text {fm!r}: {stxt!r}"
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        if r.text:
                            rPr = r._r.find(qn("a:rPr"))
                            assert rPr is not None, f"Slide {idx} run missing rPr: {r.text!r}"
                            latin = rPr.find(qn("a:latin"))
                            ea = rPr.find(qn("a:ea"))
                            assert latin is not None and latin.get("typeface") == latin_font, f"Slide {idx} run bad latin font: {r.text!r}"
                            assert ea is not None and ea.get("typeface") == cjk_font, f"Slide {idx} run bad ea font: {r.text!r}"
        nt = s.notes_slide.notes_text_frame.text
        assert nt.strip(), f"Slide {idx} has empty notes!"
        assert nt == records[idx - 1][3], f"Slide {idx} notes changed on save!"
        assert "—" not in nt and "–" not in nt, f"Slide {idx} notes contain em/en-dash!"
        assert "！" not in nt, f"Slide {idx} notes contain exclamation mark!"
        for fw in forbidden_words:
            assert fw not in nt, f"Slide {idx} notes contain forbidden word {fw!r}!"
        for fm in forbidden_meta:
            assert fm not in nt, f"Slide {idx} notes contain forbidden meta/removed text {fm!r}!"
        total_chars += len(re.sub(r"\s+", "", nt))

    with zipfile.ZipFile(OUT_PPTX) as z:
        for name in z.namelist():
            if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                xml_bytes = z.read(name)
                assert b"DejaVu Sans Mono" not in xml_bytes, f"{name} still contains DejaVu Sans Mono!"

    print(f"Generated {OUT_PPTX} ({len(reopened.slides)} slides, {reopened.slide_width.inches:.2f}x{reopened.slide_height.inches:.2f} in)")
    print(f"Generated {OUT_NOTES_MD} (total speaker notes: {total_chars} non-whitespace chars)")


if __name__ == "__main__":
    main()
