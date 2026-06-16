from PIL import Image, ImageDraw

BG = (5, 5, 5)
GREEN = (0, 255, 156)


def draw_h(draw, size, margin_ratio=0.18, stroke_ratio=0.16):
    m = int(size * margin_ratio)
    w = int(size * stroke_ratio)
    # left vertical bar
    draw.rectangle([m, m, m + w, size - m], fill=GREEN)
    # right vertical bar
    draw.rectangle([size - m - w, m, size - m, size - m], fill=GREEN)
    # horizontal crossbar (middle third)
    mid_top = size // 2 - w // 2
    mid_bot = size // 2 + w // 2
    draw.rectangle([m, mid_top, size - m, mid_bot], fill=GREEN)


for size, name in [(192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")]:
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    draw_h(draw, size)
    out = f"static/{name}"
    img.save(out)
    print(f"wrote {out} ({size}x{size})")
