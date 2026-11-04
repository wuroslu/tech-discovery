#!/usr/bin/env python3
"""Fetch public RSS/Atom feeds. Standard library only; preserve each failed source."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, urljoin
from urllib.request import Request, HTTPRedirectHandler, build_opener
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
MAX_BYTES = 5 * 1024 * 1024
TRACKING = {'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref_src'}


def stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            result = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    try:
        if result.tzinfo is None:
            result = result.replace(tzinfo=UTC)
        return result.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)


def plain(value: str) -> str:
    parser = TextOnly()
    parser.feed(unescape(value))
    return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()


def canonical_url(value: str) -> str | None:
    try:
        parts = urlsplit(value.strip())
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return None
        if any(c.isspace() for c in parts.netloc):
            return None
        port = parts.port
        host = parts.hostname.lower()
        if ':' in host:
            host = f'[{host}]'
        if port and not (parts.scheme == 'http' and port == 80 or parts.scheme == 'https' and port == 443):
            host += f':{port}'
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
        return urlunsplit((parts.scheme, host, parts.path or '/', urlencode(query), ''))
    except (ValueError, TypeError):
        return None


def local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def child_text(element, names) -> str:
    for child in element:
        if local_name(child.tag) in names:
            return ''.join(child.itertext()).strip()
    return ''


class SafeTreeBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError('DTD/entity declarations are not accepted')


def parse_feed(payload: bytes, source: dict, now: datetime, base_url: str | None = None) -> list[dict]:
    if len(payload) > MAX_BYTES:
        raise ValueError('Feed exceeds 5 MiB limit')
    root = ET.fromstring(payload, parser=ET.XMLParser(target=SafeTreeBuilder()))
    if local_name(root.tag) not in ('rss', 'feed', 'RDF'):
        raise ValueError('Response is not RSS or Atom')
    entries = [e for e in root.iter() if local_name(e.tag) in ('item', 'entry')]
    parent_map = {child: parent for parent in root.iter() for child in parent}
    def resolve_link(value, node):
        chain = []
        while node is not None:
            chain.append(node)
            node = parent_map.get(node)
        base = base_url or source['url']
        for ancestor in reversed(chain):
            base = urljoin(base, ancestor.get('{http://www.w3.org/XML/1998/namespace}base', ''))
        return canonical_url(urljoin(base, value))
    items = []
    seen = set()
    for entry in entries[:400]:
        title = plain(child_text(entry, {'title'}))[:500]
        link = child_text(entry, {'link'})
        link_node = entry
        if local_name(entry.tag) == 'entry':
            candidates = [e for e in entry if local_name(e.tag) == 'link'
                          and e.get('rel', 'alternate') == 'alternate']
            candidates.sort(key=lambda e: e.get('type', 'text/html') not in ('text/html', 'application/xhtml+xml'))
            link_node = candidates[0] if candidates else entry
            link = candidates[0].get('href', '') if candidates else ''
        url = resolve_link(link, link_node) if link else None
        if not title or not url or url in seen:
            continue
        date = parse_date(child_text(entry, {'pubDate', 'published', 'date'}))
        # Atom updated is deliberately NOT substituted for original publication time.
        if date and date > now + timedelta(hours=24):
            continue
        seen.add(url)
        items.append({'id': hashlib.sha256(url.encode()).hexdigest()[:20],
                      'title': title, 'url': url, 'published_at': stamp(date) if date else None,
                      'first_seen_at': stamp(now), 'fetched_at': stamp(now),
                      'source_id': source['id'], 'category': source['category']})
    if entries and not items:
        raise ValueError('Feed has entries but no usable title/URL pairs')
    return items


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class HTTPSRedirectOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('Refusing a non-HTTPS feed redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(source: dict) -> tuple[bytes, str]:
    url = canonical_url(source['url'])
    if not url or not url.startswith('https://'):
        raise ValueError('Source URL must use HTTPS')
    request = Request(url, headers={'User-Agent': 'TechDiscovery/1.0 (+RSS reader; no full article scraping)',
                                    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    for attempt in range(2):
        try:
            with build_opener(HTTPSRedirectOnly()).open(request, timeout=20) as response:
                if not response.url.startswith('https://'):
                    raise ValueError('Refusing a non-HTTPS feed redirect')
                payload = response.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ValueError('Feed exceeds 5 MiB limit')
                return payload, response.url
        except (HTTPError, URLError, TimeoutError, socket.timeout):
            if attempt == 1:
                raise
            time.sleep(1)
    raise RuntimeError('Unreachable')


def merge_source(old: list[dict], fresh: list[dict], now: datetime, retention: int) -> list[dict]:
    cutoff = now - timedelta(days=retention)
    combined = {item['url']: dict(item) for item in old}
    for item in fresh:
        record = dict(item)
        if item['url'] in combined:
            record['first_seen_at'] = combined[item['url']].get('first_seen_at', record['first_seen_at'])
            if not record.get('published_at'):
                record['published_at'] = combined[item['url']].get('published_at')
        combined[item['url']] = record
    kept = [item for item in combined.values()
            if (parse_date(item.get('published_at')) or parse_date(item.get('first_seen_at')) or now) >= cutoff]
    return sorted(kept, key=lambda x: x.get('published_at') or x.get('first_seen_at', ''), reverse=True)[:250]


def update(config: dict, state: dict, previous_status: dict, now: datetime, fetcher=fetch):
    # Work on a copy. A failed fetch never replaces a source's last good items.
    state = json.loads(json.dumps(state))
    state.setdefault('by_source', {})
    state.pop('items', None)  # Initial empty-state schema migration.
    status = {'schema_version': 1, 'attempted_at': stamp(now), 'sources': {}}
    enabled = [s for s in config['sources'] if s.get('enabled', True)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(fetcher, source): source for source in enabled}
        for job in as_completed(jobs):
            source = jobs[job]
            key = source['id']
            old = state['by_source'].get(key, {'items': [], 'last_success_at': None})
            prior = previous_status.get('sources', {}).get(key, {})
            try:
                fetched = job.result()
                payload, effective_url = fetched if isinstance(fetched, tuple) else (fetched, source['url'])
                parsed = parse_feed(payload, source, now, effective_url)
                # Empty feeds may signal upstream trouble. Never erase a known good feed.
                if not parsed:
                    raise ValueError('Empty feed; retained last successful content')
                records = merge_source(old['items'], parsed, now, config.get('retention_days', 90))
                state['by_source'][key] = {'items': records, 'last_success_at': stamp(now)}
                state['last_success_at'] = stamp(now)
                status['sources'][key] = {'state': 'ok', 'attempted_at': stamp(now),
                    'last_success_at': stamp(now), 'item_count': len(records), 'error': None,
                    'consecutive_failures': 0}
            except (ET.ParseError, ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
                # Log exception types, never response bodies or credentials.
                reason = f'HTTP {exc.code}' if isinstance(exc, HTTPError) else type(exc).__name__
                status['sources'][key] = {'state': 'error', 'attempted_at': stamp(now),
                    'last_success_at': old.get('last_success_at'), 'item_count': len(old.get('items', [])),
                    'error': reason, 'consecutive_failures': prior.get('consecutive_failures', 0) + 1}
                print(f"Warning: {key}: {reason}; retained {len(old.get('items', []))} items")
    return state, status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    config = read_json(args.root / 'config/sources.json', {})
    state = read_json(args.root / 'data/news.json', {'schema_version': 1, 'by_source': {}, 'last_success_at': None})
    prior = read_json(args.root / 'data/source_status.json', {'sources': {}})
    state, status = update(config, state, prior, datetime.now(UTC))
    atomic_json(args.root / 'data/news.json', state)
    atomic_json(args.root / 'data/source_status.json', status)
    successes = sum(s['state'] == 'ok' for s in status['sources'].values())
    print(f"Fetched {successes}/{len(status['sources'])} sources. Previous content retained on failure.")
    # Partial/all upstream failures are visible in data; still deploy retained content and health.
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
