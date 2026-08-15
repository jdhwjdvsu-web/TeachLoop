# TeachLoop / 因材备课 Agent

面向初中教师的学情驱动差异化备课原型。系统读取匿名班级答题记录，完成错因聚合、教学重点选择、教案生成、教师审核、分层练习、课后反馈和下一课调整。

当前版本采用“通用教学 Skill＋可插拔学科包”架构，首批支持数学、语文、英语和物理。不配置模型时可完全离线运行；配置 OpenAI-compatible API 后，可增强复杂步骤分析、教学设计、课堂提问、分层练习和教师意见局部重写。LangGraph 负责按学科动态加载能力，Streamlit 提供教师工作台，学科验证器负责结果门禁。

## 已实现

- CSV 班级数据导入与字段检查
- 基于学生解题过程的典型错因识别
- 班级知识点正确率和错因分布
- A/B/C 三组学生分层建议
- 学情驱动的 45 分钟教案
- 三档分层练习与答案
- 质量审查及教师最终确认提示
- LangGraph 端到端工作流
- 教师直接编辑教学目标、策略、课堂活动和分层练习
- 模块锁定和单模块重新生成
- 接受、驳回 AI 建议及 SQLite 最终版本保存
- 课前与课后正确率、知识点和错因对比
- 继续干预学生名单和下一课建议
- 教材 PDF、Markdown、TXT 本地解析与向量检索
- 教案教材依据、页码和检索片段展示
- OpenAI-compatible Chat Completions 接口和自动规则回退
- API Key 仅保存在当前 Streamlit 会话，不进入教案、SQLite 或下载文件
- 一元一次不等式方向变化、端点、数轴错因诊断
- 方程与不等式的 SymPy 独立验证器
- 12 个精选通用教育 Skill 的阶段编排与来源追溯
- 数学、语文、物理统一学科包规范
- 语文开放性答案的观点—证据—解释量规
- 物理公式计算、单位完整性和实验变量意识
- 英语学科包仅用 YAML 配置即可接入错因诊断与备课流程
- 正确率 × 作答时间双维度分组、学生级错因和异常耗时分析
- A/B/C 分组花名册与学生干预明细 CSV/Word 导出
- 前后测题目级锚点、未测知识点标记和可信度提示
- 本地 BM25 教材检索以及资料重命名、删除和命中统计
- 反馈历史、schema 版本与按学科/课题筛选
- GitHub Actions：Ruff、pytest 和 70% 覆盖率门槛
- 学情、教案、分层练习、随堂测、下一课建议五份 Word 交付包

## 能力架构

LangGraph 在输入校验后执行 `load_capabilities` 节点，根据“学科＋年级＋课题”加载：

1. 通用教学能力：学情差距分析、教学目标、差异化教学、课堂提问、形成性评价、认知负荷、教师反思等。
2. 学科能力包：题型、典型错因、评价量规、提示词、课程索引和确定性验证器。
3. 教师工作流：诊断、生成、编辑锁定、确认定稿、Word 导出和课后反馈继续共用。

首批 12 个通用能力的标识和编排关系位于 `education_skills/catalog.yaml`。它们参考
[`education-agent-skills`](https://github.com/GarethManning/education-agent-skills)，当前没有复制原始 `SKILL.md` 正文；署名和许可边界见 `education_skills/NOTICE.md`。

## 目录

- `app.py`：Streamlit 入口
- `teachloop/diagnosis.py`：学情和错因诊断
- `teachloop/lesson.py`：教案及分层材料生成
- `teachloop/math_validation.py`：SymPy 数学验证
- `teachloop/workflow.py`：LangGraph 工作流
- `teachloop/knowledge_base.py`：本地教材向量知识库
- `teachloop/feedback.py`：课前课后教学效果对比
- `teachloop/storage.py`：教师版本和反馈记录持久化
- `teachloop/llm_service.py`：OpenAI-compatible 模型客户端和教育增强门禁
- `teachloop/subject_packs.py`：学科包发现、加载和验证器路由
- `teachloop/skill_registry.py`：精选通用教育 Skill 编排
- `subjects/`：数学、语文、物理学科能力包
- `education_skills/`：通用能力目录和上游署名说明
- `teachloop/word_export.py`：Word 文档和 ZIP 交付包
- `data/demo_class.csv`：匿名模拟班级数据
- `data/demo_post_class.csv`：匿名模拟随堂测数据
- `knowledge_base/curriculum.md`：第一版课程知识库
- `tests/`：自动测试

## Windows 启动

依赖已经安装时，可直接双击 `启动教师端.cmd`。

也可以在 PowerShell 中启动：

```powershell
cd 'D:\教师\TeachLoop'
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

如果系统没有 `py`，可以用已安装 Python 的完整路径创建虚拟环境。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 可选大模型配置

在侧边栏展开“大模型设置”：

1. 启用 OpenAI-compatible 模型。
2. 填写包含 `/v1` 的 Base URL。
3. 填写服务提供的实际模型 ID 和 API Key。
4. 明确勾选匿名学情数据授权。
5. 测试连接后生成教案。

系统调用 `POST /chat/completions`。模型输出必须是结构化 JSON；数学练习通过 SymPy，物理练习通过计算结果与单位完整性检查，语文开放题通过结构量规后仍需教师复核。调用失败、超时、格式错误或验证失败时自动保留确定性规则版本。

API Key 不会写入数据库或导出材料。接入外部服务前仍应核对该服务的数据处理和保留政策。

## Word 交付

教师完成编辑并点击“接受 AI 建议”后，可下载 ZIP，包含：

- 学情分析报告
- 教师最终教案
- 分层练习及答案
- 随堂测及答案
- 下一课调整建议

## CSV 字段

必填字段：

- `student_id`：匿名学生编号
- `question_id`：题目编号
- `knowledge_point`：知识点
- `student_answer`：学生最终答案
- `student_work`：学生的关键解题步骤
- `correct`：是否正确（true/false）
- `response_time_sec`：作答时间（秒）

随堂测还可增加可选字段 `linked_pre_question_id`，填写对应的课前测 `question_id`，用于题目级前后对照。教师端提供课前测与随堂测 CSV 模板下载；随堂测也可以直接在页面表格中录入。

## 数据与教育边界

Demo 仅使用模拟匿名数据。系统输出用于辅助教师备课，不替代教师的教学判断、学生评价或学校正式评价。教师必须审核后才能使用或发布生成材料。

教材知识库采用本地 BM25 检索，不调用外部服务，并支持资料重命名、删除与检索命中统计。上传的资料应当由使用者拥有合法使用授权；扫描版 PDF 当前可能无法提取文字，后续可增加 OCR。

## 新增学科包

复制 `subjects/chinese` 或 `subjects/physics` 作为模板，至少提供：

- `manifest.yaml`：学科、年级、版本、验证方式和演示数据
- `question_types.yaml`：课题、目标、时间线、分层练习和随堂测
- `misconceptions.yaml`：典型错因和干预策略
- `rubrics.yaml`：学科评价量规
- `validators.py`：模型生成内容的学科门禁
- `prompts/system.md`：学科提示词
- `curriculum/index.md`：课程与教材索引说明

保存后重启教师端，系统会自动发现该学科包。
