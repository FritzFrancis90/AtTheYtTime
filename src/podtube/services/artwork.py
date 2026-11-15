"""Podcast and episode artwork manipulation using Pillow."""

from pathlib import Path
from typing import Optional, Union
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
from podtube.config import PROJECT_ROOT


class ImageEditor:
    def __init__(self, imagePath: str, font_path: Optional[Union[str, Path]] = None):
        self.im = Image.open(imagePath)
        self.imagePath = imagePath
        self.font_path = (
            Path(font_path)
            if font_path
            else (PROJECT_ROOT / "fonts/Oswald/static/Oswald-Regular.ttf")
        )

    def GetDominantColor(self):
        colors = self.im.Image.getcolors()
        return colors[0]

    def CropToCenter(self):
        left, right, top, bottom = (0, self.im.width, 0, self.im.height)
        if self.im.width > self.im.height:
            left = (self.im.width / 2) - (self.im.height / 2)
            right = (self.im.width / 2) + (self.im.height / 2)
            top = 0
            bottom = self.im.height
        elif self.im.width < self.im.height:
            left = 0
            right = self.im.width
            top = (self.im.height / 2) - (self.im.width / 2)
            bottom = (self.im.height / 2) + (self.im.width / 2)
        self.im = self.im.crop((left, top, right, bottom))
        return self

    def ScaleImage(self, factor: int):
        self.im = self.im.resize((self.im.width * factor, self.im.height * factor))
        return self

    def ChangeBrightness(self, factor: float):
        self.im = ImageEnhance.Brightness(self.im).enhance(factor)
        return self

    def AddTextToImage(self, text: str):
        defaultFontSize = self.im.width // 30
        textTitle = text.split("\n")[-1]
        defaultMarginPercentage = 0.075
        draw = ImageDraw.Draw(self.im)
        font = ImageFont.truetype(str(self.font_path), defaultFontSize)
        textWidth = draw.textlength(textTitle, font=font)
        if textWidth >= self.im.width:
            font = ImageFont.truetype(str(self.font_path), self.im.width // 50)
            textWidth = draw.textlength(textTitle, font=font)
        draw.multiline_text(
            (
                (((1 - defaultMarginPercentage) * self.im.width) - textWidth),
                (self.im.height * 0.85),
            ),
            text,
            font=font,
            align="right",
        )
        return self

    def ApplyGradient(self, gradient: float = 1.0, initialOpacity: float = 1.0):
        if self.im.mode != "RGBA":
            self.im = self.im.convert("RGBA")
        width, height = self.im.size

        alpha_gradient = Image.new("L", (1, height), color=0xFF)
        for x in range(height):
            a = int((initialOpacity * 255.0) * (1.0 - gradient * float(x) / height))
            if a > 0:
                alpha_gradient.putpixel((0, x), a)
            else:
                alpha_gradient.putpixel((0, x), 0)
        alpha = alpha_gradient.resize(self.im.size)

        black_im = Image.new("RGBA", (width, height), color=0)
        black_im.putalpha(alpha)
        black_im = black_im.rotate(180)

        self.im = Image.alpha_composite(self.im, black_im).convert("RGB")
        return self

    def SaveImage(self) -> str:
        output_path = self.imagePath.replace(".jpg", "-altered.jpg")
        self.im.save(output_path)
        return output_path


def create_podcast_image(video, font_path: Optional[Union[str, Path]] = None) -> str:
    """Create the channel podcast cover image from the most recent episode's thumbnail."""
    altered_path = video.fileLocation.replace(".mp3", "-altered.jpg")
    return (
        ImageEditor(altered_path, font_path=font_path)
        .CropToCenter()
        .ScaleImage(2)
        .ApplyGradient(6, 0.6)
        .AddTextToImage('Latest Episode\n "' + video.Title + '"')
        .SaveImage()
    )
