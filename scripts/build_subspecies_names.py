#!/usr/bin/env python3
"""Build source-backed English subspecies names for pinned AviList v2025b.

Only exact scientific identities, matching authorities and unambiguous
source English names are emitted. Source hashes, page citations, conflicts
and exclusions are retained. No translated or geographic names are invented.

PDF extraction uses temporary build dependencies, never app dependencies:
  uv run --no-project --with pypdf==6.19.0 --with cryptography==50.0.2 \
    python scripts/build_subspecies_names.py --cache-dir DIR [--offline] [--check]
"""
import hashlib
from io import BytesIO


def extract_runs(data, *, plain_lines=False):
    """Read positioned source text with the maintained pypdf parser."""
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError('PDF requires a nonempty password')
    pages = []
    for page in reader.pages:
        if plain_lines:
            pages.append([(-10.0*i, 0.0, line, '') for i,line in enumerate(page.extract_text().splitlines())])
            continue
        runs = []
        def visitor(text, cm, tm, font, size):
            if text.strip():
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                runs.append((y, x, text.replace('\n', ''), str((font or {}).get('/BaseFont', '')).lstrip('/')))
        page.extract_text(visitor_text=visitor)
        pages.append(runs)
    return pages, reader


import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA_VERSION = 1
TAXONOMY_RELEASE = 'v2025b'
CONCEPT_SET_ID = 'rg:concept-set:avilist-v2025b'
TAXON_ID_PREFIX = f'avilist-taxon:{TAXONOMY_RELEASE}:'
RETRIEVED_ON = '2026-10-06'

SOURCES = {
    'avilist-v2025b': {
        'title': 'AviList v2025b (Explorer JSON)',
        'url': 'https://explore.avilist.org/data/avilist-2025b.json',
        'landing_url': 'https://www.avilist.org/checklist/v2025b/',
        'sha256': '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411',
        'file': 'avilist-2025b.json',
        'license': 'CC BY 4.0',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'role': 'taxon identity only (no English subspecies names: columns are empty for all subspecies rows)',
    },
    'dof-2019': {
        'title': 'Dansk Ornitologisk Forening, Navnegruppen: Navne paa alverdens fugle (file stamp 231119)',
        'url': 'https://www.dof.dk/images/organisationen/publikationer/Navne_pa_alverdens_fugle-til_DOF2019.pdf',
        'sha256': 'bdf253b373fccf20649664402003fd2c731199872d5c03a4511fbf5505ba678e',
        'file': 'dof-navne-pa-alverdens-fugle-2019.pdf',
        'license': 'No open licence. Notice on physical PDF page 5: individual names may be used freely; the files or parts of them may not be reproduced in other printed or electronic form without written permission from Navnegruppen.',
        'license_url': 'https://www.dof.dk/images/organisationen/publikationer/Navne_pa_alverdens_fugle-til_DOF2019.pdf',
        'role': 'English column of "Scientific name + Author . Danish . English . German" rows',
    },
    'birds-nz-2022': {
        'title': 'Checklist Committee (OSNZ) 2022. Checklist of the Birds of New Zealand, 5th edition',
        'url': 'https://www.birdsnz.org.nz/wp-content/uploads/2022/05/checklist-2022.pdf',
        'sha256': 'e2cb09bae5c46e2bf585a11fa0dee9ddee36a5445a4086942bfa128bffb7659b',
        'file': 'birds-nz-checklist-2022.pdf',
        'license': 'All rights reserved by Ornithological Society of New Zealand (copyright page 3); no open licence. Only short individual names with page citation are kept.',
        'license_url': 'https://www.birdsnz.org.nz/wp-content/uploads/2022/05/checklist-2022.pdf',
        'role': 'English side of "English | Maori" species/subspecies headings (physical PDF page 10 explains the bar convention)',
    },
}

