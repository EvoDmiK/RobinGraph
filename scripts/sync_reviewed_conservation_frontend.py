#!/usr/bin/env python3
"""Generate the frontend's approved expert-record manifest from pinned evidence."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from robingraph.retrieval.reviewed_conservation import reviewed_index
START='  // BEGIN GENERATED REVIEWED CONSERVATION MANIFEST'
END='  // END GENERATED REVIEWED CONSERVATION MANIFEST'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    records=reviewed_index()
    if not records:raise SystemExit('Pinned expert index invalid or empty')
    literal=json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    generated=START+'\n  var REVIEWED_CONSERVATION_MANIFEST = '+literal+';\n'+END
    path=ROOT/'src/robingraph/api/static/chat.js';text=path.read_text(encoding="utf-8")
    if START in text:
        a=text.index(START);b=text.index(END,a)+len(END);updated=text[:a]+generated+text[b:]
    else:
        updated=text.replace('  function expertReferenceInfo(',generated+'\n\n  function expertReferenceInfo(',1)
    if args.check:
        if updated!=text:raise SystemExit('Frontend expert manifest stale; run sync script')
    else:path.write_text(updated, encoding="utf-8")

if __name__=='__main__':main()
