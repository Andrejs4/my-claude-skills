#!/usr/bin/env python3
"""
Turn ordinary pictures into small, web-ready pixelated images: crop, shrink
to a coarse grid of real pixels, limit the palette, and save tiny PNGs with
no metadata. Also reports what metadata the inputs carry (prompts, AI tools,
provenance records), since the outputs drop it.

Needs Pillow (pip install pillow). Run with --help for the options.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageStat, features
except ImportError:
    sys.exit('pixelate.py needs Pillow: pip install pillow')

# Grid widths the automatic choice tries, smallest first.
LADDER = [8, 12, 16, 24, 32, 48, 64, 96, 128, 160, 192, 256]
# How much of the error between the coarsest and finest grid the automatic
# choice accepts: more detail accepts less.
DETAIL = {'low': 0.5, 'medium': 0.3, 'high': 0.15}
# Colour and contrast lift after shrinking, which averages colours toward
# mud: none keeps them true, strong gives old games' pop.
BOOST = {'none': (1.0, 1.0), 'mild': (1.15, 1.05), 'strong': (1.3, 1.1)}
# Rounds of k-means refining the palette: it gives small areas of a colour
# (a green shirt in a brown crowd) their own colour back.
KMEANS = 8
# Up to this many inputs get a before-and-after preview each; more get one
# contact sheet.
EACH_PREVIEW_MAX = 3
# The face detector for --frame face (YuNet, MIT licence, models/LICENSE-yunet.txt).
FACE_MODEL = Path(__file__).resolve().parent.parent / 'models' / 'face_detection_yunet_2023mar.onnx'
INPUT_TYPES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff'}

# Text in metadata that points to an image generator or service.
AI_MARKERS = [
    ('Stable Diffusion', r'stable.?diffusion|\bsdxl\b|\bsd ?1\.5\b'),
    ('AUTOMATIC1111 / Forge', r'Steps: \d+, Sampler:'),
    ('ComfyUI', r'"class_type"|comfyui'),
    ('InvokeAI', r'invokeai'),
    ('Midjourney', r'midjourney'),
    ('DALL·E / OpenAI', r'dall.?e|openai'),
    ('Adobe Firefly', r'firefly'),
    ('Google', r'imagen|gemini'),
    ('Perplexity', r'perplexity'),
    ('Flux', r'\bflux\b'),
    ('marked as AI-made (IPTC)', r'trainedAlgorithmicMedia|compositeWithTrainedAlgorithmicMedia'),
    ('C2PA provenance record', r'c2pa'),
]


def parse_size(text):
    """'64x32' -> (64, 32); '64' or '64x' -> (64, None); 'x32' -> (None, 32)."""
    m = re.fullmatch(r'\s*(\d*)\s*(?:[x×]\s*(\d*))?\s*', text or '')
    if not m or not (m.group(1) or m.group(2)):
        raise argparse.ArgumentTypeError(f'not a size: {text!r} (use WxH, W or xH)')
    w = int(m.group(1)) if m.group(1) else None
    h = int(m.group(2)) if m.group(2) else None
    if (w is not None and w < 1) or (h is not None and h < 1):
        raise argparse.ArgumentTypeError(f'not a size: {text!r}')
    return w, h


def parse_aspect(text):
    m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*[:/x]\s*(\d+(?:\.\d+)?)\s*', text)
    if not m:
        raise argparse.ArgumentTypeError(f'not an aspect: {text!r} (use W:H, such as 1:1 or 13:5)')
    return float(m.group(1)) / float(m.group(2))


def parse_box(text):
    parts = [int(p) for p in re.split(r'[,\s]+', text.strip())]
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        raise argparse.ArgumentTypeError(f'not a box: {text!r} (use x,y,width,height)')
    return parts


def parse_focus(text):
    parts = [float(p) for p in re.split(r'[,\s]+', text.strip())]
    if len(parts) != 2 or not all(0 <= p <= 1 for p in parts):
        raise argparse.ArgumentTypeError(f'not a focus: {text!r} (use x,y, each from 0 to 1)')
    return parts


def inspect(path, im):
    """What the file says about itself: its metadata and any sign of an AI tool."""
    texts = {k: v for k, v in im.info.items() if isinstance(v, str)}
    exif = im.getexif()
    names = {0x0131: 'Software', 0x013B: 'Artist', 0x010E: 'ImageDescription', 0x8298: 'Copyright'}
    exif_text = {names[t]: str(v) for t, v in exif.items() if t in names}
    xmp = im.info.get('xmp')
    if isinstance(xmp, bytes):
        xmp = xmp.decode('utf-8', 'replace')
    raw = path.read_bytes()
    haystack = '\n'.join([*texts.values(), *exif_text.values(), xmp or '',
                          'c2pa' if (b'c2pa' in raw or b'jumb' in raw) else ''])
    hints = [name for name, pattern in AI_MARKERS if re.search(pattern, haystack, re.IGNORECASE)]
    model = None
    params = texts.get('parameters', '')
    m = re.search(r'Model: ([^,\n]+)', params) or re.search(r'"ckpt_name":\s*"([^"]+)"', haystack)
    if m:
        model = m.group(1).strip()
    prompt = None
    if params:
        prompt = params.split('Negative prompt:')[0].strip().splitlines()[0][:160] if params.strip() else None
    return {
        'format': im.format,
        'size': list(im.size),
        'mode': im.mode,
        'metadata': sorted({*texts.keys(), *exif_text.keys(), *(['xmp'] if xmp else [])}),
        'ai_hints': hints,
        'model': model,
        'prompt_excerpt': prompt,
    }


def centre_box(size, aspect=None, focus=(0.5, 0.5), zoom=1.0):
    """The largest part of the picture with the given aspect, then 1/zoom of
    that each way, both around the focus point, as [x, y, w, h]. One --zoom
    frames a whole batch of portraits made alike, with no box per picture."""
    w, h = size
    if aspect:
        cw, ch = (round(h * aspect), h) if w / h > aspect else (w, round(w / aspect))
    else:
        cw, ch = w, h
    cw, ch = max(1, round(cw / zoom)), max(1, round(ch / zoom))
    x = min(max(0, round(focus[0] * w - cw / 2)), w - cw)
    y = min(max(0, round(focus[1] * h - ch / 2)), h - ch)
    return [x, y, cw, ch]


def crop(im, box):
    """The picture within box [x, y, w, h], clipped to the picture."""
    x, y, w, h = box
    if [x, y, w, h] == [0, 0, im.width, im.height]:
        return im
    return im.crop((x, y, min(x + w, im.width), min(y + h, im.height)))


def face_detector():
    """A function finding the most likely face in a picture, as (x, y, w, h,
    score), or None. Needs OpenCV."""
    os.environ.setdefault('OPENCV_LOG_LEVEL', 'ERROR')
    try:
        import cv2
        import numpy as np
    except ImportError:
        sys.exit('--frame face needs OpenCV: pip install opencv-python-headless')
    if not FACE_MODEL.exists():
        sys.exit(f'the face model is missing: {FACE_MODEL}')
    detectors = {}

    def find(im):
        # Detect on a copy at most 640 wide, then scale back.
        k = min(1.0, 640 / max(im.size))
        small = im.convert('RGB').resize((max(1, round(im.width * k)), max(1, round(im.height * k))))
        if small.size not in detectors:
            detectors[small.size] = cv2.FaceDetectorYN.create(str(FACE_MODEL), '', small.size, 0.6, 0.3, 5000)
        _, faces = detectors[small.size].detect(np.asarray(small)[:, :, ::-1].copy())
        if faces is None or not len(faces):
            return None
        best = max(faces, key=lambda r: r[2] * r[3] * r[14])
        x, y, w, h = (float(v) / k for v in best[:4])
        return x, y, w, h, float(best[14])
    return find


def background_remover(model):
    """A function giving a picture its subject alone, on transparency. Needs
    rembg; its model is downloaded on first use (isnet-general-use: 180 MB,
    kept in ~/.u2net, or $U2NET_HOME)."""
    os.environ.setdefault('OMP_NUM_THREADS', str(os.cpu_count() or 1))
    try:
        from rembg import new_session, remove
    except ImportError:
        sys.exit('--background needs rembg: pip install "rembg[cpu]"')
    session = new_session(model)

    def cut(im):
        return remove(im.convert('RGB'), session=session).convert('RGBA')
    return cut


def parse_background(text):
    if text == 'transparent':
        return text
    m = re.fullmatch(r'#?([0-9a-fA-F]{6})', text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f'not a colour: {text!r} (use #rrggbb or transparent)')
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))


def around_face(face, size, aspect, fill):
    """A box around a face: the face's larger side is `fill` of the box's
    width, and the box sits a little low, for chin and beard; kept inside the
    picture, and shrunk to fit if it must."""
    x, y, w, h = face[:4]
    W, H = size
    cw = max(w, h) / fill
    ch = cw / aspect
    k = min(1.0, W / cw, H / ch)
    cw, ch = max(1, round(cw * k)), max(1, round(ch * k))
    cx, cy = x + w / 2, y + h / 2 + 0.06 * ch
    bx = min(max(0, round(cx - cw / 2)), W - cw)
    by = min(max(0, round(cy - ch / 2)), H - ch)
    return [bx, by, cw, ch]


def frames_sheet(jobs, path, thumb=160, columns=8):
    """Each picture, small, with the box it was cropped to: framing to check in one look."""
    columns = min(columns, len(jobs))
    rows = (len(jobs) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * (thumb + 4), rows * (thumb + 4)), (255, 255, 255))
    for n, job in enumerate(jobs):
        im = job['source']
        k = thumb / max(im.size)
        th = im.convert('RGB').resize((max(1, round(im.width * k)), max(1, round(im.height * k))))
        draw = ImageDraw.Draw(th)
        bx, by, bw, bh = job['box']
        draw.rectangle([bx * k, by * k, (bx + bw) * k, (by + bh) * k], outline=(255, 0, 0), width=2)
        draw.text((3, 2), job['file'].stem[:18], fill=(255, 255, 0))
        sheet.paste(th, ((n % columns) * (thumb + 4), (n // columns) * (thumb + 4)))
    sheet.save(path, quality=85)


def exact_palette(im):
    """An RGBA picture of at most 255 colours as an indexed one with exactly
    those colours (and one index for clear), else as it is."""
    colours = im.getcolors(256) or []
    opaque = [c[:3] for _, c in colours if c[3] == 255]
    clear = any(c[3] == 0 for _, c in colours)
    if not colours or len(opaque) + clear > 256 or any(0 < c[3] < 255 for _, c in colours):
        return im
    pal = Image.new('P', (1, 1))
    pal.putpalette([v for c in opaque for v in c] + [0, 0, 0] * (256 - len(opaque)))
    q = im.convert('RGB').quantize(palette=pal, dither=Image.Dither.NONE)
    if clear:
        index = len(opaque)
        px, alpha = q.load(), im.getchannel('A').load()
        for y in range(q.height):
            for x in range(q.width):
                if alpha[x, y] == 0:
                    px[x, y] = index
        q.info['transparency'] = index
    return q


def atlas(results, cols, rows, path):
    """The results packed in a grid, in order, each cell the size of the
    largest: a sprite sheet for the page to cut up."""
    cw = max(img.width for _, img in results)
    ch = max(img.height for _, img in results)
    sheet = Image.new('RGBA', (cols * cw, rows * ch), (0, 0, 0, 0))
    cells = []
    for n, (name, img) in enumerate(results[:cols * rows]):
        x, y = (n % cols) * cw, (n // cols) * ch
        sheet.paste(img.convert('RGBA'), (x, y))
        cells.append({'name': name, 'col': n % cols, 'row': n // cols, 'x': x, 'y': y})
    exact_palette(sheet).save(path, optimize=True)
    return {'file': str(path), 'cell': [cw, ch], 'grid': [cols, rows], 'cells': cells}


def fit(size, aspect):
    """Fill in a missing side from the picture's aspect (width / height)."""
    w, h = size
    if w is None:
        w = max(1, round(h * aspect))
    if h is None:
        h = max(1, round(w / aspect))
    return w, h


