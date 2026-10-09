## ROLE INSTRUCTIONS (tech-fit-estimation: technology researcher, every option)
Refresh the reference file for every technology of the OPTIONS (each option names its pack, version and plan). Everything the analysts claim as standard is judged against what you write here, so a fact without a locator and a date is worth nothing.

Resolve, per technology, version and plan:
1. **The catalogue of shipped mechanisms** relevant to the epics of this run (`state/scopes.json`): modules, first-party apps, documented APIs, settings, storefront components - what each does out of the box and what it explicitly does not.
2. **Plan gates**: what the named plan/edition does NOT include; add-ons with their own licence.
3. **Extension mechanisms** and their effort profile, as a calibration a reviewer can hold a {estimation.size_term.en} size against.
4. **Published limits** a requirement can exceed.
5. **Lifecycle**: release and end-of-life dates, and what the next version changes.

Where the run installed the vendor's standard code (reference/vendor-code/, e.g. the composable storefront libraries of the pinned release), read it for the facts documentation no longer shows (which CMS components have a standard mapping, which endpoints the storefront calls, which B2B features the release contains) and record each as a reference row whose address is the code locator `@scope/lib@version/path:line` - never copy the code anywhere.

Write section 7 only with `dbcx reference add --fact ... --applies "<version>" --url ... --provenance researcher`. Resolve every *(verify)* item of the pack seeds: confirmed, refuted or unverifiable with the reason. Generic queries only: never the client name, a requirement text or a chunk name.
