"""Render a complete contribution snake run as a self-contained SVG animation."""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from xml.etree import ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
CELL, MARGIN, TOP = 16, 36, 76
ROWS, SWEEP_WIDTH = 7, 12
STEP_MS, DEATH_MS = 75, 2600
LEVELS = {name: i for i, name in enumerate((
    "NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE",
))}
Point = tuple[int, int]

PALETTES = {
    "light": {
        "paper": "#f6f9ff", "edge": "#d8e2ef", "ink": "#172d49", "muted": "#52657f",
        "dots": ("#e4ecf6", "#b8d3f0", "#7daee3", "#437cbd", "#22518c"),
        "head": "#08766a", "eyes": "#ffffff", "body": "#2a9b8a", "tail": "#70baaa",
        "hit": "#a32c45", "body-hit": "#c95b6d", "tail-hit": "#d58a99",
        "alert": "#fff4f6", "alert-edge": "#d498a5",
    },
    "dark": {
        "paper": "#101a2a", "edge": "#2a3a50", "ink": "#e6efff", "muted": "#9aaec9",
        "dots": ("#1d2b40", "#254774", "#3368a5", "#4e91d2", "#88bdef"),
        "head": "#91f5ce", "eyes": "#0e2f33", "body": "#54c8ab", "tail": "#299f93",
        "hit": "#ff9ba6", "body-hit": "#ce637c", "tail-hit": "#a75166",
        "alert": "#291b2b", "alert-edge": "#a45a72",
    },
}


@dataclass
class Run:
    frames: list[tuple[Point, ...]]
    bites: dict[Point, int]

    @property
    def impact_ms(self):
        return (len(self.frames) - 1) * STEP_MS

    @property
    def duration(self):
        return self.impact_ms + DEATH_MS


def sweep(left, right, active_columns):
    """Sweep blocks of the calendar, crossing empty blocks along the current edge."""
    row = 0
    for start in range(left, right + 1, SWEEP_WIDTH):
        stop = min(start + SWEEP_WIDTH - 1, right)
        columns = range(start, stop + 1)
        if not active_columns.intersection(columns):
            yield from ((x, row) for x in columns)
            continue

        direction = 1 if row == 0 else -1
        for offset in range(ROWS):
            scan_row = row + offset * direction
            scan_columns = reversed(columns) if offset % 2 else columns
            yield from ((x, scan_row) for x in scan_columns)
        row = scan_row

    # The last turn starts outside the calendar column being swept. It hooks
    # back through the occupied cells even when the snake is still four links long.
    inward = 1 if row == 0 else -1
    yield from ((right + 1, row), (right + 1, row + inward), (right, row + inward), (right, row))


def play(week_count, cells):
    remaining = {point for point, level in cells.items() if level}
    active_columns = {x for x, _ in remaining}
    left = max(0, min(active_columns) - 1) if active_columns else 0
    right = max(active_columns) if active_columns else min(3, week_count - 1)
    tail_direction = -1 if left >= 3 and left + 3 >= week_count else 1
    body = tuple((left + offset * tail_direction, -1) for offset in range(4))
    run = Run([body], {})
    for point in sweep(left, right, active_columns):
        if point in body:
            if remaining:
                raise ValueError("The route collided before reaching every contribution cell")
            run.frames.append((point, *body[:-1]))
            return run
        if point in remaining:
            remaining.remove(point)
            run.bites[point] = len(run.frames) * STEP_MS
            body = (point, *body)
        else:
            body = (point, *body[:-1])
        run.frames.append(body)
    raise ValueError("The closing turn must end in a self-collision")


def add(parent, tag, **attributes):
    return ET.SubElement(parent, f"{{{SVG}}}{tag}", {key: str(value) for key, value in attributes.items()})


def label(parent, text, x, y, size, fill, **attributes):
    element = add(parent, "text", x=x, y=y, fill=fill, **{"font-size": size, **attributes})
    element.text = text


def keyframes(name, frames, duration):
    rules = "".join(f"{time * 100 / duration:.5f}%{{{style}}}" for time, style in frames)
    return f"@keyframes {name}{{{rules}}}"


def animation(name, run, easing="linear"):
    return f"animation:{name} {run.duration}ms {easing} infinite"


def position(point):
    x, y = point
    return f"transform:translate({x * CELL}px,{y * CELL}px)"


