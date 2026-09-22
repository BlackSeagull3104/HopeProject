"""Shared ordered media grouping and dimensions for all four renderers."""
from .document_style import PAGE, MARGIN_X, BODY_WIDTH, IMAGE_HEIGHT, IMAGE_GAP_FRACTION

LONG_IMAGE_RATIO = 2.5

def classification(width, height):
    if height / width >= LONG_IMAGE_RATIO: return 'long'
    if width / height < .85: return 'portrait'
    if width / height > 1.35: return 'landscape'
    return 'regular'

def single_width_percent(size):
    return {'long':38,'portrait':46,'landscape':65,'regular':55}[classification(*size)] if size else 55

def fit_image(width, height, max_width=450, max_height=600):
    if width <= 0 or height <= 0: raise ValueError("Invalid image dimensions")
    scale=min(max_width/width,max_height/height,1)
    return width*scale,height*scale

PDF_PAGE = PAGE
PDF_MARGIN = MARGIN_X
PDF_BODY_WIDTH = BODY_WIDTH
PDF_IMAGE_GAP = BODY_WIDTH * IMAGE_GAP_FRACTION


def group_sizes(sizes):
    """Preserve compatible Markdown triptychs; never pair long/incompatible media.

    Minimum intrinsic width 192px prevents grouping tiny thumbnails. Similar
    aspect ratios keep neighbours visually balanced. Unknown sizes stand alone.
    """
    def compatible(batch):
        if any(not s or min(s) <= 0 or s[0] < 192 or classification(*s) == 'long' for s in batch):
            return False
        ratios = [w / h for w, h in batch]
        return max(ratios) / min(ratios) <= 1.5
    index = 0
    while index < len(sizes):
        count = 1
        if len(sizes) == 3 and index == 0 and compatible(sizes):
            count = 3
        elif index + 1 < len(sizes) and compatible(sizes[index:index + 2]):
            count = 2
        yield index, count
        index += count


def cell_fraction(count, size):
    return .31 if count == 3 else .48 if count == 2 else single_width_percent(size) / 100


def image_rows(images, available_width=PDF_BODY_WIDTH):
    """Return ordered rows of (bytes, display size), in points, without cropping."""
    rows = []
    for index, count in group_sizes([size for _, size in images]):
        batch = images[index:index + count]
        row = []
        for data, (w, h) in batch:
            width = available_width * cell_fraction(count, (w, h))
            row.append((data, fit_image(w * .75, h * .75, width, IMAGE_HEIGHT)))
        rows.append(row)
    return rows
