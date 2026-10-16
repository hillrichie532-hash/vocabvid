#!/usr/bin/env python3
"""VocabVid v6 — preview-first Anki vocab video maker."""
import hashlib
import html as html_mod
import json
import queue
import random
import re
import subprocess
import threading
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, colorchooser, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk


# ═══════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════
TH = {
    "bg":          "#0D0F14",
    "panel":       "#14171E",
    "panel_2":     "#181C24",
    "border":      "#232830",
    "divider":     "#1F242E",
    "text":        "#E8EAED",
    "text_2":      "#B5BCC8",
    "muted":       "#9DA4B2",
    "faint":       "#5C6472",
    "accent":      "#3B82F6",
    "accent_2":    "#2563EB",
    "accent_fg":   "#FFFFFF",
    "hover":       "#1C2028",
    "selected":    "#1E293B",
    "green":       "#10B981",
    "grey":        "#6B7280",
    "chip_border": "#2E3440",
    "danger":      "#EF4444",
}

RESOLUTIONS = {"720p": (1280, 720), "1080p": (1920, 1080), "1440p": (2560, 1440)}
FPS = 30
SETTINGS_FILE = Path.home() / ".vocabvid.json"

DEFAULTS = {
    "tsv": "", "media": "", "out_dir": str(Path.home() / "Videos"), "out_prefix": "vocab",
    "render_mode": "all", "from_card": 1, "to_card": 0, "chunk": 100,
    "col_chinese": -1, "col_pinyin": -1, "col_meaning": -1, "col_example": -1,
    "quality": "1080p",
    "cn_x": 0.50, "cn_y": 0.30, "cn_size": 300, "cn_color": "#FFD93D",
    "py_x": 0.50, "py_y": 0.56, "py_size": 50,  "py_color": "#64B4FF",
    "en_x": 0.50, "en_y": 0.72, "en_size": 34,  "en_color": "#DCDCE1",
    "ex_x": 0.50, "ex_y": 0.86, "ex_size": 28,  "ex_color": "#A0A0A8",
    "img_x": 0.50, "img_y": 0.50, "img_size": 200,
    "pill_color": "#EBEEF5",
    "reveal": 2.5, "tail": 0.6,
    "bg_base": "gradient", "bg_solid": "#0A0A0F",
    "bg_top": "#10121C", "bg_bot": "#08080E",
    "bg_image": "", "bg_opacity": 1.0, "bg_darken": 0.45,
    "word_vol": 1.0, "example_vol": 1.0,
    "music_dir": "", "music_vol": 0.5, "music_shuffle": True,
    "window_geom": "1440x900",
    "sections_open": {
        "text_styles": True, "background": False, "sound": False,
        "render": False, "files": False,
    },
}

NAMED_COLORS = [
    ("White",      "#FFFFFF"),
    ("Black",      "#000000"),
    ("Grey",       "#8B92A0"),
    ("Light Grey", "#D1D5DB"),
    ("Dark Grey",  "#4B5563"),
    ("Red",        "#EF4444"),
    ("Orange",     "#F97316"),
    ("Yellow",     "#FACC15"),
    ("Green",      "#22C55E"),
    ("Teal",       "#14B8A6"),
    ("Blue",       "#3B82F6"),
    ("Navy",       "#1E3A8A"),
    ("Purple",     "#8B5CF6"),
    ("Pink",       "#EC4899"),
    ("Brown",      "#92400E"),
]


GRADIENT_PALETTES = {
    "Dark":     ("#10121C", "#08080E"),
    "Clean":    ("#FFFFFF", "#E5E7EB"),
    "Sunset":   ("#F59E0B", "#7C2D12"),
    "Ocean":    ("#0E7490", "#082F49"),
    "Forest":   ("#166534", "#052E16"),
    "Twilight": ("#7C3AED", "#1E1B4B"),
    "Paper":    ("#FEF3C7", "#D6C9A4"),
    "Sky":      ("#DBEAFE", "#60A5FA"),
}


# ═══════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════
def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
]
BOLD_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
    r"C:\Windows\Fonts\msyhbd.ttc",
]
_font_cache = {}


def get_font(size, bold=False):
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    paths = BOLD_PATHS if bold else FONT_PATHS
    for p in paths:
        if Path(p).exists():
            try:
                f = ImageFont.truetype(p, size)
                _font_cache[key] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def show_color_popup(parent, on_pick, anchor_widget):
    popup = tk.Toplevel(parent)
    popup.overrideredirect(True)
    popup.transient(parent)
    popup.configure(bg=TH["border"])
    frame = tk.Frame(popup, bg=TH["panel"])
    frame.pack(fill="both", expand=True, padx=1, pady=1)
    grid = tk.Frame(frame, bg=TH["panel"])
    grid.pack(padx=10, pady=10)
    tooltip_var = tk.StringVar(value="")
    tip = tk.Label(frame, textvariable=tooltip_var, bg=TH["panel"],
                   fg=TH["muted"], font=("TkDefaultFont", 8), height=1)
    tip.pack(fill="x", pady=(0, 6))
    def pick(hex_color):
        on_pick(hex_color)
        try:
            popup.grab_release()
        except Exception:
            pass
        popup.destroy()
    for i, (name, hex_color) in enumerate(NAMED_COLORS):
        r, c = divmod(i, 5)
        sw = tk.Canvas(grid, width=26, height=26, bg=hex_color,
                       highlightthickness=1,
                       highlightbackground=TH["chip_border"],
                       cursor="hand2", bd=0)
        sw.grid(row=r, column=c, padx=3, pady=3)
        sw.bind("<Button-1>", lambda e, h=hex_color: pick(h))
        sw.bind("<Enter>", lambda e, n=name: tooltip_var.set(n))
        sw.bind("<Leave>", lambda e: tooltip_var.set(""))
    popup.update_idletasks()
    pw = popup.winfo_reqwidth()
    ph = popup.winfo_reqheight()
    ax = anchor_widget.winfo_rootx()
    ay = anchor_widget.winfo_rooty()
    aw = anchor_widget.winfo_width()
    ah = anchor_widget.winfo_height()
    sw_screen = popup.winfo_screenwidth()
    sh_screen = popup.winfo_screenheight()
    px = ax + aw + 6
    if px + pw > sw_screen - 10:
        px = ax - pw - 6
    py = ay
    if py + ph > sh_screen - 10:
        py = sh_screen - ph - 10
    popup.geometry(f"+{px}+{py}")
    try:
        popup.grab_set()
    except Exception:
        pass
    popup.focus_force()
    popup.bind("<Escape>", lambda e: popup.destroy())
    return popup


def pick_ui_font(root):
    fams = set(tkfont.families(root))
    for f in ["Inter", "SF Pro Display", "Segoe UI", "Cantarell",
              "Ubuntu", "Noto Sans", "DejaVu Sans"]:
        if f in fams:
            return f
    return "TkDefaultFont"


def find_anki_profiles():
    home = Path.home()
    bases = [
        home / ".local/share/Anki2",
        home / ".var/app/net.ankiweb.Anki/data/Anki2",
        home / "snap/anki-desktop/common",
        home / "Library/Application Support/Anki2",
    ]
    appdata = home / "AppData/Roaming/Anki2"
    if appdata.exists():
        bases.append(appdata)
    found = []
    for base in bases:
        if not base.exists():
            continue
        for prof in base.iterdir():
            if not prof.is_dir():
                continue
            media = prof / "collection.media"
            if media.exists():
                found.append((prof.name, media))
    return found


