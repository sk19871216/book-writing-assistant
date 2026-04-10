# 网文写作助手 - 多 Agent 协作系统

一个基于多 Agent 协作的网文创意孵化系统，通过头脑风暴、逻辑审核、爆款分析三个专业 Agent 的协作，帮助作者快速生成高质量的故事大纲。

## 项目结构

```
book_helpers/
├── src/
│   ├── storage.py           # 数据库层
│   ├── workflow.py         # 工作流引擎
│   ├── agents/             # Agent 角色定义
│   │   ├── agent_a.md       # 头脑风暴者
│   │   ├── agent_b.md       # 逻辑审核者
│   │   └── agent_c.md       # 爆款分析师
│   └── skills/              # 技能模块
│       ├── brainstorm/      # 头脑风暴技能
│       ├── golden_finger/   # 金手指设计技能
│       └── critic/          # 逻辑批判技能
├── web/
│   ├── server.py            # Flask Web 服务器
│   └── templates/
│       └── index.html       # 前端界面
├── workspace/
│   └── book_helper.db       # SQLite 数据库
└── requirements.txt         # Python 依赖
```

## 模块详解

### 1. 数据库层 (`src/storage.py`)

负责管理会话数据的持久化存储。

#### 主要功能

- **会话管理**：创建、查询、更新会话状态
- **条目记录**：存储 Agent 和用户的发言
- **用户选择**：记录用户的方向选择和反馈

#### 核心函数

```python
# 初始化数据库
init_db()

# 创建新会话，返回会话 ID
conv_id = create_conversation(topic: str) -> int

# 获取会话详情（含所有条目）
conv = get_conversation(conv_id: int) -> Optional[Dict]

# 列出最近会话
conversations = list_conversations(limit: int = 20) -> List[Dict]

# 追加发言记录
entry_id = append_entry(
    conversation_id: int,
    agent: str,          # 'A', 'B', 'C', 'user'
    round_num: int,
    content: str
) -> int

# 保存用户选择
selection_id = save_user_selection(
    conversation_id: int,
    round_num: int,
    direction: Optional[str] = None,
    feedback: Optional[str] = None
) -> int

# 获取最新用户选择
selection = get_latest_user_selection(conv_id: int) -> Optional[Dict]

# 获取特定 Agent 的最新发言
entry = get_latest_entry_by_agent(conv_id: int, agent: str) -> Optional[Dict]

# 删除会话
delete_conversation(conv_id: int) -> None
```

#### 数据库表结构

**conversations** - 会话表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| topic | TEXT | 主题 |
| round | INTEGER | 当前轮次 |
| status | TEXT | 状态 (in_progress/approved/rejected) |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**entries** - 发言记录表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| conversation_id | INTEGER | 外键 |
| agent | TEXT | 发言者 (A/B/C/user) |
| round | INTEGER | 轮次 |
| timestamp | DATETIME | 时间戳 |
| content | TEXT | 内容 |

**user_selections** - 用户选择表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| conversation_id | INTEGER | 外键 |
| round | INTEGER | 轮次 |
| direction | TEXT | 选择的方向 |
| feedback | TEXT | 用户反馈 |
| timestamp | DATETIME | 时间戳 |

---

### 2. 工作流引擎 (`src/workflow.py`)

核心工作流逻辑，协调多个 Agent 的执行顺序。

#### WorkflowEngine 类

```python
from src.workflow import WorkflowEngine, start_workflow, continue_workflow

# 创建工作流引擎
engine = WorkflowEngine(conv_id: int, ws_broadcaster: Optional[Callable] = None)

# 启动完整工作流
result = engine.run_workflow() -> Dict[str, Any]
# 返回: {'action': 'wait_for_user', 'iteration': 1, 'round': 1, 'phase': '...'}

# 处理用户输入后继续工作流
result = engine.continue_workflow(user_input: str) -> Dict[str, Any]
```

#### 快捷函数

```python
# 启动新工作流
result = start_workflow(topic: str, ws_broadcaster: Optional[Callable] = None)

# 继续已有工作流
result = continue_workflow(conv_id: int, user_input: str, ws_broadcaster: Optional[Callable] = None)
```

#### 工作流程

```
┌──────────────────────────────────────────────────────────────┐
│ 1. 新建对话 → Agent A 生成 10 个简单创意方向                  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. 用户选择感兴趣的创意：                                      │
│    - 选择方向（如：方向1、3、5）→ 进入步骤3                   │
│    - 细化方向（如：细化方向2）→ 进入步骤2a                    │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2a. Agent A 基于选定方向生成 10 个更细致的子方向              │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2b. 用户选择子方向（如：子方向1、3）→ 进入步骤3              │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. Agent A 基于选择生成详细创意方案                            │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. 用户选择：                                                 │
│    - 输入「让B审核」→ 进入步骤5                               │
│    - 输入修改意见 → Agent A调整 → 重复步骤4                   │
│    - 输入「满意」→ 直接进入步骤6                              │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 5. Agent B 审核详细方案                                       │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 6. B审核后，用户选择：                                        │
│    - 输入「修改」→ 按B的改                                    │
│    - 输入反馈 → 综合B的意见与用户的反馈再改                    │
│    - 输入「满意」→ 交给分析师                                 │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 7. Agent C 生成网文爆款建议和故事大纲                          │
└──────────────────────────────────────────────────────────────┘
```

