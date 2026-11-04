#!/usr/bin/env python3
"""Build static pages, portable JSON and two RSS feeds without dependencies."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from email.utils import format_datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from aggregate import atomic_json, canonical_url, parse_date, read_json, stamp

ROOT = Path(__file__).resolve().parents[1]
ATOM = 'http://www.w3.org/2005/Atom'
ET.register_namespace('atom', ATOM)


def deduplicate(items: list[dict], source_map: dict) -> list[dict]:
    result, by_url, by_title = [], {}, {}
    for raw in sorted(items, key=lambda i: (i.get('first_seen_at', ''), i.get('url', ''))):
        item = dict(raw)
        url = canonical_url(item.get('url', ''))
        if not url or not item.get('title'):
            continue
        title_key = re.sub(r'[^\w\u4e00-\u9fff]', '', item['title'].casefold())
        # Short generic titles are not enough evidence for cross-source deduplication.
        existing = by_url.get(url) or (by_title.get(title_key) if len(title_key) >= 24 else None)
        source = source_map.get(item['source_id'])
        if not source:
            continue
        label = {'id': source['id'], 'name': source['name'], 'kind': source['kind']}
        if existing is not None:
            if label['id'] not in [s['id'] for s in existing['sources']]:
                existing['sources'].append(label)
            existing['first_seen_at'] = min(existing.get('first_seen_at', '9999'), item.get('first_seen_at', '9999'))
            if not existing.get('published_at') and item.get('published_at'):
                existing['published_at'] = item['published_at']
            by_url[url] = existing
            if len(title_key) >= 24:
                by_title[title_key] = existing
            continue
        item['url'] = url
        item['sources'] = [label]
        result.append(item)
        by_url[url] = item
        if len(title_key) >= 24:
            by_title[title_key] = item
    return sorted(result, key=lambda i: i.get('published_at') or '', reverse=True)


def rss(items: list[dict], title: str, description: str, site_url: str, filename: str, now: datetime) -> bytes:
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    ET.SubElement(channel, 'title').text = title
    ET.SubElement(channel, 'link').text = site_url or 'https://example.invalid/'
    ET.SubElement(channel, 'description').text = description
    ET.SubElement(channel, 'language').text = 'zh-CN'
    ET.SubElement(channel, 'lastBuildDate').text = format_datetime(now)
    if site_url:
        ET.SubElement(channel, f'{{{ATOM}}}link', href=site_url + filename, rel='self', type='application/rss+xml')
    for item in items[:100]:
        entry = ET.SubElement(channel, 'item')
        ET.SubElement(entry, 'title').text = item['title']
        ET.SubElement(entry, 'link').text = item['url']
        ET.SubElement(entry, 'guid', isPermaLink='false').text = item.get('id') or hashlib.sha256(item['url'].encode()).hexdigest()
        date = parse_date(item.get('published_at') or item.get('added_at'))
        if date:
            ET.SubElement(entry, 'pubDate').text = format_datetime(date)
        names = '、'.join(s['name'] for s in item.get('sources', []))
        desc = item.get('note') or (f'来源：{names}。请查看原文；本条为来源标题，不代表独立核验。' if names else '')
        ET.SubElement(entry, 'description').text = desc
        ET.SubElement(entry, 'category').text = item['category']
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def build(root: Path, site_url: str = '', now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    if site_url:
        if urlsplit(site_url).query or urlsplit(site_url).fragment:
            raise ValueError('SITE_URL must not include query parameters or fragments')
        site_url = canonical_url(site_url)
        if not site_url or not site_url.startswith('https://'):
            raise ValueError('SITE_URL must be an HTTPS URL')
        site_url = site_url.rstrip('/') + '/'
    config = read_json(root / 'config/sources.json', {})
    state = read_json(root / 'data/news.json', {})
    status = read_json(root / 'data/source_status.json', {'sources': {}})
    discoveries = read_json(root / 'data/discoveries.json', {'items': []})['items']
    source_map = {s['id']: s for s in config['sources'] if s.get('enabled', True)}
    raw_items = [i for key, source in state.get('by_source', {}).items() if key in source_map for i in source['items']]
    news = deduplicate(raw_items, source_map)
    sources = [{**s, **status.get('sources', {}).get(s['id'], {'state': 'not_run', 'last_success_at': None, 'item_count': 0})}
               for s in source_map.values()]
    for item in discoveries:
        if not canonical_url(item.get('url', '')) or not item.get('title') or not item.get('verified_at'):
            raise ValueError('Every discovery needs a safe URL, title, and verification date')
    payload = {'schema_version': 1, 'built_at': stamp(now), 'last_success_at': state.get('last_success_at'),
               'attempted_at': status.get('attempted_at'), 'site_url': site_url,
               'lookback_days': config.get('lookback_days', 14), 'news': news,
               'discoveries': discoveries, 'sources': sources}
    out = root / 'public'
    out.mkdir(exist_ok=True)
    for source in (root / 'site').iterdir():
        if source.is_file():
            shutil.copyfile(source, out / source.name)
    atomic_json(out / 'data.json', payload)
    # Inline local data supports an offline double-click preview, without fetch/CORS.
    embedded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    (out / 'data.js').write_text('window.TECH_DATA = ' + embedded + ';\n', encoding='utf-8')
    (out / 'rss.xml').write_bytes(rss(news, '拾新 · 科技动态', 'AI、硬件和软件来源的更新标题。来源不等于独立核验。', site_url, 'rss.xml', now))
    evergreen = sorted(discoveries, key=lambda i: i.get('added_at', ''), reverse=True)
    (out / 'discoveries.xml').write_bytes(rss(evergreen, '拾新 · 常青发现', '不限发布时间的工具、项目和灵感。条目时间是收录时间，不是产品发布日期。', site_url, 'discoveries.xml', now))
    (out / '.nojekyll').touch()
    print(f'Built {len(news)} news items, {len(discoveries)} discoveries, and two RSS feeds in {out}')
    if not site_url:
        print('Local preview only: set SITE_URL at deployment for absolute RSS channel/self links.')
    return payload


def main():
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--site-url', default=os.environ.get('SITE_URL', ''))
    args = parser.parse_args()
    build(args.root, args.site_url)

if __name__ == '__main__':
    main()
