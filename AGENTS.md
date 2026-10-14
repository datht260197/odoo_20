# AGENTS.md — Odoo 20 Community custom addon

Canonical rules for every AI coding session. Obey them over habits from Odoo 17/18/19.
Scope: ONE standalone custom addon. Never edit Odoo core or other addons.

## 0. Verified baseline (checked against odoo/odoo branch `20.0`, `release.version_info == (20,0,0,FINAL)`)
- Python 3.12–3.14 (`MIN/MAX_PY_VERSION`), lint config: `ruff.toml` at Odoo root (target py312).
- Constraints: `models.Constraint('unique (x)', 'msg')` class attributes. Do NOT use `_sql_constraints`.
- Translations in Python: `self.env._("text %s", arg)`; module level: `from odoo.tools.translate import _lt`. Never f-strings/`%`/`.format` inside the translated literal; pass args.
- Access control: **`ir.access`** replaces `ir.model.access` + `ir.rule`.
  File `security/ir.access.csv`, header `id,name,model_id,group_id/id,operation,domain`
  (`operation` ∈ crud subsets; row WITH group = permission, row WITHOUT group = restriction/global rule;
  domains may use `company_ids`, e.g. `['|',('company_id','parent_of',company_ids),('company_id','=',False)]`).
  Do NOT create `ir.model.access.csv` or `ir.rule` records.
- Groups: `res.groups.privilege` (`privilege_id`) groups roles in the Settings UI; users via `res.users.group_ids`
  (not `groups_id`); group XML uses `user_ids`. Check `odoo/addons/base/security/base_groups.xml` and `addons/hr/security/hr_security.xml` as templates.
- Views: `<list>` (never `<tree>`), `invisible/readonly/required="<python expr>"` (never `attrs=`/`states=`), `<chatter/>` in forms.
- Access checks in code: `records.check_access('read'|'write'|'create'|'unlink')`, `has_access(op)`. Old `check_access_rights/check_access_rule` are gone.
- Domains: `from odoo.fields import Domain`.
- Multi-company: `company_id` + `_check_company_auto = True` + `check_company=True` on relational fields (see `hr.employee`).
- HR note: `hr` in 20 uses `hr.version` views (contract data lives on employee versions). Never assume `hr.contract`.
- Manifest default keys: `odoo/modules/module.py::_DEFAULT_MANIFEST`. Use `'license'`, `'version'`, `'depends'`, `'data'`, `'assets'` only if needed; `'application'` only for a top-level app.

**Unverified (re-check before relying):** XML syntax for creating `ir.access` records (CSV is verified); `odoo-bin i18n` subcommand usage (`odoo/cli/i18n.py` exists); anything outside the cloned folders `odoo, addons/{base,mail,hr,contacts}, doc`.
Never trust memory for an API: `grep` Odoo source first (`odoo/orm/`, `odoo/addons/base/`, `addons/<module>/`).

## 1. Project discovery (do once per session, cache in notes, don't repeat)
Find and record: Odoo source path, `odoo-bin`, venv/python, `odoo.conf`, addons_path, dev DB name, PG host/port/user, addon folder, installed modules.
Never invent paths/DB names. If unknown, ask once or report as unverified. Never touch a production DB; run only on a dedicated dev DB (name must clearly be dev/test).

## 2. Data reuse (highest priority)
Before ANY new model/field, grep the source and existing addon, then classify:
- **A** standard field/model suffices → use it.
- **B** extend/link: `_inherit`, Many2one/One2many/Many2many, `related=`, computed non-stored → proceed automatically.
- **C** new stored business field/model needed → **STOP** (see §3).
Reuse: customers/vendors/contacts `res.partner`; internal users `res.users`; companies `res.company`; employees `hr.employee` (only if `hr` is an approved dependency); products `product.template/product.product` (only if `product` approved); currency `res.currency`, country `res.country`, language `res.lang`, etc.
Never duplicate standard data into copied fields. Never add a dependency on an optional module without user approval. Never assume a field exists — verify in source.

