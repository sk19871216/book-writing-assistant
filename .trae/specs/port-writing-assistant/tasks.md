# Tasks - 写作助手多 Agent 系统移植

- [x] Task 1: 创建目录结构
  - [x] 创建 `src/agents/` 目录
  - [x] 创建 `src/skills/` 目录及其子目录
  - [x] 创建 `web/` 目录
  - [x] 创建 `workspace/` 目录

- [x] Task 2: 移植 Agent 定义文件（3个）
  - [x] 复制 `agent_a.md` 到 `src/agents/`
  - [x] 复制 `agent_b.md` 到 `src/agents/`
  - [x] 复制 `agent_c.md` 到 `src/agents/`

- [x] Task 3: 移植 Skill 定义文件（4个）
  - [x] 复制 `brainstorm/SKILL.md` 到 `src/skills/brainstorm/`
  - [x] 复制 `critic/SKILL.md` 到 `src/skills/critic/`
  - [x] 复制 `golden_finger/SKILL.md` 到 `src/skills/golden_finger/`
  - [x] 复制 `character_design/SKILL.md` 到 `src/skills/character_design/`

- [x] Task 4: 实现数据存储层（重新设计的 SQLite）
  - [x] 创建 `src/storage.py`
  - [x] 设计简化表结构（conversations, entries, user_selections）
  - [x] 实现会话 CRUD 操作
  - [x] 实现条目追加功能
  - [x] 实现轮次管理

- [x] Task 5: 实现工作流引擎
  - [x] 创建 `src/workflow.py`
  - [x] 实现 Agent 加载和调用逻辑
  - [x] 实现 Skill 注入机制
  - [x] 实现 WebSocket 推送集成
  - [x] 实现迭代循环
  - [x] 实现 Agent C 评估和结果处理
  - [x] 实现最终大纲生成

- [x] Task 6: 实现 Web 服务器（新 UI + WebSocket）
  - [x] 创建 `web/server.py`
  - [x] 集成 Flask 和 WebSocket
  - [x] 设计现代化 UI（HTML/CSS/JavaScript）
  - [x] 实现 WebSocket 双向通信
  - [x] 实现会话列表功能
  - [x] 实现聊天功能
  - [x] 实现实时状态更新

- [x] Task 7: 测试与验证
  - [x] 测试数据存储层
  - [x] 测试工作流引擎
  - [x] 测试 WebSocket 通信
  - [x] 测试 Web 服务器
  - [x] 端到端测试

# Task Dependencies

- Task 2 依赖 Task 1
- Task 3 依赖 Task 1
- Task 4 依赖 Task 1
- Task 5 依赖 Task 2、Task 3、Task 4
- Task 6 依赖 Task 1、Task 5
- Task 7 依赖 Task 2、Task 3、Task 4、Task 5、Task 6

## 项目文件结构

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
│   ├── server.py             # Web 服务器
│   └── templates/
│       └── index.html         # 前端页面
├── workspace/                # 运行时数据目录
├── requirements.txt         # Python 依赖
└── .trae/
    └── specs/
        └── port-writing-assistant/
```

## 启动方式

```bash
cd f:\trae_project\book_helper
pip install -r requirements.txt
python web/server.py
```

然后访问 http://localhost:5000
