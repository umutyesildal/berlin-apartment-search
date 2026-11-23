# Launch demo assets

`demo.gif` is a 22-second terminal-style animation generated with Python/Pillow
from captured command output, not a recording of an AI conversation. It uses
fictional offline data only. `hero.png` is the final shortlist frame.
Pillow is only an asset-generation tool, not a dependency of the skill.

The commands ran against a copy installed by `npx skills add` from a local
checkout into a clean temporary workspace. Offline Python processes had socket
connections disabled. No real listing, personal profile or live search result
appears in either asset.

## What the demo shows

1. A fictional Mitte apartment: 50 m², two rooms, €900 cold rent, €1,000 warm
   rent and €4,000 deposit. The text demands advance payment by Western Union
   and promises posted keys from an owner abroad.
2. The actual `scam_check.py` JSON output: score 15, four signals, high review.
3. The actual `rent_check.py` JSON output: €18/m² cold rent, deposit above three
   cold rents, and an **unknown** rent-cap comparison without dated comparison
   data. This is orientation, not a legal conclusion.
4. A shortlist created by `search.py` with a mocked source returning two
   fictional listings, then passed to `report.py`. A small display helper reads
   `groups[].members[]` from `flat-search/results.json` and prints the existing
   `fit.score` and `scam.review` values without recalculating them. Both examples
   fit the profile equally, but their scam signals differ. **Fit is not safety.**

The terminal variable `S` points to the installed skill's scripts directory.
Command output is line-wrapped to fit the image; values are not edited.
The runtime scripts remain standard-library-only and Python 3.9+ compatible.
