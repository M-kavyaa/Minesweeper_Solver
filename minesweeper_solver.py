"""
Minesweeper Solver  (AI: constraint propagation + probabilistic guessing)

Layer 1  Basic rule      -> if a number's remaining mines == 0, all its unknown
                            neighbours are safe; if remaining == #unknown, all are mines.
Layer 2  Subset rule     -> if constraint A is a subset of constraint B, then the cells
                            in (B - A) hold exactly (mines_B - mines_A) mines.
Layer 3  Guess heuristic -> when logic is stuck, pick the cell with the lowest
                            estimated mine probability.

Run:  python minesweeper_solver.py
"""
import random


# ----------------------------------------------------------------- GAME ENGINE
class Minesweeper:
    def __init__(self, rows=9, cols=9, mines=10, seed=None):
        self.rows, self.cols, self.n_mines = rows, cols, mines
        self.rng = random.Random(seed)
        self.mines = set()
        self.revealed = {}          # (r, c) -> number of adjacent mines
        self.started = False
        self.lost = False

    def neighbors(self, r, c):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                if (dr or dc) and 0 <= nr < self.rows and 0 <= nc < self.cols:
                    yield (nr, nc)

    def _place_mines(self, first):
        # first click and its neighbours are always safe
        banned = {first, *self.neighbors(*first)}
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols)
                 if (r, c) not in banned]
        self.mines = set(self.rng.sample(cells, self.n_mines))

    def reveal(self, r, c):
        if not self.started:
            self._place_mines((r, c))
            self.started = True
        if (r, c) in self.mines:
            self.lost = True
            return
        stack = [(r, c)]
        while stack:                              # flood fill on zeros
            cell = stack.pop()
            if cell in self.revealed:
                continue
            n = sum(nb in self.mines for nb in self.neighbors(*cell))
            self.revealed[cell] = n
            if n == 0:
                stack.extend(self.neighbors(*cell))

    def won(self):
        return len(self.revealed) == self.rows * self.cols - self.n_mines

    def show(self, flagged=()):
        for r in range(self.rows):
            row = ""
            for c in range(self.cols):
                if (r, c) in self.revealed:
                    row += (str(self.revealed[(r, c)]) or ".") if self.revealed[(r, c)] else ". "
                    row = row if row.endswith(" ") else row + " "
                elif (r, c) in flagged:
                    row += "F "
                elif self.lost and (r, c) in self.mines:
                    row += "* "
                else:
                    row += "# "
            print(row)


# ---------------------------------------------------------------------- SOLVER
def build_constraints(game, flagged):
    """Each revealed number gives: (set of unknown neighbours, mines still hidden there)."""
    cons = set()
    for (r, c), n in game.revealed.items():
        if n == 0:
            continue
        nbs = list(game.neighbors(r, c))
        unknown = frozenset(x for x in nbs if x not in game.revealed and x not in flagged)
        remaining = n - sum(x in flagged for x in nbs)
        if unknown:
            cons.add((unknown, remaining))
    return cons


def deduce(cons):
    """Return (safe_cells, mine_cells, rule_name). Empty sets mean logic is stuck."""
    safe, mines = set(), set()
    for unknown, rem in cons:                     # Layer 1: basic rule
        if rem == 0:
            safe |= unknown
        elif rem == len(unknown):
            mines |= unknown
    if safe or mines:
        return safe, mines, "basic"

    for a, ra in cons:                            # Layer 2: subset rule
        for b, rb in cons:
            if a < b:
                diff, d = b - a, rb - ra
                if d == 0:
                    safe |= diff
                elif d == len(diff):
                    mines |= diff
    return safe, mines, "subset"


def best_guess(game, flagged, cons, rng):
    """Layer 3: pick the cell with the lowest estimated mine probability."""
    unknown = {(r, c) for r in range(game.rows) for c in range(game.cols)
               if (r, c) not in game.revealed and (r, c) not in flagged}
    prob = {}
    for cells, rem in cons:                       # frontier cells: worst-case local estimate
        p = rem / len(cells)
        for cell in cells:
            prob[cell] = max(prob.get(cell, 0), p)
    others = unknown - set(prob)                  # cells not touching any number
    density = (game.n_mines - len(flagged)) / len(unknown)

    best_cell = min(prob, key=prob.get) if prob else None
    if best_cell is None or (others and density < prob[best_cell]):
        return rng.choice(sorted(others)), density
    return best_cell, prob[best_cell]


def solve(game, rng=None, verbose=False):
    rng = rng or random.Random()
    flagged = set()
    stats = {"basic": 0, "subset": 0, "guess": 0}
    game.reveal(game.rows // 2, game.cols // 2)

    while not game.lost and not game.won():
        cons = build_constraints(game, flagged)
        safe, mines, rule = deduce(cons)
        if safe or mines:
            stats[rule] += 1
            flagged |= mines
            for r, c in safe:
                game.reveal(r, c)
            if verbose:
                print(f"[{rule}] safe={len(safe)} mines={len(mines)}")
        else:
            cell, p = best_guess(game, flagged, cons, rng)
            stats["guess"] += 1
            if verbose:
                print(f"[guess] {cell} with mine probability {p:.2f}")
            game.reveal(*cell)
    return game.won(), stats, flagged


# ------------------------------------------------------------------------ MAIN
if __name__ == "__main__":
    # one verbose demo game
    g = Minesweeper(9, 9, 10, seed=1)
    won, stats, flags = solve(g, random.Random(1), verbose=True)
    print("\nResult:", "WON" if won else "LOST", stats)
    g.show(flags)

    # experiment: win rate on different difficulties
    print("\n--- Experiment (500 games each) ---")
    for name, (r, c, m) in {"Beginner 9x9/10": (9, 9, 10),
                            "Intermediate 16x16/40": (16, 16, 40),
                            "Expert 16x30/99": (16, 30, 99)}.items():
        wins, guesses = 0, 0
        for s in range(500):
            game = Minesweeper(r, c, m, seed=s)
            ok, st, _ = solve(game, random.Random(s))
            wins += ok
            guesses += st["guess"]
        print(f"{name:24s} win rate {wins / 5:5.1f}%   avg guesses/game {guesses / 500:.1f}")
