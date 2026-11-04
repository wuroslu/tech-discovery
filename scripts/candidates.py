#!/usr/bin/env python3
"""Print recent feed candidates for editorial research. Never publishes summaries."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from aggregate import parse_date, read_json
from build import deduplicate
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=3)
    parser.add_argument('--limit',type=int,default=30)
    args=parser.parse_args()
    config=read_json(ROOT/'config/sources.json',{})
    sources={s['id']:s for s in config['sources'] if s.get('enabled',True)}
    state=read_json(ROOT/'data/news.json',{})
    raw=[item for key,source in state.get('by_source',{}).items() if key in sources for item in source['items']]
    cutoff=datetime.now(timezone.utc)-timedelta(days=args.days)
    candidates=[i for i in deduplicate(raw,sources) if parse_date(i.get('published_at')) and parse_date(i['published_at'])>=cutoff]
    print(json.dumps({'notice':'Candidates only. Read each original before writing Chinese summaries. Do not auto-publish this output.',
                      'candidate_count':len(candidates),'items':candidates[:args.limit]},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
