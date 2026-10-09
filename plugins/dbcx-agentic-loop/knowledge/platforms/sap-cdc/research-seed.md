## Research topics – SAP Customer Data Cloud (target, brownfield extension)
Seed for the engagement research (`dbcx render brief research`). Typical case: a client already runs SAP Customer Data Cloud (CDC), usually with SAP Commerce Cloud, in one country and adds a country / site / brand. Every line is a hypothesis *(verify)* until it is confirmed with a URL, the date and a verbatim quote for the client's tenant (licences, data center, site structure). The verified product facts are in reference-cache.md (read 2026-10-05); this file holds only what the documentation does not settle or what depends on the tenant.

### 1. Licence, packaging, tenant baseline (ask first)
- Which products are licensed: Customer Identity, Customer Consent (incl. ECPM: lite registration, communication topics, double opt-in), CIAM for B2B; which premium components are activated (IdentitySync, Data Store, Identity Query Tool, Hosted Pages)? *(verify)*
- Licence tier and remaining headroom: the Acceptable Use Policy rates, federated-site count, application-key quota and the B2B organization cap (10 % of allocated B2B users) are per partner and shared by every site, so a new country consumes the same allowance *(verify)*
- Does a new country or site change the commercial metric or require a contract change? *(verify)*
- Data center of the existing tenant (US1, EU1, AU1, EU2/Azure, CN1, ...) and whether the new country needs a different one (residency law) *(verify)*
- Existing site structure: single site, site group with a dummy parent, or a group with a live parent site; SSO segments; Central Login Page in place? *(verify)*
- Is the tenant on the new consent solution (per-locale versions) or still on the legacy solution (frozen since 30 June 2023)? *(verify)*
- Account model of the site group: One Account or the legacy lite-account model (fixed per site group, no migration of existing sites) *(verify)*
- Security Enhancements toggle state (it removes seamless iframe SSO) and strict schema validation state (on by default only for sites created after 10 December 2025) *(verify)*

### 2. Site / site-group decision for the new country
- Child site in the existing site group (shared user base, schema, consent statements, approval workflows, extensions) or a separate site / site group (separate user base, configuration rebuilt or copied)? The decision is effectively one-way *(verify)*
- Does the 1000-custom-field limit count per site group or per child site when the group schema is used? *(verify)*
- Can a child hold child-only fields (accounts.setSchema scope "site"), or only required-flag overrides, and does the Schema Editor show them? *(verify)*
- Does strict validation of a new child created after 10 December 2025 follow the parent or the child's creation date? *(verify)*
- Which policies must differ for the new country (password, verification, TFA, RBA, CAPTCHA, email templates), and are they in the short list a child may override? *(verify)*
- Will social login apps be shared with the new site (identical permissions required) or registered per country? *(verify)*

### 3. Customer Identity, screen-sets, front end
- Is the new country's language among the 15 built-in UI Builder locales, or does it need a full translation CSV for every screen-set of the collection? *(verify)*
- Were existing screen-sets changed with Advanced Customization (no longer editable in the UI Builder)? *(verify)*
- Country-specific registration rules (minimum age other than the COPPA 13+ gate, mandatory fields, address formats): screen-set JavaScript, an OnBeforeAccountsRegister extension, or an undocumented setting? *(verify)*
- Hosted Pages availability in the tenant's data center (documented: US1 incl. au1/eu1, and EU2) and CNAME / certificate lead time for a new top-level domain (support ticket) *(verify)*
- Cross-domain SSO between the existing and the new country domain: CLP, storageDomainOverride, custom API domain prefix, certificate per root domain; SSO segments do not work with a CLP *(verify)*
- Passwordless, passkeys or phone login for the new market: SMS provider coverage for the country, FIDO RP domain per site *(verify)*

### 4. CIAM for B2B
- Can one site group route organization approvals by country (approval workflows are per site group: max 3 paths x 3 steps, 10 approver emails per step), or does that need a remote approval consumer? *(verify)*
- Do human approvers for the new country exist as console IT Admins with Organization Workspace write permission? *(verify)*
- Can custom organization attributes be passed to accounts.b2b.registerOrganization and shown on the standard OrganizationRegistration screen-set (fixed fields and mappings)? *(verify)*
- How are SAP Commerce B2B unit hierarchies represented when CDC has no nested organizations (business entities, Commerce-side units)? *(verify)*
- Default and maximum of memberLimit per organization; behaviour of accounts.b2b.auth.getAssets (40 calls/s per partner) when Commerce calls it on every login *(verify)*
- Can a new B2B language go live with partial translations (the docs require all required translations before activation)? *(verify)*
- Is Bring Your Own Identity still SAML only, and is OIDC planned? *(verify)*
- Can Authorization Workspace objects (applications, asset types, policies, conditions) and approval workflows be exported / imported between environments or site groups? *(verify)*
- The standard S/4HANA -> CDC iFlow is one-way: does the landscape need CDC-originated organizations in the ERP (custom), and several sales organizations or countries per iFlow configuration? *(verify)*

