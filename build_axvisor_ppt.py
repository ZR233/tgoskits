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

TOTAL_SLIDES = 17


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
            "从 TGOSKits 选用底层组件并叠加虚拟化包，自底向上求同存异适配四种架构。"
        ),
        (
            "02 · 通过 std 构建内核态安全隔离", SAFE_GREEN, SAFE_BG, SAFE_BORDER,
            "传统内核态缺乏隔离边界，业务与底层汇编、调度混跑易破坏宿主。",
            "以内核态 Rust std 收敛底层调度与 unsafe 汇编，使上层具备应用级安全保障。"
        ),
        (
            "03 · 省掉实时客户机并复用 std 生态", AMBER_ORG, AMBER_BG, AMBER_BORDER,
            "另开实时客户机多占内存与转发开销，裸机手写管控业务研发成本高。",
            "实时任务在宿主内核态安全直跑省掉客户机开销，并可直接引入 std crate 简化开发。"
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
        add_card(s3, qx, qy, qw, qh, title=qtitle, accent=accent, fill=WHITE, border=bd, title_size=25.5, header_band=True)
        add_rect(s3, qx + 0.28, qy + 0.88, qw - 0.56, 1.02, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.0, rounded=True, radius=0.06)
        add_textbox(s3, qx + 0.42, qy + 0.92, qw - 0.84, 0.94, pain, size=20.5, color=MUTED_TEXT, bold=False, valign=MSO_ANCHOR.MIDDLE)
        add_rect(s3, qx + 0.28, qy + 2.04, qw - 0.56, 1.84, fill=bg, border=bd, border_pt=1.2, rounded=True, radius=0.06)
        add_textbox(s3, qx + 0.42, qy + 2.10, qw - 0.84, 1.72, sol, size=22, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24)

    add_notes(
        s3,
        "AxVisor 的四项设计特点",
        "01 背景与取舍",
        1.6,
        """围绕这个思路，AxVisor 在架构上做了四项关键设计。

第一，按需组装专用内核。AxVisor 直接跑在硬件上，自己就得具备调度、内存管理和设备驱动。我们从开源组件工作区 TGOSKits 里选出所需的内核组件，再叠加上虚拟化组件，组装成专用的多架构宿主内核。

第二，通过内核态标准库构建安全隔离边界。传统内核态没有安全隔离，底层汇编、关中断调度与上层代码混在一起；我们用内核态 Rust 标准库把底层的调度细节和 unsafe 汇编全部收敛封装起来，让标准库之上拥有应用层的安全开发保障。

第三，省掉独立实时客户机并复用标准库生态。有了标准库这一层安全隔离，实时控制任务可以直接在宿主内核态安全运行，省掉单独开一台实时客户机的内存和转发开销；同时还能直接引入 Tokio、Axum 等成熟的标准库组件，大幅简化宿主业务开发。

第四，用声明式设备图简化客户机配置。配置文件只声明需要哪些虚拟设备，由设备图统一分配地址和中断号，同步生成宿主路由表和客户机固件描述。

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
        "多架构复用：虚拟处理器线程的通用阶段与共性抽象",
        "每个虚拟处理器对应宿主机上一个独立内核线程，通用层固化四阶段执行骨架，底层硬件差异编译期静态绑定",
        7, "抽象边界",
        "执行顺序、并发安全边界与休眠唤醒只维护一份通用状态机，四种芯片后端只实现最小硬件动作。"
    )
    add_card(s7, 1.12, 2.84, 11.15, 8.65, title="本质模型与跨架构共性抽象", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=26, header_band=True)
    add_rect(s7, 1.46, 3.80, 10.46, 1.88, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.2)
    add_textbox(s7, 1.71, 3.92, 9.96, 0.44, "运行本质：宿主机上的一个独立线程", size=23, color=DARK_NAVY, bold=True)
    add_textbox(
        s7, 1.71, 4.42, 9.96, 1.14,
        "每个虚拟处理器由一个宿主内核线程独占承载：上核后切入客户机原生执行指令，遇拦截事件再退回线程处理。",
        size=21, color=BODY_TEXT, line_spacing=1.2
    )
    add_rect(s7, 1.46, 5.90, 10.46, 2.36, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.2)
    add_textbox(s7, 1.71, 6.04, 9.96, 0.44, "四种芯片不变的共性部分", size=23, color=BRAND_BLUE, bold=True)
    add_textbox(
        s7, 1.71, 6.54, 9.96, 1.58,
        "进出客户机的阶段顺序、固定物理核防迁移、本地中断开关时机、防漏唤醒检查，以及退回后的重入与休眠流程完全相同。",
        size=21, color=DARK_NAVY, line_spacing=1.2
    )
    add_rect(s7, 1.46, 8.48, 10.46, 2.68, fill=AMBER_BG, border=AMBER_BORDER, border_pt=1.2)
    add_textbox(s7, 1.71, 8.62, 9.96, 0.44, "共性抽象方式：骨架上提 + 编译期静态绑定", size=23, color=AMBER_ORG, bold=True)
    add_textbox(
        s7, 1.71, 9.12, 9.96, 1.90,
        "通用层固化唯一一份线程循环与安全守卫；将装卸状态、切入运行、读取退出原因抽成最小硬件接口，编译时静态接入目标芯片。",
        size=21, color=DARK_NAVY, line_spacing=1.2
    )

    add_card(s7, 12.60, 2.84, 12.95, 8.65, title="虚拟处理器线程单轮执行的四个通用阶段", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=26, header_band=True)
    vcpu_steps = [
        ("1. 进入前准备与装入状态", "写回上一轮处理结果并注入待处理中断，随后固定在当前物理核、关闭本地中断，将客户机状态装入硬件。", BRAND_BLUE, ICE_FILL),
        ("2. 物理核原生运行", "将当前物理核切换进客户机模式，直接在真实处理器硬件上全速执行客户机操作系统与应用指令。", AMBER_ORG, AMBER_BG),
        ("3. 拦截切回与恢复宿主", "客户机访问虚拟外设、执行休眠指令或收到外部中断时切回宿主，记录退出原因、卸下客户机状态并恢复线程环境。", ALERT_RED, RED_BG),
        ("4. 普通线程内分发处理", "回到可加锁、可睡眠的普通线程上下文，完成虚拟设备模拟后进入下一轮，或将线程挂起休眠等待中断唤醒。", SAFE_GREEN, SAFE_BG),
    ]
    for index, (label, description, color, fill) in enumerate(vcpu_steps):
        y = 3.77 + index * 1.87
        add_rect(s7, 12.92, y, 12.31, 1.47, fill=fill, border=color, border_pt=1.3)
        add_textbox(s7, 13.13, y + 0.10, 11.89, 0.44, label, size=24, color=color, bold=True)
        add_textbox(s7, 13.13, y + 0.56, 11.89, 0.80, description, size=20.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)
        if index < len(vcpu_steps) - 1:
            add_arrow(s7, 18.88, y + 1.49, 0.38, 0.29, "down", color)

    add_notes(
        s7,
        "多架构复用：虚拟处理器线程的通用阶段与共性抽象",
        "02 专用内核",
        2.0,
        """解决了驱动在不同内核之间的复用，再往上走到虚拟化核心层，还要面对四种不同处理器架构的硬件差异。要看清这一层怎么跨架构复用，先要明确虚拟处理器在宿主机里到底是什么：客户机的每一个虚拟处理器，对应的其实就是宿主机上的一个独立内核线程。它不像软件模拟器那样逐条解释指令，而是当宿主机调度器把这个线程放到某颗物理核上运行时，由线程把物理核直接切换进客户机模式，在硬件上原生执行客户机代码，遇到需要宿主介入的事件再退回线程循环。

不管底层是哪一种芯片，这个宿主线程驱动虚拟处理器跑一轮，都会依次经历右边这四个通用阶段。第一阶段是进入前准备与装入状态：线程先把上一轮处理完的结果写回虚拟寄存器、填入待投递的虚拟中断，接着固定在当前物理核上禁止跨核迁移，关闭本地中断，做完进入前的最后一次唤醒检查后，把客户机的寄存器状态装入硬件。第二阶段是物理核原生运行：处理器切入客户机模式，直接在硬件上执行客户机指令。

第三阶段是拦截切回与恢复宿主环境：一旦客户机读写虚拟串口这类外设、执行休眠指令，或者来了外部物理中断，硬件就会自动切回宿主；这时必须先记录退出原因、卸下当前核上的客户机硬件状态，再重新打开本地中断并解除物理核绑定，恢复成正常的宿主线程环境。第四阶段是回到普通线程上下文做分发处理：此时线程已经允许加锁和睡眠，如果是访问虚拟设备，就调用设备模拟逻辑，带着结果进入下一轮循环；如果客户机当前无事可做，就把这个宿主线程挂到等待队列上休眠，让出物理核，等中断到来再唤醒。

看清这四个阶段，共性部分的抽象方式就很自然了。看左下角，四种芯片真正不同的只是寄存器布局和具体的切换指令，而整套四阶段的先后顺序、禁迁移与关中断的安全边界、进入前防漏唤醒的检查，以及退回线程后的重入与休眠分支，在所有芯片上完全一致。因此我们在通用层只维护唯一一份线程执行状态机和安全作用域守卫，把控制流骨架彻底固定下来；同时把装卸硬件状态、切入客户机运行、读取退出原因和写入中断这几个真正跟芯片绑定的动作，提炼成一组极窄的底层硬件接口，由各芯片后端各自实现，并在编译阶段按目标芯片静态绑定。这样既不用把执行循环重复写四遍，改一处并发逻辑四种架构同时生效，也没有运行时动态分发的额外开销。既然虚拟处理器的运行主流程能抽成同一套骨架，那再往底层走一步，中断投递的状态管理能不能也照这个办法合并成一套通用代码？"""
    )

    # =========================================================================
    # SLIDE 8: 保留架构差异
    # =========================================================================
    s8 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s8, True, "02 专用内核", AMBER_ORG,
        "多架构差异：为什么底层中断与处理器切换不能强行合并",
        "同样叫「向客户机发中断」，不同芯片的硬件拓扑、确认时机与控制结构连形状都不同",
        8, "保留差异",
        "中断的路由、确认与再次投递规则由各芯片后端独立掌握，不为了表面整齐牺牲硬件加速能力。"
    )
    # Left Card: ARM64 GIC — single controller list registers + 3-stage hardware split
    add_card(s8, 1.12, 2.84, 11.95, 7.22, title="ARM64：单控制器硬件列表与三阶段完成", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=26, header_band=True)
    add_rect(s8, 1.42, 3.78, 4.15, 1.22, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.3)
    add_textbox(s8, 1.54, 3.84, 3.91, 1.10, "外设 / 虚拟中断源\n产生待投递中断", size=20.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s8, 5.69, 4.18, 0.62, 0.42, "right", BRAND_BLUE)
    add_rect(s8, 6.43, 3.78, 6.33, 1.22, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.5)
    add_textbox(s8, 6.58, 3.84, 6.03, 1.10, "GIC 硬件列表寄存器\n进入客户机后由硬件自动切换挂起与激活态", size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s8, 6.88, 5.06, 0.40, 0.30, "down", BRAND_BLUE)

    add_rect(s8, 1.42, 5.42, 11.34, 2.52, fill=WHITE, border=BRAND_BLUE, border_pt=1.5, dash=MSO_LINE_DASH_STYLE.DASH)
    add_textbox(s8, 1.62, 5.50, 10.94, 0.42, "物理中断直通的三阶段硬件状态拆分（状态全程留在 GIC 侧）", size=20.5, color=BRAND_BLUE, bold=True)
    arm_stages = [
        ("① 宿主应答", "读取中断号并认领", BRAND_BLUE, ICE_FILL),
        ("② 宿主降优先级", "放行其他中断响应", BRAND_BLUE, ICE_FILL),
        ("③ 客户机去激活", "处理完直写硬件结束", SAFE_GREEN, SAFE_BG),
    ]
    for idx, (st_lbl, st_sub, st_col, st_bg) in enumerate(arm_stages):
        sx = 1.62 + idx * 3.82
        add_rect(s8, sx, 6.02, 3.32, 1.70, fill=st_bg, border=st_col, border_pt=1.3)
        add_textbox(s8, sx + 0.12, 6.12, 3.08, 0.48, st_lbl, size=21, color=st_col, bold=True, align=PP_ALIGN.CENTER)
        add_textbox(s8, sx + 0.12, 6.66, 3.08, 0.92, st_sub, size=19.5, color=DARK_NAVY, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        if idx < 2:
            add_arrow(s8, sx + 3.40, 6.66, 0.34, 0.40, "right", BRAND_BLUE)

    add_rect(s8, 1.42, 8.14, 11.34, 1.64, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.3)
    add_textbox(s8, 1.64, 8.22, 10.90, 1.48, "处理器切换路径：单一 EL2 虚拟化特权级，统一管理客户机系统寄存器与二阶段页表", size=20.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # Right Card: x86-64 — 2-chip routing + EOI rescan feedback loop + Intel/AMD fork
    add_card(s8, 13.60, 2.84, 11.95, 7.22, title="x86-64：双控制器分级路由与双厂商分支", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=26, header_band=True)
    add_rect(s8, 13.90, 3.78, 2.66, 1.22, fill=AMBER_BG, border=AMBER_ORG, border_pt=1.3)
    add_textbox(s8, 13.98, 3.84, 2.50, 1.10, "外设中断线\n引脚电平信号", size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s8, 16.64, 4.18, 0.46, 0.42, "right", AMBER_ORG)
    add_rect(s8, 17.18, 3.78, 3.82, 1.22, fill=AMBER_BG, border=AMBER_ORG, border_pt=1.3)
    add_textbox(s8, 17.28, 3.84, 3.62, 1.10, "板级 I/O APIC\n查重定向表转成向量", size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s8, 21.08, 4.18, 0.46, 0.42, "right", AMBER_ORG)
    add_rect(s8, 21.62, 3.78, 3.62, 1.22, fill=AMBER_BG, border=AMBER_ORG, border_pt=1.5)
    add_textbox(s8, 21.72, 3.84, 3.42, 1.10, "核内虚拟 LAPIC\n按向量位图排队投递", size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s8, 13.90, 5.42, 11.34, 2.52, fill=RED_BG, border=ALERT_RED, border_pt=1.5, dash=MSO_LINE_DASH_STYLE.DASH)
    add_textbox(s8, 14.10, 5.50, 10.94, 0.42, "电平触发中断的跨控制器闭环回写（两级状态机协同）", size=20.5, color=ALERT_RED, bold=True)
    add_rect(s8, 14.10, 6.02, 4.86, 1.70, fill=WHITE, border=ALERT_RED, border_pt=1.2)
    add_textbox(s8, 14.22, 6.10, 4.62, 1.54, "客户机写 EOI 通知处理完毕\n核内虚拟 LAPIC 拦截结束信号", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s8, 19.12, 6.62, 0.88, 0.50, "lr", ALERT_RED)
    add_rect(s8, 20.16, 6.02, 4.88, 1.70, fill=WHITE, border=ALERT_RED, border_pt=1.2)
    add_textbox(s8, 20.28, 6.10, 4.64, 1.54, "反向通知板级虚拟 I/O APIC\n重查引脚电平决定是否继续投递", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s8, 13.90, 8.14, 5.50, 1.64, fill=AMBER_BG, border=AMBER_ORG, border_pt=1.5)
    add_textbox(s8, 14.04, 8.22, 5.22, 1.48, "Intel 路线（VMX）\n独立 VMCS 控制结构与专属切换指令", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_rect(s8, 19.74, 8.14, 5.50, 1.64, fill=PURP_BG, border=PURPLE, border_pt=1.5)
    add_textbox(s8, 19.88, 8.22, 5.22, 1.48, "AMD 路线（SVM）\n独立 VMCB 控制块与事件注入格式", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s8, 1.12, 10.28, 24.43, 1.14, fill=DARK_NAVY, border=None)
    add_textbox(s8, 1.40, 10.36, 23.87, 0.98, "左图是单芯片三阶段硬件闭环，右图是双芯片协同回写加双厂商分支：底层规则不等价，必须留在各后端独立调优。", size=22.5, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s8,
        "多架构差异：为什么底层中断与处理器切换不能强行合并",
        "02 专用内核",
        1.8,
        """做多架构适配时很容易产生一个直觉：既然每种芯片都要给客户机发中断，干脆在最底层定一个统一接口，就叫「向某个虚拟处理器注入中断」。但把左右两张真实的硬件结构图摆在一起，一眼就能看出两边的状态流转连形状都不一样。

先看左边 ARM 架构。宿主机在单一的虚拟化特权级上管理上下文，虚拟中断直接写进中断控制器的硬件列表寄存器，进客户机后由硬件自动切换挂起和激活状态；如果做物理外设中断直通，一次中断还要拆成宿主机应答认领、宿主机降低优先级放行其他中断、最后由客户机处理完直接写硬件去激活三个阶段，状态全程由这一套控制器维护。

再看右边 x86 架构，完全是另一幅拓扑。外设引脚信号要先经过板级中断控制器查表转成中断向量，再发给目标核内的本地虚拟中断控制器排队；遇到一条电平触发中断，必须等客户机写结束寄存器，核内控制器拦截到信号后再反向通知板级控制器重查引脚电平，才能决定要不要继续投递。甚至同在 x86 内部，英特尔和超威两家的硬件控制块格式与进出指令也是完全分开的两套。

这就是底下深色框强调的结论：表面都叫发中断，但状态归谁管、什么时候算处理完、什么时候允许发下一次，底层硬件规则根本不等价。如果在最底层强行捏合成一套通用状态机，要么为了迁就共同点丢掉硬件原有的直通加速能力，要么在通用代码里塞满芯片判断分支。所以这一层我们明确保留差异，让各后端管好自己的中断状态机。底层既然不能强行合并，那公共接口到底应该定在哪一层？"""
    )

    # =========================================================================
    # SLIDE 9: 求同存异
    # =========================================================================
    s9 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s9, False, "02 专用内核", SAFE_GREEN,
        "求同存异：从底层异构硬件逐层向上收敛共性",
        "不在顶层预设大而全的统一接口，而是保留底层四路硬件差异，走到行为真正一致的那一层再提取共用机制",
        9, "分层边界",
        "异构硬件原语留在各后端，部分架构能力独立成窄接口，完全一致的等待与执行骨架只维护一份。"
    )
    # Left Card: Bottom-up Visual Convergence Lattice (4 pillars -> asymmetric 2+2 -> 1 shared bar -> 1 top contract)
    add_card(s9, 1.12, 2.84, 11.95, 8.65, title="结构收敛：从四路异构底座向上提取共性", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=26, header_band=True)

    # Layer 1 (Top - All 4 converged)
    add_rect(s9, 1.44, 3.78, 11.31, 1.38, fill=ICE_FILL, border=BRAND_BLUE, border_pt=2.0)
    add_textbox(s9, 1.66, 3.86, 10.87, 0.44, "顶层统一架构入口（四种架构全部满足）", size=22.5, color=BRAND_BLUE, bold=True)
    add_textbox(s9, 1.66, 4.34, 10.87, 0.72, "组合运行、机器资源、启动交接与镜像装载四组基础契约，通用代码零架构判断", size=19.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_arrow(s9, 6.88, 5.22, 0.42, 0.32, "up", BRAND_BLUE)

    # Layer 2 (Shared default mechanisms)
    add_rect(s9, 1.44, 5.60, 11.31, 1.38, fill=SAFE_BG, border=SAFE_GREEN, border_pt=2.0)
    add_textbox(s9, 1.66, 5.68, 10.87, 0.44, "共享默认机制层（行为一致处只维护唯一一份）", size=22.5, color=SAFE_GREEN, bold=True)
    add_textbox(s9, 1.66, 6.16, 10.87, 0.72, "虚拟处理器四阶段执行顺序、防漏唤醒等待队列等共同算法全部收拢于此", size=19.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_arrow(s9, 4.05, 7.04, 0.38, 0.32, "up", PURPLE)
    add_arrow(s9, 9.75, 7.04, 0.38, 0.32, "up", SLATE_DARK)

    # Layer 3 (Asymmetric partial capability: solid 2-arch vs dashed unsupported 2-arch)
    add_rect(s9, 1.44, 7.42, 5.62, 1.48, fill=PURP_BG, border=PURPLE, border_pt=1.8)
    add_textbox(s9, 1.60, 7.50, 5.30, 0.44, "部分架构窄接口：从核唤醒", size=21, color=PURPLE, bold=True)
    add_textbox(s9, 1.60, 7.98, 5.30, 0.82, "仅 ARM64 与 RISC-V 显式实现\n响应客户机动态唤醒从核请求", size=18.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s9, 7.26, 7.42, 5.49, 1.48, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.6, dash=MSO_LINE_DASH_STYLE.DASH)
    add_textbox(s9, 7.42, 7.50, 5.17, 0.44, "x86-64 / 龙芯：不写空实现", size=21, color=SLATE_DARK, bold=True)
    add_textbox(s9, 7.42, 7.98, 5.17, 0.82, "无此调用路径则不实现该接口\n一旦误调在编译期直接报错拦截", size=18.5, color=MUTED_TEXT, valign=MSO_ANCHOR.MIDDLE)

    # Layer 4 (Bottom - 4 distinct narrow hardware silos!)
    hw_pillars = [
        ("ARM64", "GIC 列表寄存器\nEL2 系统寄存器", BRAND_BLUE, ICE_FILL),
        ("RISC-V", "PLIC 外设中断\nHS 扩展寄存器", SAFE_GREEN, SAFE_BG),
        ("x86-64", "I/O·本地 APIC\nVMX / SVM 控制块", AMBER_ORG, AMBER_BG),
        ("龙芯 LoongArch", "LVZ 虚拟化扩展\n私有中断同步槽", PURPLE, PURP_BG),
    ]
    for pi, (pname, pdesc, pcol, pbg) in enumerate(hw_pillars):
        px = 1.44 + pi * 2.88
        add_arrow(s9, px + 1.16, 8.96, 0.34, 0.30, "up", pcol)
        add_rect(s9, px, 9.32, 2.67, 1.88, fill=pbg, border=pcol, border_pt=1.8)
        add_rect(s9, px + 0.08, 9.40, 2.51, 0.48, fill=pcol, border=None, rounded=True, radius=0.10)
        add_textbox(s9, px + 0.10, 9.40, 2.47, 0.48, pname, size=18.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s9, px + 0.08, 9.94, 2.51, 1.18, pdesc, size=17.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)

    # Right Card: Y-shaped Convergence Funnel for VcpuWait Race Prevention
    add_card(s9, 13.40, 2.84, 12.15, 8.65, title="运行实例：休眠前夕中断到达（异构检查汇入共用等待）", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=24.5, header_band=True)

    chip_checks = [
        ("ARM64 私有检查", "查 GIC 虚拟中断挂起\n与核内虚拟定时器状态", BRAND_BLUE, ICE_FILL),
        ("x86-64 私有检查", "查虚拟 LAPIC 向量位图\n与待注入事件标志", AMBER_ORG, AMBER_BG),
        ("RISC-V / 龙芯检查", "查架构中断挂起寄存器\n与核间唤醒通知槽", PURPLE, PURP_BG),
    ]
    for ci, (ctitle, cdesc, ccol, cbg) in enumerate(chip_checks):
        cx = 13.72 + ci * 3.92
        add_rect(s9, cx, 3.78, 3.67, 1.96, fill=cbg, border=ccol, border_pt=1.6)
        add_textbox(s9, cx + 0.12, 3.88, 3.43, 0.46, ctitle, size=20.5, color=ccol, bold=True, align=PP_ALIGN.CENTER)
        add_textbox(s9, cx + 0.12, 4.40, 3.43, 1.22, cdesc, size=18.5, color=DARK_NAVY, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)
        add_arrow(s9, cx + 1.65, 5.82, 0.36, 0.36, "down", ccol)

    add_rect(s9, 14.52, 6.24, 9.91, 0.72, fill=DARK_NAVY, border=None, rounded=True, radius=0.18)
    add_textbox(s9, 14.68, 6.26, 9.59, 0.68, "向上只暴露一个最小问题：「当前是否有事件就绪？」", size=20.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s9, 19.26, 7.02, 0.42, 0.34, "down", SAFE_GREEN)

    add_rect(s9, 13.72, 7.42, 11.51, 2.08, fill=SAFE_BG, border=SAFE_GREEN, border_pt=2.0)
    add_textbox(s9, 13.96, 7.52, 11.03, 0.46, "四架构共用一份防漏唤醒等待队列", size=22.5, color=SAFE_GREEN, bold=True)
    add_textbox(
        s9, 13.96, 8.04, 11.03, 1.34,
        "① 准备休眠前先记录通知代次 → ② 回调上面的最小接口复查硬件就绪态 →\n"
        "③ 确认无事件才挂起宿主线程；其间到达的任何中断都会触发唤醒重查，绝不漏通知",
        size=19.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22
    )
    add_arrow(s9, 19.26, 9.56, 0.42, 0.32, "down", BRAND_BLUE)

    add_rect(s9, 13.72, 9.94, 11.51, 1.26, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.5)
    add_textbox(s9, 13.96, 10.02, 11.03, 1.10, "上层通用执行线程：醒来后直接回到四阶段循环，完全不感知底层芯片差异", size=20.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s9,
        "求同存异：从底层异构硬件逐层向上收敛共性",
        "02 专用内核",
        1.9,
        """如果一开始就在顶层定一个大而全的统一接口让四种芯片去填空，底下一定会塞满空实现和芯片名称判断。我们的「求同存异」反过来走：从底层的真实硬件差异出发，一层一层往上收敛，走到哪一层语义真正一致了，才在哪一层提取共用代码。

看左图从下往上的收敛结构。最底下四根独立柱子，分别保留四种芯片各自的寄存器、页表与中断硬件原语，绝不强行拉平。往上一层，遇到只有部分芯片才有的能力，比如响应客户机动态唤醒从核的请求，只有 ARM64 和 RISC-V 需要处理；我们就把它拆成独立的窄接口，只由这两类芯片实现，右边的 x86 和龙芯根本不写空实现凑数，万一被误调用，编译阶段直接报错拦截。再往上走到绿色层，像虚拟处理器的四阶段进出顺序、休眠唤醒的并发保护，四种芯片行为完全一致，就收拢成唯一一份共享机制。最顶层再把所有芯片都具备的运行、机器资源、启动交接和镜像装载四组能力组合成统一入口，上层通用代码一行芯片判断都不用写。

右图就是一个典型的「底异上同」实例。当虚拟处理器空闲准备休眠时，最怕刚检查完没事件、还没真正睡下，中断恰好赶到，漏掉通知就会一直卡在休眠状态。看上方三格，怎么判断有没有待处理事件，ARM 要查虚拟中断和定时器，x86 要查本地中断向量位图，RISC-V 和龙芯各有各的寄存器，底层检查方式完全不同；但往上收敛一步，各后端只需要回答一个最简单的问题：当前有没有事件就绪。中间绿框里的防漏唤醒队列先记录通知代次、再回调这个就绪接口复查，确认没事件才挂起宿主线程，这套防竞态逻辑四种架构完全共用一份。到这里，跨架构的裸机宿主底座就真正立住了。"""
    )

    # =========================================================================
    # SLIDE 10: 03 安全隔离——通过 Rust std 收敛底层调度与 unsafe 汇编
    # =========================================================================
    s10 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s10, True, "03 安全隔离", SAFE_GREEN,
        "安全隔离：通过 Rust std 收敛底层调度与不安全操作",
        "以内核态标准库为安全分界线：向下收敛复杂调度与 unsafe 汇编，向上提供应用级安全开发环境",
        10, "隔离价值",
        "既保留内核态直接运行的零客户机与零系统调用开销，又获得应用层 Safe Rust 的安全保障与 crate 生态。"
    )
    # Left Card: Kernel-space safety isolation divided by Rust std
    add_card(s10, 1.12, 2.84, 12.60, 8.65, title="内核态中的安全分界线：以 std 隔离底层特权与上层业务", accent=DARK_NAVY, fill=WHITE, border=BORDER_BLU, title_size=24.5, header_band=True)

    # Above std: Application-level safe layer in kernel mode
    add_rect(s10, 1.44, 3.76, 11.96, 2.40, fill=SAFE_BG, border=SAFE_GREEN, border_pt=2.0, rounded=True, radius=0.06)
    add_rect(s10, 1.64, 3.94, 3.36, 2.04, fill=SAFE_GREEN, border=None, rounded=True, radius=0.08)
    add_textbox(s10, 1.70, 3.98, 3.24, 1.96, "std 之上\n应用级安全层\n（100% Safe Rust）", size=20, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s10, 5.18, 3.86, 8.02, 2.20,
        "• 承载实时控制任务、虚拟化编排、网页管理台与远程终端\n"
        "• 仅通过标准线程、同步锁、文件与网络等类型安全接口编程\n"
        "• 语法层面隔绝裸指针、关中断与寄存器，业务缺陷写不坏内核",
        size=19.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22
    )

    # The std Isolation Boundary Bar
    add_rect(s10, 1.44, 6.32, 11.96, 0.80, fill=DARK_NAVY, border=SAFE_GREEN, border_pt=1.8, rounded=True, radius=0.14)
    add_textbox(
        s10, 1.60, 6.36, 11.64, 0.72,
        "▲ 向上提供标准库安全契约   |   内核态 Rust std 隔离层（ax-std）   |   ▼ 向下收敛底层特权机制",
        size=18.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE
    )

    # Below std: Converged low-level scheduling + tapered unsafe assembly core
    add_rect(s10, 1.44, 7.28, 11.96, 3.94, fill=LIGHT_GRAY, border=ALERT_RED, border_pt=1.6, dash=MSO_LINE_DASH_STYLE.DASH, rounded=True, radius=0.06)
    add_textbox(s10, 1.66, 7.36, 11.52, 0.42, "std 之下 · 底层复杂调度与 unsafe 汇编集中收敛区（内部封闭审计）", size=19, color=ALERT_RED, bold=True)

    add_rect(s10, 1.68, 7.86, 11.48, 1.34, fill=AMBER_BG, border=AMBER_ORG, border_pt=1.5, rounded=True, radius=0.05)
    add_textbox(
        s10, 1.86, 7.94, 11.12, 1.18,
        "底层调度与同步收敛：多核抢占调度切换 · 关中断自旋锁 · 页表分配 · 跨内核硬件驱动\n"
        "（所有容易因关抢占、死锁或并发失序导致内核崩溃的底层状态机全部封装在此层内部）",
        size=18.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18
    )

    add_arrow(s10, 2.06, 9.86, 0.72, 0.44, "right", ALERT_RED)
    add_rect(s10, 2.90, 9.36, 9.04, 1.66, fill=RED_BG, border=ALERT_RED, border_pt=2.0, rounded=True, radius=0.06)
    add_textbox(
        s10, 3.08, 9.44, 8.68, 1.50,
        "最小 unsafe 汇编底座（极窄可信基）\n"
        "特权级进出汇编 · 处理器寄存器保存恢复 · 二阶段页表与受控寄存器映射",
        size=19, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.20
    )
    add_arrow(s10, 12.06, 9.86, 0.72, 0.44, "left", ALERT_RED)

    # Right Card: Three Core Payoffs + Codebase Audit Proof
    add_card(s10, 14.04, 2.84, 11.51, 8.65, title="std 安全隔离带来的三大收益与源码实证", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=24.5, header_band=True)

    payoffs = [
        ("① 内核态安全应用开发", "业务代码享有应用层内存与并发安全，逻辑错误不会破坏宿主内核。", SAFE_GREEN, SAFE_BG),
        ("② 省掉实时客户机与客户机开销", "实时控制直接在宿主内核态安全运行，免去客户机内存与中断转发损耗。", AMBER_ORG, AMBER_BG),
        ("③ 复用 std crate 大幅简化开发", "直接引入 Tokio、Axum、Serde 等标准库生态，告别裸机从零手写轮子。", BRAND_BLUE, ICE_FILL),
    ]
    for pi, (ptitle, pdesc, pcol, pbg) in enumerate(payoffs):
        py = 3.74 + pi * 1.32
        add_rect(s10, 14.34, py, 10.91, 1.18, fill=pbg, border=pcol, border_pt=1.5, rounded=True, radius=0.06)
        add_textbox(s10, 14.54, py + 0.08, 10.51, 0.44, ptitle, size=20.5, color=pcol, bold=True)
        add_textbox(s10, 14.54, py + 0.54, 10.51, 0.54, pdesc, size=18.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s10, 14.34, 7.80, 10.91, 3.42, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.3, rounded=True, radius=0.06)
    add_rect(s10, 14.54, 7.96, 10.51, 0.98, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.6, rounded=True, radius=0.06)
    add_textbox(s10, 14.68, 8.00, 2.85, 0.90, "9 / 16", size=44, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s10, 17.60, 8.02, 7.28, 0.86,
        "16 个虚拟化实现包中 9 个实现 0 处 unsafe\n合计 55,809 行复杂协议与设备逻辑纯安全",
        size=18.5, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18
    )

    safe_crates = [
        ("axdevice 设备图与授权", "27,636 行 · 0 unsafe"),
        ("aarch64_sysreg 寄存器解码", "12,735 行 · 0 unsafe"),
        ("axvirtio 磁盘与网络协议", "12,646 行 · 0 unsafe"),
        ("axvmconfig 配置与虚拟中断", "2,792 行 · 0 unsafe"),
    ]
    for sci, (sc_name, sc_stat) in enumerate(safe_crates):
        sc_col = sci % 2
        sc_row = sci // 2
        scx = 14.54 + sc_col * 5.34
        scy = 9.10 + sc_row * 1.00
        add_rect(s10, scx, scy, 5.17, 0.88, fill=WHITE, border=SAFE_BORDER, border_pt=1.2, rounded=True, radius=0.05)
        add_textbox(s10, scx + 0.14, scy + 0.06, 4.89, 0.40, sc_name, size=18, color=DARK_NAVY, bold=True)
        add_textbox(s10, scx + 0.14, scy + 0.44, 4.89, 0.36, sc_stat, size=17.5, color=SAFE_GREEN, bold=True)

    add_notes(
        s10,
        "安全隔离：通过 Rust std 收敛底层调度与不安全操作",
        "03 安全隔离",
        1.9,
        """搭好了跨架构宿主底座，接下来进入另一个核心话题：宿主机内部的安全隔离。在传统 C 语言编写的内核或虚拟机监控器里，内核态内部是没有安全边界的，上层逻辑和底层的内联汇编、关中断锁、调度器切换混在同一片地址空间里，写错一个指针就可能把整个宿主机搞崩溃。这也是为什么传统轻量监控器不敢在宿主内核里跑复杂业务，什么功能都只能往客户机里塞。

看左图，AxVisor 在宿主内核内部引入了内核态 Rust 标准库，把它做成一道清晰的安全隔离分界线。在这条分界线之下，我们把两类最危险的操作全部收敛封装起来：一类是最底层的特权级进出汇编、寄存器切换和二阶段页表硬件映射，另一类是容易因关抢占或并发失序引发死锁的多核调度器和底层同步锁。而在标准库分界线之上，向上只暴露类型安全的线程、同步、文件与网络接口，并且通过函数直调底层模块，没有传统系统调用的切换损耗。

如右图所示，这种「底层收敛、上层安全」的隔离结构直接带来了三项关键收益：第一是实现了内核态的安全应用开发，标准库之上的代码完全使用安全 Rust 编写，连虚拟化核心层也有超过五万五千行协议与设备逻辑做到了零处不安全代码；第二是正因为宿主内核态足够安全，原本为了隔离风险而不得不单开的实时客户机现在可以直接省掉，在内核态直跑实时应用，省去整套客户机开销；第三是可以直接使用成熟的标准库开源组件，大幅简化业务开发。我们先看它怎么帮系统省掉实时客户机开销。"""
    )

    # =========================================================================
    # SLIDE 11: 03 安全隔离——省掉实时客户机，内核态直跑零客户机开销
    # =========================================================================
    s11 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s11, True, "03 安全隔离", AMBER_ORG,
        "省掉实时客户机：内核态安全直跑实时任务",
        "依托 std 上层的应用级安全保障与底层实时调度，关键控制直接在宿主内核态运行，省掉客户机开销",
        11, "零客户机损耗",
        "既省去单独维护实时客户机的镜像与内存开销，又消除物理中断拦截与虚拟中断转发延迟。"
    )
    add_card(s11, 1.12, 2.84, 12.60, 8.65, title="为什么要省掉独立实时客户机：两套路径对比", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=25, header_band=True)

    # Path 1: Traditional Guest RTOS (extra VM memory + extra trap/vIRQ hop)
    add_rect(s11, 1.42, 3.74, 12.00, 3.24, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.5, rounded=True, radius=0.05)
    add_textbox(s11, 1.62, 3.82, 11.60, 0.42, "传统做法：宿主缺乏安全边界与调度，被迫另开实时客户机", size=20.5, color=SLATE_DARK, bold=True)
    add_rect(s11, 1.62, 4.34, 3.24, 2.44, fill=WHITE, border=GRAY_BORDER, border_pt=1.2, rounded=True, radius=0.05)
    add_textbox(s11, 1.72, 4.44, 3.04, 2.24, "客户机 A\n复杂 Linux\n（视觉 / AI / 界面）", size=19.5, color=BODY_TEXT, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s11, 5.06, 4.34, 2.52, 1.06, fill=RED_BG, border=ALERT_RED, border_pt=1.3, rounded=True, radius=0.05)
    add_textbox(s11, 5.14, 4.38, 2.36, 0.98, "电机 / 传感器\n物理硬件中断", size=18.5, color=ALERT_RED, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s11, 7.66, 4.68, 0.42, 0.36, "right", ALERT_RED)
    add_rect(s11, 8.16, 4.34, 5.04, 1.06, fill=SLATE_DARK, border=None, rounded=True, radius=0.05)
    add_textbox(s11, 8.26, 4.38, 4.84, 0.98, "开销一：拦截物理中断 → 转换注入虚拟中断", size=18, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s11, 10.48, 5.44, 0.36, 0.28, "down", ALERT_RED)
    add_rect(s11, 5.06, 5.76, 8.14, 1.02, fill=WHITE, border=ALERT_RED, border_pt=1.4, dash=MSO_LINE_DASH_STYLE.DASH, rounded=True, radius=0.05)
    add_textbox(s11, 5.18, 5.80, 7.90, 0.94, "开销二：单独预留实时客户机内存，等虚拟核调度上核才响应", size=18, color=ALERT_RED, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # Path 2: AxVisor Host-Direct Safe RT on std + Isolated Linux Guest
    add_rect(s11, 1.42, 7.16, 12.00, 4.08, fill=AMBER_BG, border=AMBER_ORG, border_pt=2.2, rounded=True, radius=0.05)
    add_textbox(s11, 1.62, 7.24, 11.60, 0.42, "AxVisor 做法：std 安全层直跑实时应用（省掉实时客户机开销）", size=21, color=AMBER_ORG, bold=True)
    add_rect(s11, 1.62, 7.76, 4.46, 1.82, fill=WHITE, border=BRAND_BLUE, border_pt=1.8, rounded=True, radius=0.05)
    add_textbox(s11, 1.74, 7.84, 4.22, 1.66, "硬件隔离 Linux 客户机\n承载视觉 / AI / 复杂应用\n故障封锁在二阶段页表内", size=19, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)

    add_rect(s11, 6.28, 7.76, 2.38, 1.82, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.6, rounded=True, radius=0.05)
    add_textbox(s11, 6.36, 7.84, 2.22, 1.66, "控制外设\n硬件中断\n直达宿主", size=19.5, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s11, 8.74, 8.46, 0.48, 0.42, "right", SAFE_GREEN)
    add_rect(s11, 9.30, 7.76, 3.90, 1.82, fill=SAFE_GREEN, border=None, rounded=True, radius=0.05)
    add_textbox(s11, 9.40, 7.84, 3.70, 1.66, "宿主 std 安全实时线程\n省去实时客户机内存\n零二阶段页表与转发损耗", size=18.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)

    add_rect(s11, 1.62, 9.72, 11.58, 1.34, fill=DARK_NAVY, border=None, rounded=True, radius=0.05)
    add_textbox(s11, 1.76, 9.78, 11.30, 1.22, "硬件虚拟化隔离外部重型 Linux 负载  +  软件 std 边界安全承载宿主内核态实时控制（同时保留托管独立实时客户机能力）", size=18.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22)

    add_card(s11, 14.04, 2.84, 11.51, 4.10, title="std 之下封装的三层抢占调度（保障实时线程严格优先）", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=23.5, header_band=True)
    sched_rows = [
        ("P1 · 截止期调度（Deadline）", "最高抢占级，按周期截止时间与预算严格保障电机等周期控制线程", ALERT_RED, RED_BG),
        ("P2 · 实时抢占调度（FIFO / 轮转）", "次高抢占级，支持 1 至 99 级固定优先级，承载事件驱动实时线程", AMBER_ORG, AMBER_BG),
        ("P3 · 公平分时调度（Fair）", "普通分时级，承载宿主管控服务与常规客户机虚拟处理器线程", BRAND_BLUE, ICE_FILL),
    ]
    for si, (st, sd, sc, sb) in enumerate(sched_rows):
        sy = 3.74 + si * 1.02
        add_rect(s11, 14.32, sy, 10.95, 0.88, fill=sb, border=sc, border_pt=1.2, rounded=True, radius=0.06)
        add_textbox(s11, 14.48, sy + 0.04, 4.25, 0.80, st, size=19.5, color=sc, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s11, 18.78, sy + 0.04, 6.36, 0.80, sd, size=18.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE)

    add_card(s11, 14.04, 7.14, 11.51, 4.35, title="std 之下收敛的四级显式锁（消除优先级反转与关中断抖动）", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=23.5, header_band=True)
    lock_rows = [
        ("优先级继承互斥锁", "高优先级控制线程等锁时，自动抬高持锁低优先级线程以尽快放锁"),
        ("实时可睡眠自旋锁", "锁竞争时允许让出处理器且约束持锁迁移，避免长关抢占拖慢响应"),
        ("短临界区关中断锁", "仅用于极短底层临界区，自动保存并在离开作用域时恢复中断状态"),
        ("每核本地锁 + 死锁检测", "核内数据免跨核争抢，运行期自动检测锁依赖环路拦截死锁隐患"),
    ]
    for li, (lt, ld) in enumerate(lock_rows):
        ly = 8.02 + li * 0.84
        add_rect(s11, 14.32, ly, 10.95, 0.72, fill=LIGHT_GRAY if li % 2 else SAFE_BG, border=GRAY_BORDER, border_pt=1.0, rounded=True, radius=0.05)
        add_textbox(s11, 14.48, ly + 0.04, 3.85, 0.64, lt, size=18.5, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s11, 18.38, ly + 0.04, 6.76, 0.64, ld, size=18.5, color=BODY_TEXT, bold=False, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s11,
        "省掉实时客户机：内核态安全直跑实时任务",
        "03 安全隔离",
        1.8,
        """先看这项隔离设计带来的第一个显著变化：直接省掉独立的实时客户机。看左图上方，以往做混合关键性系统时，为了防止控制代码和复杂业务互相干扰，也因为传统监控器自己没有安全的业务运行环境，往往只能在 Linux 客户机旁边再单独起一台实时操作系统客户机。这样做有两重额外开销：一是要给这台实时客户机单独划分内存、维护独立固件；二是外设物理中断到达后，必须先陷入监控器、转换成虚拟中断注入进去，再等虚拟核调度上核才能响应。

再看左图下方 AxVisor 的做法。正因为标准库之上已经具备了应用级安全隔离，不再担心控制业务逻辑写坏宿主内核，我们就可以把电机控制这类实时应用直接写成安全 Rust 线程，放在宿主内核态运行。这样一来，整台实时客户机的内存和启动开销直接省掉了；控制外设由宿主直接管理时，物理硬件中断一到就直达宿主实时线程，连二阶段页表转换和虚拟中断转发的开销也一并归零，旁边的复杂 Linux 视觉业务依然关在硬件隔离的客户机沙箱里。

同时，右侧那些容易写错的底层实时调度和同步机制都已经收敛在标准库之下：右上角通过截止期调度、固定优先级抢占和公平分时三层策略，保证周期控制线程严格优先于普通管理线程；右下角通过优先级继承互斥锁和可睡眠实时锁消除优先级反转。上层控制代码不用碰关中断细节，就能拿到确定性的实时响应。除了省掉实时客户机，标准库隔离层还彻底改变了宿主机自身的业务开发方式。"""
    )

    # =========================================================================
    # SLIDE 12: 03 安全隔离——复用 std crate 大幅简化业务开发
    # =========================================================================
    s12 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s12, True, "03 安全隔离", BRAND_BLUE,
        "简化业务开发：内核态直接复用成熟 std crate 生态",
        "底层调度、锁与网络协议收敛在 std 之下，上层直接引入应用层开源库快速构建复杂管控业务",
        12, "研发提效",
        "告别裸机 no_std 从零手写协议与状态机，在内核态以普通应用开发体验交付板载网页管理台与多路终端。"
    )
    service_steps = [
        ("1. 收敛底层机制", "调度、同步锁、文件系统\n与网络栈封装在底层模块", SLATE_DARK),
        ("2. 标准库安全边界", "ax-std 提供标准系统接口\n内核态函数直调零切换损耗", SAFE_GREEN),
        ("3. 引入成熟 std crate", "直接编译运行 Tokio、Axum\n与 Serde 等应用层开源库", BRAND_BLUE),
        ("4. 极简交付复杂业务", "少量安全代码实现板载网页\n管理台与多路远程串口终端", PURPLE),
    ]
    for index, (label, description, color) in enumerate(service_steps):
        x = 1.12 + index * 6.29
        add_card(s12, x, 2.80, 5.56, 1.88, title=label, accent=color, fill=WHITE, border=color, title_size=22, header_band=True, header_band_h=0.58)
        add_textbox(s12, x + 0.16, 3.44, 5.24, 1.14, description, size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)
        if index < len(service_steps) - 1:
            arrow_dir = "lr" if index == 2 else "right"
            add_arrow(s12, x + 5.66, 3.54, 0.52, 0.44, arrow_dir, color)

    screenshots = [
        (1.12, media["web_ui"], "实机网页管理台：基于 Axum + Tokio 构建，直观查看与启停各台客户机", BRAND_BLUE),
        (13.68, media["web_term"], "浏览器多路终端：基于 WebSocket 生态库直连宿主与多台客户机串口", SAFE_GREEN),
    ]
    for x, blob, caption, color in screenshots:
        add_rect(s12, x, 4.86, 11.87, 6.68, fill=WHITE, border=color, border_pt=1.6, rounded=True, radius=0.03)
        add_picture_fit(s12, blob, x + 0.14, 4.95, 11.59, 5.75, frame_border=None, pad=0.04)
        add_textbox(s12, x + 0.12, 10.80, 11.63, 0.62, caption, size=20, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s12,
        "简化业务开发：内核态直接复用成熟 std crate 生态",
        "03 安全隔离",
        1.6,
        """第二个直接收益，是用标准库开源生态大幅简化宿主侧的业务开发。传统裸机虚拟机监控器在内核态只有最基础的无标准库环境，开源社区里绝大多数成熟的网络框架、异步运行时和配置解析库全都依赖操作系统标准库，在裸机里根本用不了；想加一套动态管理接口或远程调试通道，只能从底层字节流和状态机手写，既费工又容易引入新的内存安全问题。

上方这条链路展示了打通标准库隔离层前后的对比：底层的线程调度、同步锁、文件系统和网络协议栈统一收敛在标准库接口之下，向上提供完整的标准库环境。开发者在宿主内核里写业务，体验和在普通电脑上写应用完全一样，可以直接引入社区成熟的 Tokio 异步运行时、Axum 网页框架和配置序列化库，全程只写安全 Rust 业务逻辑。

下方两张实机浏览器截图就是最直观的例子：不需要在板卡上挂一个重型 Linux 宿主机，裸机运行的 AxVisor 靠几百行上层安全业务代码，就提供了完整的网页虚拟机管理台和浏览器多路串口终端，插一根网线就能随时查看资源占用、动态启停客户机并同时交互调试多套系统。宿主机内部自有的实时与管控业务靠标准库隔离开之后，面对外部客户机的虚拟设备配置与内存访问，又该怎么把边界管清楚？"""
    )

    # =========================================================================
    # SLIDE 13: 04 声明式设备图——同源双生分叉拓扑图
    # =========================================================================
    s13 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s13, False, "04 声明式设备图", PURPLE,
        "声明式设备图：同源双生配置与按次最小授权",
        "一份设备声明经过冲突检查后，同时生成宿主路由表与客户机固件描述，运行期按请求临时借用内存",
        13, "设备边界",
        "消除手工同步宿主与客户机地址的错位隐患，虚拟设备在回调窗口外不持有客户机全量内存。"
    )
    # Stage 1 (Left): Config -> Planner -> Single Resolved Graph
    add_card(s13, 1.12, 2.84, 6.76, 6.32, title="1. 声明需求与冲突检查", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=24, header_band=True)
    add_rect(s13, 1.38, 3.76, 6.24, 1.72, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.2)
    add_textbox(s13, 1.54, 3.84, 5.92, 0.42, "客户机外置配置文件", size=21, color=DARK_NAVY, bold=True)
    add_textbox(s13, 1.54, 4.30, 5.92, 1.08, "只声明需要哪些虚拟串口、磁盘或网卡，无需人工计算与硬编码地址", size=19, color=BODY_TEXT, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s13, 4.28, 5.56, 0.44, 0.36, "down", BRAND_BLUE)
    add_rect(s13, 1.38, 6.00, 6.24, 2.88, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.8)
    add_textbox(s13, 1.54, 6.10, 5.92, 0.44, "设备规划器 → 唯一已解析设备图", size=21, color=BRAND_BLUE, bold=True)
    add_textbox(s13, 1.54, 6.60, 5.92, 2.14, "• 自动分配寄存器地址段与中断号\n• 启动前静态拦截地址重叠与资源冲突\n• 固化为唯一权威的数据源", size=19.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24)

    # 1-to-2 Visual Fork Arrows into Center Stage!
    add_arrow(s13, 8.00, 4.70, 0.84, 0.50, "right", PURPLE)
    add_arrow(s13, 8.00, 7.36, 0.84, 0.50, "right", BRAND_BLUE)

    # Stage 2 (Center): True 1-to-2 Fork (Host Dispatch Table + Guest FDT/ACPI)
    add_card(s13, 8.96, 2.84, 8.12, 6.32, title="2. 一份设备图，同源双生输出", accent=PURPLE, fill=WHITE, border=PURP_BORDER, title_size=24, header_band=True)
    add_rect(s13, 9.24, 3.76, 7.56, 2.38, fill=PURP_BG, border=PURPLE, border_pt=1.8)
    add_textbox(s13, 9.44, 3.86, 7.16, 0.46, "对内输出：宿主模拟设备路由表", size=21.5, color=PURPLE, bold=True)
    add_textbox(s13, 9.44, 4.38, 7.16, 1.62, "客户机访问某段设备地址触发拦截时，宿主按这张路由表精准分发给对应的虚拟设备实例", size=19.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.2)

    add_rect(s13, 9.24, 6.46, 7.56, 2.42, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.8)
    add_textbox(s13, 9.44, 6.56, 7.16, 0.46, "对外输出：客户机设备树 / ACPI 固件表", size=21.5, color=BRAND_BLUE, bold=True)
    add_textbox(s13, 9.44, 7.08, 7.16, 1.66, "由同一份分配结果自动生成硬件描述表交给客户机内核，从根源上杜绝两边地址或中断号对不上", size=19.5, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.2)

    # Arrow into Stage 3 (Runtime Scoped Grant)
    add_arrow(s13, 17.20, 5.76, 0.68, 0.50, "right", SAFE_GREEN)

    # Stage 3 (Right): Per-Request Scoped Memory Grant Lifecycle
    add_card(s13, 18.00, 2.84, 7.55, 6.32, title="3. 运行期按次最小授权", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=24, header_band=True)
    add_rect(s13, 18.28, 3.76, 6.99, 1.32, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.2)
    add_textbox(s13, 18.44, 3.84, 6.67, 1.16, "虚拟磁盘或网卡收到单次读写请求\n不预先持有整台客户机的内存引用", size=19, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s13, 21.56, 5.14, 0.42, 0.30, "down", SAFE_GREEN)
    add_rect(s13, 18.28, 5.50, 6.99, 1.72, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.8)
    add_textbox(s13, 18.44, 5.58, 6.67, 1.56, "按已登记授权区间签发临时访问句柄\n仅在本次回调窗口内借用目标内存段", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.2)
    add_arrow(s13, 21.56, 7.28, 0.42, 0.30, "down", ALERT_RED)
    add_rect(s13, 18.28, 7.64, 6.99, 1.24, fill=RED_BG, border=ALERT_RED, border_pt=1.5)
    add_textbox(s13, 18.44, 7.70, 6.67, 1.12, "回调结束自动收回句柄，杜绝悬垂越界访问", size=19.5, color=ALERT_RED, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # Bottom Bar: Passthrough & IVC Collaboration
    add_rect(s13, 1.12, 9.38, 24.43, 2.02, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.4, rounded=True, radius=0.05)
    add_rect(s13, 1.40, 9.58, 11.78, 1.62, fill=WHITE, border=AMBER_ORG, border_pt=1.4, rounded=True, radius=0.05)
    add_textbox(s13, 1.62, 9.66, 11.34, 0.42, "物理硬件直通延伸", size=20.5, color=AMBER_ORG, bold=True)
    add_textbox(s13, 1.62, 10.12, 11.34, 0.98, "设备图同样管理真实外设直通，将物理寄存器区间与硬件中断独占映射给目标客户机。", size=19, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s13, 13.48, 9.58, 11.78, 1.62, fill=WHITE, border=SAFE_GREEN, border_pt=1.4, rounded=True, radius=0.05)
    add_textbox(s13, 13.70, 9.66, 11.34, 0.42, "跨客户机高速协作", size=20.5, color=SAFE_GREEN, bold=True)
    add_textbox(s13, 13.70, 10.12, 11.34, 0.98, "按配置建立受控共享内存页与核间门铃中断，让视觉客户机与实时控制端零拷贝交换结果。", size=19, color=DARK_NAVY, valign=MSO_ANCHOR.MIDDLE)

    add_notes(
        s13,
        "声明式设备图：同源双生配置与按次最小授权",
        "04 声明式设备图",
        1.7,
        """手工配置嵌入式虚拟机时有一个非常高频的踩坑点：给 Linux 客户机加一个虚拟串口或虚拟磁盘，宿主机这边配置了一段寄存器地址和中断号，客户机的设备树或固件表里还得手动再抄一遍；只要有一边改了地址忘了同步，客户机启动后就会找不到设备或者发错中断。

看图里从左到中间的同源分叉流程。在 AxVisor 里，配置文件只声明客户机需要什么设备，不手填具体地址。启动准备阶段，左边的设备规划器统一分配地址段和中断号，静态检查有没有资源重叠，生成唯一一份已解析设备图。接着由这一份设备图同时分出两路输出：一路对内生成宿主机的模拟设备路由表，客户机访问该地址时宿主机按表精准派发；另一路对外自动生成客户机启动读取的设备树或固件描述表。两边出自同一个数据源，天然不会错位。

再看最右边的运行期内存权限控制。虚拟磁盘要把读出的数据写回客户机内存时，我们不允许虚拟设备长期持有整台客户机的内存引用，而是按单次请求和事先登记的授权范围，在回调窗口内临时借出一个受限访问入口，回调一返回立刻收回。底下两格则把同一套设备图延伸到了真实外设直通与跨客户机共享内存通道。这套架构落到真实的八核嵌入式开发板上表现如何？我们直接看两套实机部署案例。"""
    )

    # =========================================================================
    # SLIDE 14: 实机部署——RK3588 多客户机混合运行案例
    # =========================================================================
    s14 = new_styled_slide(prs, stamps["white"])
    add_content_chrome(
        s14, False, "05 实机与验证", AMBER_ORG,
        "实机部署：RK3588 大小核直通与多系统全虚拟化",
        "基于 Orange Pi 5 Plus (RK3588) 的两套实板拓扑：异构双客户机外设直通与单芯三客户机全虚拟化",
        14, "实机部署",
        "按硬件依赖边界划分外设归属，兼顾大小核直通低时延协作与多客户机虚拟网络存储共享。"
    )
    add_card(s14, 1.12, 2.84, 11.95, 6.72, title="案例一：大小核设备直通双客户机（dual-linux-zephyr / dual-starry-zephyr）", accent=AMBER_ORG, fill=WHITE, border=AMBER_BORDER, title_size=22, header_band=True)
    add_textbox(s14, 1.38, 3.60, 11.43, 0.40, "Orange Pi 5 Plus (RK3588)：大核独占视觉算力外设，小核独占控制串口，宿主守护共享链路", size=19, color=AMBER_ORG, bold=True)

    add_rect(s14, 1.38, 4.08, 5.06, 2.52, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(s14, 1.46, 4.14, 4.90, 0.48, "感知域 · A76 大核 (Linux/StarryOS)", size=18, color=BRAND_BLUE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s14, 1.52, 4.64, 4.78, 1.86,
        "• 直通 USB3 摄像头与 RKNPU 推理\n"
        "• 从客户机设备树剔除共享 PCIe PHY\n"
        "  防止客户机复位冲掉宿主管理网卡",
        size=18.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18
    )

    # Hardware isolation wall + IVC bridge across wall
    add_rect(s14, 6.96, 4.06, 0.16, 2.56, fill=ALERT_RED, border=None, rounded=False)
    add_arrow(s14, 6.54, 4.86, 1.00, 0.50, "lr", SAFE_GREEN)
    add_rect(s14, 6.42, 5.44, 1.24, 0.96, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.2, rounded=True, radius=0.08)
    add_textbox(s14, 6.44, 5.46, 1.20, 0.92, "robot-ivc\n共享内存", size=16, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.12)

    add_rect(s14, 7.68, 4.08, 5.12, 2.52, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(s14, 7.76, 4.14, 4.96, 0.48, "控制域 · A55 小核 (Zephyr 实时)", size=18, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s14, 7.82, 4.64, 4.84, 1.86,
        "• 独占物理串口 UART6 (/serial@feb90000)\n"
        "• 驱动底盘、机械臂与看门狗回路\n"
        "• 与大核视觉系统严格硬件故障隔离",
        size=18.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18
    )

    add_arrow(s14, 3.70, 6.66, 0.36, 0.30, "down", DARK_NAVY)
    add_arrow(s14, 10.06, 6.66, 0.36, 0.30, "down", DARK_NAVY)

    add_rect(s14, 1.38, 7.02, 11.42, 2.28, fill=DARK_NAVY, border=None, rounded=True, radius=0.06)
    add_textbox(
        s14, 1.58, 7.10, 11.02, 2.12,
        "AxVisor 宿主内核（独占共享基础设施与多路远程运维）\n"
        "• 持有物理管理串口、PCIe PHY 与 RTL8125 物理网卡，保障远程管控链路不断线\n"
        "• 对外输出三路独立 WebSocket 终端，同一浏览器同时观测宿主、Linux 与 Zephyr",
        size=19.5, color=WHITE, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    add_card(s14, 13.60, 2.84, 11.95, 6.72, title="案例二：单芯三客户机全虚拟化（triple-guest-functional）", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=22, header_band=True)
    add_textbox(s14, 13.86, 3.60, 11.43, 0.40, "同一块 RK3588 板卡并发运行三套异构客户机，共享单一物理网卡与板载存储", size=19, color=BRAND_BLUE, bold=True)

    guests3 = [
        ("客户机 1：Linux 6.1.99", "独立虚拟块设备根盘\n虚拟网卡接入内建交换机\n完成离线软件包安装校验", SAFE_GREEN, SAFE_BG),
        ("客户机 2：StarryOS", "本工作区构建宏内核\n独立 ext4 根盘 + 虚拟网卡\n同样通过软件包安装校验", BRAND_BLUE, ICE_FILL),
        ("客户机 3：Zephyr", "合成虚拟中断控制器\n独立虚拟串口交互终端\n三台客户机并发在线运行", PURPLE, PURP_BG),
    ]
    for gi, (gt, gd, gc, gb) in enumerate(guests3):
        gx = 13.86 + gi * 3.84
        add_rect(s14, gx, 4.08, 3.66, 2.52, fill=gb, border=gc, border_pt=1.6, rounded=True, radius=0.06)
        add_rect(s14, gx + 0.12, 4.18, 3.42, 0.50, fill=gc, border=None, rounded=True, radius=0.10)
        add_textbox(s14, gx + 0.16, 4.18, 3.34, 0.50, gt, size=18.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s14, gx + 0.14, 4.78, 3.38, 1.70, gd, size=18.5, color=DARK_NAVY, bold=False, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.18)
        add_arrow(s14, gx + 1.65, 6.64, 0.36, 0.34, "ud", gc)

    add_rect(s14, 13.86, 7.02, 11.42, 2.28, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(
        s14, 14.06, 7.10, 11.02, 2.12,
        "AxVisor 宿主内建二层虚拟交换机 + 统一存储与终端复用\n"
        "• 宿主独占板载 eMMC 文件系统与单块 RTL8125 物理网卡\n"
        "• Linux 与 StarryOS 的虚拟网卡经宿主内建二层交换机互通并接入外部局域网",
        size=19.5, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.24
    )

    add_rect(s14, 1.12, 9.76, 12.10, 1.72, fill=AMBER_BG, border=AMBER_BORDER, border_pt=1.4, rounded=True, radius=0.06)
    add_textbox(s14, 1.34, 9.84, 11.66, 0.44, "已覆盖 7 款实体板卡/主机 + 4 架构模拟器（configs/board/）", size=21, color=AMBER_ORG, bold=True)
    add_textbox(s14, 1.34, 10.30, 11.66, 1.08, "Orange Pi 5 Plus (RK3588) · 飞腾派 (E2000) · ROC-RK3568-PC · RDK-S100 · Rock 4D · TAC-E400 · ASUS NUC15CRH (x86_64)", size=19.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22)

    add_rect(s14, 13.45, 9.76, 12.10, 1.72, fill=SAFE_BG, border=SAFE_BORDER, border_pt=1.4, rounded=True, radius=0.06)
    add_textbox(s14, 13.67, 9.84, 11.66, 0.44, "已适配 6 种客户机系统 · 共 62 份客户机配置（configs/vms/）", size=21, color=SAFE_GREEN, bold=True)
    add_textbox(s14, 13.67, 10.30, 11.66, 1.08, "Linux · ArceOS · StarryOS · Zephyr · FreeRTOS · RT-Thread\n支持单核与对称多核 · 全虚拟化与物理外设直通灵活组合", size=19.5, color=DARK_NAVY, bold=False, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22)

    add_notes(
        s14,
        "实机部署：RK3588 大小核直通与多系统全虚拟化",
        "05 实机与验证",
        1.7,
        """真正把多套系统部署到一块像 RK3588 这样的八核嵌入式开发板上，外设分配往往比想象中棘手，因为片上外设之间常有共享的底层时钟和物理层依赖，不能孤立地切分地址。

看左边第一套机器人实机拓扑。我们把四颗大核划给 Linux 或 StarryOS 客户机，直通摄像头和神经网络加速核跑视觉感知；把小核划给实时系统 Zephyr，独占一路物理串口去驱动底盘和机械臂，两边中间隔着硬件故障墙，只通过受控的共享内存通道交换识别结果。这里有个很典型的实板细节：板载管理网卡依赖的底层物理层控制器如果也一并暴露给大核客户机，客户机初始化时一旦复位这个共享控制器，宿主机自己的网页管理台就会瞬间断网。因此配置里专门剔除了这部分共享底层硬件，由宿主统一守护。

右边是同一块板卡上的全虚拟化三系统拓扑：实体网卡和板载存储全部留给宿主，上面同时拉起 Linux、我们自研的宏内核 StarryOS 以及实时系统 Zephyr 三台客户机，共用宿主内建的二层虚拟交换机和虚拟块设备并发联网运行。左边这套大小核机器人配置上板之后，实际跑出了怎样的效果？"""
    )

    # =========================================================================
    # SLIDE 15: 机器人实板结果
    # =========================================================================
    s15 = new_styled_slide(prs, stamps["gradient"])
    add_content_chrome(
        s15, True, "05 实机与验证", AMBER_ORG,
        "实机结果：RK3588 机器人双客户机闭环验证",
        "Orange Pi 5 Plus（RK3588） · 2026 年 9 月 21 日实板运行记录",
        15, "验证结果",
        "两组异构双系统配置均跑满约 30 帧每秒摄像头感知帧率，跨客户机通道零丢帧并完成控制反馈。"
    )

    # Left Card: Visual Cross-Domain Closed-Loop Architecture
    add_card(s15, 1.12, 2.84, 12.12, 8.65, title="板端实测的跨客户机感知与控制闭环", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=25, header_band=True)

    add_rect(s15, 1.44, 3.80, 11.48, 2.26, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(s15, 1.66, 3.90, 11.04, 0.44, "感知客户机域（A76 大核：Linux 或 StarryOS）", size=21.5, color=BRAND_BLUE, bold=True)
    add_rect(s15, 1.66, 4.46, 5.04, 1.38, fill=WHITE, border=BRAND_BLUE, border_pt=1.2)
    add_textbox(s15, 1.78, 4.54, 4.80, 1.22, "USB3 摄像头实时采集\n持续输入真实视频流", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s15, 6.84, 4.94, 0.64, 0.42, "right", BRAND_BLUE)
    add_rect(s15, 7.62, 4.46, 5.04, 1.38, fill=WHITE, border=BRAND_BLUE, border_pt=1.2)
    add_textbox(s15, 7.74, 4.54, 4.80, 1.22, "调用直通 RKNPU\n执行实时目标检测推理", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_arrow(s15, 6.94, 6.14, 0.44, 0.34, "down", SAFE_GREEN)
    add_rect(s15, 1.84, 6.54, 10.68, 1.34, fill=SAFE_BG, border=SAFE_GREEN, border_pt=2.0, rounded=True, radius=0.12)
    add_textbox(s15, 2.04, 6.62, 10.28, 1.18, "跨客户机共享内存通道（robot-ivc）+ 核间通知中断\n高频传递感知结果与控制指令 · 全程实测丢帧数：0", size=20, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.2)
    add_arrow(s15, 6.94, 7.94, 0.44, 0.34, "down", AMBER_ORG)

    add_rect(s15, 1.44, 8.34, 11.48, 2.80, fill=AMBER_BG, border=AMBER_ORG, border_pt=1.8, rounded=True, radius=0.06)
    add_textbox(s15, 1.66, 8.44, 11.04, 0.44, "实时控制客户机域（A55 小核：Zephyr）", size=21.5, color=AMBER_ORG, bold=True)
    add_rect(s15, 1.66, 9.00, 5.04, 1.88, fill=WHITE, border=AMBER_ORG, border_pt=1.2)
    add_textbox(s15, 1.78, 9.08, 4.80, 1.72, "接收跨机目标消息\n生成底盘与机械臂控制动作", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_arrow(s15, 6.84, 9.72, 0.64, 0.42, "right", AMBER_ORG)
    add_rect(s15, 7.62, 9.00, 5.04, 1.88, fill=WHITE, border=AMBER_ORG, border_pt=1.2)
    add_textbox(s15, 7.74, 9.08, 4.80, 1.72, "回传执行状态反馈\n用例结束自动复位清理资源", size=19.5, color=DARK_NAVY, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # Right Card: Visual 30-FPS Progress Bars + Zero-Drop Badges + Honest Scope Note
    add_card(s15, 13.60, 2.84, 11.95, 8.65, title="两段采样的实测感知帧率与通道指标", accent=SAFE_GREEN, fill=WHITE, border=SAFE_BORDER, title_size=25, header_band=True)
    measurements = [
        ("Linux + Zephyr 双系统", "29.94 / 29.99 FPS", 29.965 / 30.0, BRAND_BLUE, ICE_FILL),
        ("StarryOS + Zephyr 双系统", "29.47 / 30.02 FPS", 29.745 / 30.0, SAFE_GREEN, SAFE_BG),
    ]
    for index, (label, values, ratio, color, fill) in enumerate(measurements):
        y = 3.80 + index * 1.94
        add_rect(s15, 13.94, y, 11.27, 1.72, fill=fill, border=color, border_pt=1.5, rounded=True, radius=0.05)
        add_textbox(s15, 14.16, y + 0.10, 5.60, 0.64, label, size=23, color=DARK_NAVY, bold=True, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s15, 19.76, y + 0.08, 5.20, 0.68, values, size=27, color=color, bold=True, align=PP_ALIGN.RIGHT, valign=MSO_ANCHOR.MIDDLE)
        bar_w = 10.80
        add_rect(s15, 14.16, y + 0.88, bar_w, 0.34, fill=WHITE, border=GRAY_BORDER, border_pt=0.9, rounded=True, radius=0.35)
        add_rect(s15, 14.16, y + 0.88, bar_w * min(1.0, ratio), 0.34, fill=color, border=None, rounded=True, radius=0.35)
        add_textbox(s15, 14.18, y + 1.24, 10.76, 0.42, "对比 30 FPS 摄像头满帧基线：直通摄像头与加速核基本无帧率损耗", size=16.5, color=MUTED_TEXT, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s15, 13.94, 7.72, 5.46, 1.12, fill=SAFE_BG, border=SAFE_GREEN, border_pt=1.5, rounded=True, radius=0.06)
    add_textbox(s15, 14.08, 7.80, 5.18, 0.96, "IVC 跨机丢帧：0\n两组配置全程零丢包", size=20.5, color=SAFE_GREEN, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_rect(s15, 19.75, 7.72, 5.46, 1.12, fill=ICE_FILL, border=BRAND_BLUE, border_pt=1.5, rounded=True, radius=0.06)
    add_textbox(s15, 19.89, 7.80, 5.18, 0.96, "控制反馈与清理：通过\n双端状态同步完整闭环", size=20.5, color=BRAND_BLUE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    add_rect(s15, 13.94, 9.04, 11.27, 1.24, fill=LIGHT_GRAY, border=GRAY_BORDER, border_pt=1.1, rounded=True, radius=0.05)
    add_textbox(s15, 14.15, 9.12, 10.85, 1.08, "测试边界说明：控制阶段使用预设识别结果触发受控动作，末端夹持反馈允许模拟。", size=20, color=BODY_TEXT, valign=MSO_ANCHOR.MIDDLE)
    source = add_textbox(s15, 14.13, 10.46, 10.88, 0.55, "来源：TGOSKits 2026 年 9 月月报 §2.7（PR #2314）", size=19, color=BRAND_BLUE, valign=MSO_ANCHOR.MIDDLE)
    source.text_frame.paragraphs[0].runs[0].hyperlink.address = (
        "https://github.com/rcore-os/tgoskits/blob/a28226c70077f5120b9ab05ed44e2bf498811e6a/"
        "docs/blog/2026/10-01-september-2026-retrospective/september-2026-retrospective.md#L125-L134"
    )

    add_notes(
        s15,
        "实机结果：RK3588 机器人双客户机闭环验证",
        "05 实机与验证",
        1.5,
        """在 RK3588 实板上，我们分别用 Linux 配 Zephyr、以及自研宏内核 StarryOS 配 Zephyr 两组双客户机方案跑了实测。看左边的闭环链路，前半段由大核客户机接真实摄像头和神经网络加速核跑实时视觉推理，后半段通过跨客户机共享内存通道把预设的目标识别结果发给小核上的 Zephyr，检查控制端能不能按序执行动作、回传状态并完成资源清理。

看右边的实测采样数据：无论大核跑的是原生 Linux 还是 StarryOS，两段采样的视觉感知帧率都稳定在每秒 29.5 到 30 帧之间，基本跑满了 30 帧摄像头的硬件上限，说明外设直通和二阶段页表几乎没有带来可感知的吞吐损耗；同时跨客户机共享内存通道全程记录为零丢帧。这里也客观说明测试边界：控制阶段采用预设识别结果并允许模拟末端夹持反馈，核心验证的是异构双系统在真板上的硬件隔离、高速通信与控制闭环；双客户机机器人用例在这批实测后曾暂停自动检查。"""
    )

    # =========================================================================
    # SLIDE 16: 总结与开源交流
    # =========================================================================
    s17 = new_styled_slide(prs, stamps["white"])
    add_textbox(
        s17, 1.12, 1.24, 24.43, 0.72, "总结与开源交流",
        size=40, color=DARK_NAVY, bold=True,
        valign=MSO_ANCHOR.MIDDLE, margin=(0.04, 0.04, 0, 0)
    )
    add_textbox(
        s17, 10.60, 13.48, 3.00, 0.48, f"16 / {TOTAL_SLIDES}",
        size=20, color=MUTED_TEXT, bold=True, align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE
    )

    add_card(s17, 1.50, 3.66, 15.20, 7.28, title="小结与开源仓库", accent=BRAND_BLUE, fill=WHITE, border=BORDER_BLU, title_size=27, header_band=True)
    takeaways = [
        ("1. 组件化专用宿主：", "基于 TGOSKits 按需组装，跨芯片自底向上求同存异复用执行骨架。", BRAND_BLUE),
        ("2. std 安全隔离层：", "收敛底层调度与 unsafe 汇编，在内核态构建应用级安全开发环境。", SAFE_GREEN),
        ("3. 省开销与提效率：", "内核态安全直跑实时任务省掉实时客户机，直接复用 std crate 简化开发。", AMBER_ORG),
        ("4. 声明式设备图：", "一份配置同源生成宿主路由表与客户机固件描述，按请求最小授权。", PURPLE),
    ]
    for ti, (thead, tbody, tcol) in enumerate(takeaways):
        ty = 4.48 + ti * 0.79
        add_rect(s17, 1.82, ty, 14.56, 0.68, fill=ICE_FILL, border=BORDER_BLU, border_pt=1.0, rounded=True, radius=0.06)
        add_rich_paragraphs(
            s17, 2.00, ty + 0.02, 14.20, 0.64,
            [([(thead, 21.5, tcol, True, FONT_CJK), (tbody, 21, DARK_NAVY, True, FONT_CJK)], 0, PP_ALIGN.LEFT)],
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
        1.0,
        """最后回到开场提到的那块机器人主控板。面对单颗多核芯片既要跑复杂视觉应用、又要保住硬实时控制的矛盾，AxVisor 给出的答案是用 TGOSKits 组件按需组装一个专用的裸机宿主内核：对下通过自底向上的求同存异屏蔽四种处理器差异；对内以内核态标准库为安全隔离分界线，把底层的复杂调度和 unsafe 汇编收敛起来，让上层既能直接在宿主态安全跑实时任务、省掉独立实时客户机开销，又能复用成熟的标准库生态快速构建网页管理台；对外则用声明式设备图管住客户机隔离与外设分配。

左边是我们的主仓库和测试工具仓库地址，克隆下来用一条命令就能先在模拟器里跑通体验。如果大家手头也有机器人、车载或工业控制方面的多系统混跑场景，欢迎扫右边的二维码加我微信，我们深入交流。"""
    )

    # SLIDE 17: 模板致谢页
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
