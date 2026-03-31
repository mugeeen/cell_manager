# -*- coding: utf-8 -*-
"""
Cell 业务逻辑管理模块

本模块封装 Cell 的复杂业务逻辑，协调 models 和 database 层
提供高层次的 API 供上层调用
"""

from typing import Optional, List, Dict, Any
from .models import Cell, CellStatus
from .database import DatabaseManager


class CellManager:
    """
    Cell 业务逻辑管理器
    
    封装 Cell 的 CRUD、父子关系管理、时间统计、进度计算等业务逻辑
    
    Attributes:
        db: DatabaseManager 实例
    """
    
    def __init__(self, db: DatabaseManager):
        """
        初始化管理器
        
        Args:
            db: DatabaseManager 实例
        """
        self.db = db
    
    # ==================== 基础 CRUD ====================
    
    def create_cell(
        self,
        title: str,
        description: str = "",
        parent_id: Optional[str] = None,
        priority: int = 3,
        deadline: Optional[str] = None,
        workload: float = 0.0,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> Optional[Cell]:
        """
        创建新的 Cell
        
        自动计算 level，处理父子关系
        
        Args:
            title: 标题
            description: 描述
            parent_id: 父 Cell ID
            priority: 优先级 1-5
            deadline: 截止时间（ISO格式字符串）
            workload: 任务量（仅叶子节点有效）
            tags: 标签列表
            **kwargs: 其他字段
            
        Returns:
            创建成功的 Cell，失败返回 None
        """
        from datetime import datetime
        
        # 计算 level
        level = 0
        if parent_id:
            parent = self.db.get_cell(parent_id)
            if parent:
                level = parent.level + 1
        
        # 解析 deadline
        deadline_dt = None
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(deadline)
            except ValueError:
                pass
        
        # 创建 Cell 对象
        cell = Cell(
            title=title,
            description=description,
            level=level,
            priority=priority,
            parent_id=parent_id,
            deadline=deadline_dt,
            workload=workload,
            total_workload=workload,  # 初始时 total_workload = workload
            tags=tags or [],
            **kwargs
        )
        
        # 保存到数据库
        if self.db.create_cell(cell):
            # 如果有父节点，更新父节点的 children_ids 和 total_workload
            if parent_id:
                self._add_child_to_parent(parent_id, cell.id)
                self._update_parent_total_workload(parent_id)
            return cell
        return None
    
    def get_cell(self, cell_id: str) -> Optional[Cell]:
        """获取 Cell"""
        return self.db.get_cell(cell_id)
    
    def update_cell(self, cell_id: str, **kwargs) -> bool:
        """更新 Cell"""
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        for key, value in kwargs.items():
            if hasattr(cell, key):
                setattr(cell, key, value)
        
        return self.db.update_cell(cell)
    
    def delete_cell(self, cell_id: str) -> bool:
        """删除 Cell"""
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        if cell.parent_id:
            self._remove_child_from_parent(cell.parent_id, cell_id)
            self._update_parent_total_workload(cell.parent_id)
        
        return self.db.delete_cell(cell_id)
    
    def get_root_cells(self) -> List[Cell]:
        """获取所有根节点"""
        return self.db.list_cells(parent_id=None)
    
    def get_children(self, parent_id: str) -> List[Cell]:
        """获取子 Cell 列表"""
        return self.db.get_children(parent_id)
    
    # ==================== 父子关系管理 ====================
    
    def add_child(self, parent_id: str, child_id: str) -> bool:
        """添加子 Cell"""
        parent = self.db.get_cell(parent_id)
        child = self.db.get_cell(child_id)
        
        if not parent or not child:
            return False
        
        # 检查循环引用
        if self._is_ancestor(child_id, parent_id):
            print("错误：不能将祖先节点设为子节点")
            return False
        
        # 如果子节点已有父节点，先从原父节点移除
        if child.parent_id and child.parent_id != parent_id:
            self._remove_child_from_parent(child.parent_id, child_id)
            self._update_parent_total_workload(child.parent_id)
        
        # 更新子节点
        old_level = child.level
        child.parent_id = parent_id
        child.level = parent.level + 1
        self._update_children_level(child_id, child.level - old_level)
        
        # 更新父节点
        self._add_child_to_parent(parent_id, child_id)
        
        if not self.db.update_cell(child):
            return False
        
        self._update_parent_total_workload(parent_id)
        return True
    
    def remove_child(self, parent_id: str, child_id: str) -> bool:
        """移除子 Cell"""
        parent = self.db.get_cell(parent_id)
        child = self.db.get_cell(child_id)
        
        if not parent or not child:
            return False
        
        child.parent_id = None
        child.level = 0
        old_level = parent.level + 1
        self._update_children_level(child_id, 0 - old_level)
        
        self._remove_child_from_parent(parent_id, child_id)
        
        if not self.db.update_cell(child):
            return False
        
        self._update_parent_total_workload(parent_id)
        return True
    
    def move_cell(self, cell_id: str, new_parent_id: Optional[str]) -> bool:
        """移动 Cell"""
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        old_parent_id = cell.parent_id
        
        if new_parent_id == old_parent_id:
            return True
        
        if new_parent_id and self._is_ancestor(cell_id, new_parent_id):
            print("错误：不能将节点移动到其子孙节点下")
            return False
        
        if old_parent_id:
            self._remove_child_from_parent(old_parent_id, cell_id)
            self._update_parent_total_workload(old_parent_id)
        
        if new_parent_id:
            new_parent = self.db.get_cell(new_parent_id)
            if not new_parent:
                return False
            
            cell.parent_id = new_parent_id
            cell.level = new_parent.level + 1
            self._add_child_to_parent(new_parent_id, cell_id)
            self._update_parent_total_workload(new_parent_id)
        else:
            cell.parent_id = None
            cell.level = 0
        
        self._update_children_level(cell_id, 0)
        return self.db.update_cell(cell)
    
    def _add_child_to_parent(self, parent_id: str, child_id: str) -> bool:
        """内部方法：添加子节点到父节点"""
        parent = self.db.get_cell(parent_id)
        if not parent:
            return False
        parent.add_child(child_id)
        return self.db.update_cell(parent)
    
    def _remove_child_from_parent(self, parent_id: str, child_id: str) -> bool:
        """内部方法：从父节点移除子节点"""
        parent = self.db.get_cell(parent_id)
        if not parent:
            return False
        parent.remove_child(child_id)
        return self.db.update_cell(parent)
    
    def _update_children_level(self, cell_id: str, level_delta: int) -> None:
        """内部方法：递归更新子节点 level"""
        children = self.db.get_children(cell_id)
        for child in children:
            child.level += level_delta
            self.db.update_cell(child)
            self._update_children_level(child.id, level_delta)
    
    def _is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        """检查是否为祖先"""
        current = self.db.get_cell(descendant_id)
        while current and current.parent_id:
            if current.parent_id == ancestor_id:
                return True
            current = self.db.get_cell(current.parent_id)
        return False
    
    # ==================== 任务量管理 ====================
    
    def set_workload(self, cell_id: str, workload: float) -> bool:
        """设置任务量"""
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        children = self.db.get_children(cell_id)
        if children:
            print(f"警告：Cell '{cell.title}' 有子节点，workload 无效")
        
        cell.workload = workload
        if not children:
            cell.total_workload = workload
        
        if not self.db.update_cell(cell):
            return False
        
        if cell.parent_id:
            self._update_parent_total_workload(cell.parent_id)
        return True
    
    def _update_parent_total_workload(self, parent_id: str) -> None:
        """级联更新父节点 total_workload"""
        parent = self.db.get_cell(parent_id)
        if not parent:
            return
        
        children = self.db.get_children(parent_id)
        total = sum(child.total_workload for child in children)
        parent.total_workload = total
        self.db.update_cell(parent)
        
        if parent.parent_id:
            self._update_parent_total_workload(parent.parent_id)
    
    def get_total_workload(self, cell_id: str) -> float:
        """获取总任务量"""
        cell = self.db.get_cell(cell_id)
        return cell.total_workload if cell else 0.0
    
    # ==================== 时间统计管理 ====================
    
    def set_actual_hours(self, cell_id: str, hours: float) -> bool:
        """设置实际用时"""
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        children = self.db.get_children(cell_id)
        if children:
            print(f"警告：Cell '{cell.title}' 有子节点，actual_hours 无效")
        
        cell.actual_hours = hours
        if not children:
            cell.total_hours = hours
        
        if not self.db.update_cell(cell):
            return False
        
        if cell.parent_id:
            self._update_parent_total_hours(cell.parent_id)
        return True
    
    def _update_parent_total_hours(self, parent_id: str) -> None:
        """级联更新父节点 total_hours"""
        parent = self.db.get_cell(parent_id)
        if not parent:
            return
        
        children = self.db.get_children(parent_id)
        total = sum(child.actual_hours for child in children)
        parent.total_hours = total
        self.db.update_cell(parent)
        
        if parent.parent_id:
            self._update_parent_total_hours(parent.parent_id)
    
    def get_total_hours(self, cell_id: str) -> float:
        """获取总用时"""
        cell = self.db.get_cell(cell_id)
        return cell.total_hours if cell else 0.0
    
    # ==================== 进度计算 ====================
    
    def get_progress(self, cell_id: str) -> float:
        """获取任务进度百分比"""
        cell = self.db.get_cell(cell_id)
        if not cell:
            return 0.0
        
        children = self.db.get_children(cell_id)
        
        if not children:
            # 叶子节点
            return cell.get_progress()
        
        # 非叶子节点
        total_workload = 0.0
        completed_workload = 0.0
        
        for child in children:
            child_workload = child.total_workload
            total_workload += child_workload
            if child.status == CellStatus.DONE:
                completed_workload += child_workload
        
        if total_workload == 0:
            return 0.0
        
        return (completed_workload / total_workload) * 100.0
    
    def get_tree_progress(self, root_id: str) -> Dict[str, Any]:
        """获取树的进度统计"""
        root = self.db.get_cell(root_id)
        if not root:
            return {}
        
        descendants = self._get_all_descendants(root_id)
        total_cells = len(descendants) + 1
        completed_cells = sum(1 for c in descendants + [root] if c.status == CellStatus.DONE)
        
        return {
            'root_id': root_id,
            'root_title': root.title,
            'total_cells': total_cells,
            'completed_cells': completed_cells,
            'completion_rate': (completed_cells / total_cells * 100) if total_cells > 0 else 0,
            'total_workload': root.total_workload,
            'completed_workload': self._get_completed_workload(root_id),
            'overall_progress': self.get_progress(root_id)
        }
    
    def _get_completed_workload(self, cell_id: str) -> float:
        """获取已完成任务量"""
        completed = 0.0
        children = self.db.get_children(cell_id)
        
        for child in children:
            if child.status == CellStatus.DONE:
                completed += child.total_workload
            else:
                completed += self._get_completed_workload(child.id)
        
        return completed
    
    def _get_all_descendants(self, cell_id: str) -> List[Cell]:
        """获取所有后代"""
        descendants = []
        children = self.db.get_children(cell_id)
        
        for child in children:
            descendants.append(child)
            descendants.extend(self._get_all_descendants(child.id))
        
        return descendants
    
    # ==================== 树形结构操作 ====================
    
    def get_tree(self, root_id: str) -> Dict[str, Any]:
        """获取树形结构"""
        root = self.db.get_cell(root_id)
        if not root:
            return {}
        return self._build_tree_node(root)
    
    def _build_tree_node(self, cell: Cell) -> Dict[str, Any]:
        """构建树节点"""
        node = {
            'id': cell.id,
            'title': cell.title,
            'status': cell.status.value,
            'level': cell.level,
            'workload': cell.workload,
            'total_workload': cell.total_workload,
            'actual_hours': cell.actual_hours,
            'total_hours': cell.total_hours,
            'progress': self.get_progress(cell.id),
            'children': []
        }
        
        children = self.db.get_children(cell.id)
        for child in children:
            node['children'].append(self._build_tree_node(child))
        
        return node
    
    def get_ancestors(self, cell_id: str) -> List[Cell]:
        """获取祖先节点"""
        ancestors = []
        current = self.db.get_cell(cell_id)
        
        while current and current.parent_id:
            parent = self.db.get_cell(current.parent_id)
            if parent:
                ancestors.insert(0, parent)
                current = parent
            else:
                break
        
        return ancestors
