#!/usr/bin/env python3
"""Reproduce the reviewed 115-bird sample mean from the pinned public supplement."""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

SHA256 = '32b8d981cf09216ff9b5ae2a009ecb559e7c30ca8a722b2b831068c2be34bf3d'
NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def analyze(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Supplement changed; review the source before recalculating')
    with ZipFile(path) as archive:
        strings = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', NS)]
        rows = []
        for row in ET.fromstring(archive.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row', NS):
            values = {}
            for cell in row:
                value = cell.find('m:v', NS)
                if value is not None:
                    text = strings[int(value.text)] if cell.get('t') == 's' else value.text
                    values[''.join(c for c in cell.get('r') if c.isalpha())] = text
            rows.append(values)
    if rows[0].get('C') != 'sex' or rows[0].get('H') != 'weight':
        raise ValueError('Unexpected source columns')
    sample = [row for row in rows[1:] if row.get('C') in ('m','f') and row.get('H')]
    if len(sample) != 115:
        raise ValueError('Unexpected sample size')
    weights = [Decimal(row['H']) for row in sample]
    mean = (sum(weights)/len(weights)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return dict(source_sha256=SHA256, sheet='sheet1', field='weight', unit='g',
                sample_size=len(weights), sample_mean=float(mean),
                sample_min=float(min(weights)), sample_max=float(max(weights)),
                sex_counts=dict(Counter(row['C'] for row in sample)),
                age_codes=dict(Counter(row['D'] for row in sample)),
                location_codes=dict(Counter(row['A'] for row in sample)),
                scope='한국 5개 지역·2008년 3월·2년차 이상 115개체',
                source_url='https://www.nature.com/articles/s41598-025-13894-4',
                license_name='CC BY 4.0',
                limitation='해당 조사 표본의 평균과 범위이며 종 전체의 평균·일반 범위가 아님')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.snapshot), ensure_ascii=False, indent=2))