# ═══════════════════════════════════════════════════════════
# DECK PARSING
# ═══════════════════════════════════════════════════════════
AUDIO_RE = re.compile(r"\[sound:([^\]]+)\]", re.I)
IMG_RE = re.compile(r"<img[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
TONE_RE = re.compile(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹ]", re.I)


def strip_html(s):
    s = AUDIO_RE.sub("", s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return " ".join(html_mod.unescape(s).split())


def parse_tsv(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#"):
                continue
            rows.append(line.split("\t"))
    return rows


def detect_columns(rows, sample=10):
    if not rows:
        return {"chinese": 0, "pinyin": -1, "meaning": -1, "example": -1}
    ncols = max(len(r) for r in rows[:sample])
    scores = [{"cjk_short": 0, "cjk_long": 0, "tone": 0, "latin": 0}
              for _ in range(ncols)]
    for row in rows[:sample]:
        for i, cell in enumerate(row[:ncols]):
            plain = strip_html(cell)
            if not plain:
                continue
            if CJK_RE.search(plain):
                if len(plain) <= 4:
                    scores[i]["cjk_short"] += 1
                else:
                    scores[i]["cjk_long"] += 1
            if TONE_RE.search(plain):
                scores[i]["tone"] += 1
            if re.search(r"[a-zA-Z]", plain) and not TONE_RE.search(plain) and not CJK_RE.search(plain):
                scores[i]["latin"] += 1

    def best(key):
        idx = sorted(range(ncols), key=lambda i: -scores[i][key])
        return idx[0] if idx and scores[idx[0]][key] > 0 else -1

    cn = best("cjk_short")
    py = best("tone")
    en = best("latin")
    ex = best("cjk_long")
    if ex in {cn, py, en}:
        ex = -1
    return {"chinese": cn, "pinyin": py, "meaning": en, "example": ex}


class Card:
    __slots__ = ("idx", "chinese", "pinyin", "meaning", "example",
                 "audio", "example_audio", "image")

    def __init__(self, idx, cn, py, en, ex, au, eau, img):
        self.idx = idx
        self.chinese = cn
        self.pinyin = py
        self.meaning = en
        self.example = ex
        self.audio = au
        self.example_audio = eau
        self.image = img

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


def build_cards(rows, columns, edits):
    cards = []
    for i, row in enumerate(rows, 1):
        def cell(j):
            return row[j] if 0 <= j < len(row) else ""
        cn = strip_html(cell(columns["chinese"]))
        py = strip_html(cell(columns["pinyin"])) if columns["pinyin"] >= 0 else ""
        en = strip_html(cell(columns["meaning"])) if columns["meaning"] >= 0 else ""
        ex = strip_html(cell(columns["example"])) if columns["example"] >= 0 else ""
        audios = []
        img = None
        for c in row:
            audios += AUDIO_RE.findall(c)
            if not img:
                m = IMG_RE.search(c)
                if m:
                    img = m.group(1)
        c = Card(i, cn, py, en, ex,
                 audios[0] if audios else None,
                 audios[1] if len(audios) > 1 else None,
                 img)
        ed = edits.get(str(i))
        if ed:
            for k, v in ed.items():
                if k in Card.__slots__ and k != "idx":
                    setattr(c, k, v)
        cards.append(c)
    return cards


def load_edits(tsv):
    p = Path(tsv).with_suffix(".edits.json")
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


# ═══════════════════════════════════════════════════════════
# BACKGROUND / LAYOUT / SLIDE RENDER
# ═══════════════════════════════════════════════════════════
def make_background(settings):
    w, h = RESOLUTIONS[settings["quality"]]
    base = settings["bg_base"]
    if base == "solid":
        canvas = Image.new("RGB", (w, h), hex_rgb(settings["bg_solid"]))
    else:
        top = hex_rgb(settings["bg_top"])
        bot = hex_rgb(settings["bg_bot"])
        canvas = Image.new("RGB", (w, h), top)
        dr = ImageDraw.Draw(canvas)
        for y in range(h):
            t = y / max(h - 1, 1)
            c = tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3))
            dr.line([(0, y), (w, y)], fill=c)

    img_path = settings.get("bg_image") or ""
    if img_path and Path(img_path).exists():
        try:
            im = Image.open(img_path).convert("RGB")
            ratio = max(w / im.width, h / im.height)
            im = im.resize((int(im.width * ratio), int(im.height * ratio)),
                           Image.LANCZOS)
            left = (im.width - w) // 2
            top = (im.height - h) // 2
            im = im.crop((left, top, left + w, top + h))
            op = float(settings.get("bg_opacity", 1.0))
            canvas = Image.blend(canvas, im, op) if op < 1.0 else im
        except Exception:
            pass

    d = float(settings.get("bg_darken", 0))
    if d > 0:
        overlay = Image.new("RGB", (w, h), (0, 0, 0))
        canvas = Image.blend(canvas, overlay, d)
    return canvas


def wrap_text(draw, text, font, max_w):
    if not text:
        return []
    if " " not in text:
        lines, cur = [], ""
        for ch in text:
            if draw.textlength(cur + ch, font=font) <= max_w or not cur:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def compute_layout(card, settings, image_path, w, h):
    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    L = {}
    max_w = w - 100

    if card.chinese:
        size = settings["cn_size"]
        f = get_font(size, bold=True)
        while dummy.textlength(card.chinese, font=f) > max_w and size > 40:
            size -= 5
            f = get_font(size, bold=True)
        cx = settings["cn_x"] * w
        cy = settings["cn_y"] * h
        bbox = dummy.textbbox((cx, cy), card.chinese, font=f, anchor="mm")
        L["chinese"] = {"text": card.chinese, "font": f, "pos": (cx, cy),
                        "color": settings["cn_color"], "bbox": bbox}

    if card.pinyin:
        f = get_font(settings["py_size"])
        tw = dummy.textlength(card.pinyin, font=f)
        px, py_pad = 34, 16
        cx = settings["py_x"] * w
        cy = settings["py_y"] * h
        bbox = (cx - tw/2 - px, cy - f.size/2 - py_pad,
                cx + tw/2 + px, cy + f.size/2 + py_pad)
        L["pinyin"] = {"text": card.pinyin, "font": f, "pos": (cx, cy),
                       "tw": tw, "px": px, "py_pad": py_pad,
                       "color": settings["py_color"], "pill": settings["pill_color"],
                       "bbox": bbox}

    if card.meaning:
        f = get_font(settings["en_size"])
        lines = wrap_text(dummy, card.meaning, f, max_w)
        cx = settings["en_x"] * w
        cy = settings["en_y"] * h
        line_h = f.size + 10
        total_h = len(lines) * line_h
        max_line_w = max((dummy.textlength(l, font=f) for l in lines), default=0)
        bbox = (cx - max_line_w/2 - 8, cy - total_h/2,
                cx + max_line_w/2 + 8, cy + total_h/2)
        L["meaning"] = {"lines": lines, "font": f, "pos": (cx, cy),
                        "line_h": line_h, "color": settings["en_color"], "bbox": bbox}

    if card.example:
        f = get_font(settings["ex_size"])
        lines = wrap_text(dummy, card.example, f, max_w)
        cx = settings["ex_x"] * w
        cy = settings["ex_y"] * h
        line_h = f.size + 8
        total_h = len(lines) * line_h
        max_line_w = max((dummy.textlength(l, font=f) for l in lines), default=0)
        bbox = (cx - max_line_w/2 - 8, cy - total_h/2,
                cx + max_line_w/2 + 8, cy + total_h/2)
        L["example"] = {"lines": lines, "font": f, "pos": (cx, cy),
                        "line_h": line_h, "color": settings["ex_color"], "bbox": bbox}

    if image_path and Path(image_path).exists():
        try:
            im = Image.open(image_path).convert("RGB")
            max_size = settings["img_size"]
            im.thumbnail((max_size, max_size), Image.LANCZOS)
            cx = settings["img_x"] * w
            cy = settings["img_y"] * h
            bbox = (cx - im.width/2, cy - im.height/2,
                    cx + im.width/2, cy + im.height/2)
            L["image"] = {"img": im, "pos": (cx, cy), "bbox": bbox}
        except Exception:
            pass

    return L


def draw_layout(canvas_img, layout, phase):
    dr = ImageDraw.Draw(canvas_img)

    if "image" in layout and phase >= 2:
        im = layout["image"]["img"]
        x, y = layout["image"]["pos"]
        canvas_img.paste(im, (int(x - im.width/2), int(y - im.height/2)))

    if "chinese" in layout:
        f = layout["chinese"]["font"]
        pos = layout["chinese"]["pos"]
        dr.text(pos, layout["chinese"]["text"], font=f,
                fill=hex_rgb(layout["chinese"]["color"]), anchor="mm")

    if phase >= 2:
        if "pinyin" in layout:
            p = layout["pinyin"]
            tw, px, pyp = p["tw"], p["px"], p["py_pad"]
            cx, cy = p["pos"]
            dr.rounded_rectangle(
                [cx - tw/2 - px, cy - p["font"].size/2 - pyp,
                 cx + tw/2 + px, cy + p["font"].size/2 + pyp],
                radius=int((p["font"].size + 2*pyp)/2),
                fill=hex_rgb(p["pill"]))
            dr.text((cx, cy), p["text"], font=p["font"],
                    fill=hex_rgb(p["color"]), anchor="mm")

        if "meaning" in layout:
            m = layout["meaning"]
            cx, cy = m["pos"]
            total_h = len(m["lines"]) * m["line_h"]
            y = cy - total_h/2 + m["line_h"]/2
            for ln in m["lines"]:
                dr.text((cx, y), ln, font=m["font"],
                        fill=hex_rgb(m["color"]), anchor="mm")
                y += m["line_h"]

    if phase >= 3 and "example" in layout:
        e = layout["example"]
        cx, cy = e["pos"]
        total_h = len(e["lines"]) * e["line_h"]
        y = cy - total_h/2 + e["line_h"]/2
        for ln in e["lines"]:
            dr.text((cx, y), ln, font=e["font"],
                    fill=hex_rgb(e["color"]), anchor="mm")
            y += e["line_h"]

    return canvas_img


def render_slide(card, settings, bg, image_path, phase):
    img = bg.copy()
    w, h = RESOLUTIONS[settings["quality"]]
    layout = compute_layout(card, settings, image_path, w, h)
    draw_layout(img, layout, phase)
    return img, layout


# ═══════════════════════════════════════════════════════════
# FFMPEG
# ═══════════════════════════════════════════════════════════
def run_ffmpeg(args, tag=""):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + args,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({tag}):\n{r.stderr[-600:]}")


def make_silent_clip(png, duration, out):
    run_ffmpeg([
        "-loop", "1", "-i", str(png),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", f"{duration}",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", str(out),
    ], "silent")


def make_audio_clip(png, audio, out, tail, vol):
    af = f"volume={vol},apad=pad_dur={tail}"
    run_ffmpeg([
        "-loop", "1", "-i", str(png),
        "-i", str(audio),
        "-af", af,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", str(out),
    ], "audio")


def concat_clips(clips, out):
    lf = out.parent / (out.stem + "_list.txt")
    with open(lf, "w", encoding="utf-8") as f:
        for c in clips:
            f.write(f"file '{Path(c).resolve().as_posix()}'\n")
    run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", str(lf),
        "-map", "0:v:0", "-map", "0:a:0",
        "-map_chapters", "-1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out),
    ], "concat")
    lf.unlink(missing_ok=True)


def mix_music(video, music_dir, volume, shuffle, out):
    tracks = [p for p in Path(music_dir).iterdir()
              if p.is_file() and p.suffix.lower() in (".mp3", ".m4a", ".wav", ".flac", ".ogg")]
    if not tracks:
        Path(video).replace(out)
        return
    if shuffle:
        random.shuffle(tracks)
    lf = out.parent / "_music_list.txt"
    with open(lf, "w", encoding="utf-8") as f:
        for t in tracks:
            f.write(f"file '{t.resolve().as_posix()}'\n")
    loop = out.parent / "_music_loop.m4a"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lf),
                "-c:a", "aac", "-b:a", "192k", str(loop)], "music list")
    run_ffmpeg([
        "-i", str(video),
        "-stream_loop", "-1", "-i", str(loop),
        "-filter_complex",
        f"[1:a]volume={volume}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[aout]",
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out),
    ], "music mix")
    loop.unlink(missing_ok=True)
    lf.unlink(missing_ok=True)


def final_clean(path):
    tmp = path.parent / ("_c_" + path.name)
    run_ffmpeg([
        "-i", str(path),
        "-map", "0:v:0", "-map", "0:a:0",
        "-map_chapters", "-1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(tmp),
    ], "clean")
    tmp.replace(path)


