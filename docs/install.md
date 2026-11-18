# Install and update

These are [Agent Skills](https://agentskills.io/specification): each folder has a `SKILL.md` entry point. They require an agent that can read your repository. The knowledge helpers need **Python 3.10+** and **Git**; they have no package dependencies. No MCP server, cloud service, paid API or Obsidian plugin is required by the bundle.

## With npm

The package is [`project-spec`](https://www.npmjs.com/package/project-spec) on the npm registry, with one command of the same name. It needs Node 18+ in addition to Python. Nothing has to be installed first:

```sh
npx project-spec install --claude      # or --codex, or --dir knowledge/tooling
npx project-spec serve                 # the viewer for the project in the current folder
npx project-spec build --out FILE      # the same viewer as one file, to show on a server
npx project-spec coverage              # what the code has that no spec page mentions yet
```

Then ask your agent to use the `project-knowledge` skill ([example prompts](workflows.md#example-prompts)).

To pin one version for everyone on a project, add it as a development dependency:

```sh
npm install --save-dev project-spec
```

The lockfile then pins the version, and `npm update project-spec` moves it forward. The command keeps every copy of the skills in step with that version:

```sh
npx project-spec status    # where the copies are and whether each is current
npx project-spec update    # refresh every copy that status lists
```

`status` and `update` look in `~/.claude/skills`, `~/.codex/skills` and the usual folders of the current project (`knowledge/tooling`, `.claude/skills`, `.codex/skills`, `.agents/skills`). `update` refreshes what is there and adds nothing new; `install` adds. A copy you edited by hand is not replaced unless you pass `--force`, and the old files are kept under `~/.project-spec/backups` first. `--skills project-knowledge` limits an install to the skills you name.

A copy of a skill holds its instructions and, for `project-knowledge`, four helper scripts: about 2,900 lines, nothing else. The viewer page stays in the package and is opened with `npx project-spec serve`. `install --with-viewer` adds the page to a copy, for a place where the helpers run without Node (a Python-only build step, for example); `install --no-viewer` takes it out again. `update` keeps a copy as it is: with the viewer if it has one, without if not. Copies made by versions before 0.10.0 have the viewer and keep it until you run `install` with `--no-viewer` for their folder.

To run the unreleased version from this repository, use `npx github:WorldStoryCm/project-spec-skills status` in place of `npx project-spec status`.

## Claude Code plugin

The repository is also a plugin marketplace for Claude Code. Inside Claude Code:

```text
/plugin marketplace add WorldStoryCm/project-spec-skills
/plugin install project-spec@project-spec-skills
```

The two skills then appear as `/project-spec:project-knowledge` and `/project-spec:spec-change`, and Claude Code updates them with the plugin. The plugin does not add the `project-spec` command; ask the agent to open the viewer (the plugin carries the page), or use `npx project-spec serve`.

## Codex

Ask the built-in skill installer:

```text
Install these skills from WorldStoryCm/project-spec-skills:
skills/project-knowledge
skills/spec-change
```

If you already have a skill with the same name, compare versions before replacing it. The installer in Codex handles its own destination. In Codex you can name a skill with `$name`, for example `$spec-change`.

## Claude Code, by hand

Copy the whole skill folder (it contains the references and helper scripts, and no viewer: use `npx project-spec serve` for that) to one of:

- `~/.claude/skills/<name>/` to use it in all your projects, or
- `.claude/skills/<name>/` inside one project.

```sh
git clone https://github.com/WorldStoryCm/project-spec-skills.git
mkdir -p ~/.claude/skills
cp -R project-spec-skills/skills/project-knowledge ~/.claude/skills/
cp -R project-spec-skills/skills/spec-change ~/.claude/skills/
```

Then ask in plain language, or invoke a skill by name with `/<name>`, for example `/spec-change`. Claude Code finds a skill from its description, so an ordinary request often picks the right one.

## Any agent with repository access

Clone this repository, then ask the agent to read the chosen `skills/<name>/SKILL.md` and follow it in your target project. Keep that skill's directory intact so its references and scripts resolve. Use your host's documented installation mechanism if it supports skills. Hosts other than Codex and Claude Code have not been integration-tested, and the format change described in [VALIDATION.md](../VALIDATION.md) has not yet been tested with an agent on any host.
