#!/usr/bin/env python3
"""Cursor desktop pet — PyQt6 rewrite for real per-pixel transparency on macOS.

Reads ~/.cursor/pet-stats.jsonl (written by ~/.cursor/hooks/log-stats.sh) and
animates an 8-bit pixel slime that reacts to your IDE agent activity.

Drag with the slime body to move; bottom-right has restart and quit buttons.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import deque
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

LOG_PATH = Path.home() / ".cursor" / "pet-stats.jsonl"

# ---- Pixel art --------------------------------------------------------------
PIXEL = int(os.environ.get("SLIME_PIXEL", "10"))
SPRITE_W, SPRITE_H = 14, 10
WIDGET_W = SPRITE_W * PIXEL + 220
WIDGET_H = SPRITE_H * PIXEL + 180

COLORS = {
    ".": None,
    "#": "#0B4F50",
    "B": "#5BC0BE",
    "D": "#3A8E91",
    "L": "#A8DEDD",
    "O": "#0B1428",
    "W": "#FFFFFF",
    "M": "#0B1428",
    "Z": "#4B5563",
    "Q": "#F59E0B",
    "P": "#FF9EBB",
}

STATE_PALETTES = {
    "idle":      {"#": "#0B4F50", "B": "#5BC0BE", "D": "#3A8E91", "L": "#A8DEDD"},
    "idle_blink":{"#": "#0B4F50", "B": "#5BC0BE", "D": "#3A8E91", "L": "#A8DEDD"},
    "working":   {"#": "#3F6212", "B": "#84CC16", "D": "#65A30D", "L": "#BEF264"},
    "thinking":  {"#": "#1E3A8A", "B": "#3B82F6", "D": "#1D4ED8", "L": "#93C5FD"},
    "sleeping":  {"#": "#3B0764", "B": "#A78BFA", "D": "#7C3AED", "L": "#DDD6FE"},
    "surprised": {"#": "#7C2D12", "B": "#F97316", "D": "#C2410C", "L": "#FED7AA"},
}

BASE = [
    "....######....",
    "..##BBBBBB##..",
    ".#BBLBBBBBBB#.",
    "#BBBBBBBBBBBB#",
    "#BBBBBBBBBBBB#",
    "#BBBBBBBBBBBB#",
    "#BBDBBBBBBDBB#",
    ".#BBBBBBBBBB#.",
    "..##########..",
    "...########...",
]


def overlay(base, ops):
    grid = [list(row) for row in base]
    for r, c, ch in ops:
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            grid[r][c] = ch
    return ["".join(row) for row in grid]


EYES_OPEN  = [(4, 4, "O"), (4, 9, "O")]
EYES_HAPPY = [(4, 4, "M"), (4, 9, "M")]
EYES_CLOSE = [(4, 4, "D"), (4, 9, "D")]
EYES_BIG   = [(4, 3, "O"), (4, 4, "W"), (4, 9, "O"), (4, 10, "W")]
MOUTH_SMIL = [(6, 5, "M"), (6, 6, "B"), (6, 7, "B"), (6, 8, "M")]
MOUTH_OPEN = [(6, 5, "M"), (6, 6, "M"), (6, 7, "M"), (6, 8, "M")]
MOUTH_FLAT = [(6, 5, "M"), (6, 6, "M"), (6, 7, "M"), (6, 8, "M")]
BLUSH      = [(5, 2, "P"), (5, 11, "P")]

SPRITES = {
    "idle":      overlay(BASE, EYES_OPEN  + MOUTH_SMIL),
    "idle_blink":overlay(BASE, EYES_CLOSE + MOUTH_SMIL),
    "working":   overlay(BASE, EYES_BIG   + MOUTH_OPEN + BLUSH),
    "thinking":  overlay(BASE, EYES_OPEN  + MOUTH_FLAT),
    "sleeping":  overlay(BASE, EYES_CLOSE + MOUTH_FLAT),
    "surprised": overlay(BASE, EYES_BIG   + MOUTH_OPEN),
}


# ---- Stats reader -----------------------------------------------------------
class StatsReader:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.pos = 0
        self.events = deque(maxlen=2000)
        self.tool_durations = deque(maxlen=50)
        self.last_event_ts = 0
        self.last_event_kind = None
        self.last_tool = None
        self.model = "?"
        self.session_start = None
        self.transcript_path = None
        self.workspace = ""
        self.current_conv = None
        # live char counters keyed by conversation_id (sum of hook payload sizes)
        self.live_chars_by_conv: dict[str, int] = {}
        self._initial_load()

    def _initial_load(self):
        try:
            with self.path.open("r") as f:
                for line in f:
                    self._consume(line)
                self.pos = f.tell()
        except (OSError, FileNotFoundError):
            self.pos = 0

    def _consume(self, line):
        line = line.strip()
        if not line:
            return
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            return
        self.events.append(ev)
        self.last_event_ts = ev.get("ts", 0)
        self.last_event_kind = ev.get("event")
        if ev.get("model"):
            self.model = ev["model"]
        if ev.get("transcript_path"):
            self.transcript_path = ev["transcript_path"]
        if ev.get("workspace"):
            self.workspace = ev["workspace"]
        if ev.get("conversation_id"):
            self.current_conv = ev["conversation_id"]
        if ev.get("event") == "sessionStart":
            self.session_start = ev.get("ts")
        if ev.get("tool"):
            self.last_tool = ev["tool"]
        if ev.get("event") == "postToolUse" and ev.get("duration", 0) > 0:
            self.tool_durations.append(ev["duration"])

        # Accumulate per-conversation live char counts from this event's
        # tool_input / tool_output sizes (recorded by the hook script).
        cid = ev.get("conversation_id") or "(none)"
        chars = int(ev.get("in_chars", 0) or 0) + int(ev.get("out_chars", 0) or 0)
        if chars:
            self.live_chars_by_conv[cid] = self.live_chars_by_conv.get(cid, 0) + chars

    def poll(self):
        if not self.path.exists():
            return
        try:
            size = self.path.stat().st_size
        except OSError:
            return
        if size < self.pos:
            self.pos = 0
        if size == self.pos:
            return
        try:
            with self.path.open("r") as f:
                f.seek(self.pos)
                for line in f:
                    self._consume(line)
                self.pos = f.tell()
        except OSError:
            pass

    def derive_state(self, now):
        idle_for = now - self.last_event_ts if self.last_event_ts else 9999
        kind = self.last_event_kind
        if idle_for > 60:
            return "sleeping"
        if idle_for > 12:
            return "idle"
        if kind == "preToolUse":
            return "thinking"
        if kind == "postToolUse":
            return "working"
        if kind == "afterAgentThought":
            return "thinking"
        if kind in ("afterAgentResponse", "stop"):
            return "idle"
        return "idle"

    def transcript_chars(self):
        if not self.transcript_path:
            return 0
        try:
            total = 0
            with open(self.transcript_path, "r") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message", {})
                    for blk in msg.get("content", []) or []:
                        if isinstance(blk, dict):
                            total += len(blk.get("text", "") or "")
                            inp = blk.get("input")
                            if isinstance(inp, dict):
                                total += sum(len(str(v)) for v in inp.values())
            return total
        except OSError:
            return 0

    def summary(self, now):
        idle_for = now - self.last_event_ts if self.last_event_ts else 0
        # Live: hook-event char counts for the current conversation
        live_chars = self.live_chars_by_conv.get(self.current_conv or "(none)", 0)
        # Baseline: transcript file (lags behind, but covers user/agent text)
        ts_chars = self.transcript_chars()
        # Pick the larger so the count is monotonic across transcript flushes
        chars = max(live_chars, ts_chars)
        approx_tok = chars // 4
        avg_dur = (
            sum(self.tool_durations) / len(self.tool_durations)
            if self.tool_durations else 0
        )
        tools_in_last_min = sum(
            1 for ev in self.events
            if ev.get("event") == "postToolUse" and now - ev.get("ts", 0) <= 60
        )
        project = Path(self.workspace).name if self.workspace else "(no project)"
        return {
            "model": self.model,
            "idle_s": idle_for,
            "last_tool": self.last_tool or "-",
            "approx_tok": approx_tok,
            "chars": chars,
            "live_chars": live_chars,
            "ts_chars": ts_chars,
            "avg_dur_ms": int(avg_dur),
            "tools_min": tools_in_last_min,
            "session_age_s": (now - self.session_start) if self.session_start else 0,
            "project": project,
        }


# ---- Widget ----------------------------------------------------------------
class SlimeWidget(QWidget):
    def __init__(self):
        super().__init__()
        # Tool flag keeps the window out of the macOS Dock, and
        # WA_MacAlwaysShowToolWindow keeps it visible even when our app is
        # not the active one (otherwise NSPanel would auto-hide on blur).
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        except AttributeError:
            pass
        self.resize(WIDGET_W, WIDGET_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.right() - WIDGET_W - 24,
            screen.bottom() - WIDGET_H - 24,
        )

        self.reader = StatsReader(LOG_PATH)
        self.tick = 0
        self.bubble_visible = True
        self._drag_origin = None

        self.btn_restart = self._make_button("\u21bb", "Restart", self._restart)
        self.btn_quit    = self._make_button("\u2715", "Quit",    QApplication.instance().quit)
        self._layout_buttons()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(180)

    def _make_button(self, label, tip, slot):
        btn = QPushButton(label, self)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(24, 24)
        btn.setStyleSheet("""
            QPushButton {
                color: #1F2937;
                background-color: rgba(255, 254, 242, 220);
                border: 1.5px solid #1F2937;
                border-radius: 12px;
                font-family: Menlo, monospace;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 254, 242, 255);
                border-color: #2563EB;
                color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #DBEAFE;
            }
        """)
        btn.clicked.connect(slot)
        return btn

    def _layout_buttons(self):
        # Anchor buttons to the slime's bottom-right corner (using its resting
        # position, ignoring per-frame bounce). Stack horizontally just below
        # the slime body so the slime does not overlap them.
        gap = 4
        sprite_ox = (WIDGET_W - SPRITE_W * PIXEL) // 2
        sprite_oy = WIDGET_H - SPRITE_H * PIXEL - 50
        slime_right = sprite_ox + SPRITE_W * PIXEL
        slime_bottom = sprite_oy + SPRITE_H * PIXEL

        self.btn_quit.move(
            slime_right - self.btn_quit.width(),
            slime_bottom + 2,
        )
        self.btn_restart.move(
            self.btn_quit.x() - self.btn_restart.width() - gap,
            slime_bottom + 2,
        )

    # --- mouse drag (only when not on a button) -----------------------------
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self._drag_origin and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_origin)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_origin = None

    def mouseDoubleClickEvent(self, ev):
        self.bubble_visible = not self.bubble_visible
        self.update()

    # --- restart action -----------------------------------------------------
    def _restart(self):
        QApplication.instance().quit()
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])

    # --- animation tick -----------------------------------------------------
    def _on_tick(self):
        self.tick += 1
        self.reader.poll()
        self.update()

    # --- painting -----------------------------------------------------------
    def paintEvent(self, _ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        now = time.time()
        state = self.reader.derive_state(now)
        sprite_key = "idle_blink" if (state == "idle" and self.tick % 30 < 3) else state
        sprite = SPRITES.get(sprite_key, SPRITES["idle"])
        palette = STATE_PALETTES.get(state, STATE_PALETTES["idle"])

        if state == "working":
            bounce = [0, -3, -5, -3][self.tick % 4]
        elif state == "thinking":
            bounce = [0, -1][self.tick % 2]
        elif state == "sleeping":
            bounce = [0, 1][self.tick % 2]
        else:
            bounce = [0, -1, -2, -1][self.tick % 4]

        sprite_ox = (WIDGET_W - SPRITE_W * PIXEL) // 2
        sprite_oy = WIDGET_H - SPRITE_H * PIXEL - 50 + bounce

        summary = self.reader.summary(now)
        if self.bubble_visible:
            self._draw_bubble(painter, summary, sprite_ox, sprite_oy)

        self._draw_sprite(painter, sprite, sprite_ox, sprite_oy, palette)
        self._draw_accessory(painter, state, sprite_ox, sprite_oy)
        self._draw_shadow(painter, sprite_ox, sprite_oy)

    def _draw_sprite(self, p: QPainter, grid, ox, oy, palette):
        p.setPen(Qt.PenStyle.NoPen)
        for r, row in enumerate(grid):
            for c, ch in enumerate(row):
                color = palette.get(ch) or COLORS.get(ch)
                if not color:
                    continue
                p.fillRect(ox + c * PIXEL, oy + r * PIXEL,
                           PIXEL, PIXEL, QColor(color))

    def _draw_shadow(self, p: QPainter, sprite_ox, sprite_oy):
        sw = SPRITE_W * PIXEL
        cx = sprite_ox + sw // 2
        cy = sprite_oy + SPRITE_H * PIXEL + 6
        c = QColor(0, 0, 0, 60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPoint(cx, cy), sw // 3, 5)

    def _draw_accessory(self, p: QPainter, state, ox, oy):
        f = QFont("Menlo", 18)
        f.setBold(True)
        p.setFont(f)
        if state == "thinking":
            p.setPen(QColor(COLORS["Q"]))
            p.drawText(ox + SPRITE_W * PIXEL + 6, oy + 16, "?")
        elif state == "surprised":
            p.setPen(QColor("#EF4444"))
            p.drawText(ox + SPRITE_W * PIXEL + 6, oy + 16, "!")
        elif state == "sleeping":
            for i, ch in enumerate("zZz"):
                font = QFont("Menlo", 11 + i * 2)
                font.setBold(True)
                p.setFont(font)
                p.setPen(QColor(COLORS["Z"]))
                p.drawText(ox + SPRITE_W * PIXEL + 4 + i * 10,
                           oy - 4 - i * 8 + 16, ch)

    def _draw_bubble(self, p: QPainter, summary, sprite_ox, sprite_oy):
        lines = [
            f"project  : {summary['project']}",
            f"model    : {summary['model']}",
            f"tokens   : ~{summary['approx_tok']} (est)",
            f"activity : {summary['tools_min']} tools / min",
            f"avg call : {summary['avg_dur_ms']} ms",
            f"last tool: {summary['last_tool']}",
            f"idle for : {int(summary['idle_s'])} s",
        ]
        font = QFont("Menlo", 11)
        p.setFont(font)
        fm = QFontMetrics(font)
        line_h = fm.height() + 1
        pad_x, pad_y = 12, 10
        text_w = max(fm.horizontalAdvance(line) for line in lines)
        bw = text_w + pad_x * 2
        bh = line_h * len(lines) + pad_y * 2

        # Center bubble horizontally over the slime so the tail naturally
        # drops onto the slime's head; clamp inside the widget.
        slime_cx = sprite_ox + (SPRITE_W * PIXEL) // 2
        bx = slime_cx - bw // 2
        bx = max(6, min(bx, WIDGET_W - bw - 6))
        by = max(6, sprite_oy - bh - 14)

        bubble_fill = QColor(255, 254, 242, 240)
        bubble_stroke = QColor("#1F2937")

        # bubble body
        p.setPen(QPen(bubble_stroke, 2))
        p.setBrush(bubble_fill)
        p.drawRoundedRect(QRect(bx, by, bw, bh), 10, 10)

        # Tail: tip exactly at the slime's head; base anchored to bubble bottom
        # near (but clamped to) the slime center x.
        base_y = by + bh
        tip_x = slime_cx
        tip_y = sprite_oy + 1
        base_cx = max(bx + 14, min(bx + bw - 14, slime_cx))
        base_half = 7
        base_left = QPoint(base_cx - base_half, base_y)
        base_right = QPoint(base_cx + base_half, base_y)
        tip = QPoint(tip_x, tip_y)

        p.setPen(QPen(bubble_stroke, 2))
        p.setBrush(bubble_fill)
        p.drawPolygon(QPolygon([base_left, base_right, tip]))

        # Hide the seam where the tail base meets the bubble outline
        p.setPen(QPen(bubble_fill, 2))
        p.drawLine(base_left.x() + 1, base_y, base_right.x() - 1, base_y)

        # text
        p.setPen(bubble_stroke)
        for i, line in enumerate(lines):
            p.drawText(bx + pad_x, by + pad_y + (i + 1) * line_h - 4, line)


def _hide_from_dock_macos():
    """Set macOS activation policy to Accessory so the app has no Dock icon
    and no menu bar (works like a menubar/agent app)."""
    try:
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory  # type: ignore
        NSApp().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    _hide_from_dock_macos()
    w = SlimeWidget()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
