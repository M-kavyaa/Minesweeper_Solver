import random
import time
import tkinter as tk
from tkinter import ttk

from minesweeper_solver import Minesweeper, build_constraints, deduce, best_guess

LEVELS = {"Beginner  9x9 / 10 mines": (9, 9, 10),
          "Intermediate  16x16 / 40 mines": (16, 16, 40),
          "Expert  16x30 / 99 mines": (16, 30, 99)}

BG, PANEL, HID, REV = "#11151b", "#1a2029", "#2c3747", "#0d1015"
TXT, MUTED, ACC = "#e6edf3", "#8b98a9", "#3b82f6"
NUM = {1: "#4aa3ff", 2: "#4cd18a", 3: "#ff6b6b", 4: "#b388ff",
       5: "#ffa94d", 6: "#2fd4d4", 7: "#e0e0e0", 8: "#9aa5b1"}
HINT = {"safe": ("#1d4a35", "#2ecc71"), "mine": ("#5a2530", "#ff5c5c"),
        "guess": ("#58481a", "#f5c542"), "info": ("#16365e", "#4aa3ff")}
F, FB = ("Segoe UI", 10), ("Segoe UI", 10, "bold")
INTRO = ("Welcome! Play yourself, or let the AI solve it.\n\n"
         "Try: Analyze ON, then click any cell to see WHY the solver thinks "
         "what it thinks. Heatmap shows every cell's mine risk (green = safe, red = dangerous).")
EXPL = {"basic": "BASIC RULE: a clue already has all its mines flagged (so its other neighbours are safe), "
                 "or it needs every unknown neighbour as a mine. These cells are certain.",
        "subset": "SUBSET RULE: one clue's unknown cells sit inside another clue's. The leftover cells "
                  "must hold exactly the difference of the two mine counts. Certain again."}


def heat(p):
    st = [(38, 160, 100), (235, 175, 55), (225, 65, 75)]
    i = 0 if p < .5 else 1
    t = p * 2 - i
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(st[i], st[i + 1]))