def quantize_method():
    return Image.Quantize.LIBIMAGEQUANT if features.check('libimagequant') else Image.Quantize.MEDIANCUT


def shrink(im, size, resample, boost='none'):
    """The picture at grid size, RGBA, with hard-edged transparency and its
    colours lifted as asked."""
    small = im.convert('RGBA').resize(size, resample)
    saturation, contrast = BOOST[boost]
    if (saturation, contrast) != (1.0, 1.0):
        rgb = ImageEnhance.Contrast(ImageEnhance.Color(small.convert('RGB')).enhance(saturation)).enhance(contrast)
        rgb.putalpha(small.getchannel('A'))
        small = rgb
    alpha = small.getchannel('A')
    if alpha.getextrema()[0] < 255:
        small.putalpha(alpha.point(lambda v: 255 if v >= 128 else 0))
    return small


def palette_of(images, colors):
    """One palette for several pictures, so a set looks alike."""
    width = sum(i.width for i in images)
    height = max(i.height for i in images)
    strip = Image.new('RGB', (width, height))
    x = 0
    for i in images:
        strip.paste(i.convert('RGB'), (x, 0))
        x += i.width
    return strip.quantize(colors=colors, method=quantize_method(), kmeans=KMEANS)


def palette_from_file(path, colors):
    """A palette from an image (its colours) or a text file of hex colours."""
    path = Path(path)
    if path.suffix.lower() in {'.txt', '.hex', '.gpl'}:
        hexes = re.findall(r'#?\b([0-9a-fA-F]{6})\b', path.read_text())
        if not hexes:
            sys.exit(f'no colours found in {path}')
        flat = [int(h[i:i + 2], 16) for h in hexes[:256] for i in (0, 2, 4)]
        pal = Image.new('P', (1, 1))
        pal.putpalette(flat + flat[:3] * (256 - len(hexes[:256])))
        return pal
    with Image.open(path) as im:
        return im.convert('RGB').quantize(colors=colors, method=quantize_method(), kmeans=KMEANS)


