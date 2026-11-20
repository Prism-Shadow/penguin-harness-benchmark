import sys
import base64
from io import BytesIO
from PIL import Image


def pixels(encoded, monochrome):
    with Image.open(BytesIO(base64.b64decode(encoded))) as image:
        if monochrome:
            assert image.size == (32, 32), 'expected 32px tray image'
        return list(image.convert('RGBA').getdata())


monochrome = sys.argv[1] == 'monochrome'
images = [pixels(encoded, monochrome) for encoded in sys.argv[2:]]
for image in images:
    visible = [pixel for pixel in image if pixel[3] > 0]
    assert visible, 'empty tray image'
    if monochrome:
        assert all(max(pixel[:3]) - min(pixel[:3]) <= 1 for pixel in visible), 'non-monochrome image'
    else:
        assert any(max(pixel[:3]) - min(pixel[:3]) > 1 for pixel in visible), 'colored running icon is monochrome'
if monochrome:
    dark, light = images
    assert any(first != second and max(first[3], second[3]) > 0 for first, second in zip(dark, light)), 'states or themes render identical pixels'
print('Rendered tray pixels verified')
