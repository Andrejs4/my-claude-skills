# My Claude skills

Skills for [Claude Code](https://claude.com/claude-code), made by Andrejs
Petrovs while working on projects, and kept here so every project can use
them. A skill is a folder of instructions (`SKILL.md`), with scripts beside it
when it needs them; Claude reads it when a request matches what it is for.

The repository is a Claude Code plugin marketplace: each plugin under
`plugins/` carries one or more skills.

## Plugins

None yet. The first one planned turns ordinary pictures into small,
web-ready pixelated images.

## Using them

In any project, in Claude Code:

```
/plugin marketplace add Andrejs4/my-claude-skills
/plugin install <plugin>@my-claude-skills
```

`/plugin marketplace update my-claude-skills` fetches newer versions later.

A single skill can also go to claude.ai on its own: zip its folder (the one
holding `SKILL.md`) and upload it under Settings → Capabilities → Skills.

## Layout

```
.claude-plugin/marketplace.json   the list of plugins
plugins/<plugin>/
  .claude-plugin/plugin.json      the plugin's name, version, description
  skills/<skill>/SKILL.md         a skill: when to use it, and how
  skills/<skill>/scripts/         its scripts, if any
templates/plugin/                 a starting point for a new plugin
```

## Adding a plugin

1. Copy `templates/plugin/` to `plugins/<plugin>/`, and rename
   `skills/skill-name/` to the skill's name.
2. Fill in `plugin.json` and `SKILL.md`; the skill's `description` decides
   when Claude uses it, so name the requests it answers.
3. List the plugin in `.claude-plugin/marketplace.json`.
4. Check it: `claude plugin validate .` and `claude plugin validate plugins/<plugin>`.

## Licence

Copyright (C) 2026 Andrejs Petrovs.

These skills are free software: you can redistribute them and/or modify them
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 2 of the License, or (at your option) any
later version (GPL-2.0-or-later). See [LICENSE](LICENSE).
