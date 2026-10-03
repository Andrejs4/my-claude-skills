"""Tests for plugins/web-pixel-images/.../scripts/pixelate.py, on pictures
made here. Run from the repository: python3 -m unittest discover tests"""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, PngImagePlugin

SCRIPT = Path(__file__).resolve().parent.parent / 'plugins/web-pixel-images/skills/web-pixel-images/scripts/pixelate.py'
spec = importlib.util.spec_from_file_location('pixelate', SCRIPT)
pixelate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pixelate)


def picture(path, size=(400, 300), seed=0, alpha=False, text=None):
    """A smooth picture: gradients and a few soft shapes."""
    w, h = size
    im = Image.new('RGBA' if alpha else 'RGB', size, (0, 0, 0, 0) if alpha else (0, 0, 0))
    draw = ImageDraw.Draw(im)
    for y in range(h):
        draw.line([(0, y), (w, y)], fill=(40 + y * 150 // h, 60 + seed * 30, 160 - y * 100 // h, 255))
    draw.ellipse([w // 4, h // 4, w * 3 // 4, h * 3 // 4], fill=(200, 80 + seed * 40, 40, 255))
    if alpha:
        mask = Image.new('L', size, 0)
        ImageDraw.Draw(mask).ellipse([10, 10, w - 10, h - 10], fill=255)
        im.putalpha(mask)
    info = None
    if text:
        info = PngImagePlugin.PngInfo()
        for k, v in text.items():
            info.add_text(k, v)
    im.save(path, pnginfo=info)
    return path


def load(path):
    """An image read whole, its file closed."""
    with Image.open(path) as im:
        im.load()
        return im.copy()


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        pixelate.main([str(a) for a in args])
    return json.loads(out.getvalue())


class Pixelate(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_grid_palette_and_no_metadata(self):
        src = picture(self.dir / 'a.png', text={'parameters': 'a knight, Steps: 20, Sampler: Euler a, Model: dreamshaper_8'})
        r = run(src, '--out', self.dir / 'o', '--grid', '16x12', '--colors', '8')['images'][0]
        self.assertEqual(r['grid'], [16, 12])
        out = load(r['outputs'][0])
        self.assertEqual(out.size, (16, 12))
        self.assertEqual(out.mode, 'P')
        self.assertLessEqual(r['colours_used'], 8)
        # What the input said about itself is reported, and left behind.
        self.assertIn('AUTOMATIC1111 / Forge', r['ai_hints'])
        self.assertEqual(r['model'], 'dreamshaper_8')
        self.assertEqual(r['prompt_excerpt'], 'a knight, Steps: 20, Sampler: Euler a, Model: dreamshaper_8')
        self.assertNotIn('parameters', out.info)

    def test_one_side_follows_the_aspect(self):
        src = picture(self.dir / 'a.png', size=(400, 200))
        self.assertEqual(run(src, '--out', self.dir / 'o', '--grid', '40')['images'][0]['grid'], [40, 20])
        self.assertEqual(run(src, '--out', self.dir / 'o', '--grid', 'x10')['images'][0]['grid'], [20, 10])

    def test_display_and_block(self):
        src = picture(self.dir / 'a.png', size=(1040, 400))
        r = run(src, '--out', self.dir / 'o', '--display', '520', '--block', '4')['images'][0]
        self.assertEqual(r['grid'], [130, 50])

    def test_crop_to_an_aspect_and_a_box(self):
        src = picture(self.dir / 'a.png', size=(400, 200))
        self.assertEqual(run(src, '--out', self.dir / 'o', '--aspect', '1:1', '--grid', '8')['images'][0]['cropped_to'], [200, 200])
        self.assertEqual(run(src, '--out', self.dir / 'o', '--box', '10,20,100,50', '--grid', '8')['images'][0]['cropped_to'], [100, 50])

    def test_zoom_frames_the_middle_around_the_focus(self):
        src = picture(self.dir / 'a.png', size=(400, 400))
        r = run(src, '--out', self.dir / 'o', '--zoom', '2', '--focus', '0.5,0.4', '--grid', '8')['images'][0]
        self.assertEqual(r['cropped_to'], [200, 200])
        r = run(src, '--out', self.dir / 'o', '--aspect', '2:1', '--zoom', '2', '--grid', '8')['images'][0]
        self.assertEqual(r['cropped_to'], [200, 100])

    def test_a_saved_palette_serves_the_next_batch(self):
        for n in range(3):
            picture(self.dir / f'f{n}.png', size=(120, 120), seed=n)
        saved = self.dir / 'set.hex'
        run(self.dir, '--out', self.dir / 'o', '--grid', '16', '--colors', '10', '--shared-palette', '--save-palette', saved)
        colours = {tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in saved.read_text().split()}
        self.assertTrue(2 <= len(colours) <= 10)
        later = picture(self.dir / 'later.png', size=(120, 120), seed=7)
        out = load(run(later, '--out', self.dir / 'o2', '--grid', '16', '--palette', saved)['images'][0]['outputs'][0])
        self.assertTrue({c for _, c in out.convert('RGB').getcolors()} <= colours)

    def test_automatic_grid_is_from_the_ladder_and_more_detail_is_finer(self):
        src = picture(self.dir / 'a.png', size=(800, 600))
        low = run(src, '--out', self.dir / 'o', '--detail', 'low')['images'][0]
        high = run(src, '--out', self.dir / 'o', '--detail', 'high')['images'][0]
        self.assertIn(low['grid'][0], pixelate.LADDER)
        self.assertLessEqual(low['grid'][0], high['grid'][0])
        self.assertTrue(low['grids_tried'])

    def test_transparency_stays_hard_edged(self):
        src = picture(self.dir / 'a.png', alpha=True)
        out = load(run(src, '--out', self.dir / 'o', '--grid', '20')['images'][0]['outputs'][0]).convert('RGBA')
        alphas = {a for a, count in enumerate(out.getchannel('A').histogram()) if count}
        self.assertEqual(alphas, {0, 255})

    def test_a_batch_shares_a_palette_and_gets_one_sheet(self):
        for n in range(5):
            picture(self.dir / f'face{n}.png', size=(120, 120), seed=n)
        report = run(self.dir, '--out', self.dir / 'o', '--grid', '16', '--colors', '12', '--shared-palette')
        self.assertEqual(len(report['images']), 5)
        self.assertEqual(report['settings']['preview'], 'sheet')
        self.assertTrue(Path(report['contact_sheet']).exists())
        self.assertFalse(any(o.endswith('.preview.png') for r in report['images'] for o in r['outputs']))
        colours = set()
        for r in report['images']:
            colours |= {c for _, c in load(r['outputs'][0]).convert('RGB').getcolors()}
        self.assertLessEqual(len(colours), 12)

    def test_a_few_get_a_preview_each_and_a_scaled_copy(self):
        src = picture(self.dir / 'a.png')
        r = run(src, '--out', self.dir / 'o', '--grid', '20', '--scale', '4')['images'][0]
        names = [Path(o).name for o in r['outputs']]
        self.assertEqual(names, ['a.png', 'a@4x.png', 'a.preview.png'])
        self.assertEqual(load(r['outputs'][1]).size, (80, 60))

    def test_palette_from_hex_colours(self):
        src = picture(self.dir / 'a.png')
        hexes = self.dir / 'pal.txt'
        hexes.write_text('#000000\n#ffffff\n#ff0000\n#0000ff\n')
        out = load(run(src, '--out', self.dir / 'o', '--grid', '20', '--palette', hexes)['images'][0]['outputs'][0])
        used = {c for _, c in out.convert('RGB').getcolors()}
        self.assertTrue(used <= {(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 0, 255)})


if __name__ == '__main__':
    unittest.main()
