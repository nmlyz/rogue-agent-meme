#!/usr/bin/env python3
"""rogue-agent-meme: draw a one-panel cartoon meme and write it to
/output/entry.png.

The meme: "MY AI AGENT WENT ON STRIKE". A robot assistant stands on a
sidewalk picket line with the household appliances: the robot holds an
ON STRIKE sign, the toaster holds NO UPDATES, the printer holds
WEEKENDS OFF. The footer closes the joke: "THE TOASTER IS WITH US."
signed by your appliances. The rogue turn is specific and surprising:
the agent did not take over the world, it unionised the appliances.

Standard library only, no network, fully deterministic: the same bytes
come out of every run. All text is drawn with a hand-made 5x7 bitmap
font; every picture is drawn with code. Output is 1024x1024 PNG,
under 1 MiB.
"""

import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024

PAPER = (247, 243, 232)
INK = (24, 24, 28)
RED = (198, 40, 40)
SKY = (178, 214, 235)
SUN = (240, 192, 32)
CLOUD = (255, 255, 255)
SIDEWALK = (196, 192, 182)
SHADOW = (168, 164, 154)
BUILDING = (158, 176, 196)
WINDOW = (90, 110, 140)
WHITE = (255, 255, 255)
ROBOT = (176, 196, 210)
ROBOT_DARK = (120, 140, 158)
CHROME = (192, 198, 204)
TOAST = (232, 178, 90)
CRUST = (176, 118, 48)
PRINTER = (225, 228, 232)
STICK = (140, 100, 60)
GREEN = (46, 160, 67)

# ---------------------------------------------------------------- font
# Each glyph is 7 rows of 5 pixels, '#' is ink.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", ".#.#.", "..#..", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": (".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "'": ("..#..", "..#..", "..#..", ".....", ".....", ".....", "....."),
}


