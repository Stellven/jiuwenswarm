"""Generic exact-source paragraph selections; no product/oracle imports."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def selections(raw):
    text = raw.decode('utf-8')
    records = []
    offset = 0
    for page, content in enumerate(text.split('\f'), 1):
        for match in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', content):
            start, end = match.span()
            while start < end:
                stop = min(start + 1000, end)
                records.append({'document_id': 'P1', 'page': page, 'start': offset + start,
                                'end': offset + stop, 'quote': content[start:stop]})
                start = stop
        offset += len(content) + 1
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'selections': records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    print(json.dumps(selections(parser.parse_args().source.read_bytes()), ensure_ascii=False, indent=2))
