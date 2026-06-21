# EvoHunter 前端架构说明

## 概览

两个独立页面，共享同一套后端 API。零外部依赖，纯 HTML/CSS/原生 JS + Canvas。

```
evohunter/web/static/
├── index.html          # 工作台 (主页面)
├── app.js              # 工作台逻辑
├── styles.css          # 工作台样式
├── evolution.html      # 进化控制台
├── evolution.js        # 进化台逻辑 (Canvas图表)
├── evolution.css       # 进化台样式
└── locales/
    ├── en.json         # 英文文案 (可忽略, 当前未使用i18n)
    └── zh.json         # 中文文案
```

---

## 一、后端 API 总览

所有 API 都是 `POST`，body 为 JSON。

### 池子管理

```
POST /api/pool/search
  入: { skills?, location?, seniority_level?, side? }  // side: "jd"|"candidate"|"both"
  出: { jds: [...], candidates: [...] }
  说明: 搜索 JD 和候选人。skills 逗号分隔模糊匹配, location/seniority 精确匹配。
        jds 和 candidates 各是基因协议 dict 数组。结构见下方"数据结构"。

POST /api/pool/seed
  入: {}
  出: { seeded: true, jds: 5, candidates: 5 }
  说明: 预置 5 个 JD + 5 个候选人 demo 数据到 SQLite。
```

### 猎头评估

```
POST /api/recruiter/assess
  入: { job_gene: {...}, resume_text: "简历文本", language: "zh" }
  出: RecruiterAssessment (见下方数据结构)
  说明: 核心 AI 调用。10 分制评分 + 推荐词生成。
        匹配度 >= 7 且信息齐全 → 自动生成推荐词
        匹配度 < 7 → requires_human_input=true, 不生成推荐词
        缺少薪资/职级/离职原因 → missing_fields 列表标注
```

### JD 和简历解析

```
POST /api/parse-job
  入: { text: "JD文本", db_path? }
  出: { job_gene: {...} }
  说明: LLM 解析 JD 文本 → 结构化 JobGene, 可选写入 SQLite

POST /api/parse-candidates
  入: { text: "简历文本", db_path? }
  出: { candidate_genes: [...] }
  说明: LLM 解析简历文本 → 结构化 CandidateGene 数组, 可选写入 SQLite
```

### 进化数据

```
POST /api/evolution/data
  入: { db_path? }
  出: { generations: [...], feedback_summary: {...}, current_strategy: {...} }
  说明: 进化历史全量数据, 供 Canvas 图表渲染

POST /api/evolution/strategy
  GET用法(无strategy字段): 返回当前策略
  POST用法: { strategy, mutation_rate, mutation_strength, target_dimensions }
  出: { saved: true }
  说明: 读写进化策略, 写入 SQLite 后下次 evolver 自动读取
```

### 其他

```
POST /api/config        → { has_api_key: bool }
POST /api/draft-outreach → { outreach_draft: { subject, message_body, rationale } }
POST /api/evaluation/generate → { final_recommendation, resume_summary, ... }
POST /api/workflow/list    → { workflows: [...] }
POST /api/workflow/execute → 完整工作流 + 进化桥接 (当前前端未使用)
POST /api/mcp/tools        → MCP 工具列表
```

---

## 二、核心数据结构

### JobGene (JD)
```json
{
  "job_id": "jd_ai_engineer",
  "job_title": "AI Agent Engineer",
  "required_skills": ["python", "llm", "langchain"],
  "preferred_skills": ["kubernetes"],
  "min_years_of_experience": 3,
  "salary_range": "25k-40k",
  "location": "shanghai",
  "seniority_level": "senior"
}
```

### CandidateGene (候选人)
```json
{
  "candidate_id": "c_zhang_ting",
  "skill_vector": ["python", "llm", "langchain", "docker"],
  "years_of_experience": 5,
  "salary_expectation": "35k-40k",
  "location_preference": "shanghai",
  "recent_projects": ["RAG架构设计"],
  "availability": "open",
  "seniority_level": "senior"
}
```

### RecruiterAssessment (猎头评估结果) ⭐ 核心
```json
{
  "candidate_name": "张婷",
  "match_degree": 8,                    // 1-10 总分
  "hard_match_score": 6.0,              // 硬匹配分(满分7 = 70%)
  "hr_bonus_score": 2.0,                // HR加分(满分3 = 30%)
  "main_match_points": ["技能完全覆盖JD"], // 匹配点
  "main_deductions": ["学历未体现"],       // 扣分项
  "conclusion": "强匹配",                 // 结论文字
  "background_summary": "5年Python和LLM经验...",
  "reasons_for_recommendation": [        // 3-4条推荐理由
    "具备LLM应用架构设计经验..."
  ],
  "tech_tags": ["Python", "LLM", "LangChain", "Docker", "RAG"],
  "current_salary": "35k/月",
  "current_level": "高级工程师",
  "reason_for_leaving": "希望做更有技术深度的产品",
  "recommendation_text": "张婷\n\n5年Python...\n\n推荐理由\n1. ...",  // 仅>=7且信息齐全时
  "requires_human_input": false,         // <7 或信息不全时为 true
  "missing_fields": []                   // 缺失的必填信息
}
```

