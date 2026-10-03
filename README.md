# My Claude skills

Skills for [Claude Code](https://claude.com/claude-code), made by Andrejs
Petrovs while working on projects, and kept here so every project can use
them. A skill is a folder of instructions (`SKILL.md`), with scripts beside it
when it needs them; Claude reads it when a request matches what it is for.

The repository is a Claude Code plugin marketplace: each plugin under
`plugins/` carries one or more skills.

## Plugins

- **web-pixel-images**: turns ordinary pictures (photos, renders,
  AI-generated images) into small, web-ready pixelated images with an
  old-game look. It crops, shrinks to a coarse grid of real pixels (a
  16 × 16 face, a 128-wide banner), limits the palette, strips metadata, and
  saves tiny PNGs: a 32 × 32 face is about 450 bytes. For a set (hero
  faces, icons) it can frame each picture around its face, gives all one
  small palette, saved for later additions, packs them into a sprite sheet
  (64 faces in about 22 KB), and makes one contact sheet instead of a
  preview each. The face detector is
  [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
  (MIT licence, in the skill's `models/`), run with OpenCV. It also asks
  which licence applies and adds credit lines. Needs Python 3 with Pillow.
  Ask Claude to "pixelate this image for the web", or for "16 × 16 pixel
  portraits of these faces".

## Using them

**On your own computer** (Claude Code in a terminal or the desktop app), in
any project:

```
/plugin marketplace add Andrejs4/my-claude-skills
/plugin install <plugin>@my-claude-skills
```

`/plugin marketplace update my-claude-skills` fetches newer versions later.

**In a cloud session** (Claude Code on the web or in the app), `/plugin`
isn't available. Add this repository to the session instead: pick it
alongside the project when starting one, or ask Claude to "add the
Andrejs4/my-claude-skills repository". Its skills then load from
`.claude/skills/`, which links to each plugin's skills.

A single skill can also go to claude.ai on its own: zip its folder (the one
holding `SKILL.md`) and upload it under Settings → Capabilities → Skills.

## Layout

```
.claude-plugin/marketplace.json   the list of plugins
plugins/<plugin>/
  .claude-plugin/plugin.json      the plugin's name, version, description
  skills/<skill>/SKILL.md         a skill: when to use it, and how
  skills/<skill>/scripts/         its scripts, if any
.claude/skills/<skill>            a link to plugins/<plugin>/skills/<skill>, for cloud sessions
templates/plugin/                 a starting point for a new plugin
tests/                            tests for the skills' scripts
```

## Adding a plugin

1. Copy `templates/plugin/` to `plugins/<plugin>/`, and rename
   `skills/skill-name/` to the skill's name.
2. Fill in `plugin.json` and `SKILL.md`; the skill's `description` decides
   when Claude uses it, so name the requests it answers.
3. List the plugin in `.claude-plugin/marketplace.json`, and link each skill
   for cloud sessions: `ln -s ../../plugins/<plugin>/skills/<skill> .claude/skills/<skill>`.
4. Check it: `claude plugin validate --strict .` and
   `claude plugin validate --strict plugins/<plugin>`, and run the tests:
   `python3 -m unittest discover tests` (needs Pillow).

## Licence

Copyright (C) 2026 Andrejs Petrovs.

These skills are free software: you can redistribute them and/or modify them
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 2 of the License, or (at your option) any
later version (GPL-2.0-or-later). See [LICENSE](LICENSE).
