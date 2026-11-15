"""Render the profile banner, GitHub activity, and growing contribution snake."""

import argparse
from datetime import date
import json
from math import floor, log10
import re
from pathlib import Path
from xml.etree import ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

# The pinned snk generator emits one movement step every 100 ms.
STEP_MS = 100
MAX_SNAKE_LENGTH = 16
COLLECTION_FRAME = re.compile(r"@keyframes c[0-9a-z]+\{([\d.]+)%\{fill:var\(--c[1-4]\)")

PALETTES = {
    "light": {
        "paper": "#f6f9ff", "edge": "#d8e2ef", "ink": "#172d49", "muted": "#52657f",
        "dots": ("#e4ecf6", "#b8d3f0", "#7daee3", "#437cbd", "#22518c"),
        "trace": "#5e89bb", "accent": "#146e65",
        "head": "#08766a", "eyes": "#ffffff", "body": "#2a9b8a", "tail": "#70baaa",
    },
    "dark": {
        "paper": "#101a2a", "edge": "#2a3a50", "ink": "#e6efff", "muted": "#9aaec9",
        "dots": ("#1d2b40", "#254774", "#3368a5", "#4e91d2", "#88bdef"),
        "trace": "#6482a8", "accent": "#70dabc",
        "head": "#91f5ce", "eyes": "#0e2f33", "body": "#54c8ab", "tail": "#299f93",
    },
}


def add(parent, tag, **attributes):
    return ET.SubElement(parent, f"{{{SVG}}}{tag}", {key: str(value) for key, value in attributes.items()})


def panel(width, height, title, description, palette):
    card = ET.Element(f"{{{SVG}}}svg", {"viewBox": f"0 0 {width} {height}", "width": str(width), "height": str(height)})
    add(card, "title").text = title
    add(card, "desc").text = description
    card.set("font-family", "system-ui, -apple-system, sans-serif")
    add(card, "rect", x=0.5, y=0.5, width=width - 1, height=height - 1, rx=14, fill=palette["paper"], stroke=palette["edge"])
    return card


def label(parent, text, x, y, fill, size, **attributes):
    element = add(parent, "text", x=x, y=y, fill=fill)
    element.attrib.update({"font-size": str(size), **attributes})
    element.text = text


def render_intro(palette):
    card = panel(920, 184, "Qichen Wang", "Computer Engineering at the National University of Singapore", palette)
    # The diagonal traces use the same grid as the end pads.
    circuit = add(card, "g", fill="none", stroke=palette["trace"], transform="translate(620 0)")
    for y in range(32, 156, 24):
        for x in range(0, 254, 24):
            add(circuit, "circle", cx=x, cy=y, r=1, opacity=0.4)
    routes = (
        ("M24 104H72L96 80H144L168 56H216", (24, 104), (216, 56)),
        ("M48 128H84L120 92H168L204 128H240", (48, 128), (240, 128)),
        ("M72 56H120L144 32H192", (72, 56), (192, 32)),
        ("M120 152H144L180 116", (120, 152), (180, 116)),
    )
    for index, (path, start, end) in enumerate(routes):
        line = add(circuit, "path", d=path, stroke=palette["accent"] if index == 1 else palette["trace"])
        line.set("stroke-width", "1.5")
        for x, y in (start, end):
            add(circuit, "circle", cx=x, cy=y, r=4, fill=palette["paper"], stroke=line.attrib["stroke"])
    label(card, "Qichen Wang", 36, 93, palette["ink"], 52, **{"font-weight": "650", "letter-spacing": "-1.65"})
    label(card, "Computer Engineering · National University of Singapore", 38, 129, palette["muted"], 17)
    return ET.ElementTree(card)


def streak_lengths(days):
    longest = run = 0
    for day in days:
        run = run + 1 if day["contributionCount"] else 0
        longest = max(longest, run)
    # An active streak through yesterday can continue until today ends.
    if not days[-1]["contributionCount"]:
        run = 0
        for day in reversed(days[:-1]):
            if not day["contributionCount"]:
                break
            run += 1
    return run, longest