EXCLUDED_SOURCES = [
    {'id': 'ioc-15.2', 'title': 'IOC World Bird List 15.2 (IOC_Names_File_Plus-15.2_full_ssp.xlsx)',
     'url': 'https://www.worldbirdnames.org/IOC_Names_File_Plus-15.2_full_ssp.xlsx',
     'sha256': '8517d4dff94e6e8ba8908146e57590f90f0736108ea19c56dd77a64fab581f30',
     'reason': 'All 19797 "ssp" rows have an empty "English name" cell; nothing to extract.'},
    {'id': 'dof-ioc-table', 'title': 'DOF "Videnskabelige, danske, engelske og tyske Navne paa alverdens fugle" (IOC 2022 table PDF)',
     'url': 'https://www.dof.dk/images/grupper/navne/dokumenter/Navne_pa_alverdens_fugle._Systematiske_danske_engelske_og_tyske_navne_PDF.pdf',
     'sha256': '6812a9672ba18de790290531936de634dbc2a017d28117ee7213697946206eea',
     'reason': 'Only 175 of 18261 AviList-matching subspecies rows carry an English cell; many are truncated or species-level strings spread over wrapped table cells (e.g. "Tinamou", "Gray-headed pileated", "Huila black Tinamou"), so the column cannot be verified exactly.'},
    {'id': 'ncbi-taxonomy-2026-10-01', 'title': 'NCBI Taxonomy taxdmp_2026-10-01.zip',
     'url': 'https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump_archive/taxdmp_2026-10-01.zip',
     'sha256': 'd744af371c0b9fc7269d80b49546b6ac4c9ddc52a2fd97bcbfd02783edb5c9eb',
     'reason': 'Only 111 of 3991 matching subspecies have any common name; they are submitter supplied, lower-case or species-level ("common mallard", "ring-necked pheasant") and not an edited checklist. Used only for the manually preserved Northern Mallard reference.'},
    {'id': 'clements-v2025', 'title': 'Clements Checklist v2025 CSV (Cornell Lab)',
     'url': 'https://www.birds.cornell.edu/clementschecklist/wp-content/uploads/2025/10/Clements-v2025-October-2025-csv.csv',
     'sha256': None,
     'reason': 'HTTP 403 from the Cornell host on 2026-10-06 (automated access blocked); its group names also span several subspecies.'},
]

CONTRIBUTING_SOURCE_IDS = ('dof-2019', 'birds-nz-2022')
PARTICLES = {'von', 'van', 'der', 'den', 'de', 'des', 'du', 'da', 'di', 'zu', 'le', 'la', 'los', 'del', 'og', 'and',
             'et', 'al', 'sr', 'jr', 'dos', 'das', 'dello'}

# =====================================================================
# Helpers
# =====================================================================


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def fold(text):
    """Case/diacritic/apostrophe-insensitive comparison key."""
    text = unicodedata.normalize('NFKD', text.replace('’', "'"))
    return ''.join(c for c in text if not unicodedata.combining(c)).casefold().strip()


def surname_tokens(authority):
    text = re.sub(r'\d{4}', ' ', authority or '')
    words = re.findall(r"[^\W\d_][^\W\d_'’\-]*(?:['’\-][^\W\d_]+)*", text)
    out = set()
    for w in words:
        if len(w) < 3 or not w[0].isupper() or w.isupper():
            continue
        if fold(w) in PARTICLES:
            continue
        out.add(fold(w))
    return out


def authority_year(authority):
    years = re.findall(r'\b(1[5-9]\d\d|20\d\d)\b', authority or '')
    return years[-1] if years else None


def authority_check(source_authority, avilist_authority, require_year):
    """Return (ok, reason).  Surnames must intersect; the year must agree when the source has one."""
    if not (source_authority or '').strip():
        return False, 'authority_missing_in_source'
    if not surname_tokens(source_authority) & surname_tokens(avilist_authority):
        return False, 'authority_surname_mismatch'
    sy, ay = authority_year(source_authority), authority_year(avilist_authority)
    if require_year and not sy:
        return False, 'authority_year_missing_in_source'
    if sy and ay and sy != ay:
        return False, 'authority_year_mismatch'
    return True, None


_ENGLISH_NAME = re.compile(r"[A-Z][A-Za-z.'’À-ɏ \-]*[A-Za-z.À-ɏ]")


def style_flags(name):
    """Verbatim-source style notes for the consumer (the name itself is never rewritten)."""
    small = {'of', 'the', 'de', 'du', 'la', 'and', 'von', 'van', 'des', 'da', 'di'}
    flags = []
    if any(w[0].islower() and w not in small for w in re.split(r'[ ]', name)):
        flags.append('lowercase_word')
    return flags


