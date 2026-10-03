---
name: web-pixel-images
description: Turn ordinary pictures (photos, renders, AI-generated images) into small, web-ready pixelated images with an old-game look, 8-bit or 16-bit style. It crops, shrinks to a coarse grid of real pixels, limits the palette, strips metadata, saves tiny PNGs and credits them. Use for "pixelate this", "make a pixel or retro version", "turn these into pixel portraits, sprites, icons or banners", and for many at once, such as a set of hero faces. Not for drawing new pictures from nothing, nor for plain resizing without the pixel look.
---

# Web pixel images

A pixelated image here means a picture rebuilt from a small grid of real
pixels (a 16 × 16 face, a 128-wide banner) in a limited palette, saved as a
tiny PNG that the page scales up crisply. A plain resize can't do it: it
blurs, or leaves hundreds of in-between colours. `scripts/pixelate.py`, in
this skill's folder, does the work.

## Steps

1. **Pillow.** `python3 -c "import PIL"`; if that fails, `pip install pillow`
   (it needs the network; if there is none, say so and stop).
2. **Ask only what's missing, once.**
   - **The grid** (size in real pixels), if the person has one in mind. To
     start from, as old games did: a face 8 × 8 (an icon) to 16 × 16 (a
     clear portrait) or 24–32 (a detailed one); a character 16 × 24 or
     32 × 48; a banner 96–160 wide.
   - If there's no grid but a display size: `--display` and `--block` (screen
     pixels per image pixel, 4 by default). With neither, leave both off:
     the script picks the smallest grid that keeps most of the picture
     (`--detail low|medium|high`).
   - **The crop.** Look at the picture first. Use `--aspect 1:1` (with
     `--focus x,y`, from 0 to 1, to move it), or `--box x,y,w,h` to frame a
     face.
3. **Look at the project.** Where will the images show: a web page, a
   canvas game, a favicon, a link preview? That decides the output (below).
   Look for a credits file (CREDITS.md, ATTRIBUTION, credits beside the
   images) and an existing palette to match (`--palette`).
4. **Run it**, into a scratch folder first:

   ```
   python3 <skill>/scripts/pixelate.py photo.png --out /tmp/px --grid 16x16 --aspect 1:1
   python3 <skill>/scripts/pixelate.py faces/ --out /tmp/px --grid 16 --colors 24 --shared-palette
   python3 <skill>/scripts/pixelate.py banner.jpg --out /tmp/px --display 520 --block 4
   ```

   It prints a JSON report (also saved as `report.json`): the grid and how
   it was chosen, colours used, file sizes, the output files, and what each
   input's metadata says.
5. **Check before handing over.**
   - Up to 3 pictures: look at each `*.preview.png` (the picture beside its
     result) and show them.
   - A batch: the script makes one `contact-sheet.png` instead. Show only
     that, once. If the person doesn't want previews, `--preview none`.
   - **Tune:**
     - mushy or blurred: a smaller grid, or `--boost strong`;
     - details lost: a larger grid;
     - noisy colours: fewer `--colors`;
     - banding: `--dither floyd`;
     - colours too loud: `--boost none`.
   - For a set (hero faces, icons), use `--shared-palette` so they look
     alike.
6. **Metadata and licence.** The outputs carry no metadata. Tell the person
   what the inputs had: `prompt_excerpt`, `model`, `ai_hints`. Then ask
   which licence applies, suggesting:
   - **Their own work** (drawn, photographed, or generated with a model run
     on their own machine): CC BY-SA 4.0 in their name.
   - **An online image service**, named in `ai_hints` or by the person
     (Perplexity, OpenAI, Midjourney, Firefly, Google…): the service's terms
     come first. Many personal plans allow non-commercial use only. Don't
     put CC BY-SA on these; credit them as "generated with <service>, under
     its terms".
   - **A downloadable model:** it has a licence too. Community models may
     forbid selling their images, so ask which model if `model` is empty and
     it matters.
   - **Someone else's picture:** its author and licence. Never guess.

   Add a line per image to the project's credits file, or offer to start one
   beside the images.
7. **Put them in place.** Copy the PNGs where the project keeps images.

## Output for the web

The small PNG is the result; the page scales it up:

```css
img.pixel { image-rendering: pixelated; }   /* no blur when scaled up */
```

Show it at a whole multiple of its grid (a 16 × 16 face at 48 or 64 px), so
every block is the same size. On a canvas, set
`ctx.imageSmoothingEnabled = false` before drawing. Where nothing scales
crisply (favicons, link previews, app stores), add `--scale 4` (or what
fits) for a copy already scaled up by whole pixels.

## Options

- `--grid WxH | W | xH`: the grid; a missing side follows the aspect.
- `--display WxH` with `--block N`: grid from display size; `--detail`: the
  automatic grid's level.
- `--aspect W:H`, `--focus x,y`, `--box x,y,w,h`: crop first.
- `--colors N` (2–256, default 32).
- `--boost none|mild|strong` (default mild): colour and contrast after
  shrinking, which averages colours toward mud.
- `--dither none|floyd`.
- `--shared-palette`; `--palette image-or-hex-list`.
- `--resample lanczos|box` (lanczos keeps edges sharper).
- `--scale N`; `--preview auto|each|sheet|none`; `--out DIR`.