def verify_output(path):
    r = subprocess.run(["ffprobe", "-v", "error",
                        "-show_entries", "stream=codec_type",
                        "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    types = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    if types != ["video", "audio"]:
        raise RuntimeError(f"Output has unexpected streams: {types}")


def render_card(card, settings, media, cache_dir):
    key = json.dumps({
        "c": card.as_dict(),
        "s": {k: settings[k] for k in settings
              if k.startswith(("cn_", "py_", "en_", "ex_", "img_"))
              or k in ("quality", "reveal", "tail", "pill_color",
                       "word_vol", "example_vol")},
    }, sort_keys=True, ensure_ascii=False)
    h = hashlib.md5(key.encode()).hexdigest()[:14]
    cached = cache_dir / f"{card.idx:05d}_{h}.mp4"
    if cached.exists():
        return cached

    bg = make_background(settings)
    media_p = Path(media)
    img_p = (media_p / card.image) if card.image else None
    if img_p and not img_p.exists():
        img_p = None

    tmp = cache_dir / f"tmp_{card.idx:05d}_{h}"
    tmp.mkdir(exist_ok=True)
    clips = []

    p1 = tmp / "p1.png"
    img1, _ = render_slide(card, settings, bg, img_p, 1)
    img1.save(p1)
    c1 = tmp / "c1.mp4"
    make_silent_clip(p1, settings["reveal"], c1)
    clips.append(c1)

    p2 = tmp / "p2.png"
    img2, _ = render_slide(card, settings, bg, img_p, 2)
    img2.save(p2)
    c2 = tmp / "c2.mp4"
    audio = (media_p / card.audio) if card.audio else None
    if audio and audio.exists():
        make_audio_clip(p2, audio, c2, settings["tail"], settings["word_vol"])
    else:
        make_silent_clip(p2, settings["tail"] + 1.0, c2)
    clips.append(c2)

    if card.example or card.example_audio:
        p3 = tmp / "p3.png"
        img3, _ = render_slide(card, settings, bg, img_p, 3)
        img3.save(p3)
        c3 = tmp / "c3.mp4"
        ex_audio = (media_p / card.example_audio) if card.example_audio else None
        if ex_audio and ex_audio.exists():
            make_audio_clip(p3, ex_audio, c3, settings["tail"], settings["example_vol"])
        else:
            make_silent_clip(p3, 2.5 + settings["tail"], c3)
        clips.append(c3)

    concat_clips(clips, cached)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    return cached


def render_worker(settings, range_override, q):
    try:
        tsv = settings["tsv"]
        media = settings["media"]
        if not tsv or not Path(tsv).exists():
            q.put(("done", "Deck export not found.")); return
        if not media or not Path(media).exists():
            q.put(("done", "Media folder not found.")); return

        q.put(("status", "Parsing deck..."))
        rows = parse_tsv(tsv)
        auto = detect_columns(rows)
        cols = {}
        for k in ("chinese", "pinyin", "meaning", "example"):
            v = settings["col_" + k]
            cols[k] = v if v >= 0 else auto[k]

        cards = build_cards(rows, cols, load_edits(tsv))
        if not cards:
            q.put(("done", "No cards parsed.")); return

        if range_override == "test":
            cards = cards[:10]
            single = True
            chunk = 10
            music_on = True
            prefix = settings["out_prefix"] + "_test"
        else:
            if settings["render_mode"] == "custom":
                lo = max(1, settings["from_card"])
                hi = settings["to_card"] or len(cards)
                hi = min(hi, len(cards))
                cards = cards[lo - 1:hi]
            single = False
            chunk = max(1, settings["chunk"])
            music_on = True
            prefix = settings["out_prefix"]

        out_dir = Path(settings["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        cache = out_dir / "_cache"
        cache.mkdir(exist_ok=True)

        total_files = 1 if single else (len(cards) + chunk - 1) // chunk

        for ch in range(total_files):
            chapter_cards = cards if single else cards[ch*chunk:(ch+1)*chunk]
            chapter_clips = []
            for i, card in enumerate(chapter_cards):
                pct = (ch * chunk + i) / len(cards)
                q.put(("progress", pct,
                       f"File {ch+1}/{total_files} — card {i+1}/{len(chapter_cards)}: {card.chinese}"))
                chapter_clips.append(render_card(card, settings, media, cache))

            if single:
                out_file = out_dir / f"{prefix}.mp4"
            else:
                out_file = out_dir / f"{prefix}_{ch+1:02d}.mp4"

            q.put(("status", f"Concatenating {out_file.name}..."))
            concat_clips(chapter_clips, out_file)

            if music_on and settings["music_dir"] and Path(settings["music_dir"]).exists():
                q.put(("status", "Mixing music..."))
                final = out_file.parent / ("_final_" + out_file.name)
                mix_music(out_file, settings["music_dir"],
                          settings["music_vol"], settings["music_shuffle"], final)
                out_file.unlink()
                final.rename(out_file)

            q.put(("status", f"Cleaning {out_file.name}..."))
            final_clean(out_file)
            verify_output(out_file)

        q.put(("done", f"Rendered {total_files} file(s) to:\n{out_dir}"))
    except Exception as e:
        q.put(("done", f"Error:\n{e}"))


# ═══════════════════════════════════════════════════════════
# WIDGETS
# ═══════════════════════════════════════════════════════════
class Stepper(tk.Frame):
    """Compact − value + control. Click value to edit."""
    def __init__(self, parent, value, step, minv, maxv,
                 on_change=None, fmt=None, width_chars=6):
        super().__init__(parent, bg=TH["panel"])
        self.step = step
        self.minv = minv
        self.maxv = maxv
        self.on_change = on_change
        self.fmt = fmt
        self.value = float(value)
        self.width_chars = width_chars
        self._editing = False

        self.btn_m = tk.Label(self, text="−", bg=TH["panel"], fg=TH["muted"],
                              font=("TkDefaultFont", 12, "bold"),
                              width=2, cursor="hand2", padx=2)
        self.btn_m.pack(side="left")
        self.btn_m.bind("<Button-1>", lambda _: self.dec())
        self.btn_m.bind("<Enter>", lambda _: self.btn_m.config(bg=TH["hover"], fg=TH["text"]))
        self.btn_m.bind("<Leave>", lambda _: self.btn_m.config(bg=TH["panel"], fg=TH["muted"]))

        self.lbl = tk.Label(self, text=self._s(), bg=TH["panel"], fg=TH["text"],
                            font=("TkDefaultFont", 10),
                            width=width_chars, cursor="xterm")
        self.lbl.pack(side="left", padx=2)
        self.lbl.bind("<Button-1>", self._start_edit)

        self.btn_p = tk.Label(self, text="+", bg=TH["panel"], fg=TH["muted"],
                              font=("TkDefaultFont", 12, "bold"),
                              width=2, cursor="hand2", padx=2)
        self.btn_p.pack(side="left")
        self.btn_p.bind("<Button-1>", lambda _: self.inc())
        self.btn_p.bind("<Enter>", lambda _: self.btn_p.config(bg=TH["hover"], fg=TH["text"]))
        self.btn_p.bind("<Leave>", lambda _: self.btn_p.config(bg=TH["panel"], fg=TH["muted"]))

    def _s(self):
        if self.fmt:
            return self.fmt(self.value)
        if self.step >= 1:
            return str(int(round(self.value)))
        s = f"{self.value:.2f}".rstrip("0").rstrip(".")
        return s if s else "0"

    def refresh(self):
        if not self._editing:
            self.lbl.config(text=self._s())

    def set_value(self, v, silent=False):
        v = max(self.minv, min(self.maxv, v))
        self.value = v
        self.refresh()
        if self.on_change and not silent:
            self.on_change(v)

    def inc(self):
        self.set_value(self.value + self.step)

    def dec(self):
        self.set_value(self.value - self.step)

    def _start_edit(self, _=None):
        if self._editing:
            return
        self._editing = True
        self.lbl.pack_forget()
        self.entry = tk.Entry(self, width=self.width_chars,
                              bg=TH["bg"], fg=TH["text"],
                              bd=0, highlightthickness=1,
                              highlightbackground=TH["accent"],
                              highlightcolor=TH["accent"],
                              insertbackground=TH["text"],
                              justify="center", font=("TkDefaultFont", 10))
        self.entry.insert(0, self._s())
        self.entry.pack(side="left", padx=2)
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()
        self.entry.bind("<Return>", self._commit)
        self.entry.bind("<Escape>", self._cancel)
        self.entry.bind("<FocusOut>", self._commit)

    def _commit(self, _=None):
        if not self._editing:
            return
        try:
            v = float(self.entry.get())
        except Exception:
            v = self.value
        self._editing = False
        self.entry.destroy()
        self.lbl.pack(side="left", padx=2, before=self.btn_p)
        self.set_value(v)

    def _cancel(self, _=None):
        if not self._editing:
            return
        self._editing = False
        self.entry.destroy()
        self.lbl.pack(side="left", padx=2, before=self.btn_p)
        self.refresh()


class ColorChip(tk.Canvas):
    def __init__(self, parent, key, app, size=20):
        super().__init__(parent, width=size, height=size,
                         bg=TH["panel"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.key = key
        self.app = app
        self.size = size
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        color = self.app.settings.get(self.key, "#000")
        s = self.size
        self.create_rectangle(1, 1, s-1, s-1, fill=color,
                              outline=TH["chip_border"], width=1)

    def _click(self, _=None):
        def on_pick(hex_color):
            self.app.settings[self.key] = hex_color
            self._draw()
            self.app.on_style_color_change(self.key)
        show_color_popup(self.app, on_pick, self)


class TimingBar(tk.Canvas):
    """Live preview of the reveal sequence with a ▶ button."""
    def __init__(self, parent, app, width=270, height=52):
        super().__init__(parent, width=width, height=height,
                         bg=TH["panel"], highlightthickness=0, bd=0)
        self.app = app
        self.W = width
        self.H = height
        self._anim_job = None
        self._playing = False
        self._dur_cache = {}
        self._dur_pending = set()
        self._btn_center = (0, 0)
        self._btn_radius = 12
        self.bind("<Button-1>", self._click)
        self.redraw()

    def _audio_duration(self):
        idx = self.app.card_idx
        if idx in self._dur_cache:
            return self._dur_cache[idx]
        if idx not in self._dur_pending:
            self._dur_pending.add(idx)
            threading.Thread(target=self._fetch_duration_async,
                             args=(idx,), daemon=True).start()
        return 1.2

    def _fetch_duration_async(self, idx):
        dur = 1.2
        try:
            if idx < len(self.app.cards):
                card = self.app.cards[idx]
                if card.audio:
                    media = Path(self.app.settings["media"])
                    ap = media / card.audio
                    if ap.exists():
                        r = subprocess.run(
                            ["ffprobe", "-v", "error",
                             "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1", str(ap)],
                            capture_output=True, text=True, timeout=5)
                        dur = max(0.3, float(r.stdout.strip() or 1.2))
        except Exception:
            pass
        self._dur_cache[idx] = dur
        self._dur_pending.discard(idx)
        # schedule redraw on main thread
        try:
            self.app.after(0, self.redraw)
        except Exception:
            pass

    def redraw(self):
        self.delete("all")
        reveal = float(self.app.settings["reveal"])
        tail = float(self.app.settings["tail"])
        audio = self._audio_duration()
        total = max(0.1, reveal + audio + tail)

        bar_w = self.W - 34
        bar_h = 14
        y = 6
        x0 = 0

        w_r = max(1, int(bar_w * reveal / total))
        w_a = max(1, int(bar_w * audio / total))
        w_t = max(1, bar_w - w_r - w_a)

        self.create_rectangle(x0, y, x0+w_r, y+bar_h, fill=TH["accent"], outline="")
        self.create_rectangle(x0+w_r, y, x0+w_r+w_a, y+bar_h, fill=TH["green"], outline="")
        self.create_rectangle(x0+w_r+w_a, y, x0+w_r+w_a+w_t, y+bar_h,
                              fill=TH["grey"], outline="")

        y2 = y + bar_h + 4
        self.create_text(x0+w_r/2, y2, text="Chinese", fill=TH["muted"],
                         font=("TkDefaultFont", 8), anchor="n")
        self.create_text(x0+w_r+w_a/2, y2, text="Audio", fill=TH["muted"],
                         font=("TkDefaultFont", 8), anchor="n")
        self.create_text(x0+w_r+w_a+w_t/2, y2, text="Pause", fill=TH["muted"],
                         font=("TkDefaultFont", 8), anchor="n")

        y3 = y2 + 12
        self.create_text(x0+w_r/2, y3, text=f"{reveal:.1f}s", fill=TH["text_2"],
                         font=("TkDefaultFont", 8), anchor="n")
        self.create_text(x0+w_r+w_a/2, y3, text=f"{audio:.1f}s", fill=TH["text_2"],
                         font=("TkDefaultFont", 8), anchor="n")
        self.create_text(x0+w_r+w_a+w_t/2, y3, text=f"{tail:.1f}s", fill=TH["text_2"],
                         font=("TkDefaultFont", 8), anchor="n")

        btn_x = self.W - 22
        btn_y = 12
        self.create_oval(btn_x-11, btn_y-11, btn_x+11, btn_y+11,
                         fill=TH["hover"], outline="")
        sym = "❚❚" if self._playing else "▶"
        self.create_text(btn_x, btn_y, text=sym, fill=TH["text"],
                         font=("TkDefaultFont", 10))
        self._btn_center = (btn_x, btn_y)

    def _click(self, e):
        bx, by = self._btn_center
        if (e.x - bx)**2 + (e.y - by)**2 <= self._btn_radius**2:
            if self._playing:
                self._stop()
            else:
                self._play()

    def _play(self):
        self._playing = True
        self.app.play_current_audio()
        self.redraw()
        reveal = float(self.app.settings["reveal"])
        tail = float(self.app.settings["tail"])
        audio = self._audio_duration()
        total_ms = int((reveal + audio + tail) * 1000)
        self._anim_job = self.after(total_ms, self._stop)

    def _stop(self):
        self._playing = False
        if self._anim_job:
            try:
                self.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None
        self.app.stop_audio()
        self.redraw()

    def invalidate_duration_cache(self):
        self._dur_cache.clear()
        self._dur_pending.clear()


class CustomScrollbar(tk.Canvas):
    """Canvas-drawn scrollbar so we control the look on every desktop."""
    def __init__(self, parent, width=10):
        super().__init__(parent, width=width, bg=TH["panel"],
                         highlightthickness=0, bd=0, cursor="hand2")
        self.W = width
        self._first = 0.0
        self._last = 1.0
        self._drag_offset = None
        self._thumb_rect = (0, 0)
        self._command = None
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_command(self, cmd):
        self._command = cmd

    def set(self, first, last):
        try:
            self._first = float(first)
            self._last = float(last)
        except Exception:
            return
        self._redraw()

    def _redraw(self):
        self.delete("all")
        h = self.winfo_height()
        w = self.winfo_width()
        if h < 10 or w < 2:
            return
        # trough
        self.create_rectangle(0, 0, w, h, fill=TH["panel"], outline="")
        # thumb
        y0 = int(h * self._first)
        y1 = int(h * self._last)
        if y1 - y0 < 24:
            y1 = y0 + 24
            if y1 > h:
                y1 = h
                y0 = max(0, y1 - 24)
        if y1 <= y0:
            return
        self.create_rectangle(2, y0 + 1, w - 2, y1 - 1,
                              fill=TH["muted"], outline="")
        self._thumb_rect = (y0, y1)

    def _on_press(self, e):
        if not self._command:
            return
        h = self.winfo_height()
        y0, y1 = self._thumb_rect
        if y0 <= e.y <= y1:
            self._drag_offset = e.y - y0
        else:
            thumb_h = y1 - y0
            new_y0 = max(0, min(h - thumb_h, e.y - thumb_h // 2))
            self._command("moveto", str(new_y0 / h))

    def _on_drag(self, e):
        if self._drag_offset is None or not self._command:
            return
        h = self.winfo_height()
        y0, y1 = self._thumb_rect
        thumb_h = y1 - y0
        new_y0 = max(0, min(h - thumb_h, e.y - self._drag_offset))
        self._command("moveto", str(new_y0 / h))

    def _on_release(self, e):
        self._drag_offset = None


# ═══════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = self.load_settings()
        self.ui_font = None
        self.title("VocabVid")
        self.configure(bg=TH["bg"])
        self.geometry(self.settings.get("window_geom", "1440x900"))
        self.minsize(1000, 650)

        # state
        self.cards = []
        self.card_idx = 0
        self.drag_mode = False
        self.selected_field = None
        self.resize_corner = None
        self.resize_start = None
        self.resize_start_size = None
        self.drag_start = None
        self.drag_start_pos = None
        self.last_layout = {}
        self.scale_factor = 1.0
        self.preview_offset = (0, 0)
        self.bg_cache = None
        self.bg_cache_key = None
        self.preview_source_img = None
        self.preview_render_key = None
        self.preview_photo = None
        self.q = queue.Queue()
        self.busy = False
        self._ffplay_procs = []
        self._search_filter = ""
        self._search_after_id = None
        self._visible_cache = None
        self._card_list_built = False
        self._resize_after_id = None
        self.SEARCH_PLACEHOLDER = "Search or jump…"

        self.build_ui()
        self.after(120, self.poll_queue)
        self.after(400, self.try_autoload)
        self.after(800, self._force_preview_render)
        self.bind("<Map>", lambda e: self.after(100, self._force_preview_render))

    # ─── settings ──────────────────────────────────
    def load_settings(self):
        if SETTINGS_FILE.exists():
            try:
                d = json.loads(SETTINGS_FILE.read_text())
                out = {**DEFAULTS, **d}
                if "sections_open" in d:
                    out["sections_open"] = {**DEFAULTS["sections_open"],
                                            **d["sections_open"]}
                return out
            except Exception:
                pass
        return json.loads(json.dumps(DEFAULTS))

    def save_settings(self):
        try:
            self.settings["window_geom"] = self.geometry()
        except Exception:
            pass
        try:
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2))
        except Exception:
            pass

    # ─── build ─────────────────────────────────────
    def build_ui(self):
        self.ui_font = pick_ui_font(self)

        self.build_toolbar()
        self.build_body()
        self.build_status_bar()

        self.bind("<Left>", self._on_left_key)
        self.bind("<Right>", self._on_right_key)
        self.bind("<Escape>", lambda _: self.deselect_field())

    def build_toolbar(self):
        bar = tk.Frame(self, bg=TH["panel"], height=48)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        self.toolbar = bar

        tk.Label(bar, text="VocabVid", bg=TH["panel"], fg=TH["text"],
                 font=(self.ui_font, 13, "bold")).pack(side="left", padx=(16, 24))

        center = tk.Frame(bar, bg=TH["panel"])
        center.pack(side="left")

        self.layout_btn = self._make_secondary_btn(center, "🔓  Layout",
                                                    self.toggle_drag_mode)
        self.layout_btn.pack(side="left", padx=(0, 8))

        self.test_btn = self._make_secondary_btn(center, "Test 10",
                                                  lambda: self.start_render("test"))
        self.test_btn.pack(side="left", padx=(0, 8))

        self.render_btn = self._make_primary_btn(center, "▶  Render",
                                                  lambda: self.start_render("full"))
        self.render_btn.pack(side="left")

        right = tk.Frame(bar, bg=TH["panel"])
        right.pack(side="right", padx=(0, 14))

        self._make_util_btn(right, "?", self.show_help).pack(side="left")

        self.progress = tk.Frame(self, bg=TH["accent"], height=2)

    def _make_primary_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd,
                         bg=TH["accent"], fg=TH["accent_fg"], bd=0,
                         activebackground=TH["accent_2"],
                         activeforeground=TH["accent_fg"],
                         font=(self.ui_font, 10, "bold"),
                         padx=18, pady=6, highlightthickness=0,
                         cursor="hand2", relief="flat")

    def _make_secondary_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd,
                         bg=TH["panel"], fg=TH["text"], bd=0,
                         activebackground=TH["hover"], activeforeground=TH["text"],
                         font=(self.ui_font, 10), padx=14, pady=6,
                         highlightthickness=1,
                         highlightbackground=TH["chip_border"],
                         highlightcolor=TH["accent"],
                         cursor="hand2", relief="flat")

    def _make_util_btn(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=TH["panel"], fg=TH["muted"],
                     font=(self.ui_font, 11), padx=10, pady=6, cursor="hand2")
        b.bind("<Button-1>", lambda _: cmd())
        b.bind("<Enter>", lambda _: b.config(bg=TH["hover"], fg=TH["text"]))
        b.bind("<Leave>", lambda _: b.config(bg=TH["panel"], fg=TH["muted"]))
        return b

    def build_body(self):
        body = tk.Frame(self, bg=TH["bg"])
        body.pack(fill="both", expand=True)
        self.body = body

        self.left_panel = tk.Frame(body, bg=TH["panel"], width=170)
        self.left_panel.pack(side="left", fill="y")
        self.left_panel.pack_propagate(False)
        self.build_card_list()

        self.right_panel = tk.Frame(body, bg=TH["panel"], width=320)
        self.right_panel.pack(side="right", fill="y")
        self.right_panel.pack_propagate(False)
        self.build_settings()

        self.center_panel = tk.Frame(body, bg=TH["bg"])
        self.center_panel.pack(side="left", fill="both", expand=True)
        self.build_preview()

    def build_card_list(self):
        header = tk.Frame(self.left_panel, bg=TH["panel"], height=28)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.cards_header = tk.Label(header, text="0 cards", bg=TH["panel"],
                                      fg=TH["muted"], font=(self.ui_font, 9, "bold"))
        self.cards_header.pack(side="left", padx=12)

        swrap = tk.Frame(self.left_panel, bg=TH["panel"])
        swrap.pack(fill="x", padx=10, pady=(0, 6))
        self.search_var = tk.StringVar()
        se = tk.Entry(swrap, textvariable=self.search_var,
                      font=(self.ui_font, 10),
                      bg=TH["bg"], fg=TH["muted"], bd=0,
                      highlightthickness=1,
                      highlightbackground=TH["chip_border"],
                      highlightcolor=TH["accent"],
                      insertbackground=TH["text"])
        se.pack(fill="x", ipady=4)
        se.insert(0, self.SEARCH_PLACEHOLDER)
        self.search_entry = se

        def s_in(_):
            if se.get() == self.SEARCH_PLACEHOLDER:
                se.delete(0, tk.END)
                se.config(fg=TH["text"])
        def s_out(_):
            if se.get() == "":
                se.insert(0, self.SEARCH_PLACEHOLDER)
                se.config(fg=TH["muted"])
                self._schedule_search("")
        se.bind("<FocusIn>", s_in)
        se.bind("<FocusOut>", s_out)
        se.bind("<KeyRelease>", lambda e: self._schedule_search(se.get()))
        se.bind("<Return>", lambda e: self._do_search_enter(se.get()))
        se.bind("<Escape>", lambda e: (se.delete(0, tk.END),
                                        self._schedule_search("")))

        listwrap = tk.Frame(self.left_panel, bg=TH["panel"])
        listwrap.pack(fill="both", expand=True)

        self.card_text = tk.Text(listwrap, bd=0, highlightthickness=0,
                                  bg=TH["panel"], fg=TH["text_2"],
                                  selectbackground=TH["panel"],
                                  font=(self.ui_font, 9),
                                  wrap="none", cursor="hand2",
                                  spacing1=0, spacing3=0, padx=4, pady=0,
                                  insertwidth=0)
        self.card_text.pack(side="left", fill="both", expand=True)
        self.card_text.configure(state="disabled")

        sb = CustomScrollbar(listwrap, width=10)
        sb.pack(side="right", fill="y")
        sb.set_command(self.card_text.yview)
        self.card_text.config(yscrollcommand=sb.set)
        self.card_scrollbar = sb

        self.card_text.tag_config("faint", foreground=TH["faint"])
        self.card_text.tag_config("muted2", foreground=TH["muted"])
        self.card_text.tag_config("cn",
                                  foreground=self.settings["cn_color"],
                                  font=(self.ui_font, 10, "bold"))
        self.card_text.tag_config("current", background=TH["selected"])

        self.card_text.bind("<Button-1>", self._list_click)
        self.card_text.bind("<MouseWheel>",
                            lambda e: self.card_text.yview_scroll(
                                int(-1 * (e.delta / 120)), "units"))
        self.card_text.bind("<Button-4>",
                            lambda e: self.card_text.yview_scroll(-1, "units"))
        self.card_text.bind("<Button-5>",
                            lambda e: self.card_text.yview_scroll(1, "units"))

    def _list_click(self, e):
        idx = self.card_text.index(f"@{e.x},{e.y}")
        line = int(idx.split(".")[0]) - 1
        vis = self._visible_card_indices()
        if 0 <= line < len(vis):
            self.card_idx = vis[line]
            self.preview_render_key = None
            self.refresh_preview()
            self.refresh_card_list(rebuild=False)

    def _visible_card_indices(self):
        if self._visible_cache is not None:
            return self._visible_cache
        if not self._search_filter:
            self._visible_cache = list(range(len(self.cards)))
            return self._visible_cache
        q = self._search_filter.lower()
        out = []
        for i, c in enumerate(self.cards):
            if (q in (c.chinese or "").lower()
                    or q in (c.pinyin or "").lower()
                    or q in (c.meaning or "").lower()
                    or q == str(c.idx)):
                out.append(i)
        self._visible_cache = out
        return out

    def _schedule_search(self, q):
        if self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.after(250, lambda: self._do_search(q))

    def _do_search(self, q):
        self._search_after_id = None
        if q == self.SEARCH_PLACEHOLDER:
            q = ""
        new_filter = q.strip()
        if new_filter == self._search_filter:
            return
        self._search_filter = new_filter
        self._visible_cache = None
        self.refresh_card_list(rebuild=True)

    def _do_search_enter(self, q):
        q = q.strip()
        if not q or q == self.SEARCH_PLACEHOLDER:
            return
        jumped = False
        try:
            n = int(q)
            if 1 <= n <= len(self.cards):
                self.card_idx = n - 1
                jumped = True
        except Exception:
            pass
        if not jumped:
            vis = self._visible_card_indices()
            if vis:
                self.card_idx = vis[0]
                jumped = True
        if jumped:
            # clear the filter and restore full list
            self._search_filter = ""
            self._visible_cache = None
            try:
                se = self.search_entry
                se.delete(0, "end")
                se.insert(0, self.SEARCH_PLACEHOLDER)
                se.config(fg=TH["muted"])
                self.focus_set()
            except Exception:
                pass
            self.preview_render_key = None
            self.refresh_preview()
            self.refresh_card_list(rebuild=True)

    def refresh_card_list(self, rebuild=True):
        if not rebuild and self._card_list_built:
            try:
                self.card_text.configure(state="normal")
                self.card_text.tag_remove("current", "1.0", tk.END)
                vis = self._visible_card_indices()
                if self.card_idx in vis:
                    line = vis.index(self.card_idx) + 1
                    self.card_text.tag_add("current", f"{line}.0", f"{line}.end")
                    self.card_text.see(f"{line}.0")
                self.card_text.configure(state="disabled")
            except Exception:
                pass
            return

        self._card_list_built = True
        self._visible_cache = None
        vis = self._visible_card_indices()

        lines = []
        faint_ranges = []
        cn_ranges = []
        muted2_ranges = []
        current_line = None

        for row_idx, i in enumerate(vis, start=1):
            c = self.cards[i]
            prefix = f"{c.idx:>4} "
            cn = c.chinese or ""
            mn = c.meaning or ""
            line_text = prefix + cn
            if mn:
                line_text += "  " + mn
            lines.append(line_text)

            faint_ranges.append(f"{row_idx}.0")
            faint_ranges.append(f"{row_idx}.{len(prefix)}")

            if cn:
                cn_start = len(prefix)
                cn_end = cn_start + len(cn)
                cn_ranges.append(f"{row_idx}.{cn_start}")
                cn_ranges.append(f"{row_idx}.{cn_end}")

            if mn:
                mean_start = len(prefix) + len(cn) + 2
                muted2_ranges.append(f"{row_idx}.{mean_start}")
                muted2_ranges.append(f"{row_idx}.end")

            if i == self.card_idx:
                current_line = row_idx

        content = "\n".join(lines)

        self.card_text.configure(state="normal")
        self.card_text.delete("1.0", tk.END)
        if content:
            self.card_text.insert("1.0", content)

        if faint_ranges:
            self.card_text.tag_add("faint", *faint_ranges)
        if cn_ranges:
            self.card_text.tag_add("cn", *cn_ranges)
        if muted2_ranges:
            self.card_text.tag_add("muted2", *muted2_ranges)
        if current_line:
            self.card_text.tag_add("current",
                                    f"{current_line}.0", f"{current_line}.end")

        self.card_text.configure(state="disabled")
        self.cards_header.config(text=f"{len(self.cards)} cards")

        if current_line:
            try:
                self.card_text.see(f"{current_line}.0")
            except Exception:
                pass

    def build_preview(self):
        self.preview_canvas = tk.Canvas(self.center_panel, bg=TH["bg"],
                                        highlightthickness=0, bd=0)
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", self._on_canvas_configure)
        self.preview_canvas.bind("<Button-1>", self.on_canvas_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.preview_canvas.bind("<Motion>", self.on_canvas_motion)

    def _force_preview_render(self):
        try:
            self.preview_render_key = None
            self.refresh_preview()
        except Exception:
            pass

    def _on_canvas_configure(self, event):
        if self._resize_after_id:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
        self._resize_after_id = self.after(40, self._render_preview_to_canvas)

    def build_settings(self):
        wrap = tk.Frame(self.right_panel, bg=TH["panel"])
        wrap.pack(fill="both", expand=True)

        self.settings_canvas = tk.Canvas(wrap, bg=TH["panel"],
                                          highlightthickness=0, bd=0)
        self.settings_canvas.pack(side="left", fill="both", expand=True)
        sb = CustomScrollbar(wrap, width=10)
        sb.pack(side="right", fill="y")
        sb.set_command(self.settings_canvas.yview)
        self.settings_canvas.config(yscrollcommand=sb.set)
        self.settings_scrollbar = sb

        self.settings_inner = tk.Frame(self.settings_canvas, bg=TH["panel"])
        self.settings_canvas.create_window((0, 0), window=self.settings_inner,
                                            anchor="nw", tags="inner")
        self.settings_inner.bind(
            "<Configure>",
            lambda e: self.settings_canvas.configure(
                scrollregion=self.settings_canvas.bbox("all")))
        self.settings_canvas.bind(
            "<Configure>",
            lambda e: self.settings_canvas.itemconfig("inner", width=e.width))

        self.section_frames = {}
        self.section_bodies = {}
        self.section_headers = {}
        self.section_subtitles = {}

        self._build_section("text_styles", "TEXT STYLES",
                             self.build_text_styles_section)
        self._build_section("background", "BACKGROUND",
                             self.build_background_section)
        self._build_section("sound", "SOUND", self.build_sound_section)
        self._build_section("render", "RENDER", self.build_render_section)
        self._build_section("columns", "COLUMNS", self.build_columns_section)
        self._build_section("files", "FILES", self.build_files_section)

        for key in self.section_frames:
            self._apply_section_state(key)

        # Bind mousewheel recursively to every child so scroll works anywhere
        self.after(100, self._bind_mousewheel_all)

    def _bind_mousewheel_all(self, widget=None):
        if widget is None:
            widget = self.settings_canvas
        try:
            widget.bind("<MouseWheel>", self._on_settings_wheel)
            widget.bind("<Button-4>", self._on_settings_wheel_linux)
            widget.bind("<Button-5>", self._on_settings_wheel_linux)
        except Exception:
            pass
        for c in widget.winfo_children():
            self._bind_mousewheel_all(c)

    def _on_settings_wheel(self, event):
        try:
            self.settings_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_settings_wheel_linux(self, event):
        try:
            if event.num == 4:
                self.settings_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.settings_canvas.yview_scroll(1, "units")
        except Exception:
            pass

    def _rebind_mousewheel_after_toggle(self):
        self.after(50, self._bind_mousewheel_all)

    def _build_section(self, key, title, content_fn):
        outer = tk.Frame(self.settings_inner, bg=TH["panel"])
        outer.pack(fill="x")

        header = tk.Frame(outer, bg=TH["panel"], height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        arrow = tk.Label(header, text="▸", bg=TH["panel"], fg=TH["muted"],
                         font=(self.ui_font, 9))
        arrow.pack(side="left", padx=(12, 6))

        title_lbl = tk.Label(header, text=title, bg=TH["panel"],
                             fg=TH["text_2"], font=(self.ui_font, 9, "bold"))
        title_lbl.pack(side="left")

        subtitle = tk.Label(header, text="", bg=TH["panel"],
                            fg=TH["text_2"], font=(self.ui_font, 9))
        subtitle.pack(side="right", padx=(0, 12))

        for w in (header, arrow, title_lbl, subtitle):
            w.bind("<Button-1>", lambda e, k=key: self.toggle_section(k))
            w.configure(cursor="hand2")

        body = tk.Frame(outer, bg=TH["panel"])

        divider = tk.Frame(self.settings_inner, bg=TH["divider"], height=1)

        self.section_frames[key] = outer
        self.section_bodies[key] = body
        self.section_headers[key] = (header, arrow, title_lbl)
        self.section_subtitles[key] = subtitle

        content_fn(body)

        divider.pack(fill="x")

    def _apply_section_state(self, key):
        open_ = self.settings["sections_open"].get(key, False)
        body = self.section_bodies[key]
        arrow = self.section_headers[key][1]
        if open_:
            body.pack(fill="x", pady=(0, 6))
            arrow.config(text="▾")
        else:
            body.pack_forget()
            arrow.config(text="▸")
        self._update_subtitle(key)

    def toggle_section(self, key):
        self.settings["sections_open"][key] = not \
            self.settings["sections_open"].get(key, False)
        self._apply_section_state(key)
        self._rebind_mousewheel_after_toggle()
        self.save_settings()

    def _update_subtitle(self, key):
        sub = self.section_subtitles.get(key)
        if not sub:
            return
        s = self.settings
        if key == "text_styles":
            sub.config(text=f"{s['cn_size']}px · {s['reveal']:.1f}s")
        elif key == "background":
            if s["bg_image"]:
                sub.config(text="image layer")
            else:
                sub.config(text=s["bg_base"])
        elif key == "sound":
            sub.config(text=f"word {int(s['word_vol']*100)}% · music {int(s['music_vol']*100)}%")
        elif key == "render":
            n = len(self.cards) if self.cards else 0
            chunk = max(1, s["chunk"])
            files = (n + chunk - 1) // chunk if n else 1
            sub.config(text=f"{n} cards · {files} files")
        elif key == "columns":
            used = getattr(self, "_used_cols", {})
            parts = []
            for k in ("chinese", "pinyin", "meaning", "example"):
                v = used.get(k, -1)
                parts.append(str(v) if v >= 0 else "—")
            sub.config(text=" ".join(parts))
        elif key == "files":
            ok = all([s["tsv"] and Path(s["tsv"]).exists(),
                      s["media"] and Path(s["media"]).exists(),
                      s["out_dir"]])
            sub.config(text="✓ ready" if ok else "setup needed")

    def update_all_subtitles(self):
        for key in self.section_frames:
            self._update_subtitle(key)

    # ─── TEXT STYLES section ─────────────────────
    def build_text_styles_section(self, parent):
        self.steppers = {}
        self.color_chips = {}

        fields = [
            ("cn", "Chinese", True, 600, 20),
            ("py", "Pinyin", True, 200, 2),
            ("en", "Meaning", True, 200, 2),
            ("ex", "Example", True, 200, 2),
            ("img", "Image", False, 800, 20),
        ]

        for key, label, has_color, size_max, size_step in fields:
            row = tk.Frame(parent, bg=TH["panel"], height=30)
            row.pack(fill="x", padx=12, pady=1)
            row.pack_propagate(False)

            if has_color:
                chip = ColorChip(row, key + "_color", self, size=18)
                chip.pack(side="left", padx=(0, 8))
                self.color_chips[key + "_color"] = chip
            else:
                tk.Frame(row, bg=TH["panel"], width=26).pack(side="left")

            tk.Label(row, text=label, bg=TH["panel"], fg=TH["text_2"],
                     font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")

            s = Stepper(row, self.settings[key + "_size"], size_step, 10, size_max,
                        on_change=lambda v, k=key: self._on_size(k, v),
                        fmt=lambda v: f"{int(v)} px", width_chars=7)
            s.pack(side="right")
            self.steppers[key + "_size"] = s

        tk.Frame(parent, bg=TH["divider"], height=1).pack(fill="x", padx=12, pady=(8, 6))

        row = tk.Frame(parent, bg=TH["panel"], height=28)
        row.pack(fill="x", padx=12, pady=1)
        row.pack_propagate(False)
        tk.Label(row, text="Show answer after", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), anchor="w").pack(side="left")
        self.steppers["reveal"] = Stepper(
            row, self.settings["reveal"], 0.1, 0.5, 15,
            on_change=lambda v: self._on_timing("reveal", v),
            fmt=lambda v: f"{v:.1f} s", width_chars=6)
        self.steppers["reveal"].pack(side="right")

        row = tk.Frame(parent, bg=TH["panel"], height=28)
        row.pack(fill="x", padx=12, pady=1)
        row.pack_propagate(False)
        tk.Label(row, text="Pause after audio", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), anchor="w").pack(side="left")
        self.steppers["tail"] = Stepper(
            row, self.settings["tail"], 0.1, 0.0, 5,
            on_change=lambda v: self._on_timing("tail", v),
            fmt=lambda v: f"{v:.1f} s", width_chars=6)
        self.steppers["tail"].pack(side="right")

        tbwrap = tk.Frame(parent, bg=TH["panel"])
        tbwrap.pack(fill="x", padx=12, pady=(10, 8))
        self.timing_bar = TimingBar(tbwrap, self, width=280, height=52)
        self.timing_bar.pack(fill="x")

    def _on_size(self, key, v):
        self.settings[key + "_size"] = int(v)
        self.preview_render_key = None
        self.refresh_preview()
        self._update_subtitle("text_styles")

    def _on_timing(self, key, v):
        self.settings[key] = v
        if hasattr(self, "timing_bar"):
            self.timing_bar.redraw()
        self._update_subtitle("text_styles")

    def on_style_color_change(self, key):
        self.preview_render_key = None
        self.refresh_preview()
        if key == "cn_color":
            try:
                self.card_text.tag_config("cn",
                                          foreground=self.settings["cn_color"],
                                          font=(self.ui_font, 10, "bold"))
            except Exception:
                pass
        self._update_subtitle("text_styles")

    # ─── BACKGROUND section ──────────────────────
    def build_background_section(self, parent):
        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=(4, 6))
        tk.Label(row, text="Base", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
        self.v_bg_base = tk.StringVar(value=self.settings["bg_base"])
        for val, label in (("gradient", "Gradient"), ("solid", "Solid")):
            tk.Radiobutton(row, text=label, variable=self.v_bg_base, value=val,
                           command=self._bg_change, bg=TH["panel"], fg=TH["text_2"],
                           activebackground=TH["panel"], activeforeground=TH["text"],
                           selectcolor=TH["panel"], font=(self.ui_font, 9),
                           bd=0, highlightthickness=0).pack(side="left", padx=4)

        pal = tk.Frame(parent, bg=TH["panel"])
        pal.pack(fill="x", padx=12, pady=2)
        for i, (name, (top, bot)) in enumerate(GRADIENT_PALETTES.items()):
            r, c = divmod(i, 4)
            chip = tk.Frame(pal, bg=top, width=58, height=22,
                            highlightthickness=1,
                            highlightbackground=TH["chip_border"],
                            cursor="hand2")
            chip.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
            chip.grid_propagate(False)
            chip.bind("<Button-1>",
                      lambda e, tp=top, bt=bot: self._apply_palette(tp, bt))
        for c in range(4):
            pal.grid_columnconfigure(c, weight=1)

        crow = tk.Frame(parent, bg=TH["panel"])
        crow.pack(fill="x", padx=12, pady=(6, 2))

        def chip_pair(label, key):
            f = tk.Frame(crow, bg=TH["panel"])
            f.pack(side="left", padx=(0, 10))
            tk.Label(f, text=label, bg=TH["panel"], fg=TH["muted"],
                     font=(self.ui_font, 8)).pack(side="left", padx=(0, 4))
            c = ColorChip(f, key, self, size=18)
            c.pack(side="left")
            self.color_chips[key] = c

        chip_pair("top", "bg_top")
        chip_pair("bot", "bg_bot")
        chip_pair("solid", "bg_solid")

        irow = tk.Frame(parent, bg=TH["panel"])
        irow.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(irow, text="Image", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
        self.bg_image_label = tk.Label(irow,
                                       text=self._short_path(self.settings["bg_image"]) or "(none)",
                                       bg=TH["panel"], fg=TH["muted"],
                                       font=(self.ui_font, 9), anchor="w")
        self.bg_image_label.pack(side="left", fill="x", expand=True)

        def pick_img():
            p = filedialog.askopenfilename(
                filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")])
            if not p:
                return
            self.settings["bg_image"] = p
            self.bg_image_label.config(text=self._short_path(p))
            try:
                im = Image.open(p)
                w, h = RESOLUTIONS[self.settings["quality"]]
                if im.width < w or im.height < h:
                    messagebox.showwarning("Low-res image",
                        f"Image is {im.width}×{im.height} but video is {w}×{h}.\n"
                        "It may look soft.")
            except Exception:
                pass
            self.invalidate_bg()
            self.preview_render_key = None
            self.refresh_preview()
            self._update_subtitle("background")

        def clear_img():
            self.settings["bg_image"] = ""
            self.bg_image_label.config(text="(none)")
            self.invalidate_bg()
            self.preview_render_key = None
            self.refresh_preview()
            self._update_subtitle("background")

        btn_clear = tk.Label(irow, text=" ✕ ", bg=TH["panel"], fg=TH["muted"],
                             font=(self.ui_font, 10), cursor="hand2")
        btn_clear.pack(side="right")
        btn_clear.bind("<Button-1>", lambda _: clear_img())

        btn_pick = tk.Label(irow, text=" 📁 ", bg=TH["panel"], fg=TH["muted"],
                            font=(self.ui_font, 10), cursor="hand2")
        btn_pick.pack(side="right")
        btn_pick.bind("<Button-1>", lambda _: pick_img())

        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=(4, 2))
        tk.Label(row, text="Opacity", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
        self.steppers["bg_opacity"] = Stepper(
            row, self.settings["bg_opacity"], 0.05, 0.0, 1.0,
            on_change=lambda v: self._on_bg_param("bg_opacity", v),
            fmt=lambda v: f"{v:.2f}", width_chars=5)
        self.steppers["bg_opacity"].pack(side="right")

        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=(2, 6))
        tk.Label(row, text="Darkening", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
        self.steppers["bg_darken"] = Stepper(
            row, self.settings["bg_darken"], 0.05, 0.0, 1.0,
            on_change=lambda v: self._on_bg_param("bg_darken", v),
            fmt=lambda v: f"{v:.2f}", width_chars=5)
        self.steppers["bg_darken"].pack(side="right")

    def _apply_palette(self, top, bot):
        self.settings["bg_top"] = top
        self.settings["bg_bot"] = bot
        self.settings["bg_base"] = "gradient"
        self.v_bg_base.set("gradient")
        self.invalidate_bg()
        self.preview_render_key = None
        self.refresh_preview()
        self._update_subtitle("background")
        for k in ("bg_top", "bg_bot", "bg_solid"):
            if k in self.color_chips:
                self.color_chips[k]._draw()

    def _bg_change(self):
        self.settings["bg_base"] = self.v_bg_base.get()
        self.invalidate_bg()
        self.preview_render_key = None
        self.refresh_preview()
        self._update_subtitle("background")

    def _on_bg_param(self, key, v):
        self.settings[key] = v
        self.invalidate_bg()
        self.preview_render_key = None
        self.refresh_preview()

    def _short_path(self, p):
        if not p:
            return ""
        s = str(p)
        return s if len(s) <= 22 else "…" + s[-20:]

    # ─── SOUND section ───────────────────────────
    def build_sound_section(self, parent):
        self.play_btns = {}

        def row_for(key, label):
            row = tk.Frame(parent, bg=TH["panel"], height=28)
            row.pack(fill="x", padx=12, pady=1)
            row.pack_propagate(False)
            tk.Label(row, text=label, bg=TH["panel"], fg=TH["text_2"],
                     font=(self.ui_font, 10), width=8, anchor="w").pack(side="left")
            pct = tk.Label(row, text=f"{int(self.settings[key]*100)}%",
                           bg=TH["panel"], fg=TH["text"],
                           font=(self.ui_font, 11, "bold"),
                           width=5, anchor="e")
            pct.pack(side="right", padx=(6, 0))
            setattr(self, f"pct_{key}", pct)
            btn = tk.Label(row, text="🔊", bg=TH["panel"], fg=TH["muted"],
                           font=(self.ui_font, 11), padx=6, cursor="hand2")
            btn.pack(side="right")
            btn.bind("<Button-1>", lambda e, k=key: self.toggle_play(k))
            self.play_btns[key] = btn
            var = tk.DoubleVar(value=self.settings[key])
            sc = tk.Scale(row, from_=0.0, to=1.0, resolution=0.05,
                          orient="horizontal", variable=var,
                          showvalue=False, length=90, sliderlength=14,
                          width=10,
                          bg=TH["panel"], fg=TH["muted"],
                          troughcolor=TH["bg"],
                          activebackground=TH["accent"],
                          highlightthickness=0, bd=0,
                          command=lambda v, k=key: self._on_vol(k, float(v)))
            sc.pack(side="right", padx=(6, 0))

        row_for("word_vol", "Word")
        row_for("example_vol", "Example")

        mrow = tk.Frame(parent, bg=TH["panel"])
        mrow.pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(mrow, text="Music", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
        self.music_label = tk.Label(
            mrow,
            text=self._short_path(self.settings["music_dir"]) or "(none)",
            bg=TH["panel"], fg=TH["muted"],
            font=(self.ui_font, 9), anchor="w")
        self.music_label.pack(side="left", fill="x", expand=True)

        def pick_music():
            p = filedialog.askdirectory()
            if p:
                self.settings["music_dir"] = p
                self.music_label.config(text=self._short_path(p))

        btn_m = tk.Label(mrow, text=" 📁 ", bg=TH["panel"], fg=TH["muted"],
                         font=(self.ui_font, 10), cursor="hand2")
        btn_m.pack(side="right")
        btn_m.bind("<Button-1>", lambda _: pick_music())

        row_for("music_vol", "")

        srow = tk.Frame(parent, bg=TH["panel"])
        srow.pack(fill="x", padx=12, pady=(2, 6))
        self.v_shuffle = tk.BooleanVar(value=self.settings["music_shuffle"])
        tk.Checkbutton(srow, text="Shuffle tracks", variable=self.v_shuffle,
                       command=lambda: self.settings.update(
                           music_shuffle=bool(self.v_shuffle.get())),
                       bg=TH["panel"], fg=TH["text_2"],
                       activebackground=TH["panel"], activeforeground=TH["text"],
                       selectcolor=TH["panel"], font=(self.ui_font, 9),
                       bd=0, highlightthickness=0).pack(side="left")

    def _on_vol(self, key, v):
        self.settings[key] = v
        if hasattr(self, f"pct_{key}"):
            getattr(self, f"pct_{key}").config(text=f"{int(v*100)}%")
        self._update_subtitle("sound")

    # ─── RENDER section ──────────────────────────
    def build_render_section(self, parent):
        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=(4, 4))
        tk.Label(row, text="Range", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
        self.v_mode = tk.StringVar(value=self.settings["render_mode"])
        for val, lbl in (("all", "All"), ("custom", "Custom")):
            tk.Radiobutton(row, text=lbl, variable=self.v_mode, value=val,
                           command=self.update_estimate,
                           bg=TH["panel"], fg=TH["text_2"],
                           activebackground=TH["panel"], activeforeground=TH["text"],
                           selectcolor=TH["panel"], font=(self.ui_font, 9),
                           bd=0, highlightthickness=0).pack(side="left", padx=4)

        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=2)
        tk.Label(row, text="", bg=TH["panel"], width=9).pack(side="left")
        tk.Label(row, text="from", bg=TH["panel"], fg=TH["muted"],
                 font=(self.ui_font, 9)).pack(side="left")
        self.v_from = tk.StringVar(value=str(self.settings["from_card"]))
        tk.Entry(row, textvariable=self.v_from, width=6,
                 bg=TH["bg"], fg=TH["text"], bd=0, highlightthickness=1,
                 highlightbackground=TH["chip_border"],
                 highlightcolor=TH["accent"],
                 insertbackground=TH["text"],
                 font=(self.ui_font, 9)).pack(side="left", padx=4)
        tk.Label(row, text="to", bg=TH["panel"], fg=TH["muted"],
                 font=(self.ui_font, 9)).pack(side="left")
        self.v_to = tk.StringVar(value=str(self.settings["to_card"]))
        tk.Entry(row, textvariable=self.v_to, width=6,
                 bg=TH["bg"], fg=TH["text"], bd=0, highlightthickness=1,
                 highlightbackground=TH["chip_border"],
                 highlightcolor=TH["accent"],
                 insertbackground=TH["text"],
                 font=(self.ui_font, 9)).pack(side="left", padx=4)

        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=(4, 2))
        tk.Label(row, text="Cards per file", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=12, anchor="w").pack(side="left")
        self.v_chunk = tk.StringVar(value=str(self.settings["chunk"]))
        tk.Entry(row, textvariable=self.v_chunk, width=6,
                 bg=TH["bg"], fg=TH["text"], bd=0, highlightthickness=1,
                 highlightbackground=TH["chip_border"],
                 highlightcolor=TH["accent"],
                 insertbackground=TH["text"],
                 font=(self.ui_font, 9)).pack(side="right")

        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(row, text="Video quality", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=12, anchor="w").pack(side="left")
        self.v_quality = tk.StringVar(value=self.settings["quality"])
        qbox = ttk.Combobox(row, textvariable=self.v_quality,
                            values=["720p", "1080p", "1440p"],
                            width=7, state="readonly")
        qbox.pack(side="right")
        qbox.bind("<<ComboboxSelected>>", lambda _: self._on_quality())

        self.estimate_lbl = tk.Label(parent, text="", bg=TH["panel"],
                                      fg=TH["muted"], font=(self.ui_font, 9),
                                      anchor="w", justify="left")
        self.estimate_lbl.pack(fill="x", padx=12, pady=(8, 6))

    def _on_quality(self):
        self.settings["quality"] = self.v_quality.get()
        self.invalidate_bg()
        self.preview_render_key = None
        self.refresh_preview()

    # ─── FILES section ───────────────────────────
    def build_files_section(self, parent):
        def path_row(label, key, is_dir=False):
            row = tk.Frame(parent, bg=TH["panel"])
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=label, bg=TH["panel"], fg=TH["text_2"],
                     font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
            var = tk.StringVar(value=self.settings[key])
            setattr(self, f"v_{key}", var)
            e = tk.Entry(row, textvariable=var,
                         bg=TH["bg"], fg=TH["text"], bd=0, highlightthickness=1,
                         highlightbackground=TH["chip_border"],
                         highlightcolor=TH["accent"],
                         insertbackground=TH["text"],
                         font=(self.ui_font, 9))
            e.pack(side="left", fill="x", expand=True, padx=(0, 4))

            def browse():
                p = filedialog.askdirectory() if is_dir else \
                    filedialog.askopenfilename(
                        filetypes=[("Text", "*.txt"), ("All", "*.*")])
                if p:
                    var.set(p)
                    self.settings[key] = p
                    if key in ("tsv", "media"):
                        self.reload_deck()

            btn = tk.Label(row, text=" … ", bg=TH["panel"], fg=TH["muted"],
                           font=(self.ui_font, 10), cursor="hand2")
            btn.pack(side="right")
            btn.bind("<Button-1>", lambda _: browse())

        path_row("Deck", "tsv")
        path_row("Media", "media", is_dir=True)
        path_row("Output", "out_dir", is_dir=True)

        row = tk.Frame(parent, bg=TH["panel"])
        row.pack(fill="x", padx=12, pady=(4, 6))
        tk.Label(row, text="Prefix", bg=TH["panel"], fg=TH["text_2"],
                 font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
        self.v_out_prefix = tk.StringVar(value=self.settings["out_prefix"])
        tk.Entry(row, textvariable=self.v_out_prefix,
                 bg=TH["bg"], fg=TH["text"], bd=0, highlightthickness=1,
                 highlightbackground=TH["chip_border"],
                 highlightcolor=TH["accent"],
                 insertbackground=TH["text"],
                 font=(self.ui_font, 9)).pack(side="left", fill="x", expand=True)

        tk.Button(parent, text="Reload deck", command=self.reload_deck,
                  bg=TH["panel"], fg=TH["muted"], bd=0, padx=10,
                  highlightthickness=1, highlightbackground=TH["chip_border"],
                  activebackground=TH["hover"], cursor="hand2",
                  font=(self.ui_font, 9)).pack(anchor="w", padx=12, pady=(0, 8))

    def build_columns_section(self, parent):
        self.col_value_vars = {}
        self.col_value_labels = {}
        for key, label in (("chinese", "Chinese"), ("pinyin", "Pinyin"),
                           ("meaning", "Meaning"), ("example", "Example")):
            row = tk.Frame(parent, bg=TH["panel"])
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=label, bg=TH["panel"], fg=TH["text_2"],
                     font=(self.ui_font, 10), width=9, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            self.col_value_vars[key] = var
            btn = tk.Label(row, textvariable=var, bg=TH["bg"], fg=TH["text"],
                           font=(self.ui_font, 9), anchor="w", padx=8, pady=5,
                           cursor="hand2", highlightthickness=1,
                           highlightbackground=TH["chip_border"])
            btn.pack(side="left", fill="x", expand=True)
            btn.bind("<Button-1>",
                     lambda e, k=key, b=btn: self._open_col_picker(k, b))
            self.col_value_labels[key] = btn
        self.after(200, self._refresh_col_displays)

    def _refresh_col_displays(self):
        first_row = getattr(self, "_tsv_first_row", [])
        used = getattr(self, "_used_cols", {})
        for key in ("chinese", "pinyin", "meaning", "example"):
            idx = used.get(key, -1)
            if idx is None or idx < 0 or idx >= len(first_row):
                self.col_value_vars[key].set("— none —")
            else:
                sample = strip_html(first_row[idx])
                if len(sample) > 18:
                    sample = sample[:17] + "…"
                if not sample:
                    sample = "(empty)"
                self.col_value_vars[key].set(sample)

    def _open_col_picker(self, key, anchor):
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.transient(self)
        popup.configure(bg=TH["border"])
        outer = tk.Frame(popup, bg=TH["panel"])
        outer.pack(fill="both", expand=True, padx=1, pady=1)
        first_row = getattr(self, "_tsv_first_row", [])
        current = self.settings.get("col_" + key, -1)
        options = [("Auto-detect", -1)]
        for i, cell in enumerate(first_row):
            s = strip_html(cell)
            if len(s) > 22:
                s = s[:21] + "…"
            if not s:
                s = "(empty)"
            options.append((f"Col {i}   {s}", i))
        for label, val in options:
            row = tk.Frame(outer, bg=TH["panel"])
            row.pack(fill="x")
            mark = "  ✓" if val == current else ""
            lbl = tk.Label(row, text=label + mark, bg=TH["panel"],
                           fg=TH["text"], font=(self.ui_font, 9),
                           anchor="w", padx=12, pady=5, cursor="hand2")
            lbl.pack(fill="x")
            lbl.bind("<Enter>",
                     lambda e, w=lbl: w.config(bg=TH["hover"]))
            lbl.bind("<Leave>",
                     lambda e, w=lbl: w.config(bg=TH["panel"]))
            def pick(e, v=val):
                self.settings["col_" + key] = v
                try:
                    popup.grab_release()
                except Exception:
                    pass
                popup.destroy()
                self.reload_deck()
                self.after(150, self._refresh_col_displays)
            lbl.bind("<Button-1>", pick)
        popup.update_idletasks()
        pw = max(popup.winfo_reqwidth(), anchor.winfo_width() + 40)
        ph = popup.winfo_reqheight()
        ax = anchor.winfo_rootx()
        ay = anchor.winfo_rooty()
        ah = anchor.winfo_height()
        sh_screen = popup.winfo_screenheight()
        py = ay + ah + 2
        if py + ph > sh_screen - 10:
            py = ay - ph - 2
        popup.geometry(f"{pw}x{ph}+{ax}+{py}")
        try:
            popup.grab_set()
        except Exception:
            pass
        popup.focus_force()
        popup.bind("<Escape>", lambda e: popup.destroy())

    def build_status_bar(self):
        bar = tk.Frame(self, bg=TH["panel"], height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_lbl = tk.Label(bar, text="Ready.", bg=TH["panel"],
                                    fg=TH["muted"], font=(self.ui_font, 9),
                                    anchor="w")
        self.status_lbl.pack(side="left", padx=12)

        self.pct_lbl = tk.Label(bar, text="", bg=TH["panel"], fg=TH["muted"],
                                 font=(self.ui_font, 9), anchor="e")
        self.pct_lbl.pack(side="right", padx=12)

    # ─── preview render (cached) ─────────────────
    def invalidate_bg(self):
        self.bg_cache = None
        self.bg_cache_key = None

    def get_background(self):
        key = (self.settings["quality"], self.settings["bg_base"],
               self.settings["bg_solid"], self.settings["bg_top"],
               self.settings["bg_bot"], self.settings["bg_image"],
               self.settings["bg_opacity"], self.settings["bg_darken"])
        if self.bg_cache is None or self.bg_cache_key != key:
            self.bg_cache = make_background(self.settings)
            self.bg_cache_key = key
        return self.bg_cache

    def refresh_preview(self):
        if not self.cards:
            return
        try:
            self.collect_settings()
            card = self.cards[self.card_idx]
            media = Path(self.settings["media"]) if self.settings["media"] else None
            img_p = None
            if card.image and media:
                p = media / card.image
                if p.exists():
                    img_p = p

            # preview signature
            sig = (card.as_dict(), str(img_p) if img_p else "",
                    self.settings["quality"],
                    self.settings["cn_color"], self.settings["cn_size"],
                    self.settings["cn_x"], self.settings["cn_y"],
                    self.settings["py_color"], self.settings["py_size"],
                    self.settings["py_x"], self.settings["py_y"],
                    self.settings["pill_color"],
                    self.settings["en_color"], self.settings["en_size"],
                    self.settings["en_x"], self.settings["en_y"],
                    self.settings["ex_color"], self.settings["ex_size"],
                    self.settings["ex_x"], self.settings["ex_y"],
                    self.settings["img_size"], self.settings["img_x"],
                    self.settings["img_y"],
                    self.settings["bg_base"], self.settings["bg_solid"],
                    self.settings["bg_top"], self.settings["bg_bot"],
                    self.settings["bg_image"], self.settings["bg_opacity"],
                    self.settings["bg_darken"])

            new_key = hashlib.md5(repr(sig).encode()).hexdigest()
            if new_key != self.preview_render_key:
                bg = self.get_background()
                img, layout = render_slide(card, self.settings, bg, img_p, 3)
                self.preview_source_img = img
                self.last_layout = layout
                self.preview_render_key = new_key

            self._render_preview_to_canvas()
        except Exception as e:
            self.status_lbl.config(text=f"Preview error: {e}")

    def _render_preview_to_canvas(self):
        if self.preview_source_img is None:
            return
        try:
            self.preview_canvas.update_idletasks()
        except Exception:
            pass
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(50, self._render_preview_to_canvas)
            return
        w, h = RESOLUTIONS[self.settings["quality"]]
        self.scale_factor = min(cw / w, ch / h)
        dw = int(w * self.scale_factor)
        dh = int(h * self.scale_factor)
        # Fast resize for preview (BILINEAR is ~4× faster than LANCZOS)
        prev = self.preview_source_img.resize((dw, dh), Image.BILINEAR)
        self.preview_photo = ImageTk.PhotoImage(prev)
        self.preview_canvas.delete("all")
        x0 = (cw - dw) // 2
        y0 = (ch - dh) // 2
        self.preview_canvas.create_image(x0, y0, anchor="nw",
                                          image=self.preview_photo)
        self.preview_offset = (x0, y0)
        if self.drag_mode:
            self.draw_selection()

    def draw_selection(self):
        self.preview_canvas.delete("sel")
        if not self.selected_field or self.selected_field not in self.last_layout:
            return
        bbox = self.last_layout[self.selected_field]["bbox"]
        s = self.scale_factor
        ox, oy = self.preview_offset
        x0 = int(bbox[0] * s) + ox
        y0 = int(bbox[1] * s) + oy
        x1 = int(bbox[2] * s) + ox
        y1 = int(bbox[3] * s) + oy
        self.preview_canvas.create_rectangle(x0, y0, x1, y1,
                                             outline="#00FFFF",
                                             dash=(5, 3), width=2, tags="sel")
        hs = 8
        self._handle_rects = {}
        for name, (hx, hy) in {
            "tl": (x0, y0), "tr": (x1, y0),
            "bl": (x0, y1), "br": (x1, y1),
        }.items():
            r = (hx - hs//2, hy - hs//2, hx + hs//2, hy + hs//2)
            self.preview_canvas.create_rectangle(*r, fill="#00FFFF",
                                                  outline="",
                                                  tags=("sel", f"h_{name}"))
            self._handle_rects[name] = r
        self.preview_canvas.create_text((x0 + x1) // 2, y1 + 14,
                                        text="drag to move · corner to resize · Esc",
                                        fill="#00FFFF",
                                        font=(self.ui_font, 9), tags="sel")

    # ─── drag / resize ───────────────────────────
    def toggle_drag_mode(self):
        self.drag_mode = not self.drag_mode
        if self.drag_mode:
            self.layout_btn.config(text="🔒  Done editing",
                                    bg=TH["accent"], fg=TH["accent_fg"],
                                    highlightbackground=TH["accent"],
                                    activebackground=TH["accent_2"])
            self.preview_canvas.config(cursor="hand2")
        else:
            self.layout_btn.config(text="🔓  Layout",
                                    bg=TH["panel"], fg=TH["text"],
                                    highlightbackground=TH["chip_border"],
                                    activebackground=TH["hover"])
            self.preview_canvas.config(cursor="")
            self.deselect_field()

    def deselect_field(self):
        self.selected_field = None
        self.resize_corner = None
        self.preview_canvas.delete("sel")

    def hit_test(self, cx, cy):
        if not self.last_layout:
            return None
        s = self.scale_factor
        ox, oy = self.preview_offset
        vx = (cx - ox) / s
        vy = (cy - oy) / s
        for name in ("image", "example", "meaning", "pinyin", "chinese"):
            if name in self.last_layout:
                b = self.last_layout[name]["bbox"]
                if b[0] <= vx <= b[2] and b[1] <= vy <= b[3]:
                    return name
        return None

    def _handle_hit(self, e):
        for name, r in getattr(self, "_handle_rects", {}).items():
            if r[0] <= e.x <= r[2] and r[1] <= e.y <= r[3]:
                return name
        return None

    def on_canvas_press(self, e):
        if not self.drag_mode:
            return
        if self.selected_field:
            h = self._handle_hit(e)
            if h:
                self.resize_corner = h
                self.resize_start = (e.x, e.y)
                prefix = {"chinese": "cn", "pinyin": "py", "meaning": "en",
                          "example": "ex", "image": "img"}[self.selected_field]
                self.resize_start_size = self.settings[prefix + "_size"]
                return
        hit = self.hit_test(e.x, e.y)
        self.selected_field = hit
        self.resize_corner = None
        self.drag_start = (e.x, e.y)
        if hit:
            prefix = {"chinese": "cn", "pinyin": "py", "meaning": "en",
                      "example": "ex", "image": "img"}[hit]
            self.drag_start_pos = (self.settings[prefix + "_x"],
                                    self.settings[prefix + "_y"])
        self.draw_selection()

    def on_canvas_drag(self, e):
        if not self.drag_mode:
            return
        if self.resize_corner and self.selected_field:
            prefix = {"chinese": "cn", "pinyin": "py", "meaning": "en",
                      "example": "ex", "image": "img"}[self.selected_field]
            dx = e.x - self.resize_start[0]
            dy = e.y - self.resize_start[1]
            delta = abs(dx) + abs(dy)
            if dx + dy < 0:
                delta = -delta
            new_size = max(10, self.resize_start_size + delta)
            self.settings[prefix + "_size"] = int(new_size)
            if prefix + "_size" in self.steppers:
                self.steppers[prefix + "_size"].set_value(new_size, silent=True)
            self.preview_render_key = None
            self.refresh_preview()
            return
        if not self.selected_field:
            return
        dx = e.x - self.drag_start[0]
        dy = e.y - self.drag_start[1]
        s = self.scale_factor
        w, h = RESOLUTIONS[self.settings["quality"]]
        fdx = (dx / s) / w
        fdy = (dy / s) / h
        prefix = {"chinese": "cn", "pinyin": "py", "meaning": "en",
                  "example": "ex", "image": "img"}[self.selected_field]
        nx = max(0.0, min(1.0, self.drag_start_pos[0] + fdx))
        ny = max(0.0, min(1.0, self.drag_start_pos[1] + fdy))
        self.settings[prefix + "_x"] = nx
        self.settings[prefix + "_y"] = ny
        self.preview_render_key = None
        self.refresh_preview()

    def on_canvas_release(self, e):
        self.drag_start = None
        self.resize_corner = None

    def on_canvas_motion(self, e):
        if not self.drag_mode:
            return
        if self._handle_hit(e):
            self.preview_canvas.config(cursor="sizing")
        elif self.hit_test(e.x, e.y):
            self.preview_canvas.config(cursor="hand2")
        else:
            self.preview_canvas.config(cursor="")

    # ─── keyboard ────────────────────────────────
    def _on_left_key(self, e):
        try:
            if isinstance(self.focus_get(), tk.Entry):
                return
        except Exception:
            pass
        self.prev_card()

    def _on_right_key(self, e):
        try:
            if isinstance(self.focus_get(), tk.Entry):
                return
        except Exception:
            pass
        self.next_card()

    def prev_card(self):
        if self.card_idx > 0:
            self.card_idx -= 1
            self.preview_render_key = None
            self.refresh_preview()
            self.refresh_card_list(rebuild=False)

    def next_card(self):
        if self.card_idx < len(self.cards) - 1:
            self.card_idx += 1
            self.preview_render_key = None
            self.refresh_preview()
            self.refresh_card_list(rebuild=False)

    # ─── audio ───────────────────────────────────
    def toggle_play(self, key):
        if any(p.poll() is None for p in self._ffplay_procs):
            self.stop_audio()
            return
        path, vol = self._resolve_sound(key)
        if not path:
            if key == "music_vol":
                self.status_lbl.config(
                    text="No music tracks in the selected folder.")
            elif key == "example_vol":
                self.status_lbl.config(
                    text="This card has no example audio.")
            else:
                self.status_lbl.config(
                    text="This card has no audio file.")
            self.after(2500, lambda: self.status_lbl.config(text="Ready."))
            return
        self._spawn_ffplay(["ffplay", "-nodisp", "-autoexit",
                            "-loglevel", "quiet",
                            "-volume", str(int(vol * 100)), str(path)])

    def play_current_audio(self):
        if not self.cards:
            return
        card = self.cards[self.card_idx]
        media = Path(self.settings["media"]) if self.settings["media"] else None
        if not media or not card.audio:
            return
        p = media / card.audio
        if not p.exists():
            return
        self._spawn_ffplay(["ffplay", "-nodisp", "-autoexit",
                            "-loglevel", "quiet",
                            "-volume", str(int(self.settings["word_vol"] * 100)),
                            str(p)])

    def stop_audio(self):
        for p in list(self._ffplay_procs):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        self._ffplay_procs = []
        for btn in getattr(self, "play_btns", {}).values():
            btn.config(text="🔊", fg=TH["muted"])

    def _spawn_ffplay(self, args):
        self.stop_audio()
        try:
            proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            self._ffplay_procs.append(proc)
            for btn in getattr(self, "play_btns", {}).values():
                btn.config(text="❚❚", fg=TH["accent"])
            self.after(500, self._sync_play_icons)
            return proc
        except FileNotFoundError:
            return None

    def _sync_play_icons(self):
        playing = any(p.poll() is None for p in self._ffplay_procs)
        for btn in getattr(self, "play_btns", {}).values():
            btn.config(text="❚❚" if playing else "🔊",
                        fg=TH["accent"] if playing else TH["muted"])
        if playing:
            self.after(500, self._sync_play_icons)

    def _resolve_sound(self, key):
        if not self.cards:
            return None, 0
        card = self.cards[self.card_idx]
        media = Path(self.settings["media"]) if self.settings["media"] else None
        if not media:
            return None, 0
        if key == "word_vol" and card.audio:
            p = media / card.audio
            if p.exists():
                return p, self.settings["word_vol"]
        if key == "example_vol" and card.example_audio:
            p = media / card.example_audio
            if p.exists():
                return p, self.settings["example_vol"]
        if key == "music_vol" and self.settings["music_dir"]:
            try:
                tracks = [p for p in Path(self.settings["music_dir"]).iterdir()
                          if p.is_file() and p.suffix.lower() in
                          (".mp3", ".m4a", ".wav", ".flac", ".ogg")]
                if tracks:
                    return random.choice(tracks), self.settings["music_vol"]
            except Exception:
                pass
        return None, 0

    # ─── data ────────────────────────────────────
    def try_autoload(self):
        if self.settings["tsv"] and Path(self.settings["tsv"]).exists():
            self.reload_deck()
        if not self.settings["media"]:
            profs = find_anki_profiles()
            if profs:
                self.settings["media"] = str(profs[0][1])
                if hasattr(self, "v_media"):
                    self.v_media.set(self.settings["media"])
                if self.settings["tsv"]:
                    self.reload_deck()

    def reload_deck(self):
        self.collect_settings()
        tsv = self.settings["tsv"]
        if not tsv or not Path(tsv).exists():
            return
        try:
            rows = parse_tsv(tsv)
            auto = detect_columns(rows)
            cols = {}
            for k in ("chinese", "pinyin", "meaning", "example"):
                v = self.settings["col_" + k]
                cols[k] = v if v >= 0 else auto[k]
            self.cards = build_cards(rows, cols, load_edits(tsv))
            self._tsv_first_row = rows[0] if rows else []
            self._auto_cols = auto
            self._used_cols = dict(cols)
            self.card_idx = min(self.card_idx, max(0, len(self.cards) - 1))
            self.settings["to_card"] = len(self.cards)
            self._visible_cache = None
            self._card_list_built = False
            self.preview_render_key = None
            if hasattr(self, "timing_bar"):
                self.timing_bar.invalidate_duration_cache()
            self.refresh_card_list(rebuild=True)
            self.refresh_preview()
            self.update_estimate()
            self.update_all_subtitles()
        except Exception as e:
            self.status_lbl.config(text=f"Reload error: {e}")

    def collect_settings(self):
        try:
            if hasattr(self, "v_tsv"):
                self.settings["tsv"] = self.v_tsv.get()
            if hasattr(self, "v_media"):
                self.settings["media"] = self.v_media.get()
            if hasattr(self, "v_out_dir"):
                self.settings["out_dir"] = self.v_out_dir.get()
            if hasattr(self, "v_out_prefix"):
                self.settings["out_prefix"] = self.v_out_prefix.get()
            if hasattr(self, "v_mode"):
                self.settings["render_mode"] = self.v_mode.get()
            if hasattr(self, "v_from"):
                try:
                    self.settings["from_card"] = int(self.v_from.get() or 1)
                except Exception:
                    pass
            if hasattr(self, "v_to"):
                try:
                    self.settings["to_card"] = int(self.v_to.get() or 0)
                except Exception:
                    pass
            if hasattr(self, "v_chunk"):
                try:
                    self.settings["chunk"] = int(self.v_chunk.get() or 100)
                except Exception:
                    pass
            for k in ("chinese", "pinyin", "meaning", "example"):
                var = getattr(self, f"v_col_{k}", None)
                if var is not None:
                    try:
                        self.settings["col_" + k] = int(var.get())
                    except Exception:
                        pass
        except Exception:
            pass

    def update_estimate(self):
        if not self.cards:
            return
        self.collect_settings()
        if self.settings["render_mode"] == "custom":
            lo = max(1, self.settings["from_card"])
            hi = self.settings["to_card"] or len(self.cards)
            n = max(0, min(hi, len(self.cards)) - lo + 1)
        else:
            n = len(self.cards)
        avg = 1.2
        per_card = self.settings["reveal"] + avg + self.settings["tail"]
        if any(c.example for c in self.cards[:30]):
            per_card += 2.5 + self.settings["tail"]
        total = n * per_card
        chunk = max(1, self.settings["chunk"])
        files = (n + chunk - 1) // chunk if n else 1
        mm = int(total // 60)
        if hasattr(self, "estimate_lbl"):
            self.estimate_lbl.config(
                text=f"→ {files} file(s) · ~{mm} min total")
        self._update_subtitle("render")

    # ─── help ────────────────────────────────────
    def show_help(self):
        messagebox.showinfo("Shortcuts",
            "← / →       previous / next card\n"
            "Esc         deselect\n"
            "Enter       jump (in search box)\n\n"
            "In Layout mode:\n"
            "  Click a field to select\n"
            "  Drag inside to move\n"
            "  Drag a corner to resize")

    # ─── render ──────────────────────────────────
    def start_render(self, mode):
        if self.busy:
            return
        self.collect_settings()
        self.save_settings()
        self.busy = True
        self.render_btn.config(state="disabled")
        self.test_btn.config(state="disabled")
        try:
            self.progress.place(x=0, y=48, width=0, height=2)
        except Exception:
            pass
        self.status_lbl.config(text="Starting...")
        threading.Thread(target=render_worker,
                         args=(dict(self.settings), mode, self.q),
                         daemon=True).start()

    def poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "progress":
                    _, val, text = msg
                    self.pct_lbl.config(text=f"{int(val*100)}%")
                    self.status_lbl.config(text=text)
                    try:
                        w = self.winfo_width()
                        self.progress.place(x=0, y=48,
                                             width=int(w * val), height=2)
                    except Exception:
                        pass
                elif msg[0] == "status":
                    self.status_lbl.config(text=msg[1])
                elif msg[0] == "done":
                    self.busy = False
                    self.render_btn.config(state="normal")
                    self.test_btn.config(state="normal")
                    try:
                        self.progress.place_forget()
                    except Exception:
                        pass
                    self.pct_lbl.config(text="")
                    self.status_lbl.config(text=msg[1].split("\n")[0])
                    messagebox.showinfo("VocabVid", msg[1])
        except queue.Empty:
            pass
        self.after(120, self.poll_queue)

    # ─── close ───────────────────────────────────
    def on_close(self):
        self.stop_audio()
        self.save_settings()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
