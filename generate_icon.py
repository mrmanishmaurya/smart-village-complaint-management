import os
from PIL import Image, ImageDraw

def create_smart_village_icon(output_path="smart_village.ico"):
    # Create high resolution 256x256 image
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded rectangle background (Royal Blue)
    margin = 8
    draw.rounded_rectangle(
        [margin, margin, size[0] - margin, size[1] - margin],
        radius=48,
        fill=(13, 110, 253, 255),
        outline=(255, 255, 255, 220),
        width=4
    )

    # Inner Emblem - House / Village Roof
    draw.polygon(
        [(128, 48), (56, 120), (200, 120)],
        fill=(255, 255, 255, 255)
    )

    # House Body
    draw.rectangle(
        [(76, 120), (180, 200)],
        fill=(255, 255, 255, 255)
    )

    # House Door (Green)
    draw.rounded_rectangle(
        [(112, 144), (144, 200)],
        radius=6,
        fill=(25, 135, 84, 255)
    )

    # Small Windows
    draw.rounded_rectangle(
        [(88, 136), (104, 156)],
        radius=4,
        fill=(13, 110, 253, 255)
    )
    draw.rounded_rectangle(
        [(152, 136), (168, 156)],
        radius=4,
        fill=(13, 110, 253, 255)
    )

    # Save multi-resolution ICO file
    img.save(
        output_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    )
    print(f"Icon generated successfully at {output_path}")

if __name__ == "__main__":
    create_smart_village_icon()