class App:
    def __init__(self, root):
        self.root = root
        root.title("Minesweeper AI Solver")
        root.configure(bg=BG)
        root.resizable(False, False)
        self.rng = random.Random()
        self.level = tk.StringVar(value=list(LEVELS)[0])
        self.speed = tk.IntVar(value=70)
        self.sv = {k: tk.StringVar(value="0") for k in ("basic", "subset", "guess")}
        self.mines_v, self.time_v = tk.StringVar(), tk.StringVar(value="0s")
        self.status_v = tk.StringVar()
        self.auto, self.analyze_on, self.heat_on, self.last = False, False, False, None
        self._build_ui()
        self.new_game()
        self._tick()

    # ------------------------------------------------------------------ UI
    def _btn(self, parent, text, cmd, bg=ACC):
        b = tk.Label(parent, text=text, bg=bg, fg="white", font=FB,
                     padx=12, pady=7, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def _build_ui(self):
        left = tk.Frame(self.root, bg=BG)
        left.pack(side="left", padx=16, pady=16)
        bar = tk.Frame(left, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        for var, lab in ((self.mines_v, "MINES"), (self.time_v, "TIME")):
            box = tk.Frame(bar, bg=PANEL, padx=14, pady=6)
            box.pack(side="left", padx=(0, 8))
            tk.Label(box, text=lab, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(box, textvariable=var, bg=PANEL, fg=TXT, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(bar, textvariable=self.status_v, bg=BG, fg=TXT,
                 font=("Segoe UI", 12, "bold")).pack(side="right")
        self.cv = tk.Canvas(left, bg=BG, highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", self.on_left)
        for b in ("<Button-2>", "<Button-3>"):
            self.cv.bind(b, self.on_right)

        right = tk.Frame(self.root, bg=PANEL, padx=16, pady=16, width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Game", bg=PANEL, fg=MUTED, font=FB).pack(anchor="w")
        cb = ttk.Combobox(right, textvariable=self.level, values=list(LEVELS),
                          state="readonly", width=32)
        cb.pack(fill="x", pady=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda e: self.new_game())
        self._btn(right, "New Game", self.new_game, "#2f3b4d").pack(fill="x")

        tk.Label(right, text="AI Solver", bg=PANEL, fg=MUTED, font=FB).pack(anchor="w", pady=(16, 4))
        row = tk.Frame(right, bg=PANEL)
        row.pack(fill="x")
        self._btn(row, "Hint", self.show_hint, "#2f3b4d").pack(side="left", expand=True, fill="x", padx=(0, 4))
        self._btn(row, "Step", self.ai_step).pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.auto_btn = self._btn(right, "Auto-play", self.toggle_auto, "#1f9d63")
        self.auto_btn.pack(fill="x", pady=(8, 0))
        row2 = tk.Frame(right, bg=PANEL)
        row2.pack(fill="x", pady=(8, 0))
        self.an_btn = self._btn(row2, "Analyze: OFF", self.toggle_analyze, "#2f3b4d")
        self.an_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.heat_btn = self._btn(row2, "Heatmap: OFF", self.toggle_heat, "#2f3b4d")
        self.heat_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))
        tk.Label(right, text="Speed (slow to fast)", bg=PANEL, fg=MUTED, font=F).pack(anchor="w", pady=(10, 0))
        tk.Scale(right, from_=1, to=100, orient="horizontal", variable=self.speed, bg=PANEL,
                 fg=TXT, troughcolor=BG, highlightthickness=0, showvalue=False).pack(fill="x")

        tk.Label(right, text="Rules fired", bg=PANEL, fg=MUTED, font=FB).pack(anchor="w", pady=(10, 4))
        for key, name in (("basic", "Basic rule"), ("subset", "Subset rule"), ("guess", "Probability guess")):
            r = tk.Frame(right, bg=PANEL)
            r.pack(fill="x")
            tk.Label(r, text=name, bg=PANEL, fg=TXT, font=F).pack(side="left")
            tk.Label(r, textvariable=self.sv[key], bg=PANEL, fg=TXT, font=FB).pack(side="right")

        tk.Label(right, text="Explanation", bg=PANEL, fg=MUTED, font=FB).pack(anchor="w", pady=(14, 4))
        self.explain_box = tk.Text(right, height=12, bg=REV, fg=TXT, font=F, relief="flat",
                                   state="disabled", wrap="word", padx=8, pady=8)
        self.explain_box.pack(fill="both", expand=True)
        self.logbox = tk.Text(left, height=6, bg=PANEL, fg=MUTED, font=("Consolas", 9),
                              relief="flat", state="disabled", wrap="word")
        self.logbox.pack(fill="x", pady=(10, 0))
        tk.Label(right, text="Left-click: reveal   Right-click: flag\nGreen = safe   Red = mine\nYellow = guess   Blue = clue",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8), justify="left").pack(anchor="w", pady=(8, 0))

    def log(self, msg):
        self.logbox.config(state="normal")
        self.logbox.insert("end", msg + "\n")
        self.logbox.see("end")
        self.logbox.config(state="disabled")

    # ---------------------------------------------------------------- state
    def new_game(self):
        self.auto = False
        self.auto_btn.config(text="Auto-play", bg="#1f9d63")
        r, c, m = LEVELS[self.level.get()]
        self.g = Minesweeper(r, c, m)
        self.flags, self.ai_flags, self.hint = set(), set(), {}
        self.stats = {"basic": 0, "subset": 0, "guess": 0}
        self.t0, self.over, self.last = None, False, None
        self.cs = min(40, 770 // c, 640 // r)
        self.cv.config(width=c * self.cs, height=r * self.cs)
        self.logbox.config(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.config(state="disabled")
        self.status_v.set("Ready")
        self.say(INTRO)
        self.refresh()

    def refresh(self):
        for k, v in self.stats.items():
            self.sv[k].set(str(v))
        self.mines_v.set(str(self.g.n_mines - len(self.flags | self.ai_flags)))
        self.draw()

    def _tick(self):
        if self.t0 and not self.over:
            self.time_v.set(f"{int(time.time() - self.t0)}s")
        self.root.after(500, self._tick)

    def end_check(self):
        if self.g.lost:
            self.over, self.auto = True, False
            self.status_v.set("Hit a mine")
            self.log("Game over: a mine was revealed.")
        elif self.g.won():
            self.over, self.auto = True, False
            self.status_v.set("Solved!")
            self.log("All safe cells revealed. Solved!")
        if self.over:
            self.auto_btn.config(text="Auto-play", bg="#1f9d63")

    def after_move(self):
        self.hint = {}
        if self.t0 is None:
            self.t0 = time.time()
        if not self.over:
            self.status_v.set("Playing")
        self.end_check()
        self.refresh()

    # ---------------------------------------------------------- human input
    def cell_at(self, e):
        r, c = e.y // self.cs, e.x // self.cs
        return (r, c) if 0 <= r < self.g.rows and 0 <= c < self.g.cols else None

    def on_left(self, e):
        cell = self.cell_at(e)
        if cell and self.analyze_on:
            return self.analyze(cell)
        if not cell or self.over or cell in self.flags or cell in self.g.revealed:
            return
        self.last = cell
        self.g.reveal(*cell)
        self.after_move()

    def on_right(self, e):
        cell = self.cell_at(e)
        if not cell or self.over or cell in self.g.revealed:
            return
        self.flags ^= {cell}
        self.refresh()

    # -------------------------------------------------------------- AI part
    def show_hint(self):
        if self.over:
            return
        g = self.g
        if not g.started:
            self.hint = {(g.rows // 2, g.cols // 2): "guess"}
            self.log("Hint: first click is always safe. Start at the centre.")
            return self.refresh()
        cons = build_constraints(g, self.ai_flags)
        safe, mines, rule = deduce(cons)
        if safe or mines:
            self.hint = {**{c: "safe" for c in safe}, **{c: "mine" for c in mines}}
            self.log(f"Hint ({rule} rule): {len(safe)} safe, {len(mines)} mines")
        else:
            cell, p = best_guess(g, self.ai_flags, cons, self.rng)
            self.hint = {cell: "guess"}
            self.log(f"Hint: no certain move. Best guess {cell}, P(mine) = {p:.0%}")
        self.refresh()

    def ai_step(self):
        if self.over:
            return
        g = self.g
        if not g.started:
            g.reveal(g.rows // 2, g.cols // 2)
            self.log("First move: centre cell (safe by design)")
            return self.after_move()
        cons = build_constraints(g, self.ai_flags)
        safe, mines, rule = deduce(cons)
        if safe or mines:
            self.stats[rule] += 1
            self.ai_flags |= mines
            for r, c in safe:
                g.reveal(r, c)
            self.log(f"{rule.upper()} rule: {len(safe)} safe, {len(mines)} mines")
            self.say(EXPL[rule])
        else:
            cell, p = best_guess(g, self.ai_flags, cons, self.rng)
            self.stats["guess"] += 1
            self.log(f"GUESS {cell}, P(mine) = {p:.0%}")
            self.say(f"NO CERTAIN MOVE. Logic is stuck, so the solver gambles smartly: it picks the "
                     f"lowest-risk cell, {cell}, with about {p:.0%} chance of a mine.")
            self.last = cell
            g.reveal(*cell)
        self.after_move()

    def toggle_auto(self):
        if self.over:
            return
        self.auto = not self.auto
        self.auto_btn.config(text="Pause" if self.auto else "Auto-play",
                             bg="#c2410c" if self.auto else "#1f9d63")
        if self.auto:
            self._auto_loop()

    def _auto_loop(self):
        if self.auto and not self.over:
            self.ai_step()
            self.root.after(max(5, 600 - self.speed.get() * 6), self._auto_loop)

    # ------------------------------------------------------ explain / analyze
    def say(self, text):
        b = self.explain_box
        b.config(state="normal")
        b.delete("1.0", "end")
        b.insert("end", text)
        b.config(state="disabled")

    def toggle_analyze(self):
        self.analyze_on = not self.analyze_on
        self.an_btn.config(text="Analyze: " + ("ON" if self.analyze_on else "OFF"),
                           bg=ACC if self.analyze_on else "#2f3b4d")
        self.hint = {}
        self.say("Analyze is ON. Click any cell to see the reasoning." if self.analyze_on else "")
        self.refresh()

    def toggle_heat(self):
        self.heat_on = not self.heat_on
        self.heat_btn.config(text="Heatmap: " + ("ON" if self.heat_on else "OFF"),
                             bg=ACC if self.heat_on else "#2f3b4d")
        self.refresh()

    def prob_map(self, cons):
        g, prob = self.g, {}
        for u, rem in cons:
            for x in u:
                prob[x] = max(prob.get(x, 0), rem / len(u))
        unknown = g.rows * g.cols - len(g.revealed) - len(self.ai_flags)
        return prob, (g.n_mines - len(self.ai_flags)) / max(1, unknown)

    def analyze(self, cell):
        g, (r, c) = self.g, cell
        cons = build_constraints(g, self.ai_flags)
        if cell in g.revealed:
            n = g.revealed[cell]
            nbs = list(g.neighbors(r, c))
            fl = sum(x in self.ai_flags for x in nbs)
            unk = [x for x in nbs if x not in g.revealed and x not in self.ai_flags]
            rem = n - fl
            if n == 0:
                text = "A zero: none of its neighbours is a mine, so the game opened them all."
            else:
                text = (f"CLUE {n}: {n} mines touch this cell. {fl} already flagged, so {rem} "
                        f"remain among {len(unk)} unknown neighbours (yellow).\n\n")
                if not unk:
                    text += "Nothing left to decide here."
                elif rem == 0:
                    text += "Remaining = 0, so ALL unknown neighbours are SAFE."
                elif rem == len(unk):
                    text += "Remaining = number of unknowns, so ALL are MINES."
                else:
                    text += f"Not certain: each is a mine with probability {rem}/{len(unk)} = {rem / len(unk):.0%}."
            self.hint = {cell: "info", **{x: "guess" for x in unk}}
        elif cell in self.ai_flags:
            text, self.hint = "The solver PROVED this cell is a mine and flagged it.", {cell: "mine"}
        else:
            probs, dens = self.prob_map(cons)
            inv = [(u, rem) for u, rem in cons if cell in u]
            safe, mines, _ = deduce(cons)
            if inv:
                text = f"Cell {cell} is touched by {len(inv)} clue(s) (blue):\n"
                for u, rem in inv:
                    text += f"  - needs {rem} mine(s) in {len(u)} cells = {rem}/{len(u)} = {rem / len(u):.0%}\n"
                text += f"\nSolver keeps the worst case: {probs[cell]:.0%} mine risk."
            else:
                left = g.n_mines - len(self.ai_flags)
                text = (f"No clue touches {cell}, so nothing is known locally. Fallback = global density: "
                        f"{left} mines left / {g.rows * g.cols - len(g.revealed) - len(self.ai_flags)} "
                        f"unknown cells = {dens:.0%}.")
            if cell in safe:
                text += "\n\nLogic PROVES this cell is SAFE."
            elif cell in mines:
                text += "\n\nLogic PROVES this cell is a MINE."
            self.hint = {cell: "guess", **{x: "info" for x in g.neighbors(r, c)
                                           if x in g.revealed and g.revealed[x] > 0}}
        self.say(text)
        self.refresh()

    # ------------------------------------------------------------- drawing
    def draw(self):
        cv, g, cs = self.cv, self.g, self.cs
        cv.delete("all")
        allflags = self.flags | self.ai_flags
        probs, dens = (self.prob_map(build_constraints(g, self.ai_flags))
                       if self.heat_on and g.started and not self.over else (None, 0))
        for r in range(g.rows):
            for c in range(g.cols):
                x0, y0 = c * cs, r * cs
                x1, y1 = x0 + cs - 2, y0 + cs - 2
                cell = (r, c)
                revealed = cell in g.revealed
                fill = REV if revealed else (heat(probs.get(cell, dens))
                                             if probs is not None and cell not in allflags else HID)
                outline, width = fill, 1
                if g.lost and cell in g.mines:
                    fill = "#5a2530"
                if cell in self.hint:
                    fill, outline = HINT[self.hint[cell]]
                    width = 3
                cv.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=width)
                if not revealed and cell not in self.hint:       # 3D bevel
                    cv.create_line(x0, y0, x1, y0, x0, y0, x0, y1, fill="#5b6d86")
                    cv.create_line(x0, y1, x1, y1, x1, y0, fill="#141a22")
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                if revealed and g.revealed[cell]:
                    n = g.revealed[cell]
                    cv.create_text(mx, my, text=str(n), fill=NUM[n],
                                   font=("Segoe UI", int(cs * 0.45), "bold"))
                elif not revealed and g.lost and cell in g.mines:
                    cv.create_oval(mx - cs * .2, my - cs * .2, mx + cs * .2, my + cs * .2,
                                   fill="#ff5c5c", outline="")
                elif not revealed and cell in allflags:
                    u = cs * .25
                    cv.create_line(mx - u * .4, my - u * 1.4, mx - u * .4, my + u * 1.4,
                                   fill="#cfd8e3", width=2)
                    cv.create_polygon(mx - u * .4, my - u * 1.4, mx + u * 1.3, my - u * .5,
                                      mx - u * .4, my + u * .3, fill="#ff5c5c", outline="")
        if g.lost and self.last:                                  # explosion
            r, c = self.last
            mx, my = (c + .5) * cs, (r + .5) * cs
            for k, col in ((.9, "#7a1d2b"), (.6, "#ff5c5c"), (.3, "#ffd166")):
                cv.create_oval(mx - cs * k, my - cs * k, mx + cs * k, my + cs * k, fill=col, outline="")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
