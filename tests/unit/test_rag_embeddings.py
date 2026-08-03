"""Embedding provider unit tests."""

from retroassist.rag.embeddings import HashingEmbedder, cosine_similarity, create_embedder


def test_hashing_embedder_is_deterministic() -> None:
    embedder = HashingEmbedder(dimensions=64)
    a = embedder.embed_query("blown fuse continuity")
    b = embedder.embed_query("blown fuse continuity")
    assert a == b
    assert len(a) == 64


def test_similar_texts_outscore_unrelated() -> None:
    embedder = HashingEmbedder(dimensions=128)
    q = embedder.embed_query("mains fuse continuity check")
    near = embedder.embed_query("check fuse continuity on mains input")
    far = embedder.embed_query("strawberry cheesecake recipe")
    assert cosine_similarity(q, near) > cosine_similarity(q, far)


def test_create_embedder_factory() -> None:
    embedder = create_embedder("hashing", dimensions=32)
    assert embedder.dimensions == 32
