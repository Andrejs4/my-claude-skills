# My Claude skills: notes for Claude

Skills for Claude Code, packaged as a plugin marketplace. README.md has the
layout and how a plugin is added; this file covers the rest.

- Each plugin lives in `plugins/<plugin>/`, with `.claude-plugin/plugin.json`
  and its skills in `skills/<skill>/SKILL.md`. Every plugin is listed in
  `.claude-plugin/marketplace.json`. Start a new one from `templates/plugin/`.
- A skill's `description` (in its frontmatter) is what Claude matches
  requests against: say what it does and the phrases that should call it, and
  what it doesn't cover.
- Keep `SKILL.md` short and practical; put long reference material in files
  beside it and say when to read them. Scripts go in the skill's `scripts/`
  folder and must work from any project: no paths into this repository, and
  any dependency named in the skill with how to install it.
- Skills are used in other people's sessions and in cloud containers: scripts
  may not need network access or secrets unless the skill says so up front.
- Bump a plugin's `version` in `plugin.json` when it changes, so
  `/plugin marketplace update` picks it up.
- Before committing: `claude plugin validate --strict .` and
  `claude plugin validate --strict plugins/<plugin>` must pass, and so must
  `python3 -m unittest discover tests` (Python 3 with Pillow). A script gets
  tests in `tests/`, made on pictures the tests draw themselves.
- Licence: GPL-2.0-or-later (README, LICENSE). Put `"license":
  "GPL-2.0-or-later"` in each `plugin.json`.
