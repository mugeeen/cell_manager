# -*- coding: utf-8 -*-
"""
Cell 树形可视化模块
提供漂亮的 ASCII 艺术风格树形结构展示
"""

from typing import Dict, Any, Optional, List
from enum import Enum


class ViewMode(Enum):
    """视图模式"""
    COMPACT = "compact"      # 紧凑模式
    DETAILED = "detailed"    # 详细模式
    MINIMAL = "minimal"      # 极简模式


class TreeVisualizer:
    """树形结构可视化器"""
    
    # 状态图标映射（使用 ASCII 字符兼容 Windows）
    STATUS_ICONS = {
        'todo': '[ ]',      # 待办
        'doing': '[>]',     # 进行中
        'paused': '[||]',   # 暂停
        'done': '[X]',      # 已完成
        'cancelled': '[-]', # 已取消
    }
    
    # 树形连接符（使用 ASCII 字符）
    TREE_CHARS = {
        'branch': '|-- ',
        'last_branch': '`-- ',
        'vertical': '|   ',
        'space': '    ',
    }
    
    def __init__(self, mode: ViewMode = ViewMode.DETAILED):
        """
        初始化可视化器
        
        Args:
            mode: 视图模式，默认为详细模式
        """
        self.mode = mode
    
    def visualize(self, tree: Dict[str, Any], title: Optional[str] = None) -> str:
        """
        可视化树形结构
        
        Args:
            tree: 树形结构数据
            title: 可选的标题
            
        Returns:
            格式化的树形字符串
        """
        lines = []
        
        # 添加标题
        if title:
            lines.append(self._format_title(title))
        
        # 添加树形内容
        if tree:
            lines.extend(self._build_tree_lines(tree, '', True))
        else:
            lines.append('(空)')
        
        return '\n'.join(lines)
    
    def _format_title(self, title: str) -> str:
        """格式化标题"""
        separator = '=' * 50
        return f"\n{separator}\n  {title}\n{separator}\n"
    
    def _build_tree_lines(
        self, 
        node: Dict[str, Any], 
        prefix: str, 
        is_last: bool
    ) -> List[str]:
        """
        递归构建树形行
        
        Args:
            node: 当前节点
            prefix: 前缀字符串
            is_last: 是否是最后一个子节点
            
        Returns:
            行列表
        """
        lines = []
        
        # 构建当前行
        current_line = self._format_node(node, prefix, is_last)
        lines.append(current_line)
        
        # 处理子节点
        children = node.get('children', [])
        if children:
            # 确定新的前缀
            new_prefix = prefix + (self.TREE_CHARS['space'] if is_last else self.TREE_CHARS['vertical'])
            
            for i, child in enumerate(children):
                is_last_child = (i == len(children) - 1)
                lines.extend(self._build_tree_lines(child, new_prefix, is_last_child))
        
        return lines
    
    def _format_node(self, node: Dict[str, Any], prefix: str, is_last: bool) -> str:
        """
        格式化单个节点
        
        Args:
            node: 节点数据
            prefix: 前缀
            is_last: 是否是最后一个子节点
            
        Returns:
            格式化后的节点字符串
        """
        # 选择分支符号
        branch = self.TREE_CHARS['last_branch'] if is_last else self.TREE_CHARS['branch']
        
        # 获取节点信息
        title = node.get('title', 'Untitled')
        status = node.get('status', 'todo')
        progress = node.get('progress', 0.0)
        workload = node.get('workload', 0.0)
        total_workload = node.get('total_workload', 0.0)
        actual_hours = node.get('actual_hours', 0.0)
        total_hours = node.get('total_hours', 0.0)
        
        # 状态图标
        icon = self.STATUS_ICONS.get(status, '○')
        
        # 根据模式格式化
        if self.mode == ViewMode.MINIMAL:
            # 极简模式：只显示标题和进度
            progress_bar = self._create_progress_bar(progress, 15)
            return f"{prefix}{branch}{icon} {title} {progress_bar}"
        
        elif self.mode == ViewMode.COMPACT:
            # 紧凑模式：显示标题、进度和工作量
            progress_bar = self._create_progress_bar(progress, 10)
            workload_info = f"[{total_workload:.1f}]" if total_workload > 0 else ""
            return f"{prefix}{branch}{icon} {title} {progress_bar} {workload_info}"
        
        else:  # DETAILED
            # 详细模式：显示完整信息
            progress_bar = self._create_progress_bar(progress, 12)
            
            # 构建详细信息
            details = []
            if total_workload > 0:
                details.append(f"工作量:{total_workload:.1f}")
            if total_hours > 0:
                details.append(f"耗时:{total_hours:.1f}h")
            if actual_hours > 0 and actual_hours != total_hours:
                details.append(f"实际:{actual_hours:.1f}h")
            
            detail_str = f" ({', '.join(details)})" if details else ""
            
            return f"{prefix}{branch}{icon} {title} {progress_bar}{detail_str}"
    
    def _create_progress_bar(self, progress: float, width: int = 20) -> str:
        """
        创建进度条
        
        Args:
            progress: 进度值 (0-100 百分比)
            width: 进度条宽度
            
        Returns:
            进度条字符串
        """
        # progress 是百分比 (0-100)，转换为比例
        ratio = progress / 100.0
        filled = int(ratio * width)
        empty = width - filled
        
        # 使用 ASCII 字符表示进度（兼容 Windows）
        bar = '#' * filled + '-' * empty
        percentage = int(progress)
        
        return f"[{bar}] {percentage}%"
    
    def visualize_list(
        self, 
        trees: List[Dict[str, Any]], 
        title: Optional[str] = None
    ) -> str:
        """
        可视化多个树
        
        Args:
            trees: 树列表
            title: 可选标题
            
        Returns:
            格式化的字符串
        """
        lines = []
        
        if title:
            lines.append(self._format_title(title))
        
        for i, tree in enumerate(trees):
            if i > 0:
                lines.append('')  # 树之间添加空行
            lines.append(self.visualize(tree))
        
        return '\n'.join(lines)
    
    def visualize_summary(self, tree: Dict[str, Any]) -> str:
        """
        显示树形摘要统计
        
        Args:
            tree: 树形结构
            
        Returns:
            摘要字符串
        """
        stats = self._calculate_stats(tree)
        
        lines = [
            '',
            '=' * 40,
            '  统计摘要',
            '=' * 40,
            f"  总节点数: {stats['total_nodes']}",
            f"  已完成: {stats['completed_nodes']} ({stats['completion_rate']:.1f}%)",
            f"  进行中: {stats['in_progress_nodes']}",
            f"  待办: {stats['todo_nodes']}",
            f"  总工作量: {stats['total_workload']:.1f}",
            f"  已完成工作量: {stats['completed_workload']:.1f}",
            f"  总耗时: {stats['total_hours']:.1f}h",
            f"  整体进度: {stats['overall_progress']:.1f}%",
            '=' * 40,
        ]
        
        return '\n'.join(lines)
    
    def _calculate_stats(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归计算统计信息
        
        Args:
            node: 节点
            
        Returns:
            统计字典
        """
        stats = {
            'total_nodes': 1,
            'completed_nodes': 1 if node.get('status') == 'done' else 0,
            'in_progress_nodes': 1 if node.get('status') == 'doing' else 0,
            'todo_nodes': 1 if node.get('status') == 'todo' else 0,
            'total_workload': node.get('total_workload', 0),
            'completed_workload': node.get('total_workload', 0) if node.get('status') == 'done' else 0,
            'total_hours': node.get('total_hours', 0),
        }
        
        # 递归统计子节点
        for child in node.get('children', []):
            child_stats = self._calculate_stats(child)
            stats['total_nodes'] += child_stats['total_nodes']
            stats['completed_nodes'] += child_stats['completed_nodes']
            stats['in_progress_nodes'] += child_stats['in_progress_nodes']
            stats['todo_nodes'] += child_stats['todo_nodes']
            stats['completed_workload'] += child_stats['completed_workload']
        
        # 计算完成率和整体进度
        if stats['total_nodes'] > 0:
            stats['completion_rate'] = (stats['completed_nodes'] / stats['total_nodes']) * 100
        else:
            stats['completion_rate'] = 0
        
        if stats['total_workload'] > 0:
            stats['overall_progress'] = (stats['completed_workload'] / stats['total_workload']) * 100
        else:
            stats['overall_progress'] = 0
        
        return stats


# 便捷函数
def visualize_tree(
    tree: Dict[str, Any], 
    mode: ViewMode = ViewMode.DETAILED,
    title: Optional[str] = None,
    show_summary: bool = False
) -> str:
    """
    便捷函数：可视化树形结构
    
    Args:
        tree: 树形结构
        mode: 视图模式
        title: 标题
        show_summary: 是否显示摘要
        
    Returns:
        格式化的树形字符串
    """
    visualizer = TreeVisualizer(mode)
    result = visualizer.visualize(tree, title)
    
    if show_summary:
        result += visualizer.visualize_summary(tree)
    
    return result
