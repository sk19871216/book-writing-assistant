#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-agent workflow engine for writing assistant."""

import os
import sys
import re
import json
import subprocess
from typing import Optional, Dict, Any, Callable
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage import (
    init_db, create_conversation, get_conversation, list_conversations,
    append_entry, update_conversation_round, update_conversation_status,
    save_user_selection, get_latest_user_selection, has_agent_spoken,
    get_latest_entry_by_agent
)


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(PROJECT_DIR, 'src', 'agents')
SKILLS_DIR = os.path.join(PROJECT_DIR, 'src', 'skills')


class WorkflowEngine:
    """Workflow engine for multi-agent writing assistant."""
    
    def __init__(self, conv_id: int, ws_broadcaster: Optional[Callable] = None):
        self.conv_id = conv_id
        self.ws_broadcaster = ws_broadcaster
        self.conv = get_conversation(conv_id)
        self.topic = self.conv['topic'] if self.conv else ''
        self.current_round = self.conv['round'] if self.conv else 0
        
    def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast event to WebSocket clients."""
        if self.ws_broadcaster:
            try:
                self.ws_broadcaster({
                    'type': event_type,
                    'data': data
                })
            except Exception as e:
                print(f"WebSocket broadcast error: {e}")
    
    def load_agent_prompt(self, agent_name: str) -> str:
        """Load agent prompt from file."""
        agent_file = os.path.join(AGENTS_DIR, f'agent_{agent_name.lower()}.md')
        if os.path.exists(agent_file):
            with open(agent_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ''
    
    def load_skill(self, skill_name: str) -> str:
        """Load skill content from file."""
        skill_file = os.path.join(SKILLS_DIR, skill_name, 'SKILL.md')
        if os.path.exists(skill_file):
            with open(skill_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ''
    
    def build_prompt(self, agent_name: str) -> str:
        """Build full prompt for an agent including skills and context."""
        agent_prompt = self.load_agent_prompt(agent_name)
        
        skills_to_load = []
        if agent_name == 'A':
            skills_to_load = ['brainstorm', 'golden_finger']
        elif agent_name == 'B':
            skills_to_load = ['critic']
        
        skills_content = ""
        for skill_name in skills_to_load:
            skill_content = self.load_skill(skill_name)
            if skill_content:
                skills_content += f"\n\n=== Skill: {skill_name} ===\n{skill_content}"
        
        context = self.get_context_for_agent(agent_name)
        
        prompt = f"""项目路径: {PROJECT_DIR}

## 你的角色

{agent_prompt}

{skills_content}

---

## 当前会话上下文

{context}

---

请基于以上信息和你的角色，完成你的任务。"""
        
        return prompt
    
    def get_context_for_agent(self, agent_name: str) -> str:
        """Build context string for an agent."""
        conv = get_conversation(self.conv_id)
        if not conv:
            return "无会话数据"
        
        context_lines = [
            f"主题: {conv['topic']}",
            f"当前轮次: {conv['round']}",
            f"状态: {conv['status']}",
            "",
            "=== 讨论记录 ===",
        ]
        
        entries = conv.get('entries', [])
        for entry in entries:
            timestamp = entry.get('timestamp', '')
            agent = entry.get('agent', '')
            content = entry.get('content', '')
            if content:
                content_preview = content[:500] + '...' if len(content) > 500 else content
                context_lines.append(f"\n【{agent}】({timestamp}):\n{content_preview}")
        
        latest_selection = get_latest_user_selection(self.conv_id)
        if latest_selection:
            direction = latest_selection.get('direction', '')
            feedback = latest_selection.get('feedback', '')
            if direction:
                context_lines.append(f"\n【用户选择方向】: {direction}")
            if feedback:
                context_lines.append(f"\n【用户反馈】: {feedback}")
        
        return '\n'.join(context_lines)
    
    def call_claude(self, prompt: str) -> str:
        """Call Claude CLI to execute agent prompt."""
        try:
            result = subprocess.run(
                ['claude', '-p', '--permission-mode', 'acceptedEdits', '--no-session-persistence', prompt],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=300,
                cwd=PROJECT_DIR
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                return f"Error: {error_msg}"
            
            return result.stdout or ""
        except subprocess.TimeoutExpired:
            return "Error: Request timeout"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def run_agent(self, agent_name: str) -> str:
        """Run an agent and save its output."""
        self.broadcast('agent_start', {
            'agent': agent_name,
            'round': self.current_round
        })
        
        prompt = self.build_prompt(agent_name)
        output = self.call_claude(prompt)
        
        append_entry(self.conv_id, agent_name, self.current_round, output)
        
        self.broadcast('agent_complete', {
            'agent': agent_name,
            'round': self.current_round,
            'content': output
        })
        
        return output
    
    def is_direction_selection_phase(self) -> bool:
        """Check if current phase is direction selection."""
        a_entry = get_latest_entry_by_agent(self.conv_id, 'A')
        if not a_entry:
            return False
        
        a_content = a_entry.get('content', '')
        if '金手指' in a_content or '主角雏形' in a_content:
            return False
        
        selection = get_latest_user_selection(self.conv_id)
        if selection and selection.get('direction'):
            return False
        
        return True
    
    def parse_direction_from_input(self, user_input: str) -> Optional[str]:
        """Parse direction selection from user input."""
        pattern = r'方向\s*(\d+)'
        matches = re.findall(pattern, user_input)
        if matches:
            return '、'.join(matches)
        return None
    
    def is_user_satisfied(self, user_input: str) -> bool:
        """Check if user is satisfied with current result."""
        satisfied_keywords = ['满意', '可以', '好', '确认', 'ok', 'yes', '1']
        user_input_lower = user_input.lower()
        return any(keyword in user_input_lower for keyword in satisfied_keywords)
    
    def is_regenerate_request(self, user_input: str) -> bool:
        """Check if user wants to regenerate."""
        regenerate_keywords = ['重新生成', 'regenerate', '再来']
        user_input_lower = user_input.lower()
        return any(keyword in user_input_lower for keyword in regenerate_keywords)
    
    def run_agent_c(self) -> str:
        """Run Agent C for final evaluation."""
        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)
        
        output = self.run_agent('C')
        
        verdict = 'approved'
        if '**rejected**' in output or '**needs_work**' in output.lower():
            if '**rejected**' in output:
                verdict = 'rejected'
            else:
                verdict = 'needs_work'
        
        update_conversation_status(self.conv_id, verdict)
        
        self.broadcast('evaluation_complete', {
            'verdict': verdict,
            'content': output
        })
        
        return verdict
    
    def generate_final_outline(self) -> str:
        """Generate final story outline after approval."""
        conv = get_conversation(self.conv_id)
        
        prompt = f"""你是一位专业的网文写作助手。请根据以下讨论记录，为用户生成最终的故事大纲和章节大纲。

