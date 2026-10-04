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
   (it needs the network; if there is none, say so and stop). Framing
   around faces (`--frame face`) also needs OpenCV:
   `pip install opencv-python-headless`; the face model comes with this skill.
   Replacing backgrounds (`--background`) needs rembg:
   `pip install "rembg[cpu]"`. Its model (180 MB) downloads on first use, so
   that needs the network once.
2. **Ask only what's missing, once.**
   - **The grid** (size in real pixels), if the person has one in mind. To
     start from, as old games did: a face 8 × 8 (an icon) to 16 × 16 (a
     clear portrait) or 24–32 (a detailed one); a character 16 × 24 or
     32 × 48; a banner 96–160 wide.
   - If there's no grid but a display size: `--display` and `--block` (screen
     pixels per image pixel, 4 by default). With neither, leave both off:
     the script picks the smallest grid that keeps most of the picture
     (`--detail low|medium|high`).
   - **The crop matters most.** A face that fills a third of the frame gets
     one pixel per eye. Look at the picture first, and frame the subject
     tightly:
     - `--aspect 1:1` crops to a shape, `--focus x,y` (each from 0 to 1)
       moves it, and `--zoom Z` keeps the middle 1/Z each way.
     - For a head-and-shoulders portrait, `--zoom 1.6 --focus 0.5,0.45` frames
       the face. Pictures made alike can share one setting, with no box per
       picture.
     - `--box x,y,w,h` frames one picture exactly.
     - **Portraits whose faces sit in different places** (close-ups,
       torso shots, off-centre): `--frame face` finds each face and crops a
       square around it (`--aspect` for another shape; `--face-fill 0.6` is
       how much of the width the face takes). Check `frames.jpg`, which shows
       every picture with its box. Fix any wrong box in `OUT/crops.json`, then
       run again with `--crops OUT/crops.json`. Listed boxes win; the rest
       are framed as asked. A picture with no face found falls back to the
       centre crop, and the report says so.
3. **Look at the project.** Where will the images show: a web page, a
   canvas game, a favicon, a link preview? That decides the output (below).
   Look for a credits file (CREDITS.md, ATTRIBUTION, credits beside the
   images) and an existing palette to match (`--palette`).
4. **A set** (hero faces, icons, cards) should look like one family:
   - The same grid and framing for all.
   - One small palette, made from the set's own pictures: `--shared-palette
     --colors 12` to `16`.
   - Save it into the project with `--save-palette <dir>/palette.hex`, and
     make later pictures of the set with `--palette <dir>/palette.hex`, so
     they match.
   - Generic retro palettes (DawnBringer, PICO-8) look garish on painted
     faces, with blue and purple specks in the skin. Use them only if the
     person wants that look, best with `--dither floyd`.
   - For portraits shown small (32–64 px on screen), a 32 × 32 grid is a
     good start.
   - Different backgrounds (grey, parchment, sky, watercolour) split a set.
     `--background '#6e6e6e'` cuts out each subject (rembg, on the whole
     picture) and puts it on one flat colour, about 1 s a picture. A mid
     grey hides the cut-out's flaws best. `--background transparent` lets the
     page put any colour behind, but dark hair and beards can get holes that
     show through as specks. If the cut-out spoils a few pictures (pale
     paintings can lose their edges), redo only those without
     `--background`, with the same boxes and palette (`--crops
     OUT/crops.json --palette <saved palette>`), copy them over the first
     results, and pack the sheet again: import the script and call
     `atlas(results, cols, rows, path)`, with `results` the `(name, image)`
     pairs in order.
   - `--atlas 8x8` also packs the results, in file-name order, into one
     sprite sheet (`atlas.png`), with each cell's place in the report: one
     request for the page instead of 64. 64 faces of 32 × 32 come to about
     20–25 KB.
5. **Run it**, into a scratch folder first:

   ```
   python3 <skill>/scripts/pixelate.py photo.png --out /tmp/px --grid 16x16 --aspect 1:1
   python3 <skill>/scripts/pixelate.py faces/ --out /tmp/px --grid 32 --zoom 1.6 --focus 0.5,0.45 \
       --colors 12 --shared-palette --save-palette assets/portraits/palette.hex
   python3 <skill>/scripts/pixelate.py faces/ --out /tmp/px --frame face --grid 32 \
       --colors 12 --shared-palette --atlas 8x8
   python3 <skill>/scripts/pixelate.py banner.jpg --out /tmp/px --display 520 --block 4
   ```

   It prints a JSON report (also saved as `report.json`): the grid and how
   it was chosen, colours used, file sizes, the output files, and what each
   input's metadata says.
6. **Check before handing over.**
   - Up to 3 pictures: look at each `*.preview.png` (the picture beside its
     result) and show them.
   - A batch: the script makes one `contact-sheet.png` instead (and
     `frames.jpg`, the crops). Show only the contact sheet, or the atlas
     scaled up, once; look at `frames.jpg` yourself. If the person doesn't
     want previews, `--preview none`. Raw pictures sent in chat may arrive
     renamed by number: keep a list of which upload became which file.
   - **Tune:**
     - mushy or blurred: a smaller grid, or `--boost strong`;
     - details lost: a larger grid;
     - noisy colours: fewer `--colors`;
     - banding: `--dither floyd`;
     - colours too loud: `--boost none`.
   - For a set (hero faces, icons), use `--shared-palette` so they look
     alike.
7. **Metadata and licence.** The outputs carry no metadata. Tell the person
   what the inputs had: `prompt_excerpt`, `model`, `ai_hints`. Then ask
   which licence applies, suggesting:
   - **Their own work** (drawn, photographed, or generated with a model run
     on their own machine): CC BY-SA 4.0 in their name.
   - **An online image service**, named in `ai_hints` or by the person
     (Perplexity, OpenAI, Midjourney, Firefly, Google…): the service's terms
     come first. Many personal plans allow non-commercial use only. Don't
     put CC BY-SA on these; credit them as "generated with <service>, under
     its terms".
   - **A downloadable model:** it has a licence too. The official Stable
     Diffusion models (1.5, SDXL) allow using their images, commercially too,
     outside a list of banned uses. Community models may forbid selling
     their images, so ask which model if `model` is empty and it matters.
   - **Someone else's picture:** its author and licence. Never guess.

   Add a line per image to the project's credits file, or offer to start one
   beside the images.
8. **Put them in place.** Copy the PNGs where the project keeps images.

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
- `--aspect W:H`, `--zoom Z`, `--focus x,y`, `--box x,y,w,h`: crop first.
- `--frame face`, `--face-fill F`; `--crops FILE` (boxes per picture, JSON).
- `--atlas COLSxROWS`: a sprite sheet of the results.
- `--colors N` (2–256, default 32).
- `--background '#rrggbb' | transparent`, `--bg-model` (default
  isnet-general-use; u2netp is 5 MB but loses bodies and hoods).
- `--boost none|mild|strong` (default mild): colour and contrast after
  shrinking, which averages colours toward mud.
- `--dither none|floyd`.
- `--shared-palette`; `--palette image-or-hex-list`; `--save-palette FILE`.
- `--resample lanczos|box` (lanczos keeps edges sharper).
- `--scale N`; `--preview auto|each|sheet|none`; `--out DIR`.
