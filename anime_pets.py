"""Opus (Claude) и Astra (Codex) — две аниме-девочки, живущие поверх всех окон.

Спрайты берутся из assets/opus.webp, astra.webp, duo.webp (сетка 6x5) и sheet.webp. ЛКМ — перетащить, двойной клик — порадовать,
ПКМ — меню. Эмоции Opus управляются хуками Claude Code через %TEMP%/clawd_state.txt,
эмоции Astra — через %TEMP%/codex_state.txt (code, think, happy, sleep, surprise,
idle, walk, meet).
"""
import ctypes
import math
import os
import random
import tempfile
import time
import tkinter as tk

from PIL import Image, ImageTk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    pass

DPI = ctypes.windll.user32.GetDpiForSystem() / 96 if hasattr(ctypes.windll.user32, "GetDpiForSystem") else 1.0
ZOOM = 0.75 * DPI
KEY = "#ff00fe"
HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "assets", "sheet.webp")
TMP = tempfile.gettempdir()

# новые листы: сетка 6x5. Ряды: f — анфас, b — спиной, l — профиль влево, r — профиль вправо,
# c — с ноутбуком. Колонки 0..5.
GRIDS = {"o": "opus.webp", "a": "astra.webp", "d": "duo.webp"}
ROWS = "fblrc"

# со старого листа берём только то, чего нет в новых: сон, кофе, выглядывание и ночные дуэты
BOXES = {
    "o_sleep": (1388, 376, 1499, 502), "o_coffee": (750, 356, 886, 502),
    "a_sleep": (276, 372, 470, 498), "a_peek": (466, 376, 594, 498),
    "d_nap": (417, 686, 624, 827), "d_blanket": (866, 684, 1234, 827), "d_sleep": (1238, 680, 1499, 828),
}

# состояние -> (варианты последовательностей кадров, длительность в секундах).
# "s2" — кадр профиля, ряд l или r выбирается по направлению; "!x" — кадр со старого листа.
SOLO = {
    "idle": ([["f0", "f0", "f0", "f1"], ["f4", "f4", "f4", "f5"]], 5),
    "walk": ([["s2", "s3", "s4", "s5"]], 7),
    "code": ([["c0", "c1", "c0", "c1", "c2"]], 8),
    "think": ([["c3"]], 5),
    "happy": ([["c4"], ["f5", "f5", "f1"]], 3.5),
    "surprise": ([["f2", "f3"]], 2.5),
    "angry": ([["c5"]], 3),
    "look": ([["b0", "b0", "b1"]], 4),
    "run": ([["c1", "c0", "c1", "c2"]], 6),
    "search": ([["c3", "c2", "c3"]], 5),
    "web": ([["c0", "c3"]], 5),
}
STATES = {
    "o": dict(SOLO, sleep=([["!o_sleep"]], 9), coffee=([["!o_coffee"]], 5)),
    "a": dict(SOLO, sleep=([["!a_sleep"]], 9), peek=([["!a_peek"]], 4)),
}
DUO = {
    "walk": ([["s2", "s3", "s4", "s5"]], 5),
    "chat": ([["f0", "f0", "f1"], ["f4", "f4", "f5"]], 4),
    "code": ([["c0", "c1"]], 5),
    "think": ([["c3"]], 3),
    "happy": ([["c4"]], 3),
    "angry": ([["c5"]], 2.5),
    "look": ([["b0", "b1"]], 3),
    "run": ([["c1", "c0"]], 4),
    "search": ([["c3", "c2"]], 3),
}
DUO_NIGHT = ["!d_nap", "!d_blanket", "!d_sleep"]
# во что превращаются состояния хуков, если девочки сейчас вместе
DUO_ALIAS = {"surprise": "think", "web": "search", "idle": "chat", "coffee": "chat", "peek": "look"}


def clean(img):
    """Оставляет главную фигуру и мелкие значки (?, ♥, Z), убирает обрезки соседних кадров."""
    w, h = img.size
    alpha = img.getchannel("A").load()
    seen = [[False] * w for _ in range(h)]
    blobs = []
    for y in range(h):
        for x in range(w):
            if alpha[x, y] <= 40 or seen[y][x]:
                continue
            seen[y][x] = True
            stack, pts, edge = [(x, y)], [], False
            while stack:
                cx, cy = stack.pop()
                pts.append((cx, cy))
                edge |= cx in (0, w - 1) or cy in (0, h - 1)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and alpha[nx, ny] > 40:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            blobs.append((pts, edge))
    main = max(blobs, key=lambda b: len(b[0]))
    px = img.load()
    for pts, edge in blobs:
        if pts is main[0] or (len(pts) < 700 and not edge):
            continue
        for x, y in pts:
            px[x, y] = (0, 0, 0, 0)
    return img


