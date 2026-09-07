# RobinGraph evaluation fixture v1

This directory contains generated, synthetic test inputs. It is not an external
data source and must not be promoted to an operational release.

Regenerate and validate it with:

```sh
python3 scripts/generate_eval_fixture.py
```

The generator fixes all IDs, timestamps, records, and manifest hashes. See
`docs/evaluation.md` for the full contract and acceptance criteria.
