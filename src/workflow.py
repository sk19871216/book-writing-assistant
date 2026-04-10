#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Multi-agent workflow engine for writing assistant."""

import os
import sys
import re
import json
from typing import Optional, Dict, Any, Callable
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage import (
    init_db, create_conversation, get_conversation, list_conversations,
    append_entry, update_conversation_round, update_conversation_status,
    save_user_selection, get_latest_user_selection, has_agent_spoken,
    get_latest_entry_by_agent, get_workflow_state, set_workflow_state
)
from ai_client import get_ai_client


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
        
        # 为 Agent A 添加特殊上下文标记
        if agent_name == 'A':
            current_state = get_workflow_state(self.conv_id)
            
            # 方向细化阶段：提供被选中的方向内容（用于生成细化方向）
            if current_state == 'direction_refinement':
                # 找到用户要细化的方向
                if latest_selection and latest_selection.get('feedback'):
                    feedback = latest_selection.get('feedback', '')
                    # 提取要细化的方向编号
                    match = re.search(r'细化方向\s*(\d+)', feedback)
                    if match:
                        direction_num = match.group(1)
                        # 找到 A 的所有发言
                        a_entries = [e for e in entries if e.get('agent') == 'A']
                        if a_entries:
                            # 找到最后一次包含"子方向"的A的发言（细化后的10个子方向）
                            refinement_content = None
                            for entry in reversed(a_entries):
                                content = entry.get('content', '')
                                if '子方向' in content:
                                    refinement_content = content
                                    break
                            
                            # 如果没找到细化后的内容，使用第一次发言
                            if not refinement_content:
                                refinement_content = a_entries[0].get('content', '')
                            
                            # 尝试提取具体方向的内容
                            selected_direction_content = self._extract_direction_content(refinement_content, direction_num)
                            context_lines.append(f"\n=== 用户选择细化的方向 {direction_num} ===")
                            if selected_direction_content:
                                context_lines.append(f"方向 {direction_num} 的内容：\n{selected_direction_content}")
                            else:
                                context_lines.append(f"原始10个方向的内容：\n{refinement_content}")
                            context_lines.append(f"\n【重要任务】基于方向 {direction_num} 生成10个更细致的子方向")
            
            # 方向选择阶段：检查是否选择了子方向（用于生成详细创意）⭐【重要修复】
            elif current_state == 'direction_selection':
                # 检查用户是否选择了子方向
                if latest_selection and latest_selection.get('direction'):
                    direction = latest_selection.get('direction', '')
                    # 检查用户输入中是否包含"子方向"关键词
                    feedback = latest_selection.get('feedback', '')
                    if '子方向' in feedback or '子方向' in direction:
                        # 找到A的最后一次包含"子方向"的发言（细化后的10个子方向）
                        a_entries = [e for e in entries if e.get('agent') == 'A']
                        if a_entries:
                            refinement_content = None
                            for entry in reversed(a_entries):
                                content = entry.get('content', '')
                                if '子方向' in content:
                                    refinement_content = content
                                    break
                            
                            if refinement_content:
                                # 提取所有被选中的子方向的内容
                                direction_nums = direction.split('、')
                                context_lines.append(f"\n=== 用户选择的是【子方向】 ===")
                                context_lines.append(f"\n【重要】用户输入的是'子方向'，你在输出中必须使用'子方向'这个词，不要使用'方向'")
                                for num in direction_nums:
                                    num = num.strip()
                                    if num:
                                        selected_content = self._extract_direction_content(refinement_content, num)
                                        if selected_content:
                                            context_lines.append(f"\n**子方向 {num}**：\n{selected_content}")
                                        else:
                                            # 如果提取失败，输出警告
                                            context_lines.append(f"\n**子方向 {num}**：（内容提取失败，请参考完整列表）")
                                context_lines.append(f"\n【重要任务】基于上述用户选择的【子方向】，生成详细创意")
                                # 替换上下文中原有的讨论记录，避免A困惑
                                # 只保留最后几个关键条目
                                context_lines.append(f"\n=== 完整的子方向列表（供参考） ===")
                                context_lines.append(refinement_content[:2000] if len(refinement_content) > 2000 else refinement_content)
                    else:
                        # 用户选择的是原始方向（不包含"子方向"关键词）
                        a_entries = [e for e in entries if e.get('agent') == 'A']
                        if a_entries:
                            # 使用A的第一次发言（原始10个方向）
                            original_content = a_entries[0].get('content', '')
                            if original_content and '创意方向' in original_content:
                                # 提取所有被选中的原始方向的内容
                                direction_nums = direction.split('、')
                                context_lines.append(f"\n=== 用户选择的是【方向】 ===")
                                context_lines.append(f"\n【重要】用户输入的是'方向'，你在输出中必须使用'方向'这个词，不要使用'子方向'")
                                for num in direction_nums:
                                    num = num.strip()
                                    if num:
                                        selected_content = self._extract_direction_content(original_content, num)
                                        if selected_content:
                                            context_lines.append(f"\n**方向 {num}**：\n{selected_content}")
                                        else:
                                            context_lines.append(f"\n**方向 {num}**：（内容提取失败，请参考完整列表）")
                                context_lines.append(f"\n【重要任务】基于上述用户选择的【方向】，生成详细创意")
                                context_lines.append(f"\n=== 完整的原始方向列表（供参考） ===")
                                context_lines.append(original_content[:2000] if len(original_content) > 2000 else original_content)
            
            # B审核后的修改阶段：提供详细创意和审核意见
            elif current_state in ['feedback_after_review', 'refining_after_review']:
                # 获取 B 的最新审核
                b_entry = get_latest_entry_by_agent(self.conv_id, 'B')
                if b_entry:
                    context_lines.append(f"\n=== B的最新审核意见 ===\n{b_entry.get('content', '')}")
                
                # 获取用户的最新反馈
                if latest_selection and latest_selection.get('feedback'):
                    context_lines.append(f"\n=== 用户的最新反馈 ===\n{latest_selection.get('feedback')}")
                
                # 获取 A 自己的最新详细创意
                a_entries = [e for e in entries if e.get('agent') == 'A']
                if len(a_entries) >= 2:  # 至少有一次简单方向+一次详细创意
                    for entry in reversed(a_entries):
                        content = entry.get('content', '')
                        if '详细设计' in content or '主角设定' in content or '金手指设计' in content:
                            context_lines.append(f"\n=== 你之前生成的详细创意（需要基于这个修改） ===\n{content}")
                            break
        
        # 为 Agent C 添加特殊上下文标记
        if agent_name == 'C':
            # 获取用户选择的所有方向
            if latest_selection and latest_selection.get('direction'):
                direction = latest_selection.get('direction', '')
                direction_nums = direction.split('、')
                feedback = latest_selection.get('feedback', '')
                
                # 判断用户使用的是"方向"还是"子方向"
                if '子方向' in feedback or '子方向' in direction:
                    direction_type = '子方向'
                else:
                    direction_type = '方向'
                
                # 获取A的所有详细创意
                a_entries = [e for e in entries if e.get('agent') == 'A']
                for entry in reversed(a_entries):
                    content = entry.get('content', '')
                    if '详细设计' in content or '主角设定' in content or '金手指设计' in content:
                        context_lines.append(f"\n=== 提示：用户选择了 {len(direction_nums)} 个创意方向 ===")
                        context_lines.append(f"编号：{direction_type}{direction}")
                        context_lines.append(f"\n【重要】请使用'【{direction_type}】'这个词来输出评估结果，不要使用其他词汇")
                        context_lines.append(f"\n【重要】请分别对每个方向进行详细评估，输出格式参考：")
                        context_lines.append(f"- {direction_type} {direction_nums[0]} 的详细评估")
                        context_lines.append(f"- {direction_type} {direction_nums[1] if len(direction_nums) > 1 else '...'} 的详细评估")
                        context_lines.append(f"- ...")
                        context_lines.append(f"\n完整的详细创意内容如下，请仔细阅读后逐个评估：")
                        context_lines.append(f"\n{content[:3000]}...")  # 限制长度避免过长
                        break
        
        # 为 Agent B 添加特殊上下文标记
        if agent_name == 'B':
            # 获取用户选择的所有方向
            if latest_selection and latest_selection.get('direction'):
                direction = latest_selection.get('direction', '')
                direction_nums = direction.split('、')
                feedback = latest_selection.get('feedback', '')
                
                # 判断用户使用的是"方向"还是"子方向"
                if '子方向' in feedback or '子方向' in direction:
                    direction_type = '子方向'
                else:
                    direction_type = '方向'
                
                context_lines.append(f"\n=== 提示：用户选择的是【{direction_type}】 ===")
                context_lines.append(f"\n编号：{direction_type}{direction}")
                context_lines.append(f"\n【重要】请使用'【{direction_type}】'这个词来输出审核结果，不要使用其他词汇")
        
        return '\n'.join(context_lines)
    
    def call_claude(self, prompt: str) -> str:
        """Call Claude API to execute agent prompt."""
        try:
            client = get_ai_client()
            output = client.generate(prompt)
            return output
        except ValueError as e:
            return f"Error: {str(e)}"
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
    
    def _extract_direction_content(self, content: str, direction_num: str) -> Optional[str]:
        """Extract specific direction content from A's output.
        
        使用更简单可靠的提取逻辑：
        1. 首先尝试用正则表达式匹配
        2. 如果失败，使用按行分割的方式
        """
        direction_num_str = str(direction_num)
        
        # 尝试用正则表达式提取
        patterns_to_try = [
            # 模式1: **创意方向 1**：
            rf'\*\*创意方向\s*{direction_num_str}\*\*[:：]\s*(.*?)(?=\*\*创意方向|\*\*子方向|\Z)',
            # 模式2: **子方向 1**：
            rf'\*\*子方向\s*{direction_num_str}\*\*[:：]\s*(.*?)(?=\*\*创意方向|\*\*子方向|\Z)',
            # 模式3: 创意方向 1：
            rf'(?<![\*])创意方向\s*{direction_num_str}[:：]\s*(.*?)(?=创意方向\s*\d|子方向\s*\d|$)',
            # 模式4: 子方向 1：
            rf'(?<![\*])子方向\s*{direction_num_str}[:：]\s*(.*?)(?=子方向\s*\d|创意方向\s*\d|$)',
            # 模式5: **方向 1**：
            rf'\*\*方向\s*{direction_num_str}\*\*[:：]\s*(.*?)(?=\*\*方向|\Z)',
            # 模式6: 方向 1：
            rf'(?<![\*])方向\s*{direction_num_str}[:：]\s*(.*?)(?=方向\s*\d|$)',
        ]
        
        for pattern in patterns_to_try:
            try:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    result = match.group(1).strip()
                    if result and len(result) > 10:  # 确保提取到足够的内容
                        return result
            except:
                continue
        
        # 如果正则表达式失败，使用按行分割的方式
        lines = content.split('\n')
        result_lines = []
        in_target = False
        target_prefixes = [
            f'**创意方向 {direction_num_str}**',
            f'**子方向 {direction_num_str}**',
            f'创意方向 {direction_num_str}：',
            f'子方向 {direction_num_str}：',
            f'**方向 {direction_num_str}**',
            f'方向 {direction_num_str}：',
            f'创意方向 {direction_num_str}**',
            f'子方向 {direction_num_str}**',
            f'方向 {direction_num_str}**',
        ]
        
        # 下一个方向的编号
        next_num = int(direction_num_str) + 1
        next_prefixes = [
            f'**创意方向 {next_num}**',
            f'**子方向 {next_num}**',
            f'创意方向 {next_num}：',
            f'子方向 {next_num}：',
            f'**方向 {next_num}**',
            f'方向 {next_num}：',
        ]
        
        for i, line in enumerate(lines):
            # 检查是否到达目标方向
            if not in_target:
                for prefix in target_prefixes:
                    if prefix in line:
                        in_target = True
                        break
                continue
            
            # 检查是否到达下一个方向
            if in_target:
                is_next = False
                for prefix in next_prefixes:
                    if prefix in line:
                        is_next = True
                        break
                # 也检查是否到达任何方向（可能是重复的标题）
                for j in range(i, min(i+3, len(lines))):
                    line_lower = lines[j].lower()
                    if '方向' in line_lower and str(next_num) in lines[j]:
                        is_next = True
                        break
                    # 检查是否是任意方向标题
                    match = re.search(r'[\*]*\s*(创意)?方向\s*\d+', lines[j])
                    if match and match.group(0) != f'创意方向 {direction_num_str}':
                        is_next = True
                        break
                
                if is_next:
                    break
                
                result_lines.append(line)
        
        if result_lines:
            result = '\n'.join(result_lines).strip()
            if result and len(result) > 5:
                return result
        
        return None
    
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
        """Parse direction selection from user input.
        
        支持格式：
        - 方向1、2
        - 方向 1、2
        - 子方向1、2
        - 子方向 1、2
        - 1、2
        """
        # 方法1: 使用更智能的方式解析
        # 找到所有"方向"或"子方向"后面的所有数字（包括后面紧跟的）
        pattern = r'(?:方向|子方向)\s*(\d+)'
        matches = list(re.finditer(pattern, user_input))
        
        if matches:
            numbers = []
            for m in matches:
                num = m.group(1)
                if num not in numbers:
                    numbers.append(num)
            
            # 还需要检查"方向X"后面是否还有其他数字（用分隔符分隔的）
            for m in matches:
                # 获取匹配结束位置
                end_pos = m.end()
                # 查找后续内容中用分隔符分隔的数字
                remaining = user_input[end_pos:]
                # 匹配用中文逗号、顿号、英文逗号、"和"、"还有"等分隔的数字
                extra_nums = re.findall(r'[、，,\s和还有]+(\d+)', remaining)
                for num in extra_nums:
                    if num not in numbers:
                        numbers.append(num)
            
            return '、'.join(numbers)
        
        # 方法2: 如果没有找到"方向X"模式，尝试只匹配所有数字
        all_numbers = re.findall(r'\d+', user_input)
        if all_numbers:
            return '、'.join(all_numbers)
        
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
    
    def is_refinement_request(self, user_input: str) -> bool:
        """Check if user wants to refine a direction."""
        pattern = r'细化方向\s*(\d+)'
        return bool(re.search(pattern, user_input))

    def parse_refinement_direction(self, user_input: str) -> Optional[str]:
        """Parse which direction to refine from user input."""
        match = re.search(r'细化方向\s*(\d+)', user_input)
        if match:
            return match.group(1)
        return None
    
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
            'verdict': verdict
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
        """Run the initial workflow - only Agent A generates simple directions."""
        init_db()
        
        self.broadcast('workflow_start', {
            'conv_id': self.conv_id,
            'topic': self.topic
        })
        
        self.current_round = 1
        update_conversation_round(self.conv_id, self.current_round)
        set_workflow_state(self.conv_id, 'direction_selection')
        
        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })
        
        self.run_agent('A')
        
        self.broadcast('awaiting_user_input', {
            'phase': 'direction_selection'
        })
        
        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'direction_selection'
        }
    
    def continue_workflow(self, user_input: str) -> Dict[str, Any]:
        """Continue workflow after user input based on current state."""
        current_state = get_workflow_state(self.conv_id)

        if current_state == 'direction_selection':
            return self.handle_direction_selection(user_input)
        elif current_state == 'direction_refinement':
            # 方向细化阶段，直接调用Agent A生成子方向
            return self.handle_direction_refinement(user_input)
        elif current_state == 'detailed_ideas':
            return self.handle_detailed_ideas(user_input)
        elif current_state == 'feedback':
            return self.handle_feedback(user_input)
        elif current_state == 'feedback_after_review':
            return self.handle_feedback_after_review(user_input)
        elif current_state == 'refining_after_review':
            # B审核后的修改阶段
            return self.handle_refining_after_review(user_input)

        return {'action': 'error', 'message': f'Unknown state: {current_state}'}
    
    def handle_direction_selection(self, user_input: str) -> Dict[str, Any]:
        """Handle user input in direction selection phase."""
        # 检查是否是方向细化请求
        if self.is_refinement_request(user_input):
            direction_num = self.parse_refinement_direction(user_input)
            save_user_selection(self.conv_id, self.current_round, feedback=user_input)
            
            self.current_round += 1
            update_conversation_round(self.conv_id, self.current_round)
            
            set_workflow_state(self.conv_id, 'direction_refinement')
            
            self.broadcast('iteration_start', {
                'iteration': 1,
                'round': self.current_round
            })
            
            self.run_agent('A')
            
            set_workflow_state(self.conv_id, 'direction_selection')  # 回到方向选择，但现在是子方向
            
            self.broadcast('awaiting_user_input', {
                'phase': 'direction_selection',
                'is_refinement': True  # 标记这是细化后的选择
            })
            
            return {
                'action': 'wait_for_user',
                'iteration': 1,
                'round': self.current_round,
                'state': 'direction_selection'
            }
        
        # 原有的方向选择逻辑
        direction = self.parse_direction_from_input(user_input)
        
        if not direction:
            return {'action': 'wait', 'message': '请输入有效的方向选择（如：方向1、2）或细化请求（如：细化方向2）'}
        
        save_user_selection(self.conv_id, self.current_round, direction=direction, feedback=user_input)
        
        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)
        
        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })
        
        self.run_agent('A')
        
        set_workflow_state(self.conv_id, 'detailed_ideas')
        
        self.broadcast('awaiting_user_input', {
            'phase': 'detailed_ideas'
        })
        
        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'detailed_ideas'
        }
    
    def handle_direction_refinement(self, user_input: str) -> Dict[str, Any]:
        """Handle direction refinement - generate 10 sub-directions."""
        # 这个状态只用于标识，实际处理在handle_direction_selection中已经完成
        # 如果用户输入了内容，说明是在选择细化后的子方向
        direction = self.parse_direction_from_input(user_input)
        
        if not direction:
            return {'action': 'wait', 'message': '请输入有效的子方向选择（如：方向1、2）'}
        
        save_user_selection(self.conv_id, self.current_round, direction=direction, feedback=user_input)
        
        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)
        
        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })
        
        self.run_agent('A')
        
        set_workflow_state(self.conv_id, 'detailed_ideas')
        
        self.broadcast('awaiting_user_input', {
            'phase': 'detailed_ideas'
        })
        
        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'detailed_ideas'
        }
    
    def handle_refining_after_review(self, user_input: str) -> Dict[str, Any]:
        """Handle user input during refining after B's review."""
        if self.is_user_satisfied(user_input):
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

        if self.is_regenerate_request(user_input):
            return self.handle_regenerate()

        save_user_selection(self.conv_id, self.current_round, feedback=user_input)

        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)

        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })

        self.run_agent('A')

        set_workflow_state(self.conv_id, 'feedback')

        self.broadcast('awaiting_user_input', {
            'phase': 'feedback'
        })

        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'feedback'
        }
    
    def handle_detailed_ideas(self, user_input: str) -> Dict[str, Any]:
        """Handle user input after detailed ideas are generated."""
        if self.is_user_satisfied(user_input):
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

        if self.is_review_request(user_input):
            self.run_agent('B')

            self.broadcast('awaiting_user_input', {
                'phase': 'feedback_after_review'
            })

            return {
                'action': 'wait_for_user',
                'iteration': 1,
                'round': self.current_round,
                'state': 'feedback_after_review'
            }

        save_user_selection(self.conv_id, self.current_round, feedback=user_input)

        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)

        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })

        self.run_agent('A')

        self.broadcast('awaiting_user_input', {
            'phase': 'detailed_ideas'
        })

        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'detailed_ideas'
        }
    
    def is_review_request(self, user_input: str) -> bool:
        """Check if user wants B to review."""
        review_keywords = ['让B审核', 'B审核', '审核', '给B看', 'b审核', 'review']
        user_input_lower = user_input.lower()
        return any(keyword in user_input_lower for keyword in review_keywords)

    def handle_regenerate(self) -> Dict[str, Any]:
        """Handle regenerate request - restart from Agent A."""
        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)
        set_workflow_state(self.conv_id, 'direction_selection')

        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })

        self.run_agent('A')

        self.broadcast('awaiting_user_input', {
            'phase': 'direction_selection'
        })

        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'direction_selection'
        }

    def handle_feedback_after_review(self, user_input: str) -> Dict[str, Any]:
        """Handle user input after B has reviewed."""
        if self.is_user_satisfied(user_input):
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

        if self.is_regenerate_request(user_input):
            return self.handle_regenerate()

        save_user_selection(self.conv_id, self.current_round, feedback=user_input)

        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)

        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })
        
        # 设置状态为 refining_after_review，让 A 明确知道任务
        set_workflow_state(self.conv_id, 'refining_after_review')

        self.run_agent('A')
        
        # 完成后回到 feedback 状态
        set_workflow_state(self.conv_id, 'feedback')

        self.broadcast('awaiting_user_input', {
            'phase': 'feedback'
        })

        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'feedback'
        }

    def handle_feedback(self, user_input: str) -> Dict[str, Any]:
        """Handle user input in feedback phase."""
        if self.is_user_satisfied(user_input):
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

        if self.is_review_request(user_input):
            self.run_agent('B')

            self.broadcast('awaiting_user_input', {
                'phase': 'feedback_after_review'
            })

            return {
                'action': 'wait_for_user',
                'iteration': 1,
                'round': self.current_round,
                'state': 'feedback_after_review'
            }

        if self.is_regenerate_request(user_input):
            return self.handle_regenerate()

        save_user_selection(self.conv_id, self.current_round, feedback=user_input)

        self.current_round += 1
        update_conversation_round(self.conv_id, self.current_round)

        self.broadcast('iteration_start', {
            'iteration': 1,
            'round': self.current_round
        })

        self.run_agent('A')

        self.broadcast('awaiting_user_input', {
            'phase': 'feedback'
        })

        return {
            'action': 'wait_for_user',
            'iteration': 1,
            'round': self.current_round,
            'state': 'feedback'
        }


def start_workflow(topic: str, ws_broadcaster: Optional[Callable] = None) -> Dict[str, Any]:
    """Start a new workflow with given topic."""
    init_db()
    conv_id = create_conversation(topic)

    engine = WorkflowEngine(conv_id, ws_broadcaster)
    return engine.run_workflow()


def resume_workflow(conv_id: int, ws_broadcaster: Optional[Callable] = None) -> Dict[str, Any]:
    """Resume workflow on existing conversation."""
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
