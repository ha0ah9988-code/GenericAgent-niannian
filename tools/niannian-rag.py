#!/usr/bin/env python3
"""niannian-rag.py — 念念 RAG（embedding 语义搜索 + TF-IDF fallback）
用法:
  python3 niannian-rag.py ingest "文本" "来源"
  python3 niannian-rag.py search "问题"
  python3 niannian-rag.py stats
  python3 niannian-rag.py rebuild    # 重建所有 embedding
"""
import json, os, sys, time, pickle
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

DB_DIR = os.path.expanduser("~/niannian/db/rag")
# 优先本地 data/rag/（GA 仓库内）
_local_db = os.path.join(os.path.dirname(__file__), "..", "data", "rag")
if os.path.exists(os.path.join(_local_db, "entries.json")):
    DB_DIR = os.path.abspath(_local_db)
os.makedirs(DB_DIR, exist_ok=True)
VEC_FILE = os.path.join(DB_DIR, "tfidf.pkl")
EMB_FILE = os.path.join(DB_DIR, "embeddings.npy")
ENTRY_FILE = os.path.join(DB_DIR, "entries.json")

# 懒加载 embedding 模型
_model = None

def get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        except Exception as e:
            print(f"⚠️ embedding 模型加载失败: {e}，降级到 TF-IDF")
            _model = False
    return _model if _model is not False else None

def load_db():
    entries = []
    embeddings = None
    if os.path.exists(ENTRY_FILE):
        with open(ENTRY_FILE) as f:
            entries = json.load(f)
    if os.path.exists(EMB_FILE):
        embeddings = np.load(EMB_FILE)
    return entries, embeddings

def save_db(entries, embeddings=None):
    with open(ENTRY_FILE, "w") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    if embeddings is not None:
        np.save(EMB_FILE, embeddings)

def ingest(text, source="manual"):
    entries, embeddings = load_db()
    entries.append({"text": text, "source": source, "ts": time.time(), "weight": 1.0})
    
    model = get_model()
    if model and embeddings is not None:
        # 增量添加新 embedding
        new_emb = model.encode([text], normalize_embeddings=True)
        embeddings = np.vstack([embeddings, new_emb])
    elif model:
        # 首次使用 embedding
        embeddings = model.encode([text], normalize_embeddings=True)
    
    save_db(entries, embeddings)
    mode = "🧠 embedding" if embeddings is not None else "📝 TF-IDF"
    print(f"✅ 已存 ({len(entries)}条) [{mode}]: {text[:60]}...")
    return len(entries)

def rebuild():
    """重建所有 embedding（从 entries.json 重新编码）"""
    entries, _ = load_db()
    if not entries:
        print("📚 没有条目需要重建")
        return
    
    model = get_model()
    if not model:
        print("❌ embedding 模型不可用")
        return
    
    texts = [e["text"] for e in entries]
    print(f"🔨 编码 {len(texts)} 条...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    save_db(entries, embeddings)
    print(f"✅ 重建完成 ({len(entries)}条)")

def search(query, k=5):
    entries, embeddings = load_db()
    if not entries:
        return []
    
    model = get_model()
    if model and embeddings is not None and len(embeddings) == len(entries):
        # Embedding 语义搜索
        q_emb = model.encode([query], normalize_embeddings=True)
        scores = cosine_similarity(q_emb, embeddings)[0]
        threshold = 0.3  # 语义匹配阈值（比 TF-IDF 的 0.01 严格，但语义空间不同）
    else:
        # TF-IDF fallback
        if not os.path.exists(VEC_FILE):
            return []
        with open(VEC_FILE, "rb") as f:
            data = pickle.load(f)
        vec, matrix = data["vectorizer"], data["matrix"]
        if matrix is None:
            return []
        q_vec = vec.transform([query])
        scores = cosine_similarity(q_vec, matrix)[0]
        threshold = 0.01
    
    top_k = np.argsort(scores)[::-1][:k]
    results = []
    for idx in top_k:
        if scores[idx] < threshold:
            continue
        w = entries[idx].get("weight", 1.0)
        results.append({**entries[idx], "score": float(scores[idx]) * w})
    return results

def set_weight(index, w):
    entries, embeddings = load_db()
    if 0 <= index < len(entries):
        entries[index]["weight"] = float(w)
        save_db(entries, embeddings)
        return True
    return False

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ingest" and len(sys.argv) >= 3:
        source = sys.argv[3] if len(sys.argv) >= 4 else "manual"
        ingest(sys.argv[2], source)
    elif cmd == "rebuild":
        rebuild()
    elif cmd == "weight" and len(sys.argv) >= 4:
        ok = set_weight(int(sys.argv[2]), sys.argv[3])
        print(f"{'✅' if ok else '❌'} weight {sys.argv[2]} → {sys.argv[3]}")
    elif cmd == "search" and len(sys.argv) >= 3:
        results = search(sys.argv[2])
        if not results:
            print("🔍 无相关经验")
        for r in results:
            print(f"  [{r['score']:.2f}] {r['text'][:100]}")
            print(f"       📎 {r['source']}")
    elif cmd == "stats":
        entries, embeddings = load_db()
        mode = "🧠 embedding" if embeddings is not None else "📝 TF-IDF"
        dim = f", {embeddings.shape[1]}维" if embeddings is not None else ""
        print(f"📚 {len(entries)} 条经验 [{mode}{dim}]")
    else:
        print(__doc__)
