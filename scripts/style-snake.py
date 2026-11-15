"""Style Platane/snk's generated calendar without changing its animation path."""

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)

PALETTES = {
    "light": {
        "paper": "#f6f9ff", "edge": "#d8e2ef", "ink": "#172d49", "muted": "#52657f",
        "dots": ("#e4ecf6", "#b8d3f0", "#7daee3", "#437cbd", "#22518c"),
        "head": "#08766a", "eyes": "#ffffff", "body": "#2a9b8a", "tail": "#70baaa",
    },
    "dark": {
        "paper": "#101a2a", "edge": "#2a3a50", "ink": "#e6efff", "muted": "#9aaec9",
        "dots": ("#1d2b40", "#254774", "#3368a5", "#4e91d2", "#88bdef"),
        "head": "#91f5ce", "eyes": "#0e2f33", "body": "#54c8ab", "tail": "#299f93",
    },
}


def add(parent, tag, **attributes):
    return ET.SubElement(parent, f"{{{SVG}}}{tag}", {key: str(value) for key, value in attributes.items()})


def render(source, palette):
    grid = ET.parse(source).getroot()
    _, _, grid_width, _ = map(int, grid.attrib["viewBox"].split())
    width = grid_width + 40
    card = ET.Element(f"{{{SVG}}}svg", {"viewBox": f"0 0 {width} 250", "width": str(width), "height": "250"})
    add(card, "title").text = "Contribution snake"
    add(card, "desc").text = "A snake collects days of GitHub activity on a calendar shaded by contribution level."

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
        :root {{ --ce:{dots[0]}; --cb:transparent; --cs:{palette['body']}; {dot_colors}; }}
        text {{ font-family: system-ui, sans-serif; }}
        .s.s0 {{ fill:{palette['head']}; }}
        .s.s2, .s.s3 {{ fill:{palette['tail']}; }}
        @media (prefers-reduced-motion: reduce) {{
            .c, .s, .u {{ animation: none !important; }}
            .s, .progress {{ display: none; }}
        }}
    """

    add(card, "rect", x=0.5, y=0.5, width=width - 1, height=249, rx=14, fill=palette["paper"], stroke=palette["edge"])
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
        label = add(progress, "text", x=36, y=229, fill=palette["muted"])
        label.set("font-size", "12")
        label.text = "Collected"
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
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    for theme, palette in PALETTES.items():
        filename = "contribution-snake-dark.svg" if theme == "dark" else "contribution-snake.svg"
        render(args.source, palette).write(args.destination / filename, encoding="utf-8")


if __name__ == "__main__":
    main()
