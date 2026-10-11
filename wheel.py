"""Генерация колеса рулетки через Pillow."""

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


# 37 секторов европейской рулетки
# (число, цвет): 'red', 'black', 'green'
WHEEL_SECTORS = [
    (0, 'green'),
    (32, 'red'), (15, 'black'), (19, 'red'), (4, 'black'),
    (21, 'red'), (2, 'black'), (25, 'red'), (17, 'black'),
    (34, 'red'), (6, 'black'), (27, 'red'), (13, 'black'),
    (36, 'red'), (11, 'black'), (30, 'red'), (8, 'black'),
    (23, 'red'), (10, 'black'), (5, 'red'), (24, 'black'),
    (16, 'red'), (33, 'black'), (1, 'red'), (20, 'black'),
    (14, 'red'), (31, 'black'), (9, 'red'), (22, 'black'),
    (18, 'red'), (29, 'black'), (7, 'red'), (28, 'black'),
    (12, 'red'), (35, 'black'), (3, 'red'), (26, 'black'),
]

COLORS = {
    'red': '#c0392b',
    'black': '#1a1a1a',
    'green': '#27ae60',
}

CACHE_DIR = Path(__file__).resolve().parent / "data" / "wheels"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_font(size):
    """Возвращает шрифт. Если нет — стандартный."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()


def draw_wheel(result_index):
    """
    Рисует колесо рулетки и стрелку на result_index.
    Возвращает путь к PNG.
    """
    cache_file = CACHE_DIR / f"wheel_{result_index}.png"
    if cache_file.exists():
        return str(cache_file)

    size = 700
    img = Image.new('RGB', (size, size), '#0d0d0d')
    draw = ImageDraw.Draw(img)

    n = len(WHEEL_SECTORS)
    angle_per = 360 / n

    cx, cy = size // 2, size // 2
    radius = size // 2 - 30

    font = _get_font(22)

    for i, (number, color) in enumerate(WHEEL_SECTORS):
        start = i * angle_per - 90
        end = start + angle_per
        draw.pieslice(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            start=start, end=end,
            fill=COLORS[color], outline='#f1c40f', width=1
        )

        mid_angle = math.radians(start + angle_per / 2)
        tx = cx + math.cos(mid_angle) * (radius - 45)
        ty = cy + math.sin(mid_angle) * (radius - 45)
        draw.text((tx, ty), str(number), fill='white', anchor='mm', font=font)

    # Внутренний круг
    inner = radius - 90
    draw.ellipse(
        [cx - inner, cy - inner, cx + inner, cy + inner],
        fill='#2c2c2c', outline='#f1c40f', width=3
    )

    # Стрелка на победивший сектор
    mid_angle = math.radians(result_index * angle_per - 90 + angle_per / 2)
    ex = cx + math.cos(mid_angle) * (radius - 5)
    ey = cy + math.sin(mid_angle) * (radius - 5)
    draw.line([cx, cy, ex, ey], fill='#f1c40f', width=6)

    # Кружок на конце стрелки
    draw.ellipse([ex - 8, ey - 8, ex + 8, ey + 8], fill='#f1c40f')

    img.save(cache_file)
    return str(cache_file)


def spin_wheel():
    """
    Крутит колесо. Возвращает:
        (result_index, number, color)
    """
    idx = random.randint(0, len(WHEEL_SECTORS) - 1)
    number, color = WHEEL_SECTORS[idx]
    return idx, number, color