讨论主题：{conv['topic']}

讨论记录：
{json.dumps(conv, ensure_ascii=False, indent=2)}

---

请生成两部分内容：

## 第一部分：故事大纲
包含：
- 故事标题
- 核心创意（一句话概括核心爽点）
- 金手指（名称、核心机制、与主角矛盾的绑定）
- 人物设定（主角：身份/背景、核心特质、内在矛盾；关键配角）
- 情节框架（开端、发展、高潮、结局，各一句话概括）
- 情感基调
- 创意亮点（2-3个让读者眼前一亮的点）

## 第二部分：章节大纲
每章一句话概括核心事件，不展开具体剧情，只列出章节走向。

以 Markdown 格式输出。"""
        
        output = self.call_claude(prompt)
        
        final_outline = f"# {conv['topic']} - 最终故事大纲\n\n{output}"
        
        update_conversation_status(self.conv_id, 'approved')
        
        self.broadcast('outline_generated', {
            'content': final_outline
        })
        
        return final_outline
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """Process user input and determine next action."""
        if self.is_direction_selection_phase():
            direction = self.parse_direction_from_input(user_input)
            if direction:
                save_user_selection(self.conv_id, self.current_round, direction=direction, feedback=user_input)
                return {'action': 'continue', 'message': f'已选择方向: {direction}'}
            else:
                return {'action': 'wait', 'message': '请输入有效的方向选择（如：方向1、2）'}
        
        if self.is_user_satisfied(user_input):
            return {'action': 'final_evaluation'}
        
        if self.is_regenerate_request(user_input):
            save_user_selection(self.conv_id, self.current_round, feedback='重新生成')
            return {'action': 'regenerate'}
        
        save_user_selection(self.conv_id, self.current_round, feedback=user_input)
        return {'action': 'continue', 'message': '已收到反馈，将继续完善'}
    
    def run_workflow(self) -> Dict[str, Any]:
        """Run the complete workflow."""
        init_db()
        
        self.broadcast('workflow_start', {
            'conv_id': self.conv_id,
            'topic': self.topic
        })
        
        iteration = 0
        max_iterations = 20
        
        while iteration < max_iterations:
            iteration += 1
            self.current_round += 1
            update_conversation_round(self.conv_id, self.current_round)
            
            self.broadcast('iteration_start', {
                'iteration': iteration,
                'round': self.current_round
            })
            
            self.run_agent('A')
            
            self.run_agent('B')
            
            self.broadcast('awaiting_user_input', {
                'phase': 'direction_selection' if self.is_direction_selection_phase() else 'feedback'
            })
            
            return {
                'action': 'wait_for_user',
                'iteration': iteration,
                'round': self.current_round,
                'phase': 'direction_selection' if self.is_direction_selection_phase() else 'feedback'
            }
        
        return {'action': 'max_iterations_reached'}
    
    def continue_workflow(self, user_input: str) -> Dict[str, Any]:
        """Continue workflow after user input."""
        result = self.process_user_input(user_input)
        
        if result['action'] == 'wait':
            return result
        
        if result['action'] == 'final_evaluation':
            verdict = self.run_agent_c()
            if verdict == 'approved':
                outline = self.generate_final_outline()
                return {
                    'action': 'complete',
                    'verdict': verdict,
                    'outline': outline
                }
            else:
                return {
                    'action': 'needs_work' if verdict == 'needs_work' else 'rejected',
                    'verdict': verdict
                }
        
        if result['action'] == 'regenerate':
            self.current_round = 0
        
        return self.run_workflow()


def start_workflow(topic: str, ws_broadcaster: Optional[Callable] = None) -> Dict[str, Any]:
    """Start a new workflow with given topic."""
    init_db()
    conv_id = create_conversation(topic)
    
    engine = WorkflowEngine(conv_id, ws_broadcaster)
    return engine.run_workflow()


def continue_workflow(conv_id: int, user_input: str, ws_broadcaster: Optional[Callable] = None) -> Dict[str, Any]:
    """Continue an existing workflow."""
    engine = WorkflowEngine(conv_id, ws_broadcaster)
    return engine.continue_workflow(user_input)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python workflow.py <topic>")
        sys.exit(1)
    
    topic = sys.argv[1]
    result = start_workflow(topic)
    print(json.dumps(result, ensure_ascii=False, indent=2))