def clean_english(cell):
    """Return (name, reason).  Exactly one plain English name or a rejection reason."""
    value = re.sub(r'\s+', ' ', (cell or '').replace(' ', ' ')).strip()
    if not value:
        return None, 'empty'
    if '/' in value or ';' in value:
        return None, 'english_multiple_names'
    if not _ENGLISH_NAME.fullmatch(value) or re.search(r'-\s|\s-|--', value):
        return None, 'english_unclean'
    if re.search(r'\b(morph|group|form)\b', value, re.I):
        return None, 'english_unclean'
    if re.search('[\u00e6\u00f8\u00e5\u00c6\u00d8\u00c5\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc]', value):
        return None, 'english_contains_danish_or_german_letters'
    if len(value.split()) > 6 or any(w.isupper() and len(w) > 2 for w in value.split()):
        return None, 'english_unclean'
    return value, None


# =====================================================================
# AviList
# =====================================================================
AVILIST_COLUMNS = {'sequence': 0, 'rank': 1, 'order': 2, 'family': 3, 'scientific_name': 5,
                   'authority': 6, 'english_name': 8, 'range': 13}


def parse_avilist(rows):
    """Subspecies by exact scientific name with their parent species (preceding species row)."""
    subs, parent, names, seen_ids = {}, None, Counter(), set()
    for row in rows:
        rank = row[AVILIST_COLUMNS['rank']]
        if rank == 'species':
            parent = row
        elif rank == 'subspecies':
            sci = row[AVILIST_COLUMNS['scientific_name']]
            seq = row[AVILIST_COLUMNS['sequence']]
            if parent is None or not sci or not seq:
                raise ValueError('Subspecies row without parent species or identity')
            if seq in seen_ids:
                raise ValueError('Duplicate AviList sequence')
            seen_ids.add(seq)
            names[sci] += 1
            subs[sci] = {
                'taxon_id': TAXON_ID_PREFIX + seq, 'scientific_name': sci,
                'authority': row[AVILIST_COLUMNS['authority']] or '',
                'order': row[AVILIST_COLUMNS['order']] or '',
                'parent_id': TAXON_ID_PREFIX + parent[AVILIST_COLUMNS['sequence']],
                'parent_scientific_name': parent[AVILIST_COLUMNS['scientific_name']],
                'parent_english_name': parent[AVILIST_COLUMNS['english_name']] or '',
            }
    dupes = sorted(n for n, c in names.items() if c > 1)
    for n in dupes:  # an ambiguous exact name can never be bound to an ID
        subs[n] = None
    return subs, dupes


# =====================================================================
# DOF 2019 list
# =====================================================================
_DOF_START = re.compile(r"^\s*([A-Z][a-z]+) ([a-z]+)(?: ([a-z]+))?([0-9*†?]*)\s")
_DOF_SKIP = [re.compile(p) for p in (r'^\d+ Systematiske, danske, engelske & tyske\s*$',
                                     r'^Systematiske, danske, engelske & tyske', r'^navne på alverdens fugle',
                                     r'^\d+\s*$')]
_DOF_HEADING = re.compile(r'^[A-Z][a-z]+(idae|inae|iformes|ini|ae) ')
FIRST_DATA_PAGE = 7  # pages 1-6 are front matter (the licence notice sits on page 6)


def dof_records(pages):
    """pages: list of line lists.  Returns records with their joined text (columns split on the bullet)."""
    records, cur = [], None
    for page_no, lines in enumerate(pages, 1):
        if page_no < FIRST_DATA_PAGE:
            continue
        for line in lines:
            text = line.strip()
            if not text or any(p.match(text) for p in _DOF_SKIP):
                continue
            if _DOF_START.match(line) and '•' in line:
                cur = {'page': page_no, 'record': len(records) + 1, 'text': text}
                records.append(cur)
            elif cur and cur['text'].count('•') < 3 and not _DOF_HEADING.match(text):
                cur['text'] += ('' if cur['text'].endswith('-') else ' ') + text
    return records


def dof_parse(record):
    """Split one record.  Returns dict(name, rank, authority, parts) or None when the head is unparsable."""
    m = _DOF_START.match(record['text'])
    if not m:
        return None
    genus, species, sub, _marks = m.groups()
    parts = [p.strip() for p in record['text'].split('•')]
    head = parts[0][m.end() - 1:] if False else record['text'][:record['text'].index('•')]
    consumed = ' '.join(x for x in (genus, species, sub) if x)
    authority = head.strip()[len(consumed):]
    authority = re.sub(r'^[0-9*?\s†]+', '', authority).strip()
    return {'name': consumed, 'rank': 'subspecies' if sub else 'species', 'authority': authority, 'parts': parts,
            'page': record['page'], 'record': record['record']}


