"""MiniLM mean-pooling on CPU via ONNX; avoids installing a GPU tensor stack."""

from functools import lru_cache
import hashlib
from sqlalchemy import text
from accesslife.config import settings
from accesslife.persistence.db import Session


@lru_cache
def model():
    import onnxruntime as ort

    ort.disable_telemetry_events()
    from tokenizers import Tokenizer
    from huggingface_hub import hf_hub_download

    repo = "sentence-transformers/all-MiniLM-L6-v2"
    revision = settings().embedding_model_revision
    tokenizer = Tokenizer.from_file(hf_hub_download(repo, "tokenizer.json", revision=revision))
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        hf_hub_download(repo, "onnx/model.onnx", revision=revision),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    return tokenizer, session


def embed(texts):
    import numpy as np

    tokenizer, session = model()
    encodings = tokenizer.encode_batch(texts)
    inputs = {
        "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
        "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
    }
    required = {i.name for i in session.get_inputs()}
    hidden = session.run(None, {k: v for k, v in inputs.items() if k in required})[0]
    mask = inputs["attention_mask"][..., None]
    pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
    vectors = pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
    return vectors, [len(e.ids) for e in encodings]


def ingest_catalogue():
    from accesslife.adapters.catalogue import EVIDENCE, PLACES

    rows = []
    for evidence in EVIDENCE.values():
        place = next(p for p in PLACES if any(evidence.id in f.evidence_ids for f in p.facts))
        rows.append((evidence, place.city_id, f"{evidence.title}. {evidence.claim}"))
    vectors, counts = embed([r[2] for r in rows])
    with Session.begin() as db:
        # A tiny original-summary corpus; no proprietary pages or Qloo data are copied.
        for (evidence, city, passage), vector, count in zip(rows, vectors, counts):
            if count > 256:
                raise ValueError("Chunk exceeded model budget")
            db.execute(
                text("""INSERT INTO knowledge_chunks (id,city_id,text,source_url,source_title,corpus_version,model_revision,token_count,embedding)
                VALUES (:id,:city,:text,:url,:title,'catalogue-v1',:model,:count,CAST(:vector AS vector))
                ON CONFLICT (id) DO NOTHING"""),
                {
                    "id": hashlib.sha256(evidence.id.encode()).hexdigest(),
                    "city": city,
                    "text": passage,
                    "url": evidence.source_url,
                    "title": evidence.title,
                    "model": settings().embedding_model_revision,
                    "count": count,
                    "vector": str(vector.tolist()),
                },
            )
        for p in PLACES:
            db.execute(
                text(
                    "INSERT INTO place_locations(id,city_id,location) VALUES (:id,:city,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": p.id, "city": p.city_id, "lon": p.longitude, "lat": p.latitude},
            )
    return len(rows)


def retrieve(query, city_id):
    with Session() as db:
        count = db.scalar(
            text("SELECT count(*) FROM knowledge_chunks WHERE city_id=:city"), {"city": city_id}
        )
    if not count:
        return {"status": "not_indexed", "passages": []}
    vectors, _ = embed([query])
    with Session() as db:
        params = {
            "city": city_id,
            "model": settings().embedding_model_revision,
            "vector": str(vectors[0].tolist()),
            "query": query,
        }
        dense = (
            db.execute(
                text(
                    "SELECT id,text,source_url,source_title FROM knowledge_chunks WHERE city_id=:city AND model_revision=:model AND corpus_version='catalogue-v1' ORDER BY embedding <=> CAST(:vector AS vector) LIMIT 20"
                ),
                params,
            )
            .mappings()
            .all()
        )
        lexical = (
            db.execute(
                text(
                    "SELECT id,text,source_url,source_title FROM knowledge_chunks WHERE city_id=:city AND model_revision=:model AND corpus_version='catalogue-v1' AND search_vector @@ plainto_tsquery('english',:query) ORDER BY ts_rank(search_vector,plainto_tsquery('english',:query)) DESC LIMIT 20"
                ),
                params,
            )
            .mappings()
            .all()
        )
    scores, rows = {}, {}
    for result in (dense, lexical):
        for rank, row in enumerate(result):
            scores[row["id"]] = scores.get(row["id"], 0) + 1 / (60 + rank + 1)
            rows[row["id"]] = dict(row)
    return {
        "status": "indexed",
        "passages": [rows[k] for k in sorted(scores, key=lambda k: -scores[k])[:5]],
        "model": "all-MiniLM-L6-v2",
        "dimensions": 384,
    }


if __name__ == "__main__":
    print({"admitted_original_summaries": ingest_catalogue()})
