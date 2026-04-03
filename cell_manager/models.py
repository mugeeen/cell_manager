# -*- coding: utf-8 -*-
"""
Cell 数据模型定义

本模块定义了 Cell 的数据结构和枚举类型
Cell 是任务管理的基本单元，支持无限递归的父子关系
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
import json


class CellStatus(str, Enum):
    """
    Cell 状态枚举
    
    跟踪任务的执行状态
    简化状态：待办 -> 进行中 -> 紧急 -> 已完成
    """
    TODO = "todo"           # 待办，尚未开始
    IN_PROGRESS = "in_progress"  # 进行中
    URGENT = "urgent"       # 紧急
    COMPLETED = "completed" # 已完成


@dataclass
class Cell:
    """
    Cell 数据类
    
    任务管理的核心单元，支持父子关系形成树形结构
    可以无限递归细分，实现任务的层级管理
    
    Attributes:
        id: 唯一标识符，使用 UUID
        title: 标题，简短描述任务
        description: 详细描述
        cell_type: Cell 类型（goal/task/subtask）
        status: 当前状态
        priority: 优先级 1-5，数字越大优先级越高
        parent_id: 父 Cell 的 ID，None 表示根节点
        children_ids: 子 Cell ID 列表
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        estimated_hours: 预计用时（小时）
        actual_hours: 实际用时（小时）
        tags: 标签列表，用于分类和筛选
        metadata: 自定义元数据字典，灵活扩展
    """
    
    # 基础信息
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    
    # 层级信息：表示在任务链条中的深度，根节点为0，每下一级+1
    level: int = 0
    
    # 状态管理
    status: CellStatus = CellStatus.TODO
    priority: int = 3  # 默认中等优先级
    
    # 父子关系（支持无限递归）
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    
    # 时间跟踪
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None  # 完成时间
    deadline: Optional[datetime] = None  # 截止时间
    actual_hours: float = 0.0  # 实际用时（仅叶子节点有效）
    total_hours: float = 0.0  # 总用时（由子cell的actual_hours加和）
    
    # 任务量跟踪
    workload: float = 0.0  # 预计任务量（叶子节点可设置，非叶子节点为预计值）
    total_workload: float = 0.0  # 总任务量（由子cell的workload加和）
    
    # 扩展属性
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """
        初始化后处理
        
        确保 children_ids 是列表类型
        """
        if self.children_ids is None:
            self.children_ids = []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        用于序列化和数据库存储
        
        Returns:
            包含所有字段的字典
        """
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'level': self.level,
            'status': self.status.value,
            'priority': self.priority,
            'parent_id': self.parent_id,
            'children_ids': json.dumps(self.children_ids),
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'actual_hours': self.actual_hours,
            'total_hours': self.total_hours,
            'workload': self.workload,
            'total_workload': self.total_workload,
            'tags': json.dumps(self.tags),
            'metadata': json.dumps(self.metadata)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Cell':
        """
        从字典创建 Cell 实例
        
        用于从数据库记录反序列化
        
        Args:
            data: 包含 Cell 数据的字典
            
        Returns:
            Cell 实例
        """
        # 状态迁移映射（旧状态 -> 新状态）
        status_mapping = {
            'done': 'completed',      # 旧: DONE -> 新: COMPLETED
            'doing': 'in_progress',   # 旧: DOING -> 新: IN_PROGRESS
            'paused': 'urgent',       # 旧: PAUSED -> 新: URGENT
            'cancelled': 'todo',      # 旧: CANCELLED -> 新: TODO
            # 新状态保持不变
            'todo': 'todo',
            'in_progress': 'in_progress',
            'urgent': 'urgent',
            'completed': 'completed'
        }
        
        # 转换旧状态到新状态
        raw_status = data['status']
        mapped_status = status_mapping.get(raw_status, raw_status)
        
        try:
            status = CellStatus(mapped_status)
        except ValueError:
            # 如果映射后的状态仍然无效，默认为 TODO
            status = CellStatus.TODO
        
        return cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            level=data.get('level', 0),
            status=status,
            priority=data['priority'],
            parent_id=data['parent_id'],
            children_ids=json.loads(data['children_ids']) if data['children_ids'] else [],
            created_at=datetime.fromisoformat(data['created_at']),
            deadline=datetime.fromisoformat(data['deadline']) if data['deadline'] else None,
            actual_hours=data.get('actual_hours', 0.0),
            total_hours=data.get('total_hours', 0.0),
            workload=data.get('workload', 0.0),
            total_workload=data.get('total_workload', 0.0),
            tags=json.loads(data['tags']) if data['tags'] else [],
            metadata=json.loads(data['metadata']) if data['metadata'] else {}
        )
    
    def set_actual_hours(self, hours: float) -> None:
        """
        设置实际用时
        
        只有叶子节点（没有子cell）才能设置实际用时
        有子cell时，总用时由子cell决定
        
        Args:
            hours: 实际用时（小时）
        """
        self.actual_hours = hours
        # 如果是叶子节点，总用时等于实际用时
        if not self.children_ids:
            self.total_hours = hours
    
    def set_workload(self, workload: float) -> None:
        """
        设置任务量
        
        只有叶子节点（没有子cell）才能设置任务量
        有子cell时，总任务量由子cell决定
        
        Args:
            workload: 任务量
        """
        self.workload = workload
        # 如果是叶子节点，总任务量等于任务量
        if not self.children_ids:
            self.total_workload = workload
    
    def update_total_hours(self, children_total_hours: float) -> None:
        """
        更新总用时
        
        当添加子cell时，由父cell调用此方法更新总用时
        总用时完全由子cell的actual_hours加和决定
        
        Args:
            children_total_hours: 所有子cell的actual_hours之和
        """
        self.total_hours = children_total_hours
    
    def complete(self) -> None:
        """
        完成任务
        
        将状态设置为 COMPLETED 并记录完成时间
        """
        self.status = CellStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def add_child(self, child_id: str) -> None:
        """
        添加子 Cell
        
        Args:
            child_id: 子 Cell 的 ID
        """
        if child_id not in self.children_ids:
            self.children_ids.append(child_id)
    
    def remove_child(self, child_id: str) -> None:
        """
        移除子 Cell
        
        Args:
            child_id: 子 Cell 的 ID
        """
        if child_id in self.children_ids:
            self.children_ids.remove(child_id)
    
    def get_progress(self) -> float:
        """
        获取任务进度百分比（仅用于叶子节点）
        
        简化规则：
        - COMPLETED: 100%
        - 其他状态: 0%
        
        非叶子节点的进度由 manager.get_progress() 递归计算
        
        Returns:
            进度百分比 0.0-100.0
        """
        # 叶子节点：只有 completed 才算完成
        return 100.0 if self.status == CellStatus.COMPLETED else 0.0
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<Cell {self.id[:8]}: {self.title} ({self.status.value})>"
