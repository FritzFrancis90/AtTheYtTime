# Improting Image class from PIL module 
import PodTubeSetup
from PIL import Image, ImageFont, ImageDraw, ImageEnhance

class ImageEditor:
    im = None
    font = None
    imagePath = ""

    def __init__(self, imagePath):
        self.im = Image.open(imagePath)
        self.imagePath = imagePath
        #self.font = ImageFont.load('arial.pil')

    def GetDominantColor(self):
        colors = self.im.Image.getcolors()
        return colors[0]

    def CropToCenter(self):
        left, right, top, bottom = (0, self.im.width, 0, self.im.height)
        if(self.im.width > self.im.height):
            left = (self.im.width / 2) - (self.im.height / 2)
            right = (self.im.width / 2) + (self.im.height / 2)
            top = 0
            bottom = self.im.height
        elif(self.im.width < self.im.height):
            left = 0
            right = self.im.width
            top = (self.im.height / 2) - (self.im.width / 2) 
            bottom = (self.im.height / 2) + (self.im.width / 2) 
        self.im = self.im.crop((left, top, right, bottom))
        return self

    def ScaleImage(self, factor):
        self.im = self.im.resize((self.im.width * factor, self.im.height * factor))
        return self

    def ChangeBrightness(self, factor):
        self.im = ImageEnhance.Brightness(self.im).enhance(factor)
        return self

    def AddTextToImage(self, text):
        defaultFontSize = self.im.width // 30
        textTitle = text.split("\n")[-1]
        defaultMarginPercentage = 0.075
        includedFont = PodTubeSetup.script_dir / PodTubeSetup.includedFont
        draw = ImageDraw.Draw(self.im)
        font = ImageFont.truetype(includedFont, defaultFontSize)
        textWidth = draw.textlength(textTitle, font=font)
        if textWidth >= self.im.width:
            font = ImageFont.truetype(includedFont, self.im.width // 50)
            textWidth = draw.textlength(textTitle, font=font)
        draw.multiline_text(((((1 - defaultMarginPercentage) * self.im.width) - textWidth), (self.im.height * 0.85)), text, font=font, align="right")
        return self

    def ApplyGradient(self, gradient = 1., initialOpacity = 1.):
        # get image to operate on
        #input_im = Image.open(path_in)
        if self.im.mode != 'RGBA':
            self.im = self.im.convert('RGBA')
        width, height = self.im.size

        # create a gradient that
        # starts at full opacity * initial_value
        # decrements opacity by gradient * x / width
        alpha_gradient = Image.new('L', (1, height), color=0xFF)
        for x in range(height):
            a = int((initialOpacity * 255.) * (1. - gradient * float(x)/height))
            if a > 0:
                alpha_gradient.putpixel((0, x), a)
            else:
                alpha_gradient.putpixel((0, x), 0)
            # print '{}, {:.2f}, {}'.format(x, float(x) / width, a)
        alpha = alpha_gradient.resize(self.im.size)

        # create black image, apply gradient
        black_im = Image.new('RGBA', (width, height), color=0) # i.e. black
        black_im.putalpha(alpha)
        black_im = black_im.rotate(180)

        # make composite with original image
        self.im = Image.alpha_composite(self.im, black_im).convert('RGB')

        return self

    def SaveImage(self):
        self.im.save(self.imagePath.replace('.jpg', '-altered.jpg'))
        return self.imagePath.replace('.jpg', '-altered.jpg')