### Evolution Data (进化历史)
```json
{
  "generations": [
    {
      "generation": 1,
      "weights": {
        "skill": 0.42, "experience": 0.18,
        "salary": 0.17, "location": 0.13, "seniority": 0.10
      },
      "change_magnitude": 0.08,
      "convergence": "converging",       // stable|converging|adjusting|no_data
      "strategy": "balanced",
      "created_at": "2026-06-21T..."
    }
  ],
  "feedback_summary": {
    "reply_positive": 3,
    "salary_mismatch": 2
  },
  "current_strategy": {
    "strategy": "balanced",
    "mutation_rate": 0.4,
    "mutation_strength": 0.04,
    "target_dimensions": ["skill", "experience", "salary", "location", "seniority"]
  }
}
```

---

## 三、工作台 (`index.html` + `app.js`)

### 页面结构

```
┌─ Topbar ──────────────────────────────────────────────────┐
│  EvoHunter    Gen 0              [Seed Demo] [Evolution→] │
├─ Mode Tabs ───────────────────────────────────────────────┤
│  [🏢 I'm Hiring]  [👤 I'm Looking]                        │
├─ Mode Content (切换显示) ─────────────────────────────────┤
│                                                            │
│  ┌─ Search Row ───────────────────────────────────────┐   │
│  │  [Skills input] [Location input] [Level select] [Search] │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  Matching JDs (or Candidates) — 卡片列表, 点击选中一个     │
│  ┌────────────────┐ ┌────────────────┐                    │
│  │ 🏢 AI Engineer │ │ 🏢 Backend Dev │  ...              │
│  │ shanghai·25-40k│ │ shenzhen·35-55k│                    │
│  └────────────────┘ └────────────────┘                    │
│                                                            │
│  [+ Import new JD not in database]  ← 折叠导入区          │
│                                                            │
│  Candidates for "AI Engineer" — 选中JD后的匹配结果         │
│  ┌──────────────────────────────────────────┐             │
│  │ 张婷  8/10  python·llm·docker  ← 点击展开│             │
│  │ 赵伟  7/10  python·llm·product           │             │
│  └──────────────────────────────────────────┘             │
│                                                            │
│  ┌─ Detail Panel (展开后) ────────────────────────────┐   │
│  │  Match Points / Deductions / Tech Tags /           │   │
│  │  Recommendation Text / Compensation / Reason       │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
├─ Status Bar ───────────────────────────────────────────────┤
│  Gen 3 · 5 JDs · 5 candidates · balanced · API ready      │
└────────────────────────────────────────────────────────────┘
```

### 全局状态

```javascript
let mode = 'hiring';                    // 'hiring' | 'looking'
let pool = { jds: [], candidates: [] }; // 当前搜索/加载的数据
let selectedJD = null;                  // 选中的 JD ID (hiring模式)
let selectedCandidate = null;           // 选中的候选人 ID (looking模式)
let results = [];                       // 匹配结果数组
let selectedResult = -1;                // 选中的结果索引
```

### 交互流程

**Hiring 模式**:
1. 用户点 `Seed Demo` → `POST /api/pool/seed` → `POST /api/pool/search` 加载全部数据
2. 用户搜索 JD → `POST /api/pool/search { skills, location, level, side:"jd" }`
3. 用户点击一个 JD → `selectJD(id)`:
   - 设置 `selectedJD = id`
   - 遍历 `pool.candidates`(如果空则先加载)
   - 对每个候选人调 `POST /api/recruiter/assess { job_gene, resume_text }`
   - 结果按 score 降序排列
   - 渲染结果卡片列表
4. 用户点击结果卡片 → 展开 detail panel

**Looking 模式**:
1. 同上但方向相反: 搜索候选人 → 选一个 → 匹配全部 JD

**导入**:
- Hiring 模式: 折叠区粘贴 JD 文本 → `POST /api/parse-job` → 刷新 JD 列表
- Looking 模式: 折叠区粘贴简历文本 → `POST /api/parse-candidates` → 刷新候选人列表

### 关键函数

```javascript
init()                   // 绑定事件、检查 API key、加载数据
switchMode(m)            // 切换 hiring/looking tab

// 搜索
searchJDs()              // → /api/pool/search { side:"jd" }
searchCandidates()       // → /api/pool/search { side:"candidate" }

// 选择并匹配 (核心)
selectJD(jobId)          // 选一个JD → 遍历全部candidates调recruiter/assess → 排序
selectCandidate(candId)  // 选一个候选人 → 遍历全部JDs调recruiter/assess → 排序

// 渲染
renderJDList()           // 渲染JD卡片列表
renderCandidateList()    // 渲染候选人卡片列表
renderHiringResults()    // 渲染匹配结果
renderLookingResults()   // 渲染匹配结果

// 详情
showHiringDetail(i)      // 展开第i个结果的详情
showLookingDetail(i)
detailHTML(r)            // 生成详情HTML

// 导入
importJD()               // → /api/parse-job
importResume()           // → /api/parse-candidates

// 种子数据
seed()                   // → /api/pool/seed → loadAll()
```

