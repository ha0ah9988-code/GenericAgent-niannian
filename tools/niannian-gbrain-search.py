#!/usr/bin/env python3
"""gbrain 记忆树检索 — TF-IDF语义匹配，零LLM成本"""
import sys, sqlite3, os, json, re
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

DB = Path(os.path.expanduser("~/niannian/db/knowledge.db"))
# 优先本地 data/knowledge.db（GA 仓库内）
_local_db = Path(os.path.join(os.path.dirname(__file__), "..", "data", "knowledge.db"))
if _local_db.exists():
    DB = _local_db.resolve()
MAX_RESULTS = 3
MIN_SCORE = 0.05  # 低于此分数的不要

def search(query: str) -> list[dict]:
    if not DB.exists():
        return []
    
    conn = sqlite3.connect(str(DB))
    rows = conn.execute(
        "SELECT id, title, reason, category, time FROM knowledge ORDER BY time DESC LIMIT 200"
    ).fetchall()
    conn.close()
    
    if not rows:
        return []
    
    # 构建文档：title + summary
    docs = [f"{r[1]} {r[2]}" for r in rows]
    
    # TF-IDF
    vectorizer = TfidfVectorizer(max_features=1000)
    try:
        tfidf = vectorizer.fit_transform([query] + docs)
        sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()
    except:
        return []
    
    # 排序取Top N
    results = []
    for i, score in enumerate(sims):
        if score < MIN_SCORE:
            continue
        results.append({
            "id": rows[i][0],
            "title": rows[i][1],
            "summary": rows[i][2],
            "category": rows[i][3],
            "time": rows[i][4],
            "score": float(score)
        })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:MAX_RESULTS]

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if not query:
        print("")
        sys.exit(0)
    
    hits = search(query)
    if not hits:
        print("")
        sys.exit(0)
    
    for h in hits:
        print(f"[{h['category']}] {h['title']}")
        print(f"  {h['summary'][:300]}")
        print(f"  score:{h['score']:.3f} | {h['time']}")
        print()