#### 状态机

| 状态 | 说明 |
|------|------|
| `direction_selection` | 等待用户选择创意方向或细化方向 |
| `direction_refinement` | 方向细化阶段 |
| `detailed_ideas` | 等待用户选择：让B审核 / 继续调整 / 满意 |
| `feedback` | 等待用户反馈或让B审核 |
| `feedback_after_review` | B审核后，等待用户选择：修改 / 反馈 / 满意 |
| `refining_after_review` | B审核后修改阶段 |

#### 内置判断函数

```python
# 解析用户输入的方向（支持多种格式）
engine.parse_direction_from_input(user_input: str) -> Optional[str]
# 支持格式：方向1、2、方向 1、2、子方向1、2、子方向 1、2

# 判断用户是否满意
engine.is_user_satisfied(user_input: str) -> bool

# 判断用户是否要求重新生成
engine.is_regenerate_request(user_input: str) -> bool

# 判断用户是否想让B审核
engine.is_review_request(user_input: str) -> bool

# 判断用户是否想细化方向
engine.is_refinement_request(user_input: str) -> bool
# 支持格式：细化方向1、细化方向 1
```

---

### 3. Agent 模块

#### Agent A - 头脑风暴者 (`src/agents/agent_a.md`)

**职责**：从用户碎片信息中挖掘可能性，设计金手指和主角矛盾

**首次输出**：生成 10 个简单创意方向（类型 + 目标读者 + 一句话）

**方向细化**：基于用户选择的某个方向，生成 10 个更细致的子方向

**后续输出**：基于用户选择的多个方向（或子方向），生成详细创意，包括：
- 主角设定（身份/背景、核心特质，内在矛盾）
- 金手指设计（名称、核心机制、与主角矛盾的绑定）
- 潜在冲突和爽感预期

**重要规则**：
- 用户输入"方向"，输出使用"方向"
- 用户输入"子方向"，输出使用"子方向"
- 不会混用"方向"和"子方向"

**调用技能**：brainstorm, golden_finger

---

#### Agent B - 逻辑审核者 (`src/agents/agent_b.md`)

**职责**：使用批判性思维审查创意的逻辑自洽性

**审核维度**：
- 因果链是否自洽
- 人物动机是否与背景设定一致
- 金手指边界是否清晰
- 冲突产生是否有合理铺垫

**重要规则**：
- 必须审核所有被选中的方向
- 用户输入"方向"，输出使用"方向"
- 用户输入"子方向"，输出使用"子方向"

**调用技能**：critic

**注意**：只做逻辑审核，不做吸引力评估

---

#### Agent C - 爆款分析师 (`src/agents/agent_c.md`)

**职责**：从网文爆款逻辑评估创意是否值得发展

**重要规则**：
- 必须分别评估所有被选中的方向
- 用户输入"方向"，输出使用"方向"
- 用户输入"子方向"，输出使用"子方向"

**评估维度**：
| 维度 | 权重 | 说明 |
|------|------|------|
| 钩子密度 | 25% | 每章能否制造悬念/反转/爽点 |
| 金手指吸引力 | 25% | 能力是否独特、有记忆点 |
| 代入感与情绪爽感 | 20% | 能否快速代入，有无高情绪场景 |
| 世界观可延展性 | 10% | 能否持续展开（200+章） |
| 差异化亮点 | 10% | 与同类爆款相比的优势 |
| 角色深度 | 10% | 主角是否有成长弧光 |

**结论**：
- `approved` - 可以进入写作阶段
- `needs_work` - 有潜力，需继续打磨
- `rejected` - 问题太大，不适合发展

---

### 4. 技能模块

#### 头脑风暴技能 (`src/skills/brainstorm/SKILL.md`)

**核心技巧**：

1. **SCAMPER 强制联想** - 7 个字母改造
2. **随机输入强制连接** - 跨界联想
3. **反向头脑风暴** - 从"如何搞砸"反推
4. **无限夸张** - 推向极端看效果

---

#### 金手指设计技能 (`src/skills/golden_finger/SKILL.md`)

**优秀金手指四大标准**：

1. **简单** - 一眼就懂
2. **清晰** - 功能明确
3. **有成长空间** - 可以不断升级
4. **能推动剧情** - 天然带来任务和冲突

