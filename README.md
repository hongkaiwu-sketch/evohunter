EvoHunter: 基于 EvoMap GEP 协议的自进化猎头 Agent
. 项目愿景 (Vision)
构建一个能够自主运行、自我迭代的智能猎头系统。该系统利用 EvoMap GEP (Gene Expression Programming) 协议作为核心数据交换标准，实现从候选人搜寻、画像解析到精准匹配的全流程自动化，并通过反馈机制不断“进化”其匹配算法。
. 核心工作流 (Core Workflow)
输入：职位 JD (Job Description) + 目标人才池 URL/关键词。
感知 (Perception)：Agent 自动爬取多平台候选人公开信息。
解析 (Parsing)：将非结构化文本转化为符合 GEP 协议的标准基因序列。
决策 (Decision)：基于 GEP 算法进行人岗匹配度评分与排序。
行动 (Action)：自动生成个性化沟通话术，执行触达（邮件/消息）。
进化 (Evolution)：根据反馈（回复率、面试通过率）调整 GEP 权重参数。
. 技术栈规划 (Tech Stack Proposal)
语言: Python 3.10+
AI/LLM: OpenAI API / Local LLM (用于语义理解与话术生成)
爬虫: Playwright / Scrapy (应对动态网页)
数据存储: SQLite (轻量级) / PostgreSQL (生产环境)
协议层: EvoMap GEP SDK (自定义模块)
. 任务分工与模块拆解 (Task Breakdown)
💡 此部分用于分配给团队成员及 AI (Codex) 进行具体开发。
🧩 模块 A：GEP 协议定义与核心引擎 (Core & Protocol)
负责人: [待定]
任务描述:
定义 CandidateGene 数据结构（包含技能向量、经验年限、薪资期望等基因片段）。
实现 GEPEvaluator 类，负责计算候选人与职位的适应度函数 (Fitness Function)。
实现基础的变异与交叉算子，用于模拟“进化”。
🕷️ 模块 B：数据采集与清洗 (Data Scraper)
负责人: [待定]
任务描述:
编写针对主流招聘平台（如 LinkedIn, Boss直聘等）的爬虫脚本。
实现反爬策略（代理 IP 池、随机 User-Agent）。
输出标准化的 JSON 数据供 GEP 引擎消费。
🤖 模块 C：Agent 交互与触达 (Interaction Agent)
负责人: [待定]
任务描述:
集成 LLM，根据候选人画像生成 High-conversion 的打招呼语。
实现邮件发送或 IM 消息推送接口。
监控回复状态，并将结果回传给核心引擎。
📊 模块 D：可视化看板 (Dashboard)
负责人: [待定]
任务描述:
展示当前的“进化代数”、匹配成功率趋势。
实时显示正在处理的候选人列表。