# =====================================================================
# Birds New Zealand 2022 headings
# =====================================================================
_NZ_TRINOMIAL = re.compile(r'^([A-Z][a-z]+ [a-z]+ [a-z]+) ?$')
_MACRON = re.compile('[ĀāĒēĪīŌōŪū]')


def _strip_macrons(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c))


def nz_headings(page_runs_list):
    """Yield heading dicts from positioned runs: bold-italic trinomial, authority run(s), bold names run."""
    for page_no, runs in enumerate(page_runs_list, 1):
        for i, run in enumerate(runs):
            y, _x, text, font = run
            m = _NZ_TRINOMIAL.match(text.strip())
            if not m or 'BoldItalic' not in font:
                continue
            authority, names, stage = [], [], 0
            for nxt in runs[i + 1:i + 14]:
                if abs(nxt[0] - y) > 0.3:
                    break
                if 'Bold' in nxt[3] and 'Italic' not in nxt[3]:
                    stage = 2
                    names.append(nxt[2])
                elif stage == 0 and nxt[2].strip() != '' and 'Bold' not in nxt[3]:
                    authority.append(nxt[2])
                elif stage == 2:
                    break
            if names:
                yield {'name': m.group(1), 'authority': ' '.join(authority).strip(),
                       'names_text': ''.join(names).strip(), 'page': page_no}


def nz_english(names_text):
    """Apply the checklist convention (physical PDF page 10: 'English | Maori', left side most used) conservatively."""
    text = re.sub(r'\*+$', '', names_text.strip()).strip()
    if '|' not in text:
        if _MACRON.search(text):
            return None, 'nz_macron_name_without_english'
        return clean_english(text)
    left, right = (s.strip() for s in text.split('|', 1))
    if _strip_macrons(left).casefold() == _strip_macrons(re.sub(r'\*+$', '', right)).casefold():
        return None, 'nz_english_maori_identical_apart_from_macrons'
    if _MACRON.search(left):
        return None, 'nz_maori_name_listed_first'
    if len(left.split()) < 2:
        return None, 'nz_single_word_left_of_bar_language_unverified'
    return clean_english(left)


# =====================================================================
# Resolution
# =====================================================================


def _locator(source_id, **kw):
    return {'source_id': source_id, **kw}


