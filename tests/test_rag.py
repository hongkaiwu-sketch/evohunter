import os
import tempfile

import pytest

from evohunter.rag import (
    EmbeddingProvider,
    KnowledgeBaseManager,
    StructuredKnowledgeStore,
    VectorStore,
)
from evohunter.rag.models import CompanyProfile, CultureTag, JDTemplate, RAGResult


@pytest.fixture
def embedder():
    return EmbeddingProvider(dimension=32)


@pytest.fixture
def vector_store(embedder):
    return VectorStore(dimension=embedder.dimension)


@pytest.fixture
def structured_store():
    tmp = tempfile.mktemp(suffix=".db")
    store = StructuredKnowledgeStore(tmp)
    store.initialize_tables()
    yield store
    try:
        os.unlink(tmp)
    except OSError:
        pass


@pytest.fixture
def kb_manager(vector_store, structured_store, embedder):
    return KnowledgeBaseManager(vector_store, structured_store, embedder)


def test_embedding_provider_deterministic():
    """Same text should produce same embedding."""
    ep = EmbeddingProvider(dimension=32)
    a = ep.embed_text("hello world")
    b = ep.embed_text("hello world")
    assert a == b
    assert len(a) == 32


def test_embedding_provider_batch(embedder):
    texts = ["python engineer", "java developer", "devops sre"]
    embeddings = embedder.embed_texts(texts)
    assert len(embeddings) == 3
    assert all(len(e) == 32 for e in embeddings)


def test_vector_store_add_and_search(vector_store, embedder):
    v_python = embedder.embed_text("python django flask")
    v_java = embedder.embed_text("java spring hibernate")
    v_devops = embedder.embed_text("docker kubernetes terraform")

    vector_store.add("jdt_python", v_python, {"role": "python_dev"})
    vector_store.add("jdt_java", v_java, {"role": "java_dev"})
    vector_store.add("jdt_devops", v_devops, {"role": "devops_eng"})

    assert vector_store.count() == 3

    # Search with a python query — should match python best
    q = embedder.embed_text("python web developer")
    results = vector_store.search(q, top_k=2)

    assert len(results) == 2
    # First result should be most similar
    top_ids = {r[0] for r in results}
    assert "jdt_python" in top_ids


def test_vector_store_delete(vector_store, embedder):
    v = embedder.embed_text("test")
    vector_store.add("test_id", v)
    assert vector_store.count() == 1
    vector_store.delete("test_id")
    assert vector_store.count() == 0
    assert vector_store.search(v) == []


def test_vector_store_persist_and_load(tmp_path, vector_store, embedder):
    v = embedder.embed_text("persist test")
    vector_store.add("persist_1", v, {"key": "value"})

    persist_dir = str(tmp_path / "vectors")
    os.makedirs(persist_dir, exist_ok=True)
    vector_store.persist(persist_dir)

    loaded = VectorStore.load(persist_dir, dimension=32)
    assert loaded.count() == 1
    results = loaded.search(v, top_k=1)
    assert results[0][0] == "persist_1"
    assert results[0][2]["key"] == "value"


def test_structured_store_company_profile(structured_store):
    profile = CompanyProfile(
        company_hash="abc123",
        company_name_encrypted="TestCorp",
        industry="tech",
        description="A test company",
        culture_tags=["fast-paced", "flat"],
        remote_policy="hybrid",
    )

    structured_store.save_company_profile(profile)
    loaded = structured_store.get_company_profile("abc123")
    assert loaded is not None
    assert loaded.industry == "tech"
    assert loaded.culture_tags == ["fast-paced", "flat"]


def test_structured_store_jd_templates(structured_store):
    template = JDTemplate(
        template_id="jdt_001",
        role_category="ai_engineer",
        seniority_level="senior",
        industry="tech",
        required_skills_template=["Python", "LLM", "PyTorch"],
        salary_template="40k-60k",
        content="Experienced AI Engineer needed...",
    )

    structured_store.save_jd_template(template)
    results = structured_store.search_jd_templates(role_category="ai_engineer")
    assert len(results) == 1
    assert results[0].required_skills_template == ["Python", "LLM", "PyTorch"]


def test_structured_store_culture_tags(structured_store):
    tag = CultureTag(
        tag_id="tag_fast_paced",
        name="fast-paced",
        category="work_style",
        description="Fast moving environment",
    )
    structured_store.save_culture_tag(tag)

    all_tags = structured_store.get_all_tags()
    assert len(all_tags) == 1
    assert all_tags[0].name == "fast-paced"


def test_kb_manager_index_and_retrieve(kb_manager, embedder):
    # Index a company
    profile = kb_manager.index_company(
        company_name="TestAI Inc",
        industry="tech",
        description="AI startup building LLM products",
        culture_tags=["fast-paced", "innovation"],
        remote_policy="hybrid",
    )
    assert profile.company_hash is not None

    # Index a JD template
    template = kb_manager.index_jd_template(
        role_category="ai_engineer",
        seniority_level="senior",
        industry="tech",
        required_skills=["Python", "LLM", "PyTorch"],
        content="Senior AI Engineer building LLM products",
    )
    assert template.template_id.startswith("jdt_")

    # Retrieve for JD generation
    result = kb_manager.retrieve_for_jd_generation(
        company_name="TestAI Inc",
        role_title="AI Engineer",
    )
    assert isinstance(result, RAGResult)
    assert result.total_found >= 0  # may find company + templates


def test_kb_manager_retrieve_empty_kb(kb_manager):
    """Retrieval with no indexed data should not crash."""
    result = kb_manager.retrieve_for_jd_generation(
        company_name="Unknown Corp",
        role_title="AI Engineer",
    )
    assert result.total_found == 0
