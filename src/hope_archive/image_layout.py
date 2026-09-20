"""Shared physical image layout for PDF, Word and TeX; ratios match Markdown."""

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

PDF_PAGE = (595.28, 841.89)
PDF_MARGIN = 56
PDF_BODY_WIDTH = PDF_PAGE[0] - 2 * PDF_MARGIN - 12  # ReportLab frame padding.
PDF_IMAGE_GAP = 12


def image_rows(images, available_width=PDF_BODY_WIDTH):
    """Return ordered rows of (bytes, display size), in points, without cropping."""
    def compatible(size):
        w, h = size
        return .85 <= w / h <= 2.2 and w * .75 >= 144
    rows, index = [], 0
    while index < len(images):
        paired = (index + 1 < len(images) and compatible(images[index][1])
                  and compatible(images[index + 1][1]) and (available_width - PDF_IMAGE_GAP) / 2 >= 144)
        batch = images[index:index + (2 if paired else 1)]
        row = []
        for data, (w, h) in batch:
            if paired:
                width, height = (available_width - PDF_IMAGE_GAP) / 2, 200
            else:
                width = available_width * single_width_percent((w,h)) / 100
                height = 300 if classification(w,h)=='portrait' else 260
            row.append((data, fit_image(w * .75, h * .75, width, height)))
        rows.append(row)
        index += len(batch)
    return rows
