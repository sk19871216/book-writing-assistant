# Checklist - 写作助手多 Agent 系统移植

## 目录结构
- [x] `src/agents/` 目录已创建
- [x] `src/skills/` 目录及子目录已创建
- [x] `web/` 目录已创建
- [x] `workspace/` 目录已创建

## Agent 定义文件
- [x] `src/agents/agent_a.md` 存在且内容完整
- [x] `src/agents/agent_b.md` 存在且内容完整
- [x] `src/agents/agent_c.md` 存在且内容完整

## Skill 定义文件
- [x] `src/skills/brainstorm/SKILL.md` 存在且内容完整
- [x] `src/skills/critic/SKILL.md` 存在且内容完整
- [x] `src/skills/golden_finger/SKILL.md` 存在且内容完整
- [x] `src/skills/character_design/SKILL.md` 存在且内容完整

## 数据存储层（重新设计的 SQLite）
- [x] `src/storage.py` 存在
- [x] SQLite 表结构正确（conversations, entries, user_selections）
- [x] 会话 CRUD 操作正常
- [x] 条目追加功能正常
- [x] 轮次管理功能正常

## 工作流引擎
- [x] `src/workflow.py` 能够加载 Agent 提示词
- [x] `src/workflow.py` 能够加载 Skill 定义
- [x] `src/workflow.py` 能够调用存储层
- [x] `src/workflow.py` 支持 WebSocket 推送
- [x] `src/workflow.py` 支持迭代循环
- [x] `src/workflow.py` 支持用户交互输入
- [x] `src/workflow.py` Agent C 评估结果处理正确
- [x] `src/workflow.py` 最终大纲生成正确

## Web 服务器（新 UI + WebSocket）
- [x] `web/server.py` 可正常启动
- [x] Flask 路由配置正确
- [x] WebSocket 连接正常
- [x] 现代化 UI 设计美观
- [x] 会话列表功能正常
- [x] 聊天消息发送/接收正常
- [x] Agent 状态指示正确
- [x] 工作流引擎集成正常

## 工作流流程（不变）
- [x] A → B → 用户 循环迭代正确
- [x] 用户确认后进入 C 评估
- [x] Agent C verdict 处理正确
- [x] 故事大纲生成正确

## WebSocket 实时通信
- [x] WebSocket 服务端正常
- [x] WebSocket 客户端正常连接
- [x] Agent 完成时实时推送正常
- [x] 用户消息发送正常
- [x] 无轮询机制

## 跨平台兼容性
- [x] Windows 环境下可运行
- [x] 路径分隔符处理正确（os.path）
- [x] 编码处理正确（UTF-8）
- [x] 子进程调用正确（subprocess）

## 启动方式

```bash
cd f:\trae_project\book_helper
pip install -r requirements.txt
python web/server.py
```

然后访问 http://localhost:5000