def resolve(avilist_subs, candidates, parent_species_names, preserved):
    """candidates: list of dict(source_id, name, authority, english_cell, english, reject, require_year, locator).

    Returns (names, excluded, conflicts, unmapped, counters).
    """
    excluded, conflicts, unmapped = [], [], []
    counters = Counter()
    pending = defaultdict(list)  # taxon_id -> accepted-so-far candidates
    for c in candidates:
        sci = c['name']
        taxon = avilist_subs.get(sci, 'absent')
        if taxon == 'absent':
            counters[(c['source_id'], 'not_an_avilist_subspecies')] += 1
            if c['english']:
                unmapped.append({'source_id': c['source_id'], 'scientific_name': sci,
                                 'english_name': c['english'], 'source_authority': c['authority'],
                                 'locator': c['locator']})
            continue
        if taxon is None:
            counters[(c['source_id'], 'ambiguous_avilist_name')] += 1
            excluded.append({'source_id': c['source_id'], 'scientific_name': sci, 'reason': 'ambiguous_avilist_name',
                             'raw_english': c['english_cell'], 'locator': c['locator']})
            continue
        if c['reject'] == 'empty':
            counters[(c['source_id'], 'no_english_name_in_source')] += 1
            continue
        reason = c['reject']
        if reason is None and re.search(r'\b(?:Domestic|Society Finch|Bengalese (?:Munia|Finch))\b', c['english'], re.I):
            reason = 'domestication_name_ambiguous'
        if reason is None:
            ok, why = authority_check(c['authority'], taxon['authority'], c['require_year'])
            if not ok:
                reason = why
        if reason is None:
            fenced = {fold(taxon['parent_english_name'])} | {fold(n) for n in parent_species_names.get(
                (c['source_id'], taxon['parent_scientific_name']), ())}
            if fold(c['english']) in fenced:
                reason = 'same_as_parent_species_name'
        if reason is not None:
            counters[(c['source_id'], reason)] += 1
            excluded.append({'taxon_id': taxon['taxon_id'], 'source_id': c['source_id'], 'scientific_name': sci,
                             'reason': reason, 'raw_english': c['english_cell'], 'locator': c['locator']})
            continue
        pending[taxon['taxon_id']].append({**c, 'taxon': taxon})

    # one value per (taxon, source); contradictory duplicates inside a source are conflicts
    per_source = {}
    for tid, items in pending.items():
        by_source = defaultdict(list)
        for c in items:
            by_source[c['source_id']].append(c)
        for sid, group in by_source.items():
            if len({fold(g['english']) for g in group}) > 1:
                conflicts.append({'type': 'duplicate_source_rows_disagree', 'taxon_id': tid,
                                  'scientific_name': group[0]['name'], 'source_id': sid,
                                  'values': [{'english_name': g['english'], 'locator': g['locator']} for g in group]})
                counters[(sid, 'duplicate_source_rows_disagree')] += 1
                continue
            per_source[(tid, sid)] = group[0]

    # sibling duplicates inside one source (same English name for two subspecies of one species)
    siblings = defaultdict(list)
    for (tid, sid), c in per_source.items():
        siblings[(sid, c['taxon']['parent_id'], fold(c['english']))].append((tid, c))
    for (sid, parent_id, _name), group in siblings.items():
        if len(group) > 1:
            conflicts.append({'type': 'same_name_for_several_subspecies', 'source_id': sid, 'parent_id': parent_id,
                              'english_name': group[0][1]['english'],
                              'taxa': [{'taxon_id': t, 'scientific_name': c['name'], 'locator': c['locator']}
                                       for t, c in sorted(group)]})
            for tid, c in group:
                per_source.pop((tid, sid), None)
                counters[(sid, 'same_name_for_several_subspecies')] += 1
                excluded.append({'taxon_id': tid, 'source_id': sid, 'scientific_name': c['name'],
                                 'reason': 'same_name_for_several_subspecies', 'raw_english': c['english_cell'],
                                 'locator': c['locator']})

    # cross-source agreement and the manually verified references
    by_taxon = defaultdict(list)
    for (tid, _sid), c in sorted(per_source.items()):
        by_taxon[tid].append(c)
    names = {}
    for tid, group in sorted(by_taxon.items()):
        values = {fold(c['english']) for c in group}
        manual = preserved.get(tid)
        if manual:
            values.add(fold(manual['english_name']))
        if len(values) > 1:
            conflicts.append({'type': 'sources_disagree', 'taxon_id': tid, 'scientific_name': group[0]['name'],
                              'values': [{'source_id': c['source_id'], 'english_name': c['english'],
                                          'locator': c['locator']} for c in group] +
                                        ([{'source_id': 'manual-preserved', 'english_name': manual['english_name']}]
                                         if manual else [])})
            for c in group:
                counters[(c['source_id'], 'sources_disagree')] += 1
                excluded.append({'taxon_id': tid, 'source_id': c['source_id'], 'scientific_name': c['name'],
                                 'reason': 'sources_disagree', 'raw_english': c['english_cell'],
                                 'locator': c['locator']})
            continue
        taxon = group[0]['taxon']
        names[tid] = {
            'scientific_name': taxon['scientific_name'], 'english_name': group[0]['english'],
            'authority_avilist': taxon['authority'], 'parent_id': taxon['parent_id'],
            'matches_manual_reference': bool(manual),
            'style_flags': style_flags(group[0]['english']),
            'evidence': [{'source_id': c['source_id'], 'source_authority': c['authority'],
                          'raw_english': c['english_cell'], 'locator': c['locator']} for c in group],
        }
        for c in group:
            counters[(c['source_id'], 'accepted')] += 1
    return names, excluded, conflicts, unmapped, counters


# =====================================================================
# Orchestration
# =====================================================================


def dof_candidates(pages):
    records = [r for r in (dof_parse(x) for x in dof_records(pages)) if r]
    species_english = defaultdict(set)
    cands = []
    for r in records:
        parts = r['parts']
        well_formed = len(parts) == 4
        if r['rank'] == 'species':
            if well_formed:
                for n in parts[2].split('/'):
                    if n.strip():
                        species_english[('dof-2019', r['name'])].add(n.strip())
            continue
        if not well_formed:
            english, reject, cell = None, 'malformed_columns', ' | '.join(parts[1:])
        else:
            cell = parts[2]
            english, reject = clean_english(cell)
            if english and fold(english) in (fold(parts[1]), fold(parts[3])):
                english, reject = None, 'english_equals_danish_or_german_column'
            elif english and len(english.split()) == 1:
                # single-token cells in this list are Danish-style compounds or species names pasted into the wrong row
                english, reject = None, 'english_single_word_unverified'
        cands.append({'source_id': 'dof-2019', 'name': r['name'], 'authority': r['authority'],
                      'english_cell': cell.strip(), 'english': english, 'reject': reject, 'require_year': True,
                      'locator': _locator('dof-2019', page=r['page'], record=r['record'])})
    return cands, species_english, len(records)


