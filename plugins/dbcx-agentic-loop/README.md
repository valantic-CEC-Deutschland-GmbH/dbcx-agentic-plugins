# dbcx agentic loop

A Claude Code plugin that runs an evidence-first consulting analysis on its own: analysts write statements about the client's
subject, each with its source, and critics from the client side and from the standard side, each with separate evidence (the
client's material, the external standard), score every statement until it passes. Client-persona reviewers then read the result
like the client's stakeholders would. What comes out are formula-driven Excel deliverables in which every figure is a reviewed,
evidenced claim.

## Requirements

- Claude Code: the desktop app's Code tab or the terminal. Plugins published to your organisation need version 2.1.273 or later.
- Python 3.11 or later. The setup installs the packages the plugin needs.

## First steps

Say these in Claude Code:

1. "Set up the dbcx plugin" - checks Python and the packages, installs what is missing, runs a short self-test.
2. "Show me how the dbcx plugin works" - opens the onboarding page (English and German, with a live demo of the dashboard).
3. "Initiate the project with the dbcx agentic loop plugin for <client> …" - creates the engagement folder and the first run and
   asks for what it needs.

Then "Prepare for task 1", "Execute the plan", "How far are we?", "Pause the run", "Resume the run". While a run works, a local
dashboard opens in your browser: answer questions, send hints, pause.

## Methods

- `code-analysis` - a shop code base ahead of a platform move
- `ea-landscape` - enterprise / CX architecture: as-is landscape and target architecture
- `requirements` - requirements for a system, from client documents and workshops
- `tech-scoring` - technology shortlist with strategic scoring
- `tech-fit-estimation` - fit and effort of a requirement list against one or several solution options, or across the systems of one solution (shortlists, partner-estimated parts, gaps routed by an architect agent)

Own methods: when none of the five fits, say "Initiate the project with the dbcx agentic loop plugin – we need our own method for
<task>". Claude defines the method with you in a short interview - a new one (custom), or a copy of one of the five that you adapt
(derived) - builds it, tests it on a small example and shows you the example workbook before the first run. An own method lives in
the engagement's `methods/` folder; "Save our method to my library" keeps a copy in your personal library (`~/.dbcx/methods/`), and
"Use a method from my library" brings it into a later engagement. Change it between runs, never during one ("Change our method").
The plugin's five methods stay untouched.

## Where things live

Everything a run produces stays in the engagement folder you choose, one per client:

```text
<client>/
  engagement.json    client, language, gate personas
  input/<date>/      the client's material, by delivery date
  runs/<run>/        one folder per method run; its deliverables/ holds the workbooks the client receives
  overrides/         your settings, wording and knowledge for this engagement ("Optimize the project setup")
  methods/           your own methods for this engagement ("Create our own method")
  handover/          released results a later run builds on
```

The plugin never writes into its own folder: it is replaced on every update, and everything that belongs to you lives in the
engagement folder.

## Sending learnings to the maintainer

Every run records what went well and what did not. Say "Export the learnings": the plugin shows you everything that would leave
the project, replaces client names, and writes one file under `<client>/learnings/exports/`. Send that file to the plugin
maintainer; the name mapping stays with you.

## Privacy

- The dashboard is local: it listens on 127.0.0.1 only, with a token in its URL, and is not reachable from other machines.
- The plugin itself sends nothing anywhere. The agents' web research goes through a checked tool that refuses client names,
  internal paths and locators.
- The client's material is read-only for every agent; nothing leaves the engagement folder unless you send it.