---

## 四、进化控制台 (`evolution.html` + `evolution.js`)

### 页面结构

```
┌─ Header ───────────────────────────────────────────────────┐
│  Evolution Control Center              [Workbench]         │
├─ Top Row ──────────────────────────────────────────────────┤
│  ┌─ Convergence Gauge ─┐  ┌─ Generation Overview ────────┐ │
│  │ Canvas 半圆仪表盘    │  │ Gen / Events / Magnitude    │ │
│  │ stable/converging/   │  │ Strategy / Convergence      │ │
│  │ adjusting            │  │ Last Evolved                │ │
│  └─────────────────────┘  └──────────────────────────────┘ │
├─ Weight Evolution River ───────────────────────────────────┤
│  Canvas 多折线图: 5维度 × N代, hover tooltip, 图例可点击   │
├─ Mid Row ──────────────────────────────────────────────────┤
│  ┌─ Feedback Pulse ────┐  ┌─ Strategy Control ───────────┐ │
│  │ 柱状图: 事件分布     │  │ Strategy dropdown           │ │
│  │ reply_positive ████ │  │ Mutation Rate slider        │ │
│  │ salary_mismatch ██  │  │ Mutation Strength slider    │ │
│  │ ...                 │  │ Target Dimensions checkboxes │ │
│  │                     │  │ [Apply Strategy]            │ │
│  └─────────────────────┘  └──────────────────────────────┘ │
├─ Generation Snapshots ─────────────────────────────────────┤
│  Gen0卡片  Gen1卡片  Gen2卡片 ...  (点击展开事件详情)       │
└────────────────────────────────────────────────────────────┘
```

### 数据加载

```javascript
async function loadData() {
  evolutionData = await POST /api/evolution/data { db_path }
  // evolutionData = { generations, feedback_summary, current_strategy }
}
// 每30秒自动刷新
```

### Canvas 图表 (纯手绘, 无库)

| 图表 | Canvas ID | 绘制函数 | 说明 |
|------|-----------|----------|------|
| 收敛仪表盘 | `gauge-canvas` | `renderGauge()` | 半圆弧 + 指针, stable(绿)/converging(黄)/adjusting(红) |
| 权重河流图 | `river-canvas` | `renderRiver()` | 5条折线, X=代数 Y=权重, grid+labels+hover tooltip |
| 反馈脉冲图 | `pulse-canvas` | `renderPulse()` | 水平柱状图, 颜色编码事件类型 |

### 策略控制

```javascript
// 表单提交 → POST /api/evolution/strategy
{
  strategy: "balanced" | "conservative" | "aggressive",
  mutation_rate: 0.1~0.8,
  mutation_strength: 0.01~0.10,
  target_dimensions: ["skill", "experience", ...]
}
// 写入 SQLite evolution_strategy 表
// EvoMapEvolver._apply_strategy_override() 在下次 run_cycle 时读取
```

### 关键函数

```javascript
loadData()          // 加载进化数据
renderAll()         // 重绘全部图表

// Canvas 图表
renderGauge()       // 收敛仪表盘
renderRiver()       // 权重河流图 (含 hover 交互)
renderPulse()       // 反馈脉冲图

// 其他
renderOverview()    // 代数概览数字
renderSnapshots()   // 代际快照时间线 (可展开卡片)
initLegend()        // 河流图图例 (点击切换维度显示/隐藏)
initStrategyForm()  // 策略表单提交逻辑
```

---

## 五、设计约束 (给 Gemini 的注意事项)

1. **零外部依赖**: 不能用 React/Vue/Chart.js/Bootstrap。纯 HTML+CSS+JS。
2. **API 不变**: 后端 API 已经定型，前端只能调用现有端点，不能改 API。
3. **两个页面独立**: Workbench 和 Evolution 是独立 HTML 文件，共享同一后端。
4. **数据格式**: 所有数据都是 JSON，字段名 snake_case。
5. **核心 AI 调用**: `/api/recruiter/assess` 是 LLM 调用，有延迟(几秒)，需要 loading 状态。
6. **数据库路径**: 默认 `.evohunter/workbench.db`，通过 localStorage 读取。
7. **设计风格**: 克制专业风，琥珀色主色调 #oklch(0.56 0.16 38)，见 `DESIGN.md`。
8. **演进数据**: `/api/evolution/data` 返回的 generations 数组可能为空(无进化历史时)。
9. **策略控制**: `/api/evolution/strategy` GET 返回当前策略，POST 更新。
10. **匹配流程**: 选一个 → 遍历对面全部调 LLM → 排序。不是批量，是循环调用。