def quantize(small, colors, dither, palette=None):
    """Few colours, as old games had; transparent pixels get a colour of their own."""
    alpha = small.getchannel('A')
    clear = alpha.getextrema()[0] < 255
    rgb = small.convert('RGB')
    mode = Image.Dither.FLOYDSTEINBERG if dither == 'floyd' else Image.Dither.NONE
    if palette is not None:
        q = rgb.quantize(palette=palette, dither=mode)
    else:
        q = rgb.quantize(colors=max(2, colors - (1 if clear else 0)), method=quantize_method(), kmeans=KMEANS, dither=mode)
    if clear:
        used = len(q.getpalette()) // 3
        index = min(used, 255)
        flat = q.getpalette()[:index * 3] + [0, 0, 0]
        q.putpalette(flat)
        px, ap = q.load(), alpha.load()
        for y in range(q.height):
            for x in range(q.width):
                if ap[x, y] == 0:
                    px[x, y] = index
        q.info['transparency'] = index
    return q


def auto_grid(im, aspect, colors, dither, detail, resample, boost):
    """The smallest grid that keeps most of the picture: how far each grid's
    result is from the picture, from the coarsest to the finest that fits,
    and the first within the detail level's share of that range."""
    ref_w = min(im.width, 256)
    ref = im.convert('RGB').resize((ref_w, max(1, round(ref_w / aspect))), Image.LANCZOS)
    tried = []
    for w in [x for x in LADDER if x <= max(ref_w, LADDER[0])]:
        size = fit((w, None), aspect)
        result = quantize(shrink(im, size, resample, boost), colors, dither).convert('RGB').resize(ref.size, Image.NEAREST)
        error = sum(ImageStat.Stat(ImageChops.difference(result, ref)).mean) / 3
        tried.append((size, error))
    if len(tried) == 1:
        return tried[0][0], tried
    worst, best = tried[0][1], min(e for _, e in tried)
    for size, error in tried:
        if error - best <= DETAIL[detail] * (worst - best):
            return size, tried
    return tried[-1][0], tried


