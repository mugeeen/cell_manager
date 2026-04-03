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
        
        # 检查是否为叶子节点
        children = self.db.get_children(cell_id)
        is_leaf = len(children) == 0
        
        # 记录是否需要更新父节点汇总
        workload_changed = 'workload' in kwargs
        actual_hours_changed = 'actual_hours' in kwargs
        
        for key, value in kwargs.items():
            if hasattr(cell, key):
                # 特殊处理 status 字段，将字符串转换为 CellStatus 枚举
                if key == 'status' and isinstance(value, str):
                    from .models import CellStatus
                    try:
                        value = CellStatus(value)
                    except ValueError:
                        # 如果转换失败，跳过此字段
                        continue
                setattr(cell, key, value)
        
        # 如果是叶子节点，更新 total_workload 和 total_hours
        if is_leaf:
            if workload_changed:
                cell.total_workload = cell.workload
            if actual_hours_changed:
                cell.total_hours = cell.actual_hours
        
        if not self.db.update_cell(cell):
            return False
        
        # 更新父节点汇总
        if cell.parent_id and (workload_changed or actual_hours_changed):
            if workload_changed:
                self._update_parent_total_workload(cell.parent_id)
            if actual_hours_changed:
                self._update_parent_total_hours(cell.parent_id)
        
        return True
    
    def delete_cell(self, cell_id: str) -> bool:
        """删除 Cell"""
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        if cell.parent_id:
            self._remove_child_from_parent(cell.parent_id, cell_id)
            self._update_parent_total_workload(cell.parent_id)
        
        return self.db.delete_cell(cell_id)
    
    def get_root_cells(self, include_archived: bool = False) -> List[Cell]:
        """获取所有根节点
        
        Args:
            include_archived: 是否包含已归档的任务，默认不包含
            
        Returns:
            根节点列表
        """
        cells = self.db.list_cells(parent_id=None)
        if not include_archived:
            cells = [cell for cell in cells if not self.is_archived(cell)]
        return cells
    
    def get_children(self, parent_id: str) -> List[Cell]:
        """获取子 Cell 列表"""
        return self.db.get_children(parent_id)
    
    def search_cells(self, keyword: str, include_archived: bool = False) -> List[Cell]:
        """搜索 Cell
        
        Args:
            keyword: 搜索关键词
            include_archived: 是否包含已归档的任务，默认不包含
            
        Returns:
            匹配的 Cell 列表
        """
        cells = self.db.search_cells(keyword)
        if not include_archived:
            cells = [cell for cell in cells if not self.is_archived(cell)]
        return cells
    
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
        
        # 计算 level 变化
        old_level = cell.level
        if new_parent_id:
            new_parent = self.db.get_cell(new_parent_id)
            if not new_parent:
                return False
            new_level = new_parent.level + 1
        else:
            new_level = 0
        
        level_delta = new_level - old_level
        
        if old_parent_id:
            self._remove_child_from_parent(old_parent_id, cell_id)
            self._update_parent_total_workload(old_parent_id)
            self._update_parent_total_hours(old_parent_id)
        
        if new_parent_id:
            cell.parent_id = new_parent_id
            cell.level = new_level
            # 先保存子节点的 parent_id 变更到数据库
            self.db.update_cell(cell)
            self._add_child_to_parent(new_parent_id, cell_id)
            self._update_parent_total_workload(new_parent_id)
            self._update_parent_total_hours(new_parent_id)
        else:
            cell.parent_id = None
            cell.level = 0
        
        # 更新所有子节点的 level
        if level_delta != 0:
            self._update_children_level(cell_id, level_delta)
        
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
        if not parent_id:
            return
            
        parent = self.db.get_cell(parent_id)
        if not parent:
            return
        
        children = self.db.get_children(parent_id)
        total = sum(child.total_workload for child in children if child)
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
        # 使用 total_hours 而不是 actual_hours，因为非叶子节点的 actual_hours 为 0
        total = sum(child.total_hours for child in children)
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
        """
        获取任务进度百分比
        
        算法：递归加权平均
        - 叶子节点：由状态决定（completed=100%，其他=0%）
        - 非叶子节点：Σ(子节点.total_workload × 子节点进度) / Σ(子节点.total_workload)
        """
        cell = self.db.get_cell(cell_id)
        if not cell:
            return 0.0
        
        children = self.db.get_children(cell_id)
        
        if not children:
            # 叶子节点：由状态决定进度
            return 100.0 if cell.status == CellStatus.COMPLETED else 0.0
        
        # 非叶子节点：递归计算子节点的加权平均进度
        total_weighted_progress = 0.0
        total_workload = 0.0
        
        for child in children:
            child_workload = child.total_workload
            if child_workload <= 0:
                continue
            
            # 递归获取子节点进度
            child_progress = self.get_progress(child.id)
            
            total_weighted_progress += child_workload * child_progress
            total_workload += child_workload
        
        if total_workload == 0:
            return 0.0
        
        return total_weighted_progress / total_workload
    
    def get_tree_progress(self, root_id: str) -> Dict[str, Any]:
        """获取树的进度统计"""
        root = self.db.get_cell(root_id)
        if not root:
            return {}
        
        descendants = self._get_all_descendants(root_id)
        total_cells = len(descendants) + 1
        completed_cells = sum(1 for c in descendants + [root] if c.status == CellStatus.COMPLETED)
        
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
        """
        获取已完成任务量（按进度比例计算）
        
        与 get_progress 保持一致：
        - 叶子节点：completed 状态算全部，其他算 0
        - 非叶子节点：递归计算子节点的已完成工作量
        """
        cell = self.db.get_cell(cell_id)
        if not cell:
            return 0.0
        
        children = self.db.get_children(cell_id)
        
        if not children:
            # 叶子节点：只有 completed 状态才算完成
            return cell.total_workload if cell.status == CellStatus.COMPLETED else 0.0
        
        # 非叶子节点：递归计算子节点的已完成工作量
        completed = 0.0
        for child in children:
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
    
    def archive_cell(self, cell_id: str) -> bool:
        """
        归档单个 Cell
        
        给 Cell 添加 #archived 标签
        
        Args:
            cell_id: Cell ID
            
        Returns:
            归档成功返回 True，失败返回 False
        """
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        # 添加 #archived 标签
        if '#archived' not in cell.tags:
            cell.tags.append('#archived')
            return self.db.update_cell(cell)
        return True
    
    def unarchive_cell(self, cell_id: str) -> bool:
        """
        取消归档单个 Cell
        
        移除 Cell 的 #archived 标签
        
        Args:
            cell_id: Cell ID
            
        Returns:
            取消归档成功返回 True，失败返回 False
        """
        cell = self.db.get_cell(cell_id)
        if not cell:
            return False
        
        # 移除 #archived 标签
        if '#archived' in cell.tags:
            cell.tags.remove('#archived')
            return self.db.update_cell(cell)
        return True
    
    def archive_completed_cells(self) -> int:
        """
        归档所有符合条件的已完成 Cell
        
        归档条件：
        - 状态为 completed
        - 是叶子节点（没有子节点）
        
        Returns:
            归档的 Cell 数量
        """
        cells = self.db.list_cells()
        archived_count = 0
        
        for cell in cells:
            # 检查是否已完成且是叶子节点
            if cell.status.value == 'completed':
                children = self.db.get_children(cell.id)
                if len(children) == 0:
                    # 添加 #archived 标签
                    if '#archived' not in cell.tags:
                        cell.tags.append('#archived')
                        if self.db.update_cell(cell):
                            archived_count += 1
        
        return archived_count
    
    def is_archived(self, cell: Cell) -> bool:
        """
        检查 Cell 是否已归档
        
        Args:
            cell: Cell 实例
            
        Returns:
            已归档返回 True，否则返回 False
        """
        return '#archived' in cell.tags