## 3. Approval gate for new fields/models (hard stop)
Applies to every new business field or model on any model (incl. `_inherit`). Technical/inherited-only changes (class `_inherit` with views, constraints, methods, no new columns) don't need approval.
Forbidden workarounds: equivalent fields, `fields.Json`/Properties, auxiliary models, raw SQL columns, `ir.config_parameter` or other storage used to dodge approval.
For C, send ONE concise bilingual request (§3a) for all pending schema and wait:
1. Requirement not satisfiable by existing fields
2. Model, technical name, label, type, purpose, new model vs field on existing model
3. Why standard fields/relations are insufficient
4. stored / computed / related / required / indexed / default; relation; ACL & record-rule impact
5. Alternatives + trade-offs
6. Impact on existing data, upgrade, reports, integrations
Do not write the field or code that depends on it before explicit approval. Meanwhile continue independent work. After approval implement everything (Python, views, `ir.access.csv`, translations, tests, manifest) without further questions.

## 3a. Communication language (mandatory)
The user is not fluent in English. Every question, clarification, approval request (§3), assumption or blocker addressed to the user MUST be written in **both Vietnamese and English**, Vietnamese first, each followed by a short plain explanation (what it means, why it matters, what each option changes). Use this layout:
- 🇻🇳 Câu hỏi / đề xuất + giải thích ngắn
- 🇬🇧 Question / proposal + short explanation
Offer concrete options with a recommended default. Keep both versions equivalent and concise. Code, identifiers, commands and file contents stay in English; the final report (§11) is also bilingual.

## 4. Autonomous workflow
Inspect → reuse existing patterns → smallest complete design → implement → focused tests → fix → review diff → report.
Don't ask about routine decisions; state an assumption and proceed. Ask one concise question (bilingual, §3a) only if a missing requirement changes security, data integrity or behavior. No speculative wizards/reports/dashboards/config options/abstractions.

## 5. Engineering rules
- ORM and recordsets only; batch-safe (`@api.model_create_multi`, loops over `self`, `_read_group`/`search_fetch`/prefetch, no per-record search/read in loops).
- Compute/depends/constraints/onchange/inverse only when justified; business rules enforced in Python, not only in UI.
- No manual `commit()`/`rollback()`; no raw SQL unless ORM can't (use `SQL()` with parameters, respect access); minimal `sudo()` with a comment why and which company/user context; no secrets or PII in logs/errors.
- Stable technical names and XML IDs (`<module>.<snake_case>`), model names `module.model`, Odoo/PEP8 style; ruff-clean per Odoo `ruff.toml`.
- Data files load order in manifest: security groups → `ir.access.csv` → data → views → actions → menus → reports.
- Delete behavior explicit (`ondelete=` on Many2one; `@api.ondelete` for blocking deletes). State transitions guarded in methods.
- No custom JS/CSS/OWL when standard components work. Verify any widget exists in Odoo 20 source before using it.
- UI: list/form/search (kanban only if the workflow needs it), logical field order, `help=` on non-obvious fields, statusbar for states, one menu entry per action, no clutter.