def render_activity(collection, palette):
    calendar = collection["contributionCalendar"]
    weeks = [week["contributionDays"] for week in calendar["weeks"]]
    days = [day for week in weeks for day in week]
    current_streak, longest_streak = streak_lengths(days)
    total = calendar["totalContributions"]
    active_days = sum(day["contributionCount"] > 0 for day in days)
    card = panel(920, 306, "GitHub activity", (
        f"{total} contributions on {active_days} days. Current streak {current_streak} days. "
        f"Longest streak {longest_streak} days. The chart shows weekly contributions."
    ), palette)
    label(card, "Last 12 months", 36, 34, palette["muted"], 13, **{"font-weight": "600"})
    stats = (
        (f"{total:,}", "Contributions"), (str(active_days), "Active days"),
        (f"{current_streak}d", "Current streak"), (f"{longest_streak}d", "Longest streak"),
    )
    for index, (value, name) in enumerate(stats):
        x = 36 + index * 217
        label(card, value, x, 70, palette["ink"], 28, **{"font-weight": "650"})
        label(card, name, x, 89, palette["muted"], 13)
    add(card, "path", d="M36 104H884", stroke=palette["edge"])
    label(card, "Weekly contributions", 36, 130, palette["ink"], 15, **{"font-weight": "650"})
    label(card, "Last 16 weeks", 884, 130, palette["muted"], 12, **{"text-anchor": "end"})

    recent_weeks = weeks[-16:]
    counts = [sum(day["contributionCount"] for day in week) for week in recent_weeks]
    peak = max(1, *counts)
    half_peak = max(1, peak / 2)
    power = 10 ** floor(log10(half_peak))
    tick = next(step * power for step in (1, 2, 5, 10) if step * power >= half_peak)
    chart_top, chart_bottom, chart_left, chart_right = 151, 235, 74, 884
    chart_height = chart_bottom - chart_top
    for value in (0, tick, 2 * tick):
        y = chart_bottom - chart_height * value / (2 * tick)
        add(card, "path", d=f"M{chart_left} {y:g}H{chart_right}", stroke=palette["edge"])
        label(card, str(value), chart_left - 10, y + 4, palette["muted"], 11, **{"text-anchor": "end"})
    step = (chart_right - chart_left) / len(counts)
    for index, (week, count) in enumerate(zip(recent_weeks, counts)):
        x = chart_left + step * (index + 0.5)
        height = chart_height * count / (2 * tick)
        if count:
            bar_width = min(29, step * 0.63)
            bar = add(card, "rect", x=x - bar_width / 2, y=chart_bottom - height, width=bar_width, height=height,
                      rx=min(3, height / 2), fill=palette["accent"] if index == len(counts) - 1 else palette["dots"][3])
            add(bar, "title").text = f"Week of {week[0]['date']}: {count} contributions"
        if index % 5 == 0 or index == len(counts) - 1:
            first_day = date.fromisoformat(week[0]["date"])
            label(card, f"{first_day:%b} {first_day.day}", x, 253, palette["muted"], 11, **{"text-anchor": "middle"})
    add(card, "path", d="M36 266H884", stroke=palette["edge"])
    details = (
        ("totalCommitContributions", "commits"), ("totalPullRequestContributions", "pull requests"),
        ("totalIssueContributions", "issues"), ("totalPullRequestReviewContributions", "reviews"),
    )
    label(card, "  ·  ".join(f"{collection[key]:,} {name}" for key, name in details), 36, 287, palette["muted"], 13)
    return ET.ElementTree(card)


def extend_tail(animation, segments, style):
    duration = int(re.search(r"\.s\{[^{}]*?(\d+)ms", style.text)[1])
    meals = sorted(float(frame) for frame in COLLECTION_FRAME.findall(style.text))
    growth = meals[:MAX_SNAKE_LENGTH - len(segments)]
    # Extra links follow the old tail with a one-step delay per link.
    # A separate animation reveals each link at the matching collection frame.
    rules = [".s.follow {animation-name:s3}"]
    for level, time in reversed(list(enumerate(growth, start=1))):
        delay = level * STEP_MS
        appear_at = max(time + 0.02, delay * 100 / duration)
        size = max(6.5, 9.9 - 0.32 * level)
        offset = (16 - size) / 2
        name = f"grow{level}"
        container = add(animation, "g")
        container.set("class", "tail-growth")
        container.set("style", f"animation:{name} {duration}ms step-end infinite")
        segment = add(container, "rect", x=offset, y=offset, width=size, height=size, rx=size / 3)
        segment.set("class", "s follow")
        segment.set("style", f"animation-delay:{delay}ms;fill:var(--tail)")
        rules.append(f"@keyframes {name} {{0%{{visibility:hidden}} {appear_at:.4f}%,100%{{visibility:visible}}}}")
    style.text += "\n" + "\n".join(rules)