def bend_points(points):
    """Collinear steps with the same velocity share one CSS interpolation."""
    yield 0, points[0]
    for index, (a, b, c) in enumerate(zip(points, points[1:], points[2:]), start=1):
        if (a[0] + c[0], a[1] + c[1]) != (2 * b[0], 2 * b[1]):
            yield index, b
    if len(points) > 1:
        yield len(points) - 1, points[-1]


def link_motion(index, run):
    points = [body[index] for body in run.frames if len(body) > index]
    first_time = (len(run.frames) - len(points)) * STEP_MS
    frames = [(first_time + step * STEP_MS, position(point)) for step, point in bend_points(points)]
    if first_time:
        hidden = f"opacity:0;{position(points[0])}"
        frames[0] = (first_time, f"opacity:1;{position(points[0])}")
        frames[:0] = [(0, hidden), (first_time - 1, hidden)]
    frames.append((run.duration, f"opacity:1;{position(points[-1])}"))
    return keyframes(f"link{index}", frames, run.duration)


def draw_snake(board, run, palette, styles):
    for index in reversed(range(len(run.frames[-1]))):
        name = f"link{index}"
        styles.append(link_motion(index, run))
        link = add(board, "g", style=animation(name, run))
        link.set("class", "animated")
        diameter = max(6.6, 14.4 - (index * 0.58))
        offset = (CELL - diameter) / 2
        shade = "head" if index == 0 else "body" if index < 4 else "tail"
        add(link, "rect", x=offset, y=offset, width=diameter, height=diameter, rx=diameter / 3.2,
            fill=palette[shade], style=animation(f"tint-{shade}", run, "step-end"))
        if index == 0:
            eyes = add(link, "g", style=animation("facing", run, "step-end"))
            direction = {(1, 0): 0, (0, 1): 90, (-1, 0): 180, (0, -1): 270}
            directions = [(0, "transform:rotate(90deg)")]
            for step, (previous, current) in enumerate(zip(run.frames, run.frames[1:])):
                dx, dy = current[0][0] - previous[0][0], current[0][1] - previous[0][1]
                angle = direction[dx, dy]
                rotation = f"transform:rotate({angle}deg)"
                if rotation != directions[-1][1]:
                    directions.append((step * STEP_MS, rotation))
            directions.append((run.duration, directions[-1][1]))
            styles.append(keyframes("facing", directions, run.duration))
            eyes.set("transform-origin", "8px 8px")
            face = add(eyes, "g", fill=palette["eyes"], style=animation("alive", run, "step-end"))
            for y in (5.05, 10.95):
                add(face, "circle", cx=10.35, cy=y, r=1.26)
            cross = add(eyes, "g", stroke=palette["paper"], fill="none", style=animation("dead", run, "step-end"))
            add(cross, "path", d="M9.1 3.8l2.5 2.5m0-2.5-2.5 2.5m0 3.4 2.5 2.5m0-2.5-2.5 2.5",
                **{"stroke-width": "1.2", "stroke-linecap": "round"})


def draw_result(card, run, width, palette, styles):
    impact = run.impact_ms
    tones = {"head": "hit", "body": "body-hit", "tail": "tail-hit"}
    for alive, dead in tones.items():
        styles.append(keyframes(f"tint-{alive}", [(0, f"fill:{palette[alive]}"),
                                                  (impact, f"fill:{palette[dead]}")], run.duration))
    for name, before, after in (("alive", 1, 0), ("dead", 0, 1), ("dim", 1, 0.42)):
        styles.append(keyframes(name, [(0, f"opacity:{before}"), (impact, f"opacity:{after}")], run.duration))
    styles.append(keyframes("result", [(0, "opacity:0"), (impact, "opacity:0"),
                                        (impact + 180, "opacity:1"), (run.duration, "opacity:1")], run.duration))
    styles.append(keyframes("shock", [(0, "opacity:0"), (impact - 1, "opacity:0"), (impact, "opacity:1"),
                                       (impact + 650, "opacity:.38"), (run.duration, "opacity:.38")], run.duration))

    hit_x, hit_y = run.frames[-1][0]
    x, y = MARGIN + hit_x * CELL + CELL / 2, TOP + hit_y * CELL + CELL / 2
    ring = add(card, "circle", cx=x, cy=y, r=12.2, stroke=palette["hit"], fill="none",
               style=animation("shock", run), **{"stroke-width": "2"})
    ring.set("class", "animated")
    panel_width = 262
    panel_x = MARGIN if x >= width / 2 else width - MARGIN - panel_width
    result = add(card, "g", style=animation("result", run))
    result.set("class", "animated")
    add(result, "rect", x=panel_x, y=92, width=panel_width, height=81, rx=11,
        fill=palette["alert"], stroke=palette["alert-edge"])
    label(result, "Game over", panel_x + 17, 121, 22, palette["hit"], **{"font-weight": "700"})
    reason = f"Hit its own tail · {len(run.bites)} collected"
    label(result, reason, panel_x + 17, 148, 13, palette["ink"])