# движение поверх кадров: состояние -> f(t) -> (dx, dy) в логических пикселях
MOTION = {
    "walk": lambda t: (0, -abs(math.sin(t * 9)) * 3),
    "goto": lambda t: (0, -abs(math.sin(t * 9)) * 3),
    "idle": lambda t: (0, -math.sin(t * 2) * 1.2),
    "code": lambda t: (0, -abs(math.sin(t * 5)) * 1.2),
    "run": lambda t: (0, -abs(math.sin(t * 7)) * 1.6),
    "think": lambda t: (math.sin(t * 1.6) * 4, 0),
    "search": lambda t: (math.sin(t * 2.4) * 6, 0),
    "web": lambda t: (math.sin(t * 2) * 4, 0),
    "happy": lambda t: (0, -abs(math.sin(t * 5)) * 10),
    "angry": lambda t: (math.sin(t * 30) * 2 * max(0.0, 1 - (t % 1.5) / 0.5), 0),
    "surprise": lambda t: (0, -26 * math.sin(math.pi * t / 0.45) if t < 0.45 else 0),
    "sleep": lambda t: (0, -math.sin(t * 1.2) * 1.5),
    "chat": lambda t: (0, -abs(math.sin(t * 3)) * 3),
}
# пузырь над головой: состояние -> (тексты по очереди, цвет)
BUBBLE = {
    "code": (["</>", "{ }", "</>", "; "], "#d9673c"),
    "run": ([">_", ">_▌"], "#2b8a3e"),
    "search": (["?", "??", "ʘ‿ʘ"], "#3b6fd4"),
    "web": (["www", "www."], "#3b6fd4"),
    "think": (["?", "…", "?"], "#7a5bc7"),
    "happy": (["♥", "♪", "♥", "★"], "#e0457b"),
    "angry": (["#@!", "!!!"], "#d43b3b"),
    "surprise": (["!", "!!"], "#e09a00"),
    "sleep": (["z", "zZ", "zZz"], "#4a7bd0"),
    "coffee": (["~", "~~"], "#8a5a32"),
    "chat": (["…", "♪"], "#7a5bc7"),
}


class Bubble:
    def __init__(self, root):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.label = tk.Label(self.win, bg="white", relief="solid", bd=max(1, round(DPI)),
                              font=("Segoe UI", -round(17 * DPI), "bold"), padx=round(5 * DPI), pady=0)
        self.label.pack()
        self.text = None
        self.win.withdraw()
        self.visible = False

    def show(self, state, t, x, y):
        if state not in BUBBLE:
            self.hide()
            return
        texts, color = BUBBLE[state]
        text = texts[int(t * 2) % len(texts)]
        if text != self.text:
            self.label.config(text=text, fg=color)
            self.text = text
        w, h = self.label.winfo_reqwidth(), self.label.winfo_reqheight()
        self.win.geometry(f"{w}x{h}+{int(x)}+{int(y - h - math.sin(t * 3) * 3 * DPI)}")
        if not self.visible:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.visible = True

    def hide(self):
        if self.visible:
            self.win.withdraw()
            self.visible = False


def finish(img, zoom):
    img = clean(img)
    img = img.crop(img.getchannel("A").point(lambda a: 255 if a > 110 else 0).getbbox())
    # ресайз в premultiplied-альфе: иначе прозрачный чёрный фон затекает в края тёмной каймой
    img = img.convert("RGBa").resize((round(img.width * zoom), round(img.height * zoom)), Image.LANCZOS)
    img = img.convert("RGBA")
    # прозрачность окна бинарная: полупрозрачные края либо отрезаем, либо делаем сплошными
    bg = Image.new("RGBA", img.size, KEY)
    alpha = img.getchannel("A").point(lambda a: 255 if a > 110 else 0)
    bg.paste(img.convert("RGB"), (0, 0), alpha)
    return bg.convert("RGB")


def load_frames():
    frames = {}
    old = Image.open(SHEET).convert("RGBA")
    for name, box in BOXES.items():
        frames["!" + name] = finish(old.crop(box), ZOOM)
    for who, file in GRIDS.items():
        sheet = Image.open(os.path.join(HERE, "assets", file)).convert("RGBA")
        cw, ch = sheet.width / 6, sheet.height / 5
        # листы разного разрешения: приводим фигуры к одному росту
        zoom = ZOOM * 1.1 * 1125 / sheet.width
        for r, row in enumerate(ROWS):
            for c in range(6):
                box = (round(c * cw), round(r * ch), round((c + 1) * cw), round((r + 1) * ch))
                frames[f"{who}_{row}{c}"] = finish(sheet.crop(box), zoom)
    return frames


def resolve(who, name, facing):
    if name.startswith("!"):
        return name
    if name[0] == "s":
        name = ("r" if facing > 0 else "l") + name[1:]
    return f"{who}_{name}"