def render_snake(source, palette):
    grid = ET.parse(source).getroot()
    _, _, grid_width, _ = map(int, grid.attrib["viewBox"].split())
    width = grid_width + 40
    card = panel(width, 250, "Contribution snake",
                 "A snake grows as it collects days of GitHub activity on a contribution calendar.", palette)

    cells, segments, collected = [], [], []
    for rect in grid.findall(f"{{{SVG}}}rect"):
        category = rect.attrib.get("class", "").split(" ")[0]
        if category == "c":
            cells.append(rect)
        elif category == "s":
            segments.append(rect)
        elif category == "u":
            collected.append(rect)
    if not cells or not segments or segments[0].attrib["class"] != "s s0":
        raise ValueError("Unexpected calendar or snake structure in the source SVG")

    dots = palette["dots"]
    style = grid.find(f"{{{SVG}}}style")
    card.append(style)
    dot_colors = ";".join(f"--c{i}:{color}" for i, color in enumerate(dots))
    style.text += f"""
        :root {{ --ce:{dots[0]}; --cb:transparent; --cs:{palette['body']}; --tail:{palette['tail']}; {dot_colors}; }}
        text {{ font-family: system-ui, sans-serif; }}
        .s.s0 {{ fill:{palette['head']}; }}
        .s.s2, .s.s3 {{ fill:{palette['tail']}; }}
        @media (prefers-reduced-motion: reduce) {{
            .c, .s, .u, .tail-growth {{ animation: none !important; }}
            .s, .progress {{ display: none; }}
        }}
    """

    heading = add(card, "text", x=36, y=34, fill=palette["ink"])
    heading.attrib.update({"font-size": "18", "font-weight": "650"})
    heading.text = "Contribution snake"

    legend = add(card, "g", transform=f"translate({width - 185} 23)", fill=palette["muted"])
    legend.set("font-size", "12")
    add(legend, "text", y=10).text = "Less"
    for i, color in enumerate(dots):
        add(legend, "rect", x=33 + i * 16, width=12, height=12, rx=3, fill=color)
    add(legend, "text", x=115, y=10).text = "More"
    add(card, "path", d=f"M36 49H{width - 36}", stroke=palette["edge"])

    animation = add(card, "g", transform="translate(36 76)")
    animation.extend(cells)
    extend_tail(animation, segments, style)
    animation.extend(reversed(segments[1:]))
    # The head and both eyes share the first segment's existing keyframes.
    head = add(animation, "g")
    head.set("class", segments[0].attrib.pop("class"))
    head.append(segments[0])
    for x in (5.5, 10.5):
        add(head, "circle", cx=x, cy=6.5, r=1.25, fill=palette["eyes"])

    if collected:
        track_x, track_y, track_height = 104, 222, 5
        track_width = width - 36 - track_x
        progress = add(card, "g")
        progress.set("class", "progress")
        label(progress, "Collected", 36, 229, palette["muted"], 12)
        track = dict(x=track_x, y=track_y, width=track_width, height=track_height, rx=2.5)
        add(progress, "rect", **track, fill=dots[0])
        clip = add(add(progress, "defs"), "clipPath", id="progress-track")
        add(clip, "rect", **track)
        meter = add(progress, "g")
        meter.set("clip-path", "url(#progress-track)")
        last = collected[-1]
        bar_width = float(last.attrib["x"]) + float(last.attrib["width"])
        bar_height = float(last.attrib["height"])
        bars = add(meter, "g", transform=(
            f"translate({track_x} {track_y}) scale({track_width / bar_width} {track_height / bar_height}) "
            f"translate(0 {-float(last.attrib['y'])})"
        ))
        bars.extend(collected)

    return ET.ElementTree(card)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snake", type=Path)
    parser.add_argument("activity", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    collection = json.loads(args.activity.read_text())
    for theme, palette in PALETTES.items():
        suffix = "-dark" if theme == "dark" else ""
        graphics = {
            "profile-intro": render_intro(palette),
            "profile-activity": render_activity(collection, palette),
            "profile-snake": render_snake(args.snake, palette),
        }
        for name, graphic in graphics.items():
            graphic.write(args.destination / f"{name}{suffix}.svg", encoding="utf-8")


if __name__ == "__main__":
    main()