def nz_candidates(page_runs_list):
    cands = []
    for h in nz_headings(page_runs_list):
        english, reject = nz_english(h['names_text'])
        cands.append({'source_id': 'birds-nz-2022', 'name': h['name'], 'authority': h['authority'],
                      'english_cell': h['names_text'], 'english': english, 'reject': reject, 'require_year': False,
                      'locator': _locator('birds-nz-2022', page=h['page'])})
    return cands


def lines_from_runs(page_runs_list):
    pages = []
    for runs in page_runs_list:
        ordered = sorted(runs, key=lambda r: (-r[0], r[1]))
        lines, cur, cury = [], [], None
        for y, x, text, _f in ordered:
            if cury is None or abs(y - cury) <= 4.0:
                cur.append((x, text))
                cury = y if cury is None else cury
            else:
                lines.append(cur)
                cur, cury = [(x, text)], y
        if cur:
            lines.append(cur)
        pages.append([''.join(t for _, t in sorted(l, key=lambda r: r[0])) for l in lines])
    return pages


def load_preserved():
    """The manually verified references in taxonomy_lineage.py (must never be overridden)."""
    root = Path(__file__).resolve().parents[1] / 'src'
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from robingraph.retrieval.taxonomy_lineage import SUBSPECIES_NAME_REFERENCES
    return {k: dict(v) for k, v in SUBSPECIES_NAME_REFERENCES.items()}


def build_artifact(avilist_rows, dof_runs, nz_runs, preserved, hashes):
    avilist_subs, dupes = parse_avilist(avilist_rows)
    denominator = sum(1 for v in avilist_subs.values() if v) + len(dupes)
    dof_cands, dof_species, dof_record_count = dof_candidates(lines_from_runs(dof_runs))
    nz_cands = nz_candidates(nz_runs)
    names, excluded, conflicts, unmapped, counters = resolve(
        avilist_subs, dof_cands + nz_cands, dof_species, preserved)

    preserved_block = {}
    by_name = {v['scientific_name']: v for v in avilist_subs.values() if v}
    for tid, ref in sorted(preserved.items()):
        taxon = by_name.get(ref['scientific_name'])
        identity_ok = bool(taxon and taxon['taxon_id'] == tid)
        preserved_block[tid] = {**ref, 'identity_verified_against_avilist': identity_ok,
                                'generated_agrees': (tid in names and fold(names[tid]['english_name']) == fold(ref['english_name'])),
                                'generated_name': names.get(tid, {}).get('english_name')}
    union = set(names) | {t for t, p in preserved_block.items() if p['identity_verified_against_avilist']}

    per_order_den, per_order_num = Counter(), Counter()
    order_of = {v['taxon_id']: v['order'] for v in avilist_subs.values() if v}
    for tid in order_of:
        per_order_den[order_of[tid]] += 1
    for tid in names:
        per_order_num[order_of[tid]] += 1

    src_stats = {}
    for sid in CONTRIBUTING_SOURCE_IDS:
        src_stats[sid] = {k: v for (s, k), v in sorted(counters.items()) if s == sid}
    source_block = {}
    for sid, s in SOURCES.items():
        source_block[sid] = {k: s[k] for k in ('title', 'url', 'sha256', 'license', 'license_url', 'role')}
        source_block[sid]['retrieved_on'] = RETRIEVED_ON
        if 'landing_url' in s:
            source_block[sid]['landing_url'] = s['landing_url']
        assert hashes[sid] == s['sha256']
    excluded.sort(key=lambda e: (e['source_id'], e.get('taxon_id') or '', e['scientific_name'], e['reason']))
    unmapped.sort(key=lambda e: (e['source_id'], e['scientific_name']))
    reason_counts = Counter(f"{e['source_id']}:{e['reason']}" for e in excluded)
    return {
        'schema_version': SCHEMA_VERSION,
        'taxonomy': {'release': TAXONOMY_RELEASE, 'concept_set_id': CONCEPT_SET_ID,
                     'taxon_id_pattern': TAXON_ID_PREFIX + '<Sequence>', 'source': 'avilist-v2025b',
                     'rank': 'subspecies'},
        'policy': {
            'identity': 'exact AviList v2025b subspecies scientific name + source authority agreement (surname intersection; year equal when the source gives one)',
            'accepted_text': 'exactly one clean English name from the source English column; no translation, geography or Danish/German/Maori column is ever used',
            'rejected': ['multiple names in one cell', 'unclean/truncated/qualified names', 'rows whose column count is not 4',
                         'Birds NZ bar entries whose English side cannot be established', 'names equal to the parent species name',
                         'domestication-form names (Domestic/Society/Bengalese)', 'the same name for several subspecies of one species', 'any disagreement between sources or with the manual references'],
            'manual_references_are_authoritative': True},
        'sources': source_block,
        'evaluated_and_excluded_sources': EXCLUDED_SOURCES,
        'coverage': {
            'denominator_avilist_subspecies': denominator,
            'numerator_generated_names': len(names),
            'numerator_with_preserved_manual_references': len(union),
            'percent_generated': round(100 * len(names) / denominator, 2),
            'by_source_accepted': {sid: src_stats[sid].get('accepted', 0) for sid in CONTRIBUTING_SOURCE_IDS},
            'source_row_counts': {'dof-2019_subspecies_and_species_records': dof_record_count,
                                  'dof-2019_subspecies_candidates': len(dof_cands),
                                  'birds-nz-2022_subspecies_headings': len(nz_cands)},
            'source_outcomes': src_stats,
            'excluded_entries': len(excluded), 'excluded_by_reason': dict(sorted(reason_counts.items())),
            'conflicts': len(conflicts), 'unmapped_candidates_with_english': len(unmapped),
            'ambiguous_avilist_scientific_names': dupes,
            'by_order': {o: {'accepted': per_order_num.get(o, 0), 'subspecies': n}
                         for o, n in sorted(per_order_den.items())},
        },
        'preserved_manual_references': preserved_block,
        'names': dict(sorted(names.items(), key=lambda kv: int(kv[0].rsplit(':', 1)[1]))),
        'conflicts': conflicts,
        'excluded': excluded,
        'unmapped_candidates': unmapped,
    }


