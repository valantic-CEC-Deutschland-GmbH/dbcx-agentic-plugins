# sap-commerce pack notes

Platform pack for SAP Commerce (JSP accelerator source, 2211 CCv2 + composable storefront target); no client data.

- **Structural layer** (stable): `adapter.py` (extensions from `extensioninfo.xml`, `requires-extension`, items.xml delta with `autocreate="false"` = extended standard type, spring alias / bean-id overrides, process XML, addon folders, `build.number` / `localextensions.xml` / CCv2 `manifest.json`), `pack.json` snippets (override mechanisms, read order, hosting constraints, critic-2 persona/focus), `labels.<lang>.json` (SAP wording for categories: Storefront, OCC/API, AddOn, Backoffice, Facades, Backend-Core).
- **Derived per project**: standard extensions and standard addons from `hybris/bin/{platform,modules,ext-*}` in the client repo (`derive_knowledge`) – nothing to maintain.
- **Version-pair seed** (`knowledge.json` `_stamp`, `research-seed.md`): deprecation regexes 2205→2211/CCv2, OCC v2 endpoint families, composable storefront CMS component types. Refresh per project with `dbcx render research` (platform-researcher agent); verified facts flow back with `dbcx learn export` to the maintainer.
- Category mapping for waves: `plugin` (addons) and `frontend` last, `core` first.
- Do not run: `ant`, platform start/initialization.
- Repository layout: an on-premise checkout has `hybris/bin/...` at the root; a CCv2 repository wraps it in `core-customize/` (or another wrapper folder). `derive_knowledge` probes the standard dirs at the root and up to two levels below it - a flat-layout assumption derives nothing in CCv2, and the only symptom is the unknown-dependency warning.

- **Snippets** in `pack.json`: `active_units_config` (localextensions.xml authoritative, manifest only adds, no persona granularity, transitive closure, cleanup fan-out of dead units), `override_mechanisms` (four collision mechanisms + the alias/getBeanNamesForType quirk + AspectJ meta-annotation mismatch), `data_script_sources` (ImpEx header rule, macro definitions, `tools/impex_rows.py`), `property_resolution_order`, target `docs_domains` (help.sap.com is a JS SPA: `tools/saphelp.py`, `tools/sapsearch.py`; version-line trap), `content_model_notes` (backend type must be mapped; generate=false autocreate=false marks platform types), `best_practice` (shared-type attribute ownership). `knowledge.json` carries `shared_types_attribute_ownership`, `message_key_tag_families`, `module_name_traps`. The engine classifies scanner hits on `$macro =` lines, unused imports and commented lines by kind.

- **Resolver tools** in `tools/`: deterministic, read-only, callable as `dbcx <tool>` inside a run or `python3 <pack>/tools/<tool>.py` anywhere: `active_extensions` (localextensions.xml as XML,
  manifest extensions[]/storefrontAddons[]/exclude, requires closure; states active / declared-not-provisioned / not-decidable / inactive with
  evidence), `effective_property` (manifest useConfig chain per persona/aspect, masked secret values, files outside the chain),
  `template_diff` (rename-normalised diff against the vendor template the extension was generated from; unchanged / cosmetic / modified / new),
  `process_reach` (start-node reachability, wait-node timeout targets); `impex_rows` counts multi-line quoted rows once, accepts `Type[modifier]`
  headers and reports comment-only files (`--files`). `sap_repo.py` holds the shared layout/XML/properties helpers. The adapter uses them:
  `loaded_in` + `activation_resolved` from active_extensions, `resolve_overrides` (candidate resolution against the standard bean index),
  template diff (scanner `template_copy` bucket), process triggers, AddOn footprints. `knowledge.json check_recipes` are rendered into an analyst
  brief only when the scanner records their trigger for that unit. The `DEP-COCKPITS` deprecation pattern is split into a vendor-verified pattern and `DEP-COCKPITS-UNVERIFIED` (identifiers without a vendor removal record).
  Fixtures: `fixtures/` (impex, process, repo-mini).
