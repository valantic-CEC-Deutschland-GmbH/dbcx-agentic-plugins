# oxid pack notes

- **Seed content** (all marked `*(verify)*` in `research-seed.md`; version claims age fastest): edition facts, the B2B Suite feature list, the B2C feature list, the DACH ecosystem picture, the weakness table (headless, ecosystem size, developer pool, innovation pace, enterprise scale) and the ideal-customer profile.
- **Structural knowledge** (also marked `*(verify)*`): the `as_source` structural layer - `metadata.php` keys (extend, controllers, templates, blocks, settings, events), the `<Class>_parent` class chain and its three failure modes, `services.yaml` DI decoration as the modern override path, the metapackage-name-encodes-the-edition rule, module configuration living in `var/configuration/shops/<shopId>.yaml` from 6.2 onwards, Doctrine migrations as the schema source, per-language `_1/_2` columns and the Enterprise `oxarticles_setN` / `oxv_*` view mechanics, and the Smarty-to-Twig break at v7.
- **Roles = `["target","source"]`**: source is included because a client can plausibly be running an OXID 6.x or 7.x shop today and the unit conventions are unambiguous and inspectable in the repository - modules under `source/modules/<vendor>/<module>` with a `metadata.php`, standard code under `vendor/oxid-esales`.
- **api_name is deliberately honest**: `OXID GraphQL API` is delivered by the OPTIONAL `graphql-base` + `graphql-storefront` modules, not by the core metapackage, and there is no first-party storefront or admin REST API. Everything in `knowledge.json target_api_endpoint_families` is phrased as an operation to check per module release, not as coverage.
- **Content model**: `content_model_name` is "CMS content block" / "CMS-Inhaltsblock" but the pack states plainly that this covers three different mechanisms - core `oxcontent` pages and snippets, developer-level Twig block regions, and licensed Visual CMS widgets - with different editability and licence implications.
- **No `adapter.py`** by design, so this pack cannot scan a source repository yet; the `as_source` snippets are written for a human or agent reading the tree by hand.

A researcher must resolve these first, in this order:
1. The exact compilation and edition (metapackage name in `composer.json`/`composer.lock`) - almost every feature question below depends on CE vs PE vs EE vs B2B Edition.
2. Whether multi-shop, Visual CMS and the B2B Suite are actually licensed, rather than assumed from the feature tables.
3. The activation state: `var/configuration/shops/*.yaml` for 6.2+, or an exported `oxconfig` module list from the client for older shops - no module may be called dead before that arrives.
4. The `graphql-storefront` module version and its real query/mutation list, especially around checkout, payment and CMS content.
5. Whether the shop is on Smarty or Twig, and how many template overrides exist - that number drives the upgrade or replatform estimate more than anything else.
6. Hoster facts (PHP version, cron entries, cache backend, storage for `source/out`) - none of them are in the repository.
