"""Seed the database with sample companies and candidates for demo."""

from evohunter.storage import initialize_database, save_candidate_genes, save_job_gene


def seed_demo_data(db_path: str = ".evohunter/workbench.db") -> dict:
    """Populate the database with demo companies and candidates."""
    initialize_database(db_path)

    # ── Sample JDs ──────────────────────────────────────────────────
    jds = [
        {"job_id": "jd_ai_engineer", "job_title": "AI Agent Engineer", "required_skills": ["python", "llm", "langchain", "docker", "rag"], "preferred_skills": ["kubernetes", "mlops"], "min_years_of_experience": 3, "salary_range": "25k-40k", "location": "shanghai", "seniority_level": "senior"},
        {"job_id": "jd_data_scientist", "job_title": "Data Scientist", "required_skills": ["python", "pytorch", "sql", "machine learning"], "preferred_skills": ["spark", "tableau"], "min_years_of_experience": 2, "salary_range": "20k-35k", "location": "beijing", "seniority_level": "mid"},
        {"job_id": "jd_backend_dev", "job_title": "Senior Backend Developer", "required_skills": ["go", "rust", "postgresql", "docker", "kubernetes"], "preferred_skills": ["kafka", "grpc"], "min_years_of_experience": 5, "salary_range": "35k-55k", "location": "shenzhen", "seniority_level": "lead"},
        {"job_id": "jd_product_manager", "job_title": "AI Product Manager", "required_skills": ["product management", "ai/ml basics", "data analysis"], "preferred_skills": ["llm", "saas"], "min_years_of_experience": 4, "salary_range": "30k-45k", "location": "shanghai", "seniority_level": "senior"},
        {"job_id": "jd_devops_engineer", "job_title": "DevOps Engineer", "required_skills": ["kubernetes", "docker", "terraform", "aws", "ci/cd"], "preferred_skills": ["prometheus", "golang"], "min_years_of_experience": 3, "salary_range": "28k-42k", "location": "hangzhou", "seniority_level": "mid"},
    ]

    for jd in jds:
        save_job_gene(db_path, jd)

    # ── Sample Candidates ───────────────────────────────────────────
    candidates = [
        {"candidate_id": "c_zhang_ting", "skill_vector": ["python", "llm", "langchain", "docker", "rag", "langgraph"], "years_of_experience": 5, "salary_expectation": "35k-40k", "location_preference": "shanghai", "recent_projects": ["RAG架构", "Agent工作流"], "availability": "open", "seniority_level": "senior"},
        {"candidate_id": "c_li_ming", "skill_vector": ["go", "rust", "postgresql", "docker", "kubernetes", "kafka"], "years_of_experience": 4, "salary_expectation": "40k-50k", "location_preference": "shenzhen", "recent_projects": ["消息系统重构", "微服务治理"], "availability": "interviewing", "seniority_level": "senior"},
        {"candidate_id": "c_wang_fang", "skill_vector": ["python", "pytorch", "sql", "spark", "machine learning", "tableau"], "years_of_experience": 3, "salary_expectation": "25k-32k", "location_preference": "beijing", "recent_projects": ["预测模型", "AB测试平台"], "availability": "open", "seniority_level": "mid"},
        {"candidate_id": "c_zhao_wei", "skill_vector": ["python", "llm", "docker", "product management", "data analysis"], "years_of_experience": 6, "salary_expectation": "40k-50k", "location_preference": "shanghai", "recent_projects": ["LLM SaaS 0到1", "AI客服机器人"], "availability": "open", "seniority_level": "lead"},
        {"candidate_id": "c_chen_yu", "skill_vector": ["kubernetes", "docker", "terraform", "aws", "prometheus", "golang"], "years_of_experience": 5, "salary_expectation": "35k-45k", "location_preference": "hangzhou", "recent_projects": ["K8s运维平台", "CI/CD标准化"], "availability": "open", "seniority_level": "senior"},
    ]

    for c in candidates:
        save_candidate_genes(db_path, [c])

    return {"jds": len(jds), "candidates": len(candidates)}