def render(week_count, cells, run, palette):
    width = max(570, (week_count + 1) * CELL + 2 * MARGIN)
    card = ET.Element(f"{{{SVG}}}svg", {"viewBox": f"0 0 {width} 250", "width": str(width), "height": "250"})
    add(card, "title").text = "Contribution snake"
    add(card, "desc").text = "A snake sweeps the GitHub contribution calendar, grows with every active day it eats, and ends the run when it hits its own tail."
    css = add(card, "style")
    styles = ["text{font-family:system-ui,sans-serif}", "@media(prefers-reduced-motion:reduce){[style]{animation:none!important}.animated{display:none}}"]
    add(card, "rect", x=0.5, y=0.5, width=width - 1, height=249, rx=14, fill=palette["paper"], stroke=palette["edge"])
    label(card, "Contribution snake", MARGIN, 34, 18, palette["ink"], **{"font-weight": "650"})
    legend = add(card, "g", transform=f"translate({width - 185} 23)")
    dots = palette["dots"]
    label(legend, "Less", 0, 10, 12, palette["muted"])
    for index, color in enumerate(dots):
        add(legend, "rect", x=33 + index * 16, width=12, height=12, rx=3, fill=color)
    label(legend, "More", 115, 10, 12, palette["muted"])
    add(card, "path", d=f"M{MARGIN} 49H{width - MARGIN}", stroke=palette["edge"])

    board = add(card, "g", transform=f"translate({MARGIN} {TOP})")
    grid = add(board, "g", style=animation("dim", run, "step-end"))
    for (x, y), level in cells.items():
        px, py = x * CELL + 2, y * CELL + 2
        add(grid, "rect", x=px, y=py, width=12, height=12, rx=2, fill=dots[0])
        if level:
            bite = run.bites[x, y]
            name = f"bite{bite}"
            styles.append(keyframes(name, [(0, "opacity:1"), (bite, "opacity:1"),
                                            (bite + 110, "opacity:0"), (run.duration, "opacity:0")], run.duration))
            add(grid, "rect", x=px, y=py, width=12, height=12, rx=2, fill=dots[level], style=animation(name, run))
    draw_snake(board, run, palette, styles)
    draw_result(card, run, width, palette, styles)

    if run.bites:
        progress = add(card, "g")
        progress.set("class", "animated")
        label(progress, "Collected", MARGIN, 229, 12, palette["muted"])
        track = dict(x=104, y=222, width=width - MARGIN - 104, height=5, rx=2.5)
        add(progress, "rect", **track, fill=dots[0])
        frames = [(0, "transform:scaleX(0)")]
        for count, bite in enumerate(run.bites.values(), start=1):
            frames.append((bite, f"transform:scaleX({count / len(run.bites):.5f})"))
        styles.append(keyframes("collected", frames, run.duration))
        add(progress, "rect", **track, fill=palette["body"], style=(
            animation("collected", run, "step-end") + ";transform-origin:104px 0"
        ))
    css.text = "\n".join(styles)
    return ET.ElementTree(card)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calendar", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    weeks = json.loads(args.calendar.read_text())
    if not weeks:
        raise ValueError("GitHub returned no contribution calendar weeks")
    cells = {(x, day["weekday"]): LEVELS[day["contributionLevel"]]
             for x, week in enumerate(weeks) for day in week["contributionDays"]}
    run = play(len(weeks), cells)
    args.destination.mkdir(parents=True, exist_ok=True)
    for theme, palette in PALETTES.items():
        variant = "-dark" if theme == "dark" else ""
        target = args.destination / f"profile-snake{variant}.svg"
        render(len(weeks), cells, run, palette).write(target, encoding="utf-8")


if __name__ == "__main__":
    main()
