import copy
from datetime import datetime,timezone
from pathlib import Path
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build import build,validate_digests,rss
NOW=datetime(2026,11,4,8,tzinfo=timezone.utc)
ITEM={'id':'curated-article-001','title_zh':'一条经过核对的科技消息','what_zh':'这里说明原文中可以核对的事实。','why_zh':'这里给出明确标为编辑判断的意义。','url':'https://example.org/article','original_title':'A verified technology story','source_name':'Official source','source_language':'en','source_published_at':'2026-11-03','checked_at':'2026-11-04T07:00:00Z','review_status':'reviewed','category':'software'}
EDITION={'date':'2026-11-03','status':'published','published_at':'2026-11-04T07:05:00Z','items':[ITEM]}
class EditorialTests(unittest.TestCase):
 def document(self): return {'editions':[copy.deepcopy(EDITION)]}
 def test_backfill_keeps_actual_publication_and_source_dates(self):
  e=validate_digests(self.document(),NOW)[0]
  self.assertEqual(e['date'],'2026-11-03')
  self.assertEqual(e['items'][0]['source_published_at'],'2026-11-03')
  self.assertEqual(e['items'][0]['published_at'],'2026-11-04T07:05:00Z')
 def test_six_items_rejected_not_truncated(self):
  d=self.document();d['editions'][0]['items']=[{**ITEM,'id':f'curated-story-{i}','url':f'https://example.org/{i}'} for i in range(6)]
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_five_items_allowed(self):
  d=self.document();d['editions'][0]['items']=[{**ITEM,'id':f'curated-story-{i}','url':f'https://example.org/{i}'} for i in range(5)]
  self.assertEqual(len(validate_digests(d,NOW)[0]['items']),5)
 def test_draft_editions_are_not_published(self):
  d=self.document();d['editions'][0]['status']='draft'
  self.assertEqual(validate_digests(d,NOW),[])
 def test_unreviewed_item_rejected(self):
  d=self.document();d['editions'][0]['items'][0]['review_status']='pending'
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_english_only_copy_rejected(self):
  for field in ('title_zh','what_zh','why_zh'):
   d=self.document();d['editions'][0]['items'][0][field]='English only'
   with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_missing_source_date_rejected(self):
  d=self.document();del d['editions'][0]['items'][0]['source_published_at']
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_old_story_rejected(self):
  d=self.document();d['editions'][0]['items'][0]['source_published_at']='2026-09-01'
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_duplicate_dates_rejected(self):
  d=self.document();d['editions'].append(copy.deepcopy(d['editions'][0]))
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_duplicate_story_across_editions_rejected(self):
  d=self.document();e=copy.deepcopy(EDITION);e['date']='2026-11-04';d['editions'].append(e)
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_future_edition_rejected(self):
  d=self.document();d['editions'][0]['date']='2026-11-05'
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_future_check_rejected(self):
  d=self.document();d['editions'][0]['items'][0]['checked_at']='2026-11-05T07:00:00Z'
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_unsupported_source_language_rejected(self):
  d=self.document();d['editions'][0]['items'][0]['source_language']='unknown'
  with self.assertRaises(ValueError):validate_digests(d,NOW)
 def test_chinese_source_is_publishable(self):
  d=self.document();i=d['editions'][0]['items'][0];i.update(source_language='zh',source_name='国内官方来源',original_title='官方中文公告')
  self.assertEqual(validate_digests(d,NOW)[0]['items'][0]['source_language'],'zh')
 def test_rss_labels_chinese_original_correctly(self):
  d=self.document();d['editions'][0]['items'][0]['source_language']='zh'
  e=validate_digests(d,NOW)[0]
  r=ET.fromstring(rss(e['items'],'精选','摘要','https://example.org/','rss.xml',NOW))
  self.assertIn('中文原文：',r.findtext('channel/item/description'))
  self.assertNotIn('英文原文：',r.findtext('channel/item/description'))
 def test_rss_has_chinese_summary_and_stable_guid_after_edit(self):
  e=validate_digests(self.document(),NOW)[0]
  first=ET.fromstring(rss(e['items'],'精选','摘要','https://example.org/','rss.xml',NOW))
  e['items'][0]['title_zh']='编辑后的中文标题'
  second=ET.fromstring(rss(e['items'],'精选','摘要','https://example.org/','rss.xml',NOW))
  self.assertEqual(first.findtext('channel/item/guid'),second.findtext('channel/item/guid'))
  self.assertIn('发生了什么',first.findtext('channel/item/description'))
  self.assertIn('编辑判断',first.findtext('channel/item/description'))
  self.assertIn('2026-11-03',first.findtext('channel/item/description'))
 def test_raw_candidates_never_fill_empty_digest(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for d in ('data','config','site'):(root/d).mkdir()
   (root/'config/sources.json').write_text(json.dumps({'sources':[]}))
   (root/'data/news.json').write_text(json.dumps({'by_source':{'source':{'items':[{'id':'raw','title':'Raw must never publish','url':'https://example.org/raw'}]}}}))
   (root/'data/discoveries.json').write_text('{"items":[]}')
   result=build(root,'https://example.org/',NOW)
   self.assertEqual(result['news'],[])
   self.assertEqual(result['editions'],[])
   self.assertNotIn('Raw must never publish',(root/'public/data.json').read_text())
   self.assertEqual(ET.parse(root/'public/rss.xml').findall('channel/item'),[])
if __name__=='__main__':unittest.main()
