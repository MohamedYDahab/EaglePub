# Odoo 19 build notes — EaglePub

Things this catalogue learned the hard way. Each entry cost real debugging time,
so read this before porting or writing a module rather than after.

---

## 1. Odoo 19 API changes that bite silently

These do **not** raise. They fail quietly, which is why they cost so much time.

| What changed | Symptom | Fix |
|---|---|---|
| `_sql_constraints` no longer supported | Constraint is never created. A `CHECK(amount >= 0)` accepted `-5000` | Use `_name = models.Constraint('CHECK(...)', 'message')` as a class attribute |
| `res.groups.category_id` removed | Install fails: `Invalid field 'category_id' in 'res.groups'` | Use `privilege_id` pointing at a `res.groups.privilege` record |
| Search view `<group expand="0" string="...">` | View validation error, module won't install | Bare `<group>` — `expand` and `string` are no longer valid there |
| `<tree>` → `<list>` | Parse error | Also `view_mode: 'tree'` → `'list'` in actions, and `/tree/` → `/list/` in xpaths |
| `product.packaging` gone | Model not found | Replaced by `product.uom` (`product_id` + `uom_id` + `barcode`) |
| `uom.uom` reworked | `category_id` missing | Now `relative_uom_id` + `relative_factor`; `factor` is a computed **absolute** quantity |
| `name_get()` removed (since 17) | — | `_compute_display_name` |

### `display_type` means opposite things on two models

The single nastiest one found. A real line is:

- `account.move.line` → `display_type == 'product'` — **truthy**
- `sale.order.line` → `display_type == False` — **falsy**

A single `if line.display_type: continue` silently skipped **every** invoice line and the
first commission run returned nothing at all. Always test explicitly:

```python
if line.display_type != 'product': continue        # invoice lines
if line.display_type: continue                     # order lines
```

---

## 2. QWeb / OWL traps

**`String` is not defined in QWeb's compiled scope.** `t-on-click="() => this.press(String(d))"`
throws `TypeError: v2 is not a function` on every click. The manager PIN keypad rendered
perfectly and did nothing for days because of this. Coerce inside the JS method instead.

**`%%` collapses inside XML attributes.** QWeb templates live in XML, so `'%.1f%%'` becomes
an invalid format string and breaks PDF rendering. Format numbers in Python and pass strings
to the template, or avoid `%` formatting there entirely.

**`message_post(body=...)` escapes plain strings.** `<b>` prints as `&lt;b&gt;`. Use
`markupsafe.Markup` — its `%` operator still escapes the interpolated values, so filenames
stay safe.

**POS model records cannot reach the store.** They see `this.models[...]` only — no
`env.services`. Resolve what you need from the record's own relations, or expose an
overridable getter on the model.

---

## 3. Things that need a server restart

`-u module` updates the **database** but not the code already loaded in the long-running
Odoo process. Two symptoms seen in one session:

- **Python changes** — edited a method, upgraded, and the old behaviour persisted
- **A new asset file added to a manifest** — `_get_asset_paths` (fresh process) listed it,
  but bundles served by the running server never included it

```bash
docker compose restart odoo19
```

Editing an *existing* asset file does not need this. Adding one does.

---

## 4. Caches that will lie to you

**POS keeps loaded data in IndexedDB** (`point-of-sale-<config>-<db>`). A policy showed
`max_discount: 25` when the database said `10`, and newly-added fields came through null.
Clear it before concluding anything about POS data:

```js
indexedDB.databases().then(d => d.forEach(x => indexedDB.deleteDatabase(x.name)))
```

**Asset bundles** are cached as `ir.attachment` rows *and* by the browser. Clearing the
first does not clear the second, and the bundle URL may not change:

```sql
DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';
```

**`git show HEAD:file` applies the checkout filter.** With `core.autocrlf=true` it prints
CRLF even when the repository stores LF. Use `git ls-files --eol` or `git cat-file blob`
to see what is actually stored — measuring the working tree told the opposite story.

---

## 5. What automated checks do **not** catch

Every module here installed clean, upgraded clean, and reported zero JS load failures while
carrying real bugs:

- The PIN keypad threw on **every keypress** — the error only fires in a click handler
- Cashier policies silently stopped applying under `pos_hr`
- The OCR sample reader returned a complete, plausible bill for a document it never opened

**Click the software.** Install-clean is not works.

---

## 6. Apps Store conventions used across this catalogue

**The store sanitises `static/description/index.html`.** Observed on a live listing: it
drops `background` (solid *and* gradient), `opacity`, and `position:absolute`, while keeping
`color`, `border`, `padding`, `border-radius`.