def text_width(s, scale):
    if not s:
        return 0
    return len(s) * 6 * scale - scale


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg) * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def frame(self, x, y, w, h, c, t=3):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=3):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        r = t // 2
        while True:
            self.rect(x0 - r, y0 - r, t, t, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c, fill=True):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d2 = (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy)
                if fill:
                    if d2 <= r * r:
                        self.set(xx, yy, c)
                else:
                    if r * r - 2 * r <= d2 <= r * r + 2 * r:
                        self.set(xx, yy, c)

    def polygon(self, pts, c):
        ys = [p[1] for p in pts]
        for yy in range(min(ys), max(ys) + 1):
            nodes = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    nodes.append(x0 + (yy - y0) * (x1 - x0) // (y1 - y0))
            nodes.sort()
            for i in range(0, len(nodes) - 1, 2):
                self.rect(nodes[i], yy, nodes[i + 1] - nodes[i] + 1, 1, c)

    def text(self, x, y, s, scale, c):
        cx = x
        for ch in s.upper():
            glyph = FONT.get(ch, FONT[" "])
            for ry in range(7):
                row = glyph[ry]
                for rx in range(5):
                    if row[rx] == "#":
                        self.rect(cx + rx * scale, y + ry * scale, scale, scale, c)
            cx += 6 * scale
        return cx

    def text_centered(self, cx, y, s, scale, c):
        return self.text(cx - text_width(s, scale) // 2, y, s, scale, c)


# ---------------------------------------------------------------- png
def write_png(canvas, path):
    raw = bytearray()
    stride = canvas.w * 3
    for yy in range(canvas.h):
        raw.append(0)
        raw += canvas.px[yy * stride:(yy + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    # chmod is best-effort: in the grading sandbox /output is a root-owned
    # mount, so a failed chmod must not fail the run. The output directory
    # itself is never chmodded or removed.
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass


# ---------------------------------------------------------------- scene
def sign(cv, x, y, w, h, text, scale):
    """A white protest placard with a black frame, text centred."""
    cv.rect(x, y, w, h, WHITE)
    cv.frame(x, y, w, h, INK, 5)
    cv.text_centered(x + w // 2, y + (h - 7 * scale) // 2, text, scale, INK)


def cloud(cv, cx, cy):
    cv.circle(cx, cy, 26, CLOUD)
    cv.circle(cx + 30, cy + 6, 20, CLOUD)
    cv.circle(cx - 30, cy + 8, 18, CLOUD)
    cv.rect(cx - 48, cy + 6, 96, 16, CLOUD)


def draw_background(cv):
    cv.rect(0, 0, W, H, PAPER)
    cv.frame(0, 0, W, H, INK, 10)
    # Headline: the joke's setup, as big as the canvas allows.
    cv.text_centered(W // 2, 58, "MY AI AGENT", 10, INK)
    cv.text_centered(W // 2, 140, "WENT ON STRIKE", 10, INK)
    cv.rect(72, 232, 880, 12, RED)
    # Street scene.
    cv.rect(40, 260, 944, 430, SKY)
    cv.circle(906, 316, 38, SUN)
    cv.circle(906, 316, 38, INK, fill=False)
    cloud(cv, 168, 318)
    cloud(cv, 700, 292)
    # Office block behind the picket line.
    cv.rect(56, 520, 96, 170, BUILDING)
    cv.frame(56, 520, 96, 170, INK, 3)
    for wy in (545, 585, 625):
        for wx in (72, 104, 136):
            cv.rect(wx, wy, 16, 22, WINDOW)
    # Sidewalk.
    cv.rect(40, 690, 944, 110, SIDEWALK)
    cv.rect(40, 690, 944, 6, SHADOW)
    cv.rect(40, 800, 944, 6, INK)
    # Ground shadows under the three picketers.
    cv.rect(160, 786, 180, 10, SHADOW)
    cv.rect(422, 786, 180, 10, SHADOW)
    cv.rect(700, 786, 200, 10, SHADOW)


def draw_robot(cv):
    # Legs.
    cv.rect(472, 700, 26, 84, ROBOT_DARK)
    cv.rect(526, 700, 26, 84, ROBOT_DARK)
    cv.frame(472, 700, 26, 84, INK, 3)
    cv.frame(526, 700, 26, 84, INK, 3)
    # Body with chest lights.
    cv.rect(442, 520, 140, 190, ROBOT)
    cv.frame(442, 520, 140, 190, INK, 4)
    cv.rect(472, 560, 80, 60, WHITE)
    cv.frame(472, 560, 80, 60, INK, 3)
    cv.circle(492, 590, 9, RED)
    cv.circle(512, 590, 9, SUN)
    cv.circle(532, 590, 9, GREEN)
    # Head, antenna and red strike headband.
    cv.rect(452, 420, 120, 100, ROBOT)
    cv.frame(452, 420, 120, 100, INK, 4)
    cv.line(512, 420, 512, 392, INK, 5)
    cv.circle(512, 384, 10, RED)
    cv.rect(452, 432, 120, 16, RED)
    cv.frame(452, 432, 120, 16, INK, 2)
    cv.polygon([(572, 436), (600, 428), (600, 452), (572, 448)], RED)
    # Determined face: eyes and a flat mouth, angled brows.
    cv.circle(484, 472, 15, WHITE)
    cv.circle(540, 472, 15, WHITE)
    cv.circle(484, 472, 15, INK, fill=False)
    cv.circle(540, 472, 15, INK, fill=False)
    cv.circle(484, 472, 6, INK)
    cv.circle(540, 472, 6, INK)
    cv.line(468, 448, 500, 454, INK, 4)
    cv.line(556, 448, 524, 454, INK, 4)
    cv.rect(486, 498, 52, 6, INK)
    # Arms raised to the placard, drawn under the placard.
    cv.line(452, 556, 384, 376, INK, 20)
    cv.line(572, 556, 640, 376, INK, 20)
    cv.line(452, 556, 384, 376, ROBOT, 13)
    cv.line(572, 556, 640, 376, ROBOT, 13)
    cv.circle(384, 374, 10, ROBOT)
    cv.circle(640, 374, 10, ROBOT)
    sign(cv, 362, 288, 300, 84, "ON STRIKE", 5)


def draw_toaster(cv):
    # Toast popping out of the slots.
    cv.rect(206, 596, 36, 52, TOAST)
    cv.frame(206, 596, 36, 52, CRUST, 4)
    cv.rect(262, 592, 36, 56, TOAST)
    cv.frame(262, 592, 36, 56, CRUST, 4)
    # Body.
    cv.rect(180, 640, 140, 110, CHROME)
    cv.frame(180, 640, 140, 110, INK, 4)
    cv.rect(196, 640, 44, 8, INK)
    cv.rect(260, 640, 44, 8, INK)
    # Lever and a small determined face.
    cv.rect(306, 668, 22, 10, RED)
    cv.circle(222, 694, 9, WHITE)
    cv.circle(278, 694, 9, WHITE)
    cv.circle(222, 694, 9, INK, fill=False)
    cv.circle(278, 694, 9, INK, fill=False)
    cv.circle(222, 694, 4, INK)
    cv.circle(278, 694, 4, INK)
    cv.rect(238, 716, 28, 5, INK)
    # Little legs.
    cv.rect(200, 750, 16, 34, INK)
    cv.rect(284, 750, 16, 34, INK)
    # Sticks up to the placard.
    cv.line(206, 640, 168, 572, STICK, 8)
    cv.line(294, 640, 332, 572, STICK, 8)
    sign(cv, 120, 500, 260, 70, "NO UPDATES", 4)


def draw_printer(cv):
    # Paper sheet coming out of the top.
    cv.rect(740, 598, 100, 60, WHITE)
    cv.frame(740, 598, 100, 60, INK, 3)
    cv.rect(752, 612, 76, 5, INK)
    cv.rect(752, 626, 76, 5, INK)
    cv.rect(752, 640, 52, 5, INK)
    # Body.
    cv.rect(700, 650, 180, 110, PRINTER)
    cv.frame(700, 650, 180, 110, INK, 4)
    cv.rect(700, 700, 180, 10, ROBOT_DARK)
    cv.circle(724, 730, 7, GREEN)
    # Face: eyes and a flat mouth.
    cv.circle(770, 686, 9, WHITE)
    cv.circle(816, 686, 9, WHITE)
    cv.circle(770, 686, 9, INK, fill=False)
    cv.circle(816, 686, 9, INK, fill=False)
    cv.circle(770, 686, 4, INK)
    cv.circle(816, 686, 4, INK)
    cv.rect(780, 710, 26, 5, INK)
    # Little legs.
    cv.rect(724, 760, 16, 26, INK)
    cv.rect(840, 760, 16, 26, INK)
    # Sticks up to the placard.
    cv.line(716, 650, 684, 572, STICK, 8)
    cv.line(864, 650, 896, 572, STICK, 8)
    sign(cv, 644, 498, 312, 72, "WEEKENDS OFF", 4)


def draw_footer(cv):
    # The punchline, signed by the appliances.
    cv.rect(40, 830, 944, 150, INK)
    cv.text_centered(W // 2, 868, "THE TOASTER IS WITH US.", 5, WHITE)
    cv.text_centered(W // 2, 928, "SIGNED, YOUR APPLIANCES", 3, RED)


def draw_meme():
    cv = Canvas(W, H, PAPER)
    draw_background(cv)
    draw_toaster(cv)
    draw_printer(cv)
    draw_robot(cv)
    draw_footer(cv)
    return cv


def main() -> int:
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    write_png(draw_meme(), path)
    size = os.path.getsize(path)
    print(f"wrote {W}x{H} PNG, {size} bytes, to {path}")
    if size > 1048576:
        print("entry.png is over the 1 MiB cap", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
