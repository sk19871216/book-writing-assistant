# 写作助手多 Agent 系统 - 规格说明书

## Why

用户希望将一个在 Git Bash/Linux 环境下开发的多 Agent 写作助手系统移植到当前项目 `f:\trae_project\book_helper`。该系统使用 3 个专业 Agent 协作，配合 4 个专业 Skill，帮助用户进行网文创作创意开发。

**用户特殊要求：**
- 工作流流程保持不变
- Web 页面需要重新设计和编写（现代化 UI）
- 数据存储使用 SQLite 数据库（重新设计表结构）
- 用户输入等待机制使用 WebSocket 实时推送（替代轮询）

## What Changes

### 核心组件

#### 1. Agent 定义文件（3个）
| 文件 | 角色 | 职责 |
|------|------|------|
| `src/agents/agent_a.md` | 头脑风暴者 | 调用 brainstorm/golden_finger Skill 生成创意 |
| `src/agents/agent_b.md` | 逻辑建议者 | 调用 critic Skill 进行逻辑审查 |
| `src/agents/agent_c.md` | 网文爆款分析师 | 6维度评估（钩子密度、金手指吸引力等） |

#### 2. Skill 定义文件（4个）
| 文件 | 名称 | 用途 |
|------|------|------|
| `src/skills/brainstorm/SKILL.md` | brainstorm | 创意头脑风暴（SCAMPER、随机输入、反向思考、无限夸张） |
| `src/skills/critic/SKILL.md` | critic | 创意审判（逻辑矛盾、动机冲突评估） |
| `src/skills/golden_finger/SKILL.md` | golden_finger | 金手指设计（简单、清晰、成长空间、推动剧情） |
| `src/skills/character_design/SKILL.md` | character-design | 角色设计（三层结构：速写、驱动、弧光） |

#### 3. 数据层（重新设计的 SQLite）
| 文件 | 职责 |
|------|------|
| `src/storage.py` | SQLite 数据库操作（简化的表结构） |

#### 4. 工作流引擎
| 文件 | 职责 |
|------|------|
| `src/workflow.py` | Python 工作流引擎（保持原工作流逻辑，集成 WebSocket） |

#### 5. Web 界面（新设计 + WebSocket）
| 文件 | 职责 |
|------|------|
| `web/server.py` | Web 服务器（现代化 UI + WebSocket 实时通信） |

### 目录结构

```
book_helper/
├── src/
│   ├── agents/
│   │   ├── agent_a.md       # 头脑风暴者
│   │   ├── agent_b.md       # 逻辑建议者
│   │   └── agent_c.md       # 爆款分析师
│   ├── skills/
│   │   ├── brainstorm/
│   │   │   └── SKILL.md     # 头脑风暴 Skill
│   │   ├── critic/
│   │   │   └── SKILL.md     # 逻辑审查 Skill
│   │   ├── golden_finger/
│   │   │   └── SKILL.md     # 金手指设计 Skill
│   │   └── character_design/
│   │       └── SKILL.md     # 角色设计 Skill
│   ├── storage.py            # SQLite 数据库层
│   └── workflow.py           # 工作流引擎
├── web/
│   └── server.py             # Web 服务器（Flask + WebSocket）
├── workspace/                # 运行时数据目录
│   └── book_helper.db       # SQLite 数据库
├── .trae/
│   └── specs/
│       └── port-writing-assistant/
│           ├── spec.md
│           ├── tasks.md
│           └── checklist.md
```

### 工作流流程（不变）

```
用户输入主题/想法
     ↓
初始化会话
     ↓
┌─────────────────────────────────────────┐
│  循环（直到用户确认满意）：                │
│                                         │
│  Agent A 生成创意                        │
│       ↓                                  │
│  Agent B 调用 critic 审核               │
│       ↓                                  │
│  展示创意，引导用户：                     │
│    · 挑选喜欢的创意方向                   │
│    · 提出修改意见                         │
│    · 或确认满意                          │
│       ↓                                  │
│  用户未确认 → A 根据意见完善 → B 审核    │
│  用户确认   → 跳出循环，进入 C            │
└─────────────────────────────────────────┘
     ↓
Agent C 最终评估（approved/needs_work/rejected）
     ↓
生成故事大纲和章节大纲
```