> Never let contrast depend on a background. An earlier revision used white text on dark
> panels and 37 elements rendered white-on-white.

Check before publishing — this must be zero:

```bash
grep -coiE 'color:\s*#(fff|ffffff|f[0-9a-f]{5})' static/description/index.html
```

**Never point `<img>` at a file that does not exist** — the store renders a broken image.
Leave a comment naming the shots still to capture instead.

**House page structure:** hero → the problem → what it does → screenshots →
*"What this app does not do"* → requirements → support. The honesty section is deliberate:
it costs a few sales and saves more refunds.

**Support block** (all pages): WhatsApp `https://wa.me/201007802335` in green
`#16A34A`/`#15803D`, Email in aubergine `#714B67`, both addresses repeated as plain text.

**Palette:** `#714B67` aubergine, `#3B2436` dark plum, `#4A2F43`, body `#374151`,
muted `#6B7280`, surface `#FAF5F9`, page `#F6F7F9`.

---

## 7. Product patterns that work here

**Base + paid children + free bridges.** From the market scan: Emipro's `$56.81` Connector
Engine outsells every one of their own `$636` connectors because it is the mandatory
dependency. Publish the free base **first** — the store cannot resolve a paid app whose
dependency is not yet listed.

**Bridges use `auto_install: True`** and depend on both sides. A correctness fix nobody
remembers to install is not a fix. Expose **one overridable hook** rather than making the
bridge reimplement a method:

- `_collect_for(plan, user)` — commission sources
- `_eaglepub_policy_for(order)` / `eaglepubPolicySource` — who a POS policy belongs to

**Licensing:** paid ⇒ `OPL-1` + `price` + `currency: 'USD'`. Free ⇒ `LGPL-3`.
A paid module without a `price` lists as a free download.

---

## 8. Environment

| | |
|---|---|
| Code | `C:\odoo-dev\odoo17\addons\EaglePub` (branch `19.0`) → `/mnt/extra-addons` |
| Compose | `C:\odoo-dev\docker-compose.yml`, service `odoo19`, port **8019** |
| Config | `C:\odoo-dev\odoo19\config\odoo.conf` |
| Clean test DB | **`v19-community`** — Community-only, all modules installed |

**Enterprise addons are deliberately not mounted for `odoo19`** (line ~105 of the compose is
commented out), and `addons_path` matches that. If a database has enterprise modules marked
installed without the files present, its Settings page dies with
`"res.config.settings"."enable_ocn" field is undefined` — that is a missing mount, not a bug
in these modules.

```bash
# install / upgrade
docker exec odoo-dev-odoo19-1 odoo -d v19-community -i <module> \
    --config=/etc/odoo/odoo.conf --stop-after-init --log-level=warn

# shell
docker exec -i odoo-dev-odoo19-1 odoo shell -d v19-community \
    --config=/etc/odoo/odoo.conf --log-level=error --no-http < script.py
```

**`odoo shell` does not commit.** Seed data vanished twice before this was noticed — call
`env.cr.commit()` explicitly.

---

## 8b. Seeding sales history for testing

Two traps, both found while seeding the demand forecast module:

**`action_confirm` overwrites `date_order`.** `_prepare_confirmation_values` stamps it with
*now*, so back-dated orders all land in the current month. Write the date **after**
confirming:

```python
order.action_confirm()
order.write({'date_order': when})
```

**`negative_stock_restriction` blocks bulk seeding** in hard mode. It has a documented
bypass hook — `order.with_context(skip_neg_stock_check=True).action_confirm()` — which is
the same flag its own wizard re-enters with.

---

## 9. Still open

- **OpenAI PDF path is broken** in `eaglepub_bill_ocr` — PDFs are sent as `image_url`,
  which OpenAI accepts for images only. Claude's `document` block path is correct.
  Either refuse PDFs on OpenAI or rasterise pages first.
- **Neither live API path has ever run** — everything was verified through the `stub`
  reader. Test against a real key before selling that module.
- **Screenshots missing:** `eaglepub_pos_base`, `eaglepub_bill_ocr`,
  `eaglepub_sale_commission`, `eaglepub_sale_commission_pos`,
  `eaglepub_demand_forecast`.
- **`eaglepub_demand_forecast` has not been clicked through the UI.** Views were built
  server-side via `get_views` as a real (non-superuser) user and the arithmetic was
  verified against seeded history, but nobody has run the wizard in a browser.
- **Naming collision:** `eaglepub_sale_target` (`sale.target`) vs `sales_team_target`
  (`sales.target`) — two similar products, one letter apart.