**常见类型**：
| 类型 | 优点 | 缺点 | 适合题材 |
|------|------|------|----------|
| 系统流 | 功能明确 | 容易同质化 | 所有题材 |
| 重生流 | 真实感强 | 需熟悉历史 | 都市、历史 |
| 空间流 | 可种/养/储物 | 容易写崩 | 都市、玄幻 |
| 血脉流 | 逼格高 | 前期弱 | 玄幻、奇幻 |
| 技能流 | 灵活多样 | 容易繁琐 | 游戏、异界 |
| 鉴定流 | 适合捡漏 | 格局可能小 | 都市、赌石 |

---

#### 逻辑批判技能 (`src/skills/critic/SKILL.md`)

**评估维度**：
1. **逻辑矛盾**（首要）- 因果链、动机、边界是否自洽
2. **设定与人物动机冲突**（次要）- 行为是否一致

**流程**：
1. 黑帽压力测试（15分钟挑毛病）
2. 影响-可行性矩阵评估
3. 打补丁（修复漏洞）

---

### 5. Web 服务器 (`web/server.py`)

基于 Flask + SocketIO 的实时 Web 界面。

#### 启动方式

```bash
cd book_helpers
pip install -r requirements.txt
python web/server.py
```

服务启动后访问 `http://localhost:5000`

#### API 接口

**会话管理**
```
GET  /api/conversations              # 列出最近会话
POST /api/conversations              # 创建新会话 {"topic": "..."}
GET  /api/conversations/<id>         # 获取会话详情
POST /api/conversations/<id>/start   # 启动工作流
POST /api/conversations/<id>/continue # 继续工作流 {"input": "..."}
```

**发言记录**
```
GET  /api/conversations/<id>/entries      # 获取所有发言
POST /api/conversations/<id>/entries       # 添加用户发言 {"content": "..."}
POST /api/conversations/<id>/selection     # 保存用户选择 {"direction": "...", "feedback": "..."}
```

#### WebSocket 事件

**客户端监听**
```
workflow_event      # 工作流事件（agent_start, agent_complete, awaiting_user_input 等）
workflow_waiting    # 等待用户输入
workflow_complete   # 工作流完成
workflow_error      # 发生错误
message_received    # 收到新消息
joined              # 加入会话房间成功
```

**客户端发送**
```
join_conversation   # 加入会话房间 {"conv_id": 123}
leave_conversation  # 离开会话房间 {"conv_id": 123}
send_message        # 发送消息 {"conv_id": 123, "message": "..."}
```

---

## 使用示例

### 命令行使用

```python
from src.workflow import start_workflow, continue_workflow
from src.storage import get_conversation

# 启动新工作流
result = start_workflow("穿越到古代当医生")
print(result)

# 继续工作流
result = continue_workflow(conv_id, "方向1")
print(result)

# 查看会话详情
conv = get_conversation(conv_id)
for entry in conv['entries']:
    print(f"{entry['agent']}: {entry['content'][:100]}...")
```

### Web 界面使用

1. 启动服务器：`python web/server.py`
2. 浏览器打开 `http://localhost:5000`
3. 点击「新建对话」，输入故事主题
4. 等待 Agent A 生成 10 个简单创意方向
5. 用户选择：
   - 输入「方向1」或「方向1、2、3」选择感兴趣的方向
   - 输入「细化方向2」对某个方向进行细化
6. Agent A 生成详细创意方案（或细化后的子方向）
7. 用户选择子方向后，Agent A 基于选择生成详细创意方案
8. 用户选择：
   - 输入「让B审核」→ Agent B 审核详细方案
   - 输入修改意见 → Agent A 根据意见调整方案
   - 输入「满意」→ 直接交给 Agent C 分析
9. 如果选择让 B 审核，B 审核后用户选择：
   - 输入「修改」→ 按 B 的建议修改
   - 输入反馈 → 综合 B 的意见与用户的反馈再改
   - 输入「满意」→ 交给 Agent C 分析
10. Agent C 评估后，生成最终故事大纲

### 支持的输入格式

**方向选择**：
- 单选：`方向1`
- 多选：`方向1、2、3` 或 `方向 1、2、3`
- 子方向：`子方向1、2、3` 或 `子方向 1、2、3`

**细化方向**：
- `细化方向1` 或 `细化方向 1`

**其他指令**：
- `让B审核`：让 Agent B 审核详细方案
- `修改`：按 B 的审核意见修改
- `满意`：交给 Agent C 分析

---

## 环境要求

- Python 3.8+
- claude CLI（用于调用 Agent）
- SQLite3

## 安装依赖

```bash
pip install -r requirements.txt
```

依赖包括：
- flask>=2.3.0
- flask-socketio>=5.3.0
- python-socketio>=5.9.0
- python-engineio>=4.7.0
- gevent>=23.0.0
- gevent-websocket>=0.10.0

---

## 许可证

MIT License
