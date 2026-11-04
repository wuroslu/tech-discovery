import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.error import URLError
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from aggregate import canonical_url, merge_source, parse_date, parse_feed, update
from build import build, deduplicate, rss

NOW = datetime(2026, 11, 4, 6, 0, tzinfo=timezone.utc)
SOURCE = {'id':'test','name':'Test source','kind':'官方','category':'ai','url':'https://example.com/feed','homepage':'https://example.com'}
RSS = b'''<rss version="2.0"><channel><item><title>Fresh &amp; useful</title><link>https://example.com/post?utm_source=rss&amp;id=7#top</link><pubDate>Tue, 03 Nov 2026 12:00:00 +0000</pubDate></item></channel></rss>'''
ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom post</title><link href="https://example.com/atom"/><published>2026-11-02T12:00:00Z</published><updated>2026-11-04T12:00:00Z</updated></entry></feed>'''

class ParserTests(unittest.TestCase):
    def test_tracking_removal_preserves_semantics(self):
        self.assertEqual(canonical_url('https://Example.com:443/path?utm_source=a&id=7&fbclid=x#top'), 'https://example.com/path?id=7')
        self.assertNotEqual(canonical_url('https://example.com/?id=1'), canonical_url('https://example.com/?id=2'))
    def test_unsafe_urls_rejected(self):
        for url in ('javascript:alert(1)', 'data:text/html,test', 'https://user:pass@example.com', 'https://example.com:bad', 'https://bad host/'): self.assertIsNone(canonical_url(url))
    def test_rss_date_and_url(self):
        items = parse_feed(RSS, SOURCE, NOW)
        self.assertEqual(items[0]['title'], 'Fresh & useful')
        self.assertEqual(items[0]['url'], 'https://example.com/post?id=7')
        self.assertEqual(items[0]['published_at'], '2026-11-03T12:00:00Z')
    def test_atom_published_not_updated(self):
        self.assertEqual(parse_feed(ATOM, SOURCE, NOW)[0]['published_at'], '2026-11-02T12:00:00Z')
    def test_updated_only_stays_undated(self):
        payload = ATOM.replace(b'<published>2026-11-02T12:00:00Z</published>', b'')
        self.assertIsNone(parse_feed(payload, SOURCE, NOW)[0]['published_at'])
    def test_missing_date_not_fabricated(self):
        payload = RSS.replace(b'<pubDate>Tue, 03 Nov 2026 12:00:00 +0000</pubDate>', b'')
        self.assertIsNone(parse_feed(payload, SOURCE, NOW)[0]['published_at'])
    def test_future_entries_skipped(self):
        payload = RSS.replace(b'Tue, 03 Nov 2026', b'Thu, 03 Dec 2026')
        with self.assertRaises(ValueError): parse_feed(payload, SOURCE, NOW)
    def test_html_title_is_plain_text(self):
        payload = RSS.replace(b'Fresh &amp; useful', b'&lt;b&gt;Plain&lt;/b&gt;')
        self.assertEqual(parse_feed(payload, SOURCE, NOW)[0]['title'], 'Plain')
    def test_entities_rejected(self):
        with self.assertRaises(ValueError): parse_feed(b'<!DOCTYPE x [<!ENTITY x "boom">]><rss/>', SOURCE, NOW)
    def test_html_is_not_feed(self):
        with self.assertRaises(ValueError): parse_feed(b'<html><body>blocked</body></html>', SOURCE, NOW)
    def test_empty_feed_retains_previous(self):
        self._assert_retained(lambda s: b'<rss><channel/></rss>')
    def test_error_feed_retains_previous(self):
        def fail(s): raise URLError('timeout')
        self._assert_retained(fail)
    def _assert_retained(self, fetcher):
        old = {'schema_version':1,'last_success_at':'2026-10-01T00:00:00Z','by_source':{'test': {'last_success_at':'2026-10-01T00:00:00Z','items':parse_feed(RSS, SOURCE, NOW)}}}
        before = copy.deepcopy(old)
        state, statuses = update({'sources':[SOURCE]}, old, {}, NOW, fetcher)
        self.assertEqual(state, before)
        self.assertEqual(old, before)
        self.assertEqual(statuses['sources']['test']['state'], 'error')
    def test_success_merges_and_preserves_first_seen(self):
        fresh = parse_feed(RSS, SOURCE, NOW)
        old = copy.deepcopy(fresh); old[0]['first_seen_at'] = '2026-11-01T00:00:00Z'
        result = merge_source(old, fresh, NOW, 90)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['first_seen_at'], '2026-11-01T00:00:00Z')
    def test_mixed_success_keeps_failed_source(self):
        second = {**SOURCE, 'id':'second'}
        old = {'schema_version':1,'last_success_at':None,'by_source':{'second':{'last_success_at':None,'items':[{'title':'Keep','url':'https://example.com/old'}]}}}
        def fetcher(source):
            if source['id']=='second': raise URLError('failure')
            return RSS
        state, health = update({'sources':[SOURCE,second]}, old, {}, NOW, fetcher)
        self.assertEqual(health['sources']['test']['state'],'ok')
        self.assertEqual(health['sources']['second']['state'],'error')
        self.assertEqual(state['by_source']['second'],old['by_source']['second'])
    def test_duplicate_sources_merge_attribution(self):
        one = parse_feed(RSS, SOURCE, NOW)[0]
        two = {**one, 'source_id':'other'}
        items = deduplicate([one,two], {'test':SOURCE,'other':{**SOURCE,'id':'other','name':'Second'}})
        self.assertEqual(len(items),1)
        self.assertEqual(len(items[0]['sources']),2)
    def test_title_dedup_only_for_long_exact_titles(self):
        one = {**parse_feed(RSS, SOURCE, NOW)[0], 'title':'A sufficiently long and exact duplicate headline'}
        two = {**one, 'url':'https://example.com/another'}
        self.assertEqual(len(deduplicate([one,two], {'test':SOURCE})),1)
        one['title']=two['title']='Update'
        self.assertEqual(len(deduplicate([one,two], {'test':SOURCE})),2)
    def test_rss_escaping_and_publication(self):
        items = parse_feed(RSS,SOURCE,NOW)
        payload = rss(items,'Test & RSS','A feed','https://example.com/site/','rss.xml',NOW)
        root = ET.fromstring(payload)
        self.assertEqual(root.findtext('channel/item/title'),'Fresh & useful')
        self.assertEqual(root.find('channel/item/guid').attrib['isPermaLink'],'false')
        self.assertEqual(root.find('{*}channel/{http://www.w3.org/2005/Atom}link').attrib['href'],'https://example.com/site/rss.xml')
    def test_build_empty_and_script_injection_escaping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for d in ('config','data','site'): (root/d).mkdir()
            (root/'config/sources.json').write_text(json.dumps({'sources':[SOURCE]}))
            (root/'data/news.json').write_text(json.dumps({'by_source':{}}))
            (root/'data/discoveries.json').write_text(json.dumps({'items':[{'id':'x','title':'</script><script>alert(1)</script>','url':'https://example.com','category':'software','verified_at':'2026-11-04','added_at':'2026-11-04'}]}))
            (root/'site/index.html').write_text('<html></html>')
            result=build(root,'https://example.com/site/',NOW)
            self.assertEqual(result['news'],[])
            self.assertNotIn('</script>',(root/'public/data.js').read_text())
            self.assertTrue((root/'public/rss.xml').exists())
            ET.parse(root/'public/discoveries.xml')
    def test_invalid_site_url_rejected(self):
        with self.assertRaises(ValueError): build(Path('/tmp/unused'),'javascript:alert(1)',NOW)
    def test_utf16_entities_rejected(self):
        payload = '<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel><item><title>&x;</title><link>https://example.com/x</link></item></channel></rss>'.encode('utf-16')
        with self.assertRaises(ValueError): parse_feed(payload, SOURCE, NOW)
    def test_doctype_text_inside_cdata_allowed(self):
        payload = RSS.replace(b'</item>', b'<description><![CDATA[An example: <!DOCTYPE html>]]></description></item>')
        self.assertEqual(len(parse_feed(payload,SOURCE,NOW)),1)
    def test_overflow_dates_are_unknown(self):
        self.assertIsNone(parse_date('9999-12-31T23:59:59-23:59'))
    def test_previous_publication_date_retained(self):
        old = parse_feed(RSS,SOURCE,NOW)
        fresh = copy.deepcopy(old); fresh[0]['published_at']=None
        self.assertEqual(merge_source(old,fresh,NOW,90)[0]['published_at'],old[0]['published_at'])
    def test_relative_atom_links_resolved(self):
        payload=ATOM.replace(b'<feed xmlns=',b'<feed xml:base="https://example.org/base/" xmlns=').replace(b'https://example.com/atom',b'../article')
        self.assertEqual(parse_feed(payload,SOURCE,NOW)[0]['url'],'https://example.org/article')
    def test_merged_aliases_deduplicated(self):
        a={**parse_feed(RSS,SOURCE,NOW)[0],'title':'This exact long title should collapse all aliases'}
        b={**a,'url':'https://example.com/post-b'}
        c={**b,'title':'A changed headline at the same existing URL'}
        self.assertEqual(len(deduplicate([a,b,c],{'test':SOURCE})),1)
    def test_known_date_from_duplicate_retained(self):
        a=parse_feed(RSS,SOURCE,NOW)[0]
        b={**a,'published_at':None,'first_seen_at':'2026-11-01T00:00:00Z'}
        self.assertEqual(deduplicate([a,b],{'test':SOURCE})[0]['published_at'],a['published_at'])
    def test_query_site_url_rejected(self):
        with self.assertRaises(ValueError): build(Path('/tmp/unused'),'https://example.com/site?x=1',NOW)
    def test_bad_dates(self):
        self.assertIsNone(parse_date('not a date'))
        self.assertEqual(parse_date('2026-11-04').tzinfo,timezone.utc)

if __name__ == '__main__': unittest.main()