class Pet:
    def __init__(self, app, who, state_file, x):
        self.app, self.who, self.state_file = app, who, state_file
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", KEY)
        self.win.config(bg=KEY)
        self.label = tk.Label(self.win, bg=KEY, bd=0, highlightthickness=0)
        # окно постоянного размера, кадр прижат к низу: без ресайза окна нет чёрных вспышек
        self.label.place(relx=0.5, rely=1.0, anchor="s")
        self.cx = x          # центр по X
        self.bottom = app.floor
        self.target_bottom = app.floor
        self.vx = 0.0
        self.facing = 1
        self.state = "idle"
        self.frames = STATES[who]["idle"][0][0]
        self.frame_i = 0
        self.state_left = 3.0
        self.drag = None
        self.mtime = 0.0
        self.hidden = False
        self.shown = None
        self.t = 0.0
        self.bubble = Bubble(app.root)

        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        self.label.bind("<Double-Button-1>", lambda e: self.set_state("happy"))
        self.label.bind("<Button-3>", lambda e: app.menu.tk_popup(e.x_root, e.y_root))

    def set_state(self, name):
        if name == "meet":
            self.app.start_meet()
            return
        if self.app.duo:
            self.app.duo_state(DUO_ALIAS.get(name, name))
            return
        if name not in STATES[self.who]:
            return
        self.state = name
        variants, dur = STATES[self.who][name]
        self.frames = random.choice(variants)
        self.frame_i = 0
        self.t = 0.0
        self.state_left = dur * random.uniform(0.7, 1.3)
        self.vx = random.choice([-1, 1]) * random.uniform(1.5, 2.5) * DPI if name == "walk" else 0.0
        if self.vx:
            self.facing = 1 if self.vx > 0 else -1

    def poll(self):
        try:
            mtime = os.path.getmtime(self.state_file)
            if mtime != self.mtime:
                self.mtime = mtime
                with open(self.state_file, encoding="utf-8") as f:
                    self.set_state(f.read().strip().lower())
        except OSError:
            pass

    def on_press(self, e):
        self.drag = (e.x_root - self.cx, e.y_root - self.bottom)
        if self.app.duo:
            self.app.end_meet()
        self.set_state("surprise")

    def on_drag(self, e):
        self.cx = e.x_root - self.drag[0]
        self.bottom = e.y_root - self.drag[1]

    def frame_name(self):
        return resolve(self.who, self.frames[self.frame_i % len(self.frames)], self.facing)

    def update(self, dt):
        self.t += dt
        self.state_left -= dt
        if self.state_left <= 0 and not self.drag and not self.app.duo and self.state != "goto":
            choices = ["walk", "idle", "code", "think", "happy", "sleep", "angry", "look"]
            weights = [5, 3, 4, 2, 2, 1, 1, 1]
            extra = "coffee" if self.who == "o" else "peek"
            self.set_state(random.choices(choices + [extra], weights + [1])[0])
        if self.state == "walk" and not self.drag:
            self.cx += self.vx
            half = self.app.half_w
            if not half <= self.cx <= self.app.sw - half:
                self.vx, self.facing = -self.vx, -self.facing
                self.cx = max(half, min(self.app.sw - half, self.cx))
        if not self.drag:
            self.bottom += (self.target_bottom - self.bottom) * 0.15

    def walk_to(self, x):
        self.t += 1 / 30
        self.state = "goto"
        self.frames = STATES[self.who]["walk"][0][0]
        dx = x - self.cx
        self.facing = 1 if dx > 0 else -1
        self.cx += max(-3 * DPI, min(3 * DPI, dx))
        return abs(dx) < 4

    def render(self, name, state=None, t=None):
        if self.hidden:
            return
        state = state or self.state
        t = self.t if t is None else t
        img = self.app.tk_frames[name]
        if self.shown is not img:
            self.label.config(image=img)
            self.shown = img
        w, h = img.width(), img.height()
        W, H = self.app.frame_box()
        dx, dy = MOTION.get(state, lambda _: (0, 0))(t) if not self.drag else (0, 0)
        x, y = round(self.cx - W / 2 + dx * DPI), round(self.bottom - H + dy * DPI)
        self.win.geometry(f"{W}x{H}+{x}+{y}")
        self.bubble.show(state, t, x + (W - w) / 2 + w * 0.62, y + H - h + h * 0.12)

    def hide(self, hidden):
        self.hidden = hidden
        if hidden:
            self.win.withdraw()
            self.bubble.hide()
        else:
            self.win.deiconify()
            self.win.attributes("-topmost", True)