## 6. Security (every feature)
Evaluate and implement: ACL rows per group, restriction rows for multi-company, field `groups=`, action authorization in methods (`check_access`), input validation, state rules, ondelete, safe `sudo`. Hidden buttons/menus are NOT security. Never widen access just to silence an AccessError. Tests must include positive AND negative permission cases (user without group gets `AccessError`; other company's records invisible).

## 7. Localization: English source + mandatory Vietnamese (vi_VN)
### 7.1 Completion requirement
Every new or modified user-facing feature MUST have complete Vietnamese translations.
Missing Vietnamese is a release-blocking defect for the affected feature.
Passing Python, XML, lint or unit tests does not waive localization requirements.
The final review must distinguish translation-file validation from actual UI-language verification.
### 7.2 Source strings
Keep source-code and XML strings in English.
Translate every user-facing string: field string/help, selection labels, menus, actions, buttons, placeholders, validation errors, notifications, reports, email templates, QWeb, portal pages, JavaScript and OWL.
Use the translation mechanism supported by the specific Odoo 20 source layer. Python translation APIs do not automatically translate frontend strings.
Python: use verified self.env._() patterns and _lt() only where appropriate.
Never build translated messages using f-strings, % formatting or .format() inside the translated literal. Pass interpolation arguments through the verified translation API.
Never translate technical identifiers, XML IDs, field names, selection keys, internal codes or programmatic values.
### 7.3 Translation files
Maintain i18n/<module>.pot and i18n/vi.po.
Keep PO files UTF-8 and preserve valid metadata, plural rules and placeholders.
After source-string changes, regenerate/update POT, merge into vi.po, and translate every new or changed user-visible entry.
Never replace a complete PO file with a newly generated template.
Do not leave new visible strings untranslated or use the English source as a substitute for Vietnamese.
Reuse established translations from installed Odoo modules when appropriate.
Follow the translation header conventions verified in the installed Odoo 20 source.
### 7.4 Required localization review
Before completion:

Inventory user-visible strings across every changed file, including Python, XML, JavaScript, OWL, SCSS-related templates, reports, emails and portal content.
Check that each applicable source string is extractable by Odoo's translation workflow.
Verify that the corresponding Vietnamese translation exists and is complete.
Check PO syntax, interpolation placeholders, markup and encoding.
Check for untranslated new entries and accidental deletion of existing translations.
Verify representative translated strings using the actual vi_VN language context when runtime access is available.
### 7.5 Loading and runtime verification
Inspect the installed Odoo 20 translation commands and options before executing them.
Use only the verified development database.
Do not run translation overwrite operations blindly; inspect their impact on existing translations first.
Check that Vietnamese is installed and enabled and that the test user/session actually uses vi_VN.
Confirm that updated translations are loaded and visible in the affected UI.
If UI verification is unavailable, report it as unverified rather than claiming success.
### 7.6 Localization completion gate
A feature must not be reported as fully complete while newly introduced user-facing strings lack Vietnamese translations.

The final report must state:

Translation files changed.
Translation validation performed.
Remaining untranslated strings, if any.
Whether Vietnamese was verified in the running UI.
Do not invent legal, tax, accounting or domain-specific terminology. Flag terms requiring business confirmation.

## 8. Verification (run only what the change warrants; focused first)
Use discovered paths; typical sequence (replace placeholders from §1):
1. Static: `python -m compileall <addon>`; XML well-formed (`python -c "import lxml.etree as e,glob;[e.parse(f) for f in glob.glob('<addon>/**/*.xml',recursive=True)]"`); `ruff check <addon>` with Odoo's `ruff.toml`.
2. Install on fresh dev DB: `<python> <odoo-bin> -c <conf> -d <dev_db> -i <addon> --stop-after-init`
3. Upgrade on existing dev DB: `... -d <dev_db> -u <addon> --stop-after-init`
4. Tests: `... -d <dev_db> -u <addon> --test-enable --test-tags /<addon> --stop-after-init` (narrow with `:Class.method`).
Failures: read traceback, fix root cause, rerun only affected checks. Never claim a pass without a completed command and exit status. Report blockers separately from verified results. Tests use `odoo.tests.TransactionCase` (+`tagged('post_install','-at_install')` when depending on other modules' data), cover business rules, constraints, edge/invalid input, security, vi translation.

## 9. Quality gate before "done"
Requirements met · standard models/fields reused · no unapproved fields/models (diff `fields.` / `_name =`) · manifest depends/data complete and ordered · `ir.access.csv` correct · EN source + `vi.po` current · install/upgrade/tests actually run · `git diff` clean of debug prints, `pdb`, secrets, unrelated edits. No "zero defects" promises; give evidence.

## 10. Token discipline
Read targeted excerpts (`grep -n`, `sed -n`), no repeated full-file reads or repo-wide scans, no tutorials, no code before requirements/schema approval, short plans, concise reports, reuse known-good commands from this session.

## 11. Final report format (bilingual, §3a)
**Implemented** · **Reused standard models/fields** · **New fields/models** (none / approved by user: yes) · **Changed files** · **Tests** (exact commands + pass/fail) · **Localization** (EN/VI verified how) · **Remaining risks** (only material/unverified).
If schema approval is pending, output the §3 proposal instead of claiming completion.
