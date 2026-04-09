#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI client for calling MiniMax API using Anthropic SDK."""

import os
import anthropic
from typing import Optional


ANTHROPIC_API_KEY = os.environ.get('MINIMAX_start', '')
ANTHROPIC_BASE_URL = "https://api.minimaxi.com/anthropic"
MODEL = "MiniMax-M2.7"


class AIClient:
    """Client for calling MiniMax API using Anthropic SDK."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url=ANTHROPIC_BASE_URL
        )

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 8192) -> str:
        """Generate text using MiniMax API."""
        messages = [{"role": "user", "content": prompt}]

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages
        )

        text_content = ""
        for block in response.content:
            if block.type == "text":
                text_content += block.text

        return text_content


def get_ai_client() -> AIClient:
    """Get or create AI client instance."""
    return AIClient()
