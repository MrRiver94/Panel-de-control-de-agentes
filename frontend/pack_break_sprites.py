"""Pack four generated interaction poses into 58x72 UI sprite cells."""

import argparse
from pathlib import Path

from PIL import Image


def pack(source: Path, destination: Path) -> None:
    image = Image.open(source).convert("RGBA")
    if image.width % 4:
        raise ValueError("Expected four equal-width poses")
    source_width = image.width // 4
    sheet = Image.new("RGBA", (58 * 4, 72), (0, 0, 0, 0))
    for index in range(4):
        slot = image.crop((index * source_width, 0, (index + 1) * source_width, image.height))
        bounds = slot.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"Pose {index} is empty")
        pose = slot.crop(bounds)
        scale = min(54 / pose.width, 66 / pose.height)
        size = (round(pose.width * scale), round(pose.height * scale))
        pose = pose.resize(size, Image.Resampling.NEAREST)
        sheet.alpha_composite(pose, (index * 58 + (58 - size[0]) // 2, 70 - size[1]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    pack(args.source, args.destination)
