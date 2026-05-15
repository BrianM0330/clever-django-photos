from collections.abc import Iterable
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import pandas as pd
from PIL import Image, ImageFilter


@contextmanager
def open_image(image_source):
    if hasattr(image_source, "read"):
        image = Image.open(image_source)
        try:
            yield image
        finally:
            image.close()
        return

    source = str(image_source)
    parsed = urlparse(source)

    if parsed.scheme in {"http", "https"}:
        with urlopen(source, timeout=30) as response:  # noqa: S310
            data = response.read()
        with Image.open(BytesIO(data)) as image:
            yield image
        return

    with Image.open(Path(source)) as image:
        yield image


def compute_jaccard_affinities(like_rows: Iterable[dict], *, min_overlap: int = 3, threshold: float = 0.4):
    df = pd.DataFrame(list(like_rows))
    if df.empty:
        return []

    df = df.drop_duplicates(subset=["user_id", "photo_id"])
    user_likes = df.groupby("user_id")["photo_id"].apply(set).to_dict()
    users = sorted(user_likes)

    results: list[tuple[int, int, float]] = []

    for index, user_id in enumerate(users):
        first_likes = user_likes[user_id]
        for other_user_id in users[index + 1 :]:
            second_likes = user_likes[other_user_id]
            overlap_count = len(first_likes & second_likes)
            if overlap_count < min_overlap:
                continue

            union_count = len(first_likes | second_likes)
            if union_count == 0:
                continue

            score = overlap_count / union_count
            if score < threshold:
                continue

            results.append((user_id, other_user_id, score))
            results.append((other_user_id, user_id, score))

    return sorted(results, key=lambda row: (-row[2], row[0], row[1]))


def detect_mood(image_source) -> str:
    with open_image(image_source) as image:
        histogram = image.convert("L").histogram()

    total_pixels = sum(histogram)
    if total_pixels == 0:
        return "NEUTRAL"

    shadows = sum(histogram[0:86]) / total_pixels
    midtones = sum(histogram[86:171]) / total_pixels
    highlights = sum(histogram[171:256]) / total_pixels

    if shadows > 0.60:
        return "DARK"
    if highlights > 0.60:
        return "BRIGHT"
    if (shadows + highlights) > 0.75 and midtones < 0.25:
        return "CONTRAST"
    return "NEUTRAL"


def score_rule_of_thirds(image_source, *, size: tuple[int, int] = (300, 300), zone_radius: int = 10) -> int:
    with open_image(image_source) as image:
        edge_map = image.convert("L").resize(size).filter(ImageFilter.FIND_EDGES)

    total_edges = sum(edge_map.getdata())
    if total_edges == 0:
        return 5

    width, height = edge_map.size
    x_points = [width // 3, (2 * width) // 3]
    y_points = [height // 3, (2 * height) // 3]

    zone_sum = 0
    for x_point in x_points:
        for y_point in y_points:
            left = max(0, x_point - zone_radius)
            top = max(0, y_point - zone_radius)
            right = min(width, x_point + zone_radius)
            bottom = min(height, y_point + zone_radius)
            zone_sum += sum(edge_map.crop((left, top, right, bottom)).getdata())

    ratio = zone_sum / total_edges
    return max(1, min(10, int(ratio * 100)))