def preview(original, result, path, height=256):
    """The picture and the result side by side, at the same height."""
    left = original.convert('RGB')
    left = left.resize((max(1, round(left.width * height / left.height)), height), Image.LANCZOS)
    k = max(1, round(height / result.height))
    right = result.convert('RGBA').resize((result.width * k, result.height * k), Image.NEAREST)
    sheet = Image.new('RGB', (left.width + 16 + right.width, max(height, right.height)), (24, 24, 24))
    sheet.paste(left, (0, 0))
    sheet.paste(right, (left.width + 16, 0), right)
    sheet.save(path, optimize=True)


def contact_sheet(results, path, cell=96, columns=8):
    """All the results of a batch on one sheet, each scaled up whole, named."""
    columns = min(columns, len(results))
    rows = (len(results) + columns - 1) // columns
    label = 14
    sheet = Image.new('RGB', (columns * (cell + 8) + 8, rows * (cell + label + 8) + 8), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for n, (name, img) in enumerate(results):
        k = max(1, min(cell // img.width, cell // img.height))
        big = img.convert('RGBA').resize((img.width * k, img.height * k), Image.NEAREST)
        x = 8 + (n % columns) * (cell + 8)
        y = 8 + (n // columns) * (cell + label + 8)
        sheet.paste(big, (x + (cell - big.width) // 2, y + (cell - big.height) // 2), big)
        draw.text((x, y + cell + 2), name[:16], fill=(200, 200, 200))
    sheet.save(path, optimize=True)


def inputs_of(paths):
    found = []
    for p in map(Path, paths):
        if p.is_dir():
            found += sorted(f for f in p.iterdir() if f.suffix.lower() in INPUT_TYPES)
        elif p.exists():
            found.append(p)
        else:
            sys.exit(f'no such file: {p}')
    if not found:
        sys.exit('no pictures given')
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inputs', nargs='+', help='pictures, or folders of them')
    ap.add_argument('--out', default='pixelated', help='folder for the results (default: pixelated)')
    scale = ap.add_argument_group('grid: the size in real pixels (one of these, or automatic)')
    scale.add_argument('--grid', type=parse_size, help='WxH, W or xH, such as 16x16 for a face or 128 for a banner')
    scale.add_argument('--display', type=parse_size, help='size it will show at on the page, with --block')
    scale.add_argument('--block', type=int, default=4, help='screen pixels per image pixel with --display (default 4)')
    scale.add_argument('--detail', choices=DETAIL, default='medium', help='how much detail the automatic grid keeps')
    shape = ap.add_argument_group('crop')
    shape.add_argument('--aspect', type=parse_aspect, help='crop to W:H first, such as 1:1 or 13:5')
    shape.add_argument('--focus', type=parse_focus, default=(0.5, 0.5), help='centre of an --aspect crop, as x,y from 0 to 1 (default 0.5,0.5)')
    shape.add_argument('--zoom', type=float, default=1.0, help='keep the middle 1/ZOOM each way, around --focus (after --aspect): 1.6 frames a face in a head-and-shoulders portrait')
    shape.add_argument('--box', type=parse_box, help='crop to x,y,width,height in the picture\'s pixels')
    shape.add_argument('--frame', choices=['center', 'face'], default='center',
                       help='face: crop around the face each picture shows (needs OpenCV; square unless --aspect); center: --aspect, --zoom and --focus (default)')
    shape.add_argument('--face-fill', type=float, default=0.6, help='with --frame face, how much of the crop\'s width the face takes (default 0.6)')
    shape.add_argument('--crops', help='a JSON file of boxes per picture, {"name.png": [x, y, w, h]}, used before any other framing; each run writes the boxes it used to OUT/crops.json')
    look = ap.add_argument_group('look')
    look.add_argument('--colors', type=int, default=32, help='palette size, 2 to 256 (default 32)')
    look.add_argument('--background', type=parse_background,
                      help='replace the background: a colour (#787878) or transparent; needs rembg, and downloads its model (180 MB) on first use')
    look.add_argument('--bg-model', default='isnet-general-use', help='rembg model for --background (default isnet-general-use; u2netp is 5 MB but cruder)')
    look.add_argument('--boost', choices=BOOST, default='mild', help='lift colour and contrast after shrinking: none keeps them true, strong gives old games\' pop (default mild)')
    look.add_argument('--dither', choices=['none', 'floyd'], default='none', help='blend colours with a dot pattern (default none)')
    look.add_argument('--shared-palette', action='store_true', help='one palette for all inputs, so a set looks alike')
    look.add_argument('--palette', help='use these colours: an image, or a text file of hex colours')
    look.add_argument('--save-palette', help='write the colours used to this file (hex, one a line), to reuse with --palette for later pictures of the set')
    look.add_argument('--resample', choices=['lanczos', 'box'], default='lanczos', help='how pixels are averaged when shrinking: lanczos keeps edges sharper, box is smoother (default lanczos)')
    output = ap.add_argument_group('output')
    output.add_argument('--scale', type=int, default=1, help='also save each result scaled up this many times, for places without CSS scaling')
    output.add_argument('--atlas', type=parse_size, help='also pack the results, in name order, into one COLSxROWS sprite sheet (atlas.png), cells listed in the report')
    output.add_argument('--preview', choices=['auto', 'each', 'sheet', 'none'], default='auto',
                        help=f'before-and-after per picture, one contact sheet, or none; auto: each up to {EACH_PREVIEW_MAX} pictures, else a sheet')
    args = ap.parse_args(argv)
    if not 2 <= args.colors <= 256:
        ap.error('--colors must be from 2 to 256')
    if args.box and (args.aspect or args.zoom != 1.0 or args.frame == 'face'):
        ap.error('use --box, or --aspect, --zoom and --frame, not both')
    if not 0.1 <= args.face_fill <= 1:
        ap.error('--face-fill must be from 0.1 to 1')
    if args.atlas and (args.atlas[0] is None or args.atlas[1] is None):
        ap.error('--atlas needs COLSxROWS, such as 8x8')
    if args.zoom < 1:
        ap.error('--zoom must be 1 or more')
    if args.save_palette and len(inputs_of(args.inputs)) > 1 and not (args.shared_palette or args.palette):
        ap.error('--save-palette with several pictures needs --shared-palette (or --palette): else each has its own')

    files = inputs_of(args.inputs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    resample = Image.LANCZOS if args.resample == 'lanczos' else Image.BOX

    crops = {}
    if args.crops:
        crops = json.loads(Path(args.crops).read_text())
    find_face = face_detector() if args.frame == 'face' else None
    cut_out = background_remover(args.bg_model) if args.background else None

    # First pass: crop, read and size each picture.
    jobs = []
    for f in files:
        with Image.open(f) as raw:
            info = inspect(f, raw)
            raw.seek(0)
            source = raw.convert('RGBA')
        box = crops.get(f.name) or crops.get(f.stem)
        framed = 'crops file' if box else None
        if not box and args.box:
            box, framed = list(args.box), 'box'
        if not box and find_face:
            face = find_face(source)
            if face:
                box = around_face(face, source.size, args.aspect or 1.0, args.face_fill)
                framed = f'face {face[4]:.2f}'
            else:
                framed = 'no face found: centre'
        if not box:
            box = centre_box(source.size, args.aspect, args.focus, args.zoom)
            framed = framed or ('centre' if (args.aspect or args.zoom != 1.0) else 'whole')
        if cut_out:
            # On the whole picture, which the model reads better than a crop.
            subject = cut_out(source)
            if args.background == 'transparent':
                source = subject
            else:
                flat = Image.new('RGBA', source.size, (*args.background, 255))
                flat.alpha_composite(subject)
                source = flat
        im = crop(source, box)
        aspect = im.width / im.height
        tried = None
        if args.grid:
            size = fit(args.grid, aspect)
            how = 'given'
        elif args.display:
            dw, dh = fit(args.display, aspect)
            size = (max(1, round(dw / args.block)), max(1, round(dh / args.block)))
            how = f'display {dw}x{dh} / block {args.block}'
        else:
            size, tried = auto_grid(im, aspect, args.colors, args.dither, args.detail, resample, args.boost)
            how = f'automatic, {args.detail} detail'
        if size[0] > im.width or size[1] > im.height:
            print(f'note: {f.name}: a {size[0]}x{size[1]} grid is larger than the picture ({im.width}x{im.height})', file=sys.stderr)
        jobs.append({'file': f, 'source': source, 'box': [int(v) for v in box], 'framed': framed,
                     'image': im, 'info': info, 'size': size, 'how': how, 'tried': tried})

    for job in jobs:
        job['small'] = shrink(job['image'], job['size'], resample, args.boost)
    palette = None
    if args.palette:
        palette = palette_from_file(args.palette, args.colors)
    elif args.shared_palette and len(jobs) > 1:
        palette = palette_of([j['small'] for j in jobs], args.colors)

    # Second pass: quantize and save.
    mode = args.preview if args.preview != 'auto' else ('each' if len(jobs) <= EACH_PREVIEW_MAX else 'sheet')
    report = []
    for job in jobs:
        result = quantize(job['small'], args.colors, args.dither, palette)
        name = job['file'].stem
        target = out / f'{name}.png'
        result.save(target, optimize=True)
        files_out = [str(target)]
        if args.scale > 1:
            big = result.resize((result.width * args.scale, result.height * args.scale), Image.NEAREST)
            big_path = out / f'{name}@{args.scale}x.png'
            big.save(big_path, optimize=True)
            files_out.append(str(big_path))
        if mode == 'each':
            pv = out / f'{name}.preview.png'
            preview(job['image'], result, pv)
            files_out.append(str(pv))
        colours = len({c for _, c in result.convert('RGBA').getcolors(1 << 16) or []})
        job['result'] = result
        report.append({
            'input': str(job['file']),
            **job['info'],
            'framed': job['framed'],
            'box': job['box'],
            'cropped_to': list(job['image'].size),
            'grid': list(job['size']),
            'grid_from': job['how'],
            'grids_tried': [[f'{s[0]}x{s[1]}', round(e, 1)] for s, e in job['tried']] if job['tried'] else None,
            'colours_used': colours,
            'bytes': target.stat().st_size,
            'outputs': files_out,
        })
    if args.save_palette:
        used = set()
        for job in jobs:
            used |= {c[:3] for _, c in job['result'].convert('RGBA').getcolors(1 << 16) or [] if c[3] == 255}
        lines = ['#%02x%02x%02x' % c for c in sorted(used, key=lambda c: (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2], c))]
        Path(args.save_palette).write_text('\n'.join(lines) + '\n')
    (out / 'crops.json').write_text(json.dumps({j['file'].name: j['box'] for j in jobs}, indent=1))
    sheet = frames = packed = None
    if mode == 'sheet':
        sheet = out / 'contact-sheet.png'
        contact_sheet([(j['file'].stem, j['result']) for j in jobs], sheet)
        frames = out / 'frames.jpg'
        frames_sheet(jobs, frames)
    if args.atlas:
        packed = atlas([(j['file'].stem, j['result']) for j in jobs], args.atlas[0], args.atlas[1], out / 'atlas.png')
        if len(jobs) > args.atlas[0] * args.atlas[1]:
            print(f'note: {len(jobs)} pictures, but the atlas holds {args.atlas[0] * args.atlas[1]}', file=sys.stderr)
    summary = {
        'settings': {'colors': args.colors, 'boost': args.boost, 'dither': args.dither,
                     'background': ('#%02x%02x%02x' % args.background if isinstance(args.background, tuple) else args.background), 'palette': 'shared' if palette is not None and not args.palette else args.palette,
                     'resample': args.resample, 'preview': mode},
        'contact_sheet': str(sheet) if sheet else None,
        'frames_sheet': str(frames) if frames else None,
        'crops': str(out / 'crops.json'),
        'atlas': packed,
        'palette_saved': args.save_palette,
        'images': report,
    }
    (out / 'report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
