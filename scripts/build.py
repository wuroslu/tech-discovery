#!/usr/bin/env python3
"""Build static pages, portable JSON and two RSS feeds without dependencies."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
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


def validate_digests(document: dict, now: datetime) -> list[dict]:
    """Publication gate: candidates cannot silently become editorial content."""
    editions, seen_dates, seen_ids, seen_urls = [], set(), set(), set()
    beijing = timezone(timedelta(hours=8))
    for raw in document.get('editions', []):
        if raw.get('status') != 'published':
            continue
        edition = dict(raw)
        date_text = edition.get('date', '')
        try:
            day = datetime.strptime(date_text, '%Y-%m-%d').replace(tzinfo=beijing)
        except (TypeError, ValueError):
            raise ValueError('Published editions need a YYYY-MM-DD Beijing date')
        if date_text in seen_dates:
            raise ValueError('Only one published edition is allowed per Beijing date')
        seen_dates.add(date_text)
        published = parse_date(edition.get('published_at'))
        if not published or published > now + timedelta(minutes=5):
            raise ValueError('Edition publication time must be real and not in the future')
        if published.astimezone(beijing).date() < day.date():
            raise ValueError('Do not publish an edition dated in the future')
        items = edition.get('items', [])
        if not isinstance(items, list) or not 1 <= len(items) <= 5:
            raise ValueError('A published daily digest must contain 1 to 5 reviewed items')
        cleaned = []
        for raw_item in items:
            item = dict(raw_item)
            if item.get('review_status') != 'reviewed':
                raise ValueError('Only explicitly reviewed stories can be published')
            for field in ('title_zh', 'what_zh', 'why_zh'):
                text = item.get(field, '')
                if not isinstance(text, str) or not re.search(r'[\u4e00-\u9fff]', text):
                    raise ValueError(f'{field} must contain an original Chinese editorial summary')
            if len(item['title_zh']) > 70 or len(item['what_zh']) > 350 or len(item['why_zh']) > 220:
                raise ValueError('Digest copy exceeds concise editorial limits')
            url = canonical_url(item.get('url', ''))
            if not url or not url.startswith('https://'):
                raise ValueError('Reviewed stories need an HTTPS original-source URL')
            if item.get('source_language') not in ('zh', 'en') or not item.get('source_name') or not item.get('original_title'):
                raise ValueError('Reviewed stories need an original title, source and a supported source language (zh/en)')
            if item.get('category') not in ('ai', 'hardware', 'software'):
                raise ValueError('Story category must be ai, hardware or software')
            story_id = item.get('id', '')
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{5,80}', story_id):
                raise ValueError('Use a stable story ID, never a title or edition position')
            if story_id in seen_ids or url in seen_urls:
                raise ValueError('Do not repeat the same story across published editions')
            checked = parse_date(item.get('checked_at'))
            source_date = parse_date(item.get('source_published_at'))
            if not checked or checked > published + timedelta(minutes=5):
                raise ValueError('Each story needs a check timestamp before publication')
            if not source_date or source_date > checked + timedelta(hours=24):
                raise ValueError('Each news story needs a verified source publication date')
            if source_date < day - timedelta(days=7):
                raise ValueError('News older than 7 days belongs in evergreen discoveries')
            seen_ids.add(story_id); seen_urls.add(url)
            item['url'] = url
            item['title'] = item['title_zh']
            item['edition_date'] = date_text
            item['published_at'] = stamp(published)
            cleaned.append(item)
        edition['items'] = cleaned
        editions.append(edition)
    return sorted(editions, key=lambda e: e['date'], reverse=True)


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
        ET.SubElement(entry, 'title').text = item.get('title_zh') or item['title']
        ET.SubElement(entry, 'link').text = item['url']
        ET.SubElement(entry, 'guid', isPermaLink='false').text = item.get('id') or hashlib.sha256(item['url'].encode()).hexdigest()
        date = parse_date(item.get('published_at') or item.get('added_at'))
        if date:
            ET.SubElement(entry, 'pubDate').text = format_datetime(date)
        if item.get('what_zh'):
            # RSS date is our digest publication; source publication is explicitly separate.
            desc = (f"发生了什么：{item['what_zh']}\n\n为什么值得看（编辑判断）：{item['why_zh']}"
                    f"\n\n来源：{item['source_name']}。原文发布时间：{item['source_published_at']}。"
                    f"\n{'中文' if item.get('source_language') == 'zh' else '英文'}原文：{item['url']}")
            if item.get('caveat_zh'):
                desc += f"\n核对说明：{item['caveat_zh']}"
        else:
            names = '、'.join(source['name'] for source in item.get('sources', []))
            desc = item.get('note') or (f'来源：{names}。请查看原文。' if names else '')
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
    editorial = read_json(root / 'data/digests.json', {'editions': []})
    editions = validate_digests(editorial, now)
    news = [item for edition in editions for item in edition['items']]
    candidate_count = sum(len(source.get('items', [])) for source in state.get('by_source', {}).values())
    sources = [{**s, **status.get('sources', {}).get(s['id'], {'state': 'not_run', 'last_success_at': None, 'item_count': 0})}
               for s in source_map.values()]
    for item in discoveries:
        if not canonical_url(item.get('url', '')) or not item.get('title') or not item.get('verified_at'):
            raise ValueError('Every discovery needs a safe URL, title, and verification date')
    payload = {'schema_version': 2, 'built_at': stamp(now), 'last_success_at': state.get('last_success_at'),
               'attempted_at': status.get('attempted_at'), 'site_url': site_url,
               'timezone': 'Asia/Shanghai', 'max_daily_items': 5, 'editions': editions,
               'latest_edition_date': editions[0]['date'] if editions else None,
               'editorial_updated_at': editions[0]['published_at'] if editions else None,
               'news': news,
               'discoveries': discoveries, 'sources': sources}
    out = root / 'public'
    out.mkdir(exist_ok=True)
    for source in (root / 'site').iterdir():
        if source.is_file():
            shutil.copyfile(source, out / source.name)
    atomic_json(out / 'data.json', payload)
    # Inline local data supports an offline double-click preview, without fetch/CORS.
    embedded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    data_script = 'window.TECH_DATA = ' + embedded + ';\n'
    # A fresh HTML response must not reuse yesterday's cached data script.
    # Keep data.js for older HTML and use a relative fingerprinted URL for new
    # pages, including offline file:// previews and Pages repository subpaths.
    data_filename = 'data.' + hashlib.sha256(data_script.encode('utf-8')).hexdigest()[:20] + '.js'
    (out / 'data.js').write_text(data_script, encoding='utf-8')
    (out / data_filename).write_text(data_script, encoding='utf-8')
    index = out / 'index.html'
    if index.exists():
        index.write_text(index.read_text(encoding='utf-8').replace('src="data.js"', f'src="{data_filename}"'), encoding='utf-8')
    (out / 'rss.xml').write_bytes(rss(news, '拾新 · 每日中文精选', '每天最多五条经原文核对的中文科技摘要，覆盖国内外来源并附原文。编辑判断与事实分开。', site_url, 'rss.xml', now))
    evergreen = sorted(discoveries, key=lambda i: i.get('added_at', ''), reverse=True)
    (out / 'discoveries.xml').write_bytes(rss(evergreen, '拾新 · 常青发现', '不限发布时间的工具、项目和灵感。条目时间是收录时间，不是产品发布日期。', site_url, 'discoveries.xml', now))
    (out / '.nojekyll').touch()
    print(f'Built {len(editions)} curated editions / {len(news)} reviewed stories, {len(discoveries)} discoveries. Raw candidates are not published.')
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