### 通信机制

#### WebSocket 实时推送
- Agent 完成时主动推送结果到前端
- 前端收到推送后自动更新界面
- 无需轮询，实时性好

## Impact

- **新增能力**：多 Agent 协作创意开发工作流
- **影响文件**：新建上述所有文件

## ADDED Requirements

### Requirement: Agent 定义加载

系统 SHALL 从 `src/agents/` 目录加载 Agent 提示词模板文件。

#### Scenario: Agent 文件存在
- **WHEN** 系统需要加载 Agent 提示词
- **THEN** 从 `src/agents/{agent_name}.md` 读取 Markdown 内容作为提示词

### Requirement: Skill 定义加载

系统 SHALL 从 `src/skills/{skill_name}/SKILL.md` 加载 Skill 定义。

#### Scenario: 调用 Skill
- **WHEN** Agent 需要使用特定 Skill（如 brainstorm、critic、golden_finger）
- **THEN** 系统加载对应 SKILL.md 的内容注入到 prompt

### Requirement: 数据存储（重新设计的 SQLite）

系统 SHALL 使用简化的 SQLite 数据库存储会话数据。

#### Scenario: 数据库初始化
- **WHEN** 首次运行
- **THEN** 创建 `workspace/book_helper.db` 并初始化表结构

#### Scenario: 表结构设计
- **conversations 表**：id, topic, round, status, created_at, updated_at
- **entries 表**：id, conversation_id, agent, round, timestamp, content
- **user_selections 表**：id, conversation_id, round, direction, feedback, timestamp

### Requirement: 工作流迭代

系统 SHALL 支持 A → B → 用户 → 循环迭代的工作流，直到用户确认或达到最大迭代次数。

#### Scenario: 用户未确认
- **WHEN** 用户未输入"满意"
- **THEN** 继续下一轮 A → B 迭代

#### Scenario: 用户确认
- **WHEN** 用户输入"满意"
- **THEN** 进入 Agent C 最终评估

### Requirement: Agent C 评估结果

系统 SHALL 根据 Agent C 的 verdict（approved/needs_work/rejected）决定后续流程。

#### Scenario: 评估通过
- **WHEN** verdict = "approved"
- **THEN** 生成最终故事大纲

#### Scenario: 需改进
- **WHEN** verdict = "needs_work"
- **THEN** 提示用户可重新运行流程调整

#### Scenario: 未通过
- **WHEN** verdict = "rejected"
- **THEN** 结束流程，提示用户重新设计

### Requirement: WebSocket 实时推送

系统 SHALL 使用 WebSocket 实现 Agent 与前端的双向实时通信。

#### Scenario: Agent 完成时
- **WHEN** Agent 完成一次输出
- **THEN** 通过 WebSocket 推送结果到前端

#### Scenario: 前端发送消息
- **WHEN** 用户在前端输入消息
- **THEN** 通过 WebSocket 发送到后端

### Requirement: Web 界面（新设计）

系统 SHALL 提供现代化的 Web 界面用于可视化工作流进度和用户交互。

#### Scenario: 现代化 UI
- **WHEN** 用户访问 Web 服务器
- **THEN** 显示现代化的聊天界面，包含：
  - 会话列表侧边栏
  - 实时聊天区域
  - Agent 状态指示器
  - 用户输入区域

## MODIFIED Requirements

无。

## REMOVED Requirements

- ~~`src/database.py`~~ - 不使用原实现
- ~~`src/helpers.py`~~ - 不使用原实现
- ~~轮询机制~~ - 改用 WebSocket 实时推送

## 数据库结构设计

### conversations 表
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    round INTEGER DEFAULT 0,
    status TEXT DEFAULT 'in_progress',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### entries 表
```sql
CREATE TABLE entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    agent TEXT NOT NULL,
    round INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    content TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

### user_selections 表
```sql
CREATE TABLE user_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    round INTEGER,
    direction TEXT,
    feedback TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```