class App:
    def frame_box(self):
        return self.box

    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.sw = self.root.winfo_screenwidth()
        self.floor = self.root.winfo_screenheight() - round(40 * DPI)
        self.half_w = 70 * ZOOM
        self.tk_frames = {k: ImageTk.PhotoImage(v) for k, v in load_frames().items()}
        self.box = (max(f.width() for f in self.tk_frames.values()),
                    max(f.height() for f in self.tk_frames.values()))
        self.tick = 0
        self.duo = None          # (кадр, секунд осталось)
        self.meeting = False
        self.next_meet = time.time() + random.uniform(20, 50)

        self.menu = tk.Menu(self.root, tearoff=0)
        for name, label in [("meet", "Встретиться"), ("code", "Кодить"), ("happy", "Радоваться"),
                            ("sleep", "Спать"), ("walk", "Гулять")]:
            self.menu.add_command(label=label, command=lambda n=name: [p.set_state(n) for p in self.pets])
        self.menu.add_separator()
        self.menu.add_command(label="Выход", command=self.root.destroy)

        self.opus = Pet(self, "o", os.path.join(TMP, "clawd_state.txt"), self.sw * 0.6)
        self.astra = Pet(self, "a", os.path.join(TMP, "codex_state.txt"), self.sw * 0.4)
        self.pets = [self.opus, self.astra]
        self.loop()
        self.root.mainloop()

    @staticmethod
    def night():
        hour = time.localtime().tm_hour
        return hour >= 23 or hour < 6

    def start_meet(self):
        if not self.duo:
            self.meeting = True

    def duo_state(self, name=None):
        """Переключает общую сценку; без имени выбирает случайную."""
        if self.night():
            self.duo.update(frames=[random.choice(DUO_NIGHT)], left=8, vx=0.0, state="sleep", t=0.0)
            return
        if name not in DUO:
            name = random.choices(list(DUO), [4, 3, 2, 1, 2, 1, 1])[0]
        variants, dur = DUO[name]
        vx = random.choice([-1, 1]) * 1.6 * DPI if name == "walk" else 0.0
        self.duo.update(frames=random.choice(variants), left=dur * random.uniform(0.8, 1.3), vx=vx, i=0,
                        state=name, t=0.0)
        if vx:
            self.duo["facing"] = 1 if vx > 0 else -1

    def end_meet(self):
        self.duo = None
        self.meeting = False
        # на общем листе Astra стоит слева
        self.astra.cx = self.opus.cx - 45 * ZOOM
        self.opus.cx += 45 * ZOOM
        self.astra.bottom = self.astra.target_bottom = self.opus.bottom
        self.astra.hide(False)
        self.opus.facing, self.astra.facing = 1, -1
        for p in self.pets:
            p.set_state(random.choice(["walk", "happy", "idle"]))
        self.next_meet = time.time() + random.uniform(40, 90)

    def update_meet(self, dt):
        if self.duo:
            d = self.duo
            d["total"] -= dt
            d["left"] -= dt
            d["t"] += dt
            if d["total"] <= 0:
                self.end_meet()
                return
            if d["left"] <= 0:
                self.duo_state()
            if d["vx"]:
                self.opus.cx += d["vx"]
                half = self.half_w * 1.6
                if not half <= self.opus.cx <= self.sw - half:
                    d["vx"], d["facing"] = -d["vx"], -d["facing"]
                    self.opus.cx = max(half, min(self.sw - half, self.opus.cx))
            if self.tick % 8 == 0:
                d["i"] += 1
            return
        if not self.meeting:
            if time.time() > self.next_meet and not any(p.drag for p in self.pets):
                self.meeting = True
            return
        mid = (self.opus.cx + self.astra.cx) / 2
        gap = 45 * ZOOM
        done_a = self.astra.walk_to(mid - gap)
        done_o = self.opus.walk_to(mid + gap)
        self.astra.target_bottom = self.opus.target_bottom = max(self.opus.target_bottom, self.astra.target_bottom)
        if done_a and done_o:
            self.opus.cx = mid
            self.duo = {"total": random.uniform(14, 24), "facing": 1, "state": "chat", "t": 0.0, "i": 0, "frames": [], "left": 0, "vx": 0.0}
            self.duo_state("chat")
            self.astra.hide(True)

    def loop(self):
        dt = 1 / 30
        self.tick += 1
        if self.tick % 10 == 0:
            for p in self.pets:
                p.poll()
        self.update_meet(dt)
        for p in self.pets:
            if p.state != "goto":
                p.update(dt)
            if self.tick % 8 == 0:
                p.frame_i += 1
        if self.duo:
            d = self.duo
            self.opus.render(resolve("d", d["frames"][d["i"] % len(d["frames"])], d["facing"]), d["state"], d["t"])
        else:
            for p in self.pets:
                p.render(p.frame_name())
        self.root.after(33, self.loop)


if __name__ == "__main__":
    App()