def fetch_source(source_id, cache_dir, offline=False):
    s = SOURCES[source_id]
    path = Path(cache_dir) / s['file']
    if not path.exists():
        if offline:
            raise FileNotFoundError(f'{path} missing (offline)')
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(s['url'], headers={'User-Agent': 'RobinGraph-source-audit/1.0'})
        with urllib.request.urlopen(req, timeout=300) as resp:
            path.write_bytes(resp.read())
    data = path.read_bytes()
    if sha256_hex(data) != s['sha256']:
        raise ValueError(f'Pinned SHA-256 mismatch for {source_id}: {sha256_hex(data)}')
    return data


def serialize(artifact):
    return json.dumps(artifact, ensure_ascii=False, indent=1, sort_keys=False) + '\n'


def main(argv=None):
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cache-dir', type=Path, default=Path(tempfile.gettempdir()) / 'robingraph-subspecies-name-sources')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] /
                        'src/robingraph/retrieval/subspecies_name_references.json')
    parser.add_argument('--offline', action='store_true', help='never download; fail when a pinned file is missing')
    parser.add_argument('--check', action='store_true', help='rebuild and compare with --output instead of writing it')
    args = parser.parse_args(argv)
    raw = {sid: fetch_source(sid, args.cache_dir, args.offline) for sid in SOURCES}
    hashes = {sid: sha256_hex(b) for sid, b in raw.items()}
    avilist_rows = json.loads(raw['avilist-v2025b'])
    dof_runs, _ = extract_runs(raw['dof-2019'], plain_lines=True)
    nz_runs, _ = extract_runs(raw['birds-nz-2022'])
    artifact = build_artifact(avilist_rows, dof_runs, nz_runs, load_preserved(), hashes)
    text = serialize(artifact)
    if args.check:
        if args.output.read_text(encoding='utf-8') != text:
            print('MISMATCH: regenerated artifact differs from', args.output)
            return 1
        print('OK: regenerated artifact is byte-identical to', args.output)
        return 0
    args.output.write_text(text, encoding='utf-8')
    print(json.dumps(artifact['coverage'], ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
