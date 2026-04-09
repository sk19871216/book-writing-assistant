#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite database layer for multi-agent writing assistant workflow."""

import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, 'workspace', 'book_helper.db')


def get_db() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database and create tables if not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            round INTEGER DEFAULT 0,
            status TEXT DEFAULT 'in_progress',
            workflow_state TEXT DEFAULT 'direction_selection',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            agent TEXT NOT NULL,
            round INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            content TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            round INTEGER,
            direction TEXT,
            feedback TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    ''')
    
    conn.commit()
    conn.close()


def create_conversation(topic: str) -> int:
    """Create a new conversation and return its ID."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        'INSERT INTO conversations (topic, round, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
        (topic, 0, 'in_progress', now, now)
    )
    conv_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return conv_id


def get_conversation(conv_id: int) -> Optional[Dict[str, Any]]:
    """Get conversation with all entries and user selections."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM conversations WHERE id = ?', (conv_id,))
    conv_row = cursor.fetchone()
    
    if not conv_row:
        conn.close()
        return None
    
    cursor.execute(
        'SELECT * FROM entries WHERE conversation_id = ? ORDER BY timestamp',
        (conv_id,)
    )
    entries = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute(
        'SELECT * FROM user_selections WHERE conversation_id = ? ORDER BY round',
        (conv_id,)
    )
    selections = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    workflow_state = conv_row['workflow_state'] if 'workflow_state' in conv_row.keys() else 'direction_selection'

    return {
        'id': conv_row['id'],
        'topic': conv_row['topic'],
        'round': conv_row['round'],
        'status': conv_row['status'],
        'workflow_state': workflow_state,
        'created_at': conv_row['created_at'],
        'updated_at': conv_row['updated_at'],
        'entries': entries,
        'user_selections': selections
    }


def list_conversations(limit: int = 20) -> List[Dict[str, Any]]:
    """List recent conversations for sidebar."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, topic, round, status, created_at, updated_at
        FROM conversations
        ORDER BY updated_at DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def append_entry(conversation_id: int, agent: str, round_num: int, content: str) -> int:
    """Append an entry to a conversation. Returns entry ID."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        '''INSERT INTO entries (conversation_id, agent, round, timestamp, content)
           VALUES (?, ?, ?, ?, ?)''',
        (conversation_id, agent, round_num, now, content)
    )
    entry_id = cursor.lastrowid
    
    cursor.execute(
        'UPDATE conversations SET updated_at = ? WHERE id = ?',
        (now, conversation_id)
    )
    
    conn.commit()
    conn.close()
    
    return entry_id


def update_conversation_round(conv_id: int, round_num: int) -> None:
    """Update the round number for a conversation."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        'UPDATE conversations SET round = ?, updated_at = ? WHERE id = ?',
        (round_num, now, conv_id)
    )
    conn.commit()
    conn.close()


def update_conversation_status(conv_id: int, status: str) -> None:
    """Update conversation status (in_progress, approved, rejected)."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        'UPDATE conversations SET status = ?, updated_at = ? WHERE id = ?',
        (status, now, conv_id)
    )
    conn.commit()
    conn.close()


def save_user_selection(
    conversation_id: int,
    round_num: int,
    direction: Optional[str] = None,
    feedback: Optional[str] = None
) -> int:
    """Save user's selection/feedback. Returns selection ID."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        '''INSERT INTO user_selections (conversation_id, round, direction, feedback, timestamp)
           VALUES (?, ?, ?, ?, ?)''',
        (conversation_id, round_num, direction, feedback, now)
    )
    selection_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return selection_id


def get_latest_user_selection(conv_id: int) -> Optional[Dict[str, Any]]:
    """Get the most recent user selection for a conversation."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT * FROM user_selections 
           WHERE conversation_id = ? 
           ORDER BY id DESC LIMIT 1''',
        (conv_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_latest_entry_by_agent(conv_id: int, agent: str) -> Optional[Dict[str, Any]]:
    """Get the most recent entry by a specific agent."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT * FROM entries 
           WHERE conversation_id = ? AND agent = ?
           ORDER BY id DESC LIMIT 1''',
        (conv_id, agent)
    )
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def has_agent_spoken(conv_id: int, agent: str) -> bool:
    """Check if an agent has already spoken in this conversation."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT COUNT(*) FROM entries WHERE conversation_id = ? AND agent = ?',
        (conv_id, agent)
    )
    count = cursor.fetchone()[0]
    conn.close()
    
    return count > 0


def delete_conversation(conv_id: int) -> None:
    """Delete a conversation and all its entries and selections."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM entries WHERE conversation_id = ?', (conv_id,))
    cursor.execute('DELETE FROM user_selections WHERE conversation_id = ?', (conv_id,))
    cursor.execute('DELETE FROM conversations WHERE id = ?', (conv_id,))
    
    conn.commit()
    conn.close()


def get_all_entries(conv_id: int) -> List[Dict[str, Any]]:
    """Get all entries for a conversation."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT * FROM entries WHERE conversation_id = ? ORDER BY timestamp',
        (conv_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_workflow_state(conv_id: int) -> str:
    """Get the current workflow state for a conversation."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT workflow_state FROM conversations WHERE id = ?', (conv_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and 'workflow_state' in row.keys():
        return row['workflow_state']
    return 'direction_selection'


def set_workflow_state(conv_id: int, state: str) -> None:
    """Set the workflow state for a conversation."""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        'UPDATE conversations SET workflow_state = ?, updated_at = ? WHERE id = ?',
        (state, now, conv_id)
    )
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print(f"Database initialized at: {DB_PATH}")