### 5. Consent, preferences, marketing
- New country legal texts: new locale of a shared statement or a separate parent-site statement active only for the new site, and who signs off? *(verify)*
- Behaviour for existing users who first log in on the new site in a new language (a missing locale template blocks login without a default locale; a locale switch may force re-consent; strict vs non-strict mode) - test matrix *(verify)*
- Email-channel double opt-in on communication topics: the topics page and the double opt-in page contradict each other *(verify)*
- SMS double opt-in needs an external verifier on the communicationUpdated webhook - who builds and hosts it? *(verify)*
- Migration of an existing subscriber base with double opt-in proof (accounts.importLiteAccount does not import the double opt-in data) *(verify)*
- Consent Vault retention (global, up to 84 months) and consent-level retention (fixed at creation) against the new country's legal retention *(verify)*
- Emarsys: one Emarsys account per country or a shared one; filter rules; marketing.email locale per language; connector availability in the tenant's data center (documented AU1, EU1/EU2, US1; not on global site groups) *(verify)*
- Does the Emarsys connector sync communication topics per country, and how are they mapped? *(verify)*
- SAP Marketing Cloud (if still in the landscape): own marketing area per country? *(verify)*

### 6. Data model, extensibility, integration
- Do existing webhook consumers filter events by apiKey (in a site group every subscribed site receives the new site's events), and which notification version is in use (1.x marked deprecated)? *(verify)*
- Webhook events per message: 100 (console page) vs 500 for version 3.0 (accounts.webhooks.set reference) - documentation conflict *(verify)*
- Do existing extensions branch per site, and is a child URL override acceptable (it stops cascading from the parent)? Current timeouts, fallback policies and hosting SLA *(verify)*
- Current number of dataflows and scheduled dataflows against the per-partner defaults (25 / 25 / 5 full extracts), and will SAP raise them on request? *(verify)*
- Data Store in use or licensed; Data Field Access (Early Adopters Program) available to the tenant? *(verify)*
- Migration of the new country's existing users: source hash algorithm supported, federated identities (cannot be imported), downstream sync because imports fire no webhooks except subscriptionUpdated *(verify)*
- Is MDI in the landscape, and is its inbound-only direction sufficient? *(verify)*
- Do client integrations rely on HTTP status codes (CDC returns HTTP 200 with an errorCode by default)? *(verify)*
- NAT IP allowlisting on customer endpoints (extensions, webhooks, SFTP), and the IP address release of 26 July 2026 reflected in firewall rules *(verify)*

### 7. Environments and configuration promotion
- How is configuration promoted today (Copy Configuration Tool, scripts, manual)? The tool covers schema, screen-sets and policies only, with no rollback and no field removal *(verify)*
- Which other objects need scripted or manual deployment: extensions, webhooks, dataflows, consent statements, communication topics, permission groups and applications, site settings, SSO / CLP, social apps, B2B objects - none of them is listed for the tool *(verify)*
- Are there separate CDC sites per environment and country, and how many API keys and applications exist? *(verify)*
- Load or penetration tests for go-live must be coordinated with SAP in advance - lead time *(verify)*
- Can SAP's Project Delivery Framework templates (Project-Fit Blueprint, Configuration and Data Mapping, Project Scorecard) be obtained for the engagement? *(verify)*

### 8. SAP Commerce Cloud integration (brownfield)
- Integration in use: Integration Extension Pack module sap-customer-data-cloud (gigya* extensions) or the legacy GConnector (deprecated June 2021)? Accelerator (gigyaloginaddon / gigyab2bloginaddon, deprecated) or composable storefront (@spartacus/cdc)? *(verify)*
- One CDC site (API key) per Commerce base site, or several base sites on one CDC site? GigyaConfig, field mapping (to be maintained for all related sites), session configuration and OAuth client per base site *(verify)*
- B2B user replication: dataflow (new users only, minimum 10-minute interval) or webhook per base site (/gigyab2bwebservices/v1/<baseSiteId>/b2bwebhook)? *(verify)*
- JDK 21 line (2211-jdk21.x): does the CDC custom OAuth grant (GigyaCustomTokenGranter) work unchanged with the new authorizationserver, and together with the authorization code + PKCE flow the composable storefront requires? The gigyaservices page lists oauth2commons for JDK 21 but does not describe the flow *(verify)*
- gigyauserdeleteservices (S3) is removed with 2211-jdk21.1: is the webhook replacement in gigyawebservices configured? *(verify)*
- Which CDC features the current licensed composable storefront release of @spartacus/cdc covers beyond the 2211 help page (read the licensed package from the SAP repository, never the open-source repository) *(verify)*
- Documented gaps still valid on the current release: no cart merge on CDC login, no profile update via screen-sets on CDC global sites, refresh tokens not supported, B2B units not managed from the storefront *(verify)*
- Consent templates replicated from CDC to Commerce through the 'Replicate-Consent-Template' integration flow: per base site, and does it handle per-locale versions? *(verify)*

### 9. Effort calibration (estimator guidance, not facts)
- SAP's Recommended Staffing names sponsor, privacy / legal, PM, technical architect, technical lead, data lead, functional lead, UX lead, mobile developers and QA; how much of that a country rollout needs depends on the site-group decision *(verify)*
- Typical sizes per mechanism are in the pack snippet effort_rules; calibrate them with the client's last rollout if one exists *(verify)*
