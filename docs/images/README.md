# Launch demo assets

`demo.gif` is a 22-second terminal-style animation generated with Python/Pillow
from actual skill-command output, not a recording of an AI conversation.
`hero.png` is the final fit-score frame. Pillow is only an asset-generation
tool, not a dependency of the skill.

All three listings and the profile are fictional. The inputs live in [demo/](demo/).
Commands ran from a repository checkout with Python socket connections disabled.
No real listing, personal profile or live search result appears in either asset.

## Replay the commands

From the repository root, using Python 3.9+ and a POSIX shell:

```bash
S=skills/berlin-apartment-search/scripts
D=docs/images/demo

# Scene 1: advance payment, posted keys, owner abroad, irreversible payment.
python3 "$S/scam_check.py" < "$D/scam.txt"

# Scene 2: expensive rent against a FICTIONAL dated comparison.
python3 "$S/rent_check.py" < "$D/rent-high.json"

# Scene 3: the ordinary example triggers none of these checks.
python3 "$S/scam_check.py" < "$D/clean.json"
python3 "$S/rent_check.py" < "$D/rent-clean.json"

# Scene 4: three actual CLI scores; the inline stdlib formatter prints score only.
for name in clean high-rent scam; do
  printf '%s: ' "$name"
  python3 "$S/fit_score.py" --profile "$D/profile.json" \
    < "$D/$name.json" | python3 -c \
    'import json,sys; print(json.load(sys.stdin)["score"])'
done
```

## What the demo shows

| Fictional listing | Computed fit | Separate checks |
|---|---:|---|
| `clean` | 82.0 | No scam signals; below the synthetic rent comparison; no deposit/cost warning |
| `high-rent` | 64.0 | €23.40/m² cold rent, above the synthetic €16.50/m² limit (reference plus 10%) |
| `scam` | 41.0 | Scam score 15, high review: advance payment, posted keys, owner abroad and Western Union |

The €15/m² reference and its date are **made up for teaching**, not real Berlin
Mietspiegel data or a legal finding. The tool compares against 110% of that
reference (€16.50/m²); real use requires an applicable, dated comparison and
checks for exceptions. The profile's separate €10/m² value preference is not
a legal benchmark. Unknown freshness and commute inputs remain neutral.

Each scene runs real skill commands. There is no custom shortlist helper.
Only the final loop's inline standard-library JSON formatter reduces output to
the returned score; it does not calculate or change it. Output is line-wrapped
for the images. **Fit is not safety; no warnings does not establish safety.**
