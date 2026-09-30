"""Credit only named, passing browser evidence against the conservative inventory.

This is an evidence index, not an assertion that full operational UAT is complete.
"""
from collections import Counter
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and sys.argv[1] != '--dry-run' else root / 'artifacts'
dry_run = '--dry-run' in sys.argv[1:]
report = json.loads((out / 'coverage-inventory.json').read_text())
items = report['items']
by_key = {(item['kind'], item['file'], item['key']): item for item in items}
rows = json.loads((out / 'browser-results.json').read_text()) if (out / 'browser-results.json').exists() else []
passed = {(row['title'][0], row['title'][-1]) for row in rows if row['status'] == 'passed' and len(row['title']) >= 2}

def both(title):
    return all((project, title) in passed for project in ('desktop', 'mobile'))

levels = {'NOT_TESTED': 0, 'NAVIGATION_VERIFIED': 1, 'UI_RESULT_VERIFIED': 2, 'BEHAVIOR_VERIFIED': 3}
missing = []
def credit(kind, file, key, level, title):
    item = by_key.get((kind, file, key))
    if item is None:
        missing.append(f'{kind}:{file}:{key}')
        return
    if not both(title):
        return
    if levels[level] > levels[item['status']]:
        item['status'] = level
    item['evidence'].append({'source': 'browser-results.json', 'projects': ['desktop', 'mobile'], 'test': title})

pages = {
    'growth-suite.html': 'growth-suite.html: every rendered module tab changes visible panel',
    'enterprise-suite.html': 'enterprise-suite.html: every rendered module tab changes visible panel',
    'pos.html': 'POS: every tab, product draft cancel, creation, search and cart clear',
}
for file in ('index.html', 'property-setup.html', 'interproperty-transfer.html',
             'multi-property-foundation.html', 'hq/index.html', 'hq/control.html',
             'webpublic/index.html'):
    pages[file] = f'{file}: entrypoint renders without a browser exception'
for file, title in pages.items():
    credit('page', file, file, 'NAVIGATION_VERIFIED', title)

def controls(file, title, level, selectors):
    for selector in selectors:
        credit('html-control', file, selector, level, title)

setup = 'Property setup: save, refresh, persisted reload and restore'
controls('property-setup.html', setup, 'BEHAVIOR_VERIFIED',
         ('#propertyName', '#save', '#finalize'))
controls('property-setup.html', setup, 'UI_RESULT_VERIFIED', ('#refresh',))

readiness = 'Multi-property readiness: read-only buttons render their server results'
controls('multi-property-foundation.html', readiness, 'UI_RESULT_VERIFIED',
         ('#refresh', '#preview', '#manifest', '#contracts', '#outbox'))
snapshot = 'Multi-property snapshot: download aggregate, queue locally and reload outbox'
controls('multi-property-foundation.html', snapshot, 'UI_RESULT_VERIFIED', ('#snapshot-v2',))
controls('multi-property-foundation.html', snapshot, 'BEHAVIOR_VERIFIED', ('#queue-snapshot',))

pos = 'POS: every tab, product draft cancel, creation, search and cart clear'
controls('pos.html', pos, 'BEHAVIOR_VERIFIED',
         ('#product-sku', '#product-name', '#save-product'))
controls('pos.html', pos, 'UI_RESULT_VERIFIED',
         ('#add-product-btn', '#cancel-product-dialog', '#product-search',
          '#clear-cart', '#checkout-btn'))
sale = 'POS cash sale and void: receipt, history and stock reversal persist'
controls('pos.html', sale, 'BEHAVIOR_VERIFIED',
         ('#checkout-btn', '#payment-method', '#product-price', '#product-cost',
          '#product-initial-stock'))
controls('pos.html', sale, 'UI_RESULT_VERIFIED', ('#load-sales', '#close-receipt'))
stock = 'POS stock adjustment: add, subtract and persisted reload'
controls('pos.html', stock, 'BEHAVIOR_VERIFIED',
         ('#stock-form', '#stock-product', '#stock-delta', '#stock-reason'))
category = 'POS categories: create, reset, edit, toggle and persisted reload'
controls('pos.html', category, 'BEHAVIOR_VERIFIED',
         ('#category-form', '#category-name', '#save-category'))
controls('pos.html', category, 'UI_RESULT_VERIFIED',
         ('#manage-categories-btn', '#reset-category-form', '#cancel-category-dialog'))

pr = 'Enterprise procurement: PR approval, PO approval and GRN posting persist'
controls('enterprise-suite.html', pr, 'BEHAVIOR_VERIFIED',
         ('#pr-form', '#pr-item', '#pr-qty', '#pr-price'))
controls('enterprise-suite.html', pr, 'UI_RESULT_VERIFIED', ('#sinv-grn',))

# These stable static tab selectors are credited only when both project artifacts
# explicitly record the panel visible; the controls inside remain unverified.
for file in ('growth-suite.html', 'enterprise-suite.html'):
    title = pages[file]
    if not both(title):
        continue
    paths = [out / f'browser-{project}-{file}.json' for project in ('desktop', 'mobile')]
    if not all(path.exists() for path in paths):
        continue
    tab_sets = [set(entry['tab'] for entry in json.loads(path.read_text()) if entry.get('pass') is True)
                for path in paths]
    for tab in tab_sets[0] & tab_sets[1]:
        credit('html-control', file, f'button[data-tab="{tab}"]', 'NAVIGATION_VERIFIED', title)

report['fullOperationalUatPassed'] = False
report['evidenceReconciliation'] = {'browserTests': len(rows),
    'browserPassed': sum(row['status'] == 'passed' for row in rows),
    'browserSkipped': sum(row['status'] == 'skipped' for row in rows),
    'browserFailed': sum(row['status'] == 'failed' for row in rows),
    'missingMappedInventoryItems': sorted(set(missing))}
counts = Counter((item['kind'], item['status']) for item in items)
lines = ['# UAT coverage — NOT COMPLETE', '', report['scope'], '',
         f"Browser: {report['evidenceReconciliation']['browserPassed']}/{len(rows)} passed; "
         f"{report['evidenceReconciliation']['browserSkipped']} skipped; "
         f"{report['evidenceReconciliation']['browserFailed']} failed.", '']
for kind in sorted({item['kind'] for item in items}):
    breakdown = ', '.join(f'{status}={count}' for (name, status), count in sorted(counts.items()) if name == kind)
    lines.append(f'- {kind}: {breakdown}')
lines += ['', 'NOT_TESTED means no item-specific evidence credited here; API suites may test related behavior without a traceable item mapping.',
          'Navigation/UI-result evidence is not full control behavior or operator acceptance.',
          'Telegram live: BLOCKED_LIVE. Simulator results do not close this gate.']
if missing:
    lines += ['', f'Mapped selectors absent from inventory: {len(set(missing))}. See coverage-inventory.json.']
if not dry_run:
    (out / 'coverage-inventory.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    (out / 'coverage-summary.md').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))
if missing:
    raise SystemExit('Evidence map does not match inventory')
