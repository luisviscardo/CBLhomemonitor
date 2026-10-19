"""
Gerador de Ícones Oficiais do CBLhomemonitor (ICO e PNG)
Cria ícones multi-resolução com suporte a System Tray do Windows,
executáveis (.exe) e atalhos de Desktop.
"""
from pathlib import Path
from PIL import Image, ImageDraw

def generate_icons(output_dir: Path = None):
    if output_dir is None:
        output_dir = Path(__file__).parent / "static" / "img"
    output_dir.mkdir(parents=True, exist_ok=True)

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Escudo Hexagonal Cibernético Dark Slate
    points = [
        (128, 12),
        (236, 52),
        (236, 172),
        (128, 244),
        (20, 172),
        (20, 52)
    ]
    draw.polygon(points, fill=(15, 23, 42, 245))
    draw.polygon(points, outline=(0, 240, 255, 255), width=8)

    # Raio Neon Ciano
    bolt = [
        (140, 48),
        (88, 130),
        (130, 130),
        (116, 208),
        (176, 116),
        (134, 116),
        (156, 48)
    ]
    draw.polygon(bolt, fill=(0, 240, 255, 255))

    # Miolo Violeta Neon
    inner_bolt = [
        (136, 60),
        (98, 125),
        (132, 125),
        (124, 185),
        (165, 120),
        (135, 120),
        (150, 60)
    ]
    draw.polygon(inner_bolt, fill=(168, 85, 247, 235))

    png_path = output_dir / "icon.png"
    ico_path = output_dir / "icon.ico"

    img.save(png_path, format="PNG")
    img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Ícones gerados em: {png_path} e {ico_path}")
    return ico_path, png_path

if __name__ == "__main__":
    generate_icons()
