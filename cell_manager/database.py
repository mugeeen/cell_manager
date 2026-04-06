# -*- coding: utf-8 -*-
"""
数据库管理模块

本模块提供 SQLite 数据库的连接管理和表结构定义
负责 Cell 数据的持久化存储
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from .models import Cell, CellStatus


class DatabaseManager:
    """
    数据库管理器
    
    管理 SQLite 数据库连接和 Cell 表的 CRUD 操作
    
    Attributes:
        db_path: 数据库文件路径
        connection: 数据库连接对象
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径，默认为项目目录下的 data/cells.db
        """
        if db_path is None:
            # 默认路径：项目根目录下的 data/cells.db
            current_dir = Path(__file__).parent.parent.parent
            data_dir = current_dir / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = data_dir / "cells.db"
        
        self.db_path = str(db_path)
        self.connection: Optional[sqlite3.Connection] = None
    
    def connect(self) -> sqlite3.Connection:
        """
        建立数据库连接
        
        Returns:
            数据库连接对象
        """
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            # 启用外键支持
            self.connection.execute("PRAGMA foreign_keys = ON")
            # 设置行工厂为字典类型
            self.connection.row_factory = sqlite3.Row
        return self.connection
    
    def close(self) -> None:
        """
        关闭数据库连接
        """
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def init_tables(self) -> None:
        """
        初始化数据库表结构
        
        创建 cells 表，包含所有 Cell 字段
        """
        conn = self.connect()
        cursor = conn.cursor()
        
        # 创建 cells 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cells (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                level INTEGER DEFAULT 0,
                status TEXT DEFAULT 'todo',
                priority INTEGER DEFAULT 3,
                parent_id TEXT,
                children_ids TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                completed_at TEXT,
                deadline TEXT,
                actual_hours REAL DEFAULT 0.0,
                total_hours REAL DEFAULT 0.0,
                workload REAL DEFAULT 0.0,
                total_workload REAL DEFAULT 0.0,
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (parent_id) REFERENCES cells(id) ON DELETE SET NULL
            )
        """)
        
        # 创建索引以提高查询性能
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cells_parent_id 
            ON cells(parent_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cells_status 
            ON cells(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cells_level 
            ON cells(level)
        """)
        
        conn.commit()
    
    def create_cell(self, cell: Cell) -> bool:
        """
        创建新的 Cell 记录
        
        Args:
            cell: Cell 实例
            
        Returns:
            创建成功返回 True，失败返回 False
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            data = cell.to_dict()
            cursor.execute("""
                INSERT INTO cells (
                    id, title, description, level, status, priority,
                    parent_id, children_ids, created_at, completed_at, deadline,
                    actual_hours, total_hours, workload, total_workload,
                    tags, metadata
                ) VALUES (
                    :id, :title, :description, :level, :status, :priority,
                    :parent_id, :children_ids, :created_at, :completed_at, :deadline,
                    :actual_hours, :total_hours, :workload, :total_workload,
                    :tags, :metadata
                )
            """, data)
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"创建 Cell 失败: {e}")
            return False
    
    def get_cell(self, cell_id: str) -> Optional[Cell]:
        """
        根据 ID 获取 Cell
        
        Args:
            cell_id: Cell 的唯一标识符
            
        Returns:
            Cell 实例，不存在则返回 None
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM cells WHERE id = ?",
                (cell_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return Cell.from_dict(dict(row))
            return None
        except sqlite3.Error as e:
            print(f"获取 Cell 失败: {e}")
            return None
    
    def update_cell(self, cell: Cell) -> bool:
        """
        更新 Cell 记录
        
        Args:
            cell: Cell 实例
            
        Returns:
            更新成功返回 True，失败返回 False
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            data = cell.to_dict()
            cursor.execute("""
                UPDATE cells SET
                    title = :title,
                    description = :description,
                    level = :level,
                    status = :status,
                    priority = :priority,
                    parent_id = :parent_id,
                    children_ids = :children_ids,
                    completed_at = :completed_at,
                    deadline = :deadline,
                    actual_hours = :actual_hours,
                    total_hours = :total_hours,
                    workload = :workload,
                    total_workload = :total_workload,
                    tags = :tags,
                    metadata = :metadata
                WHERE id = :id
            """, data)
            
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"更新 Cell 失败: {e}")
            return False
    
    def delete_cell(self, cell_id: str) -> bool:
        """
        删除 Cell 记录
        
        Args:
            cell_id: Cell 的唯一标识符
            
        Returns:
            删除成功返回 True，失败返回 False
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM cells WHERE id = ?",
                (cell_id,)
            )
            
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"删除 Cell 失败: {e}")
            return False
    
    def list_cells(
        self,
        parent_id: Optional[str] = None,
        status: Optional[CellStatus] = None,
        level: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Cell]:
        """
        列出 Cell 记录
        
        Args:
            parent_id: 父 Cell ID，None 表示查询根节点
            status: 按状态筛选
            level: 按层级筛选
            limit: 返回数量限制
            offset: 分页偏移量
            
        Returns:
            Cell 实例列表
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # 构建查询条件
            conditions = []
            params = []
            
            if parent_id is not None:
                conditions.append("parent_id = ?")
                params.append(parent_id)
            else:
                conditions.append("parent_id IS NULL")
            
            if status is not None:
                conditions.append("status = ?")
                params.append(status.value)
            
            if level is not None:
                conditions.append("level = ?")
                params.append(level)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            cursor.execute(f"""
                SELECT * FROM cells
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset])
            
            rows = cursor.fetchall()
            return [Cell.from_dict(dict(row)) for row in rows]
        except sqlite3.Error as e:
            print(f"列出 Cell 失败: {e}")
            return []
    
    def get_children(self, parent_id: str) -> List[Cell]:
        """
        获取指定 Cell 的所有子 Cell
        
        Args:
            parent_id: 父 Cell ID
            
        Returns:
            子 Cell 列表
        """
        return self.list_cells(parent_id=parent_id, limit=1000)
    
    def search_cells(self, keyword: str) -> List[Cell]:
        """
        搜索 Cell
        
        根据标题或描述搜索
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的 Cell 列表
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            search_pattern = f"%{keyword}%"
            cursor.execute("""
                SELECT * FROM cells
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY created_at DESC
            """, (search_pattern, search_pattern))
            
            rows = cursor.fetchall()
            return [Cell.from_dict(dict(row)) for row in rows]
        except sqlite3.Error as e:
            print(f"搜索 Cell 失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            包含各种统计数据的字典
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # 总 Cell 数量
            cursor.execute("SELECT COUNT(*) FROM cells")
            total_count = cursor.fetchone()[0]
            
            # 各状态数量
            cursor.execute("""
                SELECT status, COUNT(*) FROM cells
                GROUP BY status
            """)
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 总用时
            cursor.execute("SELECT SUM(total_hours) FROM cells")
            total_hours = cursor.fetchone()[0] or 0.0
            
            # 各层级数量
            cursor.execute("""
                SELECT level, COUNT(*) FROM cells
                GROUP BY level
            """)
            level_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                'total_count': total_count,
                'status_counts': status_counts,
                'total_hours': total_hours,
                'level_counts': level_counts
            }
        except sqlite3.Error as e:
            print(f"获取统计信息失败: {e}")
            return {}
    
    def get_completed_leaf_cells_by_date(self, date_str: str) -> List[Cell]:
        """
        获取指定日期完成的叶子节点
        
        只返回 status='completed' 且没有子节点的 Cell
        
        Args:
            date_str: 日期字符串，格式为 'YYYY-MM-DD'
            
        Returns:
            Cell 列表
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # 查询指定日期完成的叶子节点（使用子查询判断是否为叶子节点）
            cursor.execute("""
                SELECT c.* FROM cells c
                WHERE c.status = 'completed'
                AND DATE(c.completed_at) = DATE(?)
                AND NOT EXISTS (
                    SELECT 1 FROM cells child WHERE child.parent_id = c.id
                )
                ORDER BY c.completed_at DESC
            """, (date_str,))
            
            rows = cursor.fetchall()
            return [Cell.from_dict(dict(row)) for row in rows]
        except sqlite3.Error as e:
            print(f"获取已完成叶子节点失败: {e}")
            return []
    
    def get_completed_dates(self) -> List[str]:
        """
        获取所有有完成记录的日期列表
        
        Returns:
            日期字符串列表，格式为 ['YYYY-MM-DD', ...]
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # 使用子查询判断是否为叶子节点（没有子节点）
            cursor.execute("""
                SELECT DISTINCT DATE(c.completed_at) as date
                FROM cells c
                WHERE c.status = 'completed'
                AND c.completed_at IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM cells child WHERE child.parent_id = c.id
                )
                ORDER BY date DESC
            """)
            
            rows = cursor.fetchall()
            return [row['date'] for row in rows]
        except sqlite3.Error as e:
            print(f"获取完成日期列表失败: {e}")
            return []
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
