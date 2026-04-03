# -*- coding: utf-8 -*-
"""
Cell Manager Web 路由
提供可视化所需的 API 接口
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel


class CellUpdateRequest(BaseModel):
    """Cell 更新请求模型"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    workload: Optional[float] = None
    actual_hours: Optional[float] = None


class CellCreateRequest(BaseModel):
    """Cell 创建请求模型"""
    title: str
    description: Optional[str] = ""
    parent_id: Optional[str] = None
    workload: Optional[float] = 0.0


class CellMoveRequest(BaseModel):
    """Cell 移动请求模型"""
    new_parent_id: Optional[str] = None  # None 表示移动到根节点

# 获取当前目录路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(CURRENT_DIR), 'templates')
STATIC_DIR = os.path.join(CURRENT_DIR, 'static')


class RouteHandler:
    """路由处理器"""
    
    def __init__(self, db, manager):
        self.db = db
        self.manager = manager


# 全局处理器实例
_route_handler: Optional[RouteHandler] = None


def setup_routes(app, manager, db):
    """
    设置路由
    
    Args:
        app: FastAPI 应用实例
        manager: CellManager 实例
        db: DatabaseManager 实例
    """
    global _route_handler
    _route_handler = RouteHandler(db, manager)
    
    router = APIRouter(prefix="/cell_manager")
    
    @router.get("/visualizer", response_class=HTMLResponse)
    async def visualizer_page(request: Request):
        """可视化页面"""
        return HTMLResponse(content=open(os.path.join(TEMPLATE_DIR, 'visualizer.html'), 'r', encoding='utf-8').read())
    
    @router.get("/react-flow", response_class=HTMLResponse)
    async def react_flow_page(request: Request):
        """React Flow 可视化页面"""
        return HTMLResponse(content=open(os.path.join(TEMPLATE_DIR, 'react_flow.html'), 'r', encoding='utf-8').read())
    
    @router.get("/stats", response_class=HTMLResponse)
    async def stats_page(request: Request):
        """时间统计页面（macOS 风格）"""
        return HTMLResponse(content=open(os.path.join(TEMPLATE_DIR, 'stats.html'), 'r', encoding='utf-8').read())
    
    @router.get("/api/cells/graph")
    async def get_cells_graph(root_id: str = None, include_archived: bool = False) -> Dict[str, Any]:
        """
        获取 Cell 图形数据（用于可视化）
        
        Args:
            root_id: 根节点 ID，如果提供则只返回该节点及其子树
            include_archived: 是否包含已归档的 Cell，默认 False
            
        Returns:
            包含 nodes 和 edges 的图形数据
        """
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            nodes = []
            edges = []
            
            def add_cell_to_graph(cell, parent_id=None, level=0):
                """递归添加 Cell 到图形"""
                # 检查是否已归档
                is_archived = handler.manager.is_archived(cell)
                
                # 如果不包含归档任务且当前任务已归档，则跳过
                if not include_archived and is_archived:
                    return
                
                # 确定节点颜色
                # 简化状态颜色：待办(灰) -> 进行中(蓝) -> 紧急(红) -> 已完成(绿)
                status_colors = {
                    'todo': '#9e9e9e',
                    'in_progress': '#2196f3',
                    'urgent': '#f44336',
                    'completed': '#4caf50'
                }
                
                children = handler.db.get_children(cell.id)
                is_leaf = len(children) == 0
                
                node = {
                    "data": {
                        "id": cell.id,
                        "label": cell.title,
                        "title": cell.title,
                        "description": cell.description,
                        "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                        "color": status_colors.get(cell.status.value if hasattr(cell.status, 'value') else str(cell.status), '#9e9e9e'),
                        "workload": cell.workload,
                        "actual_hours": cell.actual_hours,
                        "total_workload": cell.total_workload,
                        "total_hours": cell.total_hours,
                        "progress": handler.manager.get_progress(cell.id),
                        "level": level,
                        "is_leaf": is_leaf,
                        "is_archived": is_archived,
                        "tags": cell.tags
                    },
                    "position": {
                        "x": 100 + level * 250,
                        "y": 100 + len(nodes) * 80
                    }
                }
                nodes.append(node)
                
                if parent_id:
                    edges.append({
                        "data": {
                            "id": f"edge_{parent_id}_{cell.id}",
                            "source": parent_id,
                            "target": cell.id
                        }
                    })
                
                # 递归添加子节点
                for child in children:
                    add_cell_to_graph(child, cell.id, level + 1)
            
            if root_id:
                # 只获取指定根节点及其子树
                root_cell = handler.db.get_cell(root_id)
                if root_cell:
                    add_cell_to_graph(root_cell, None, 0)
            else:
                # 获取所有根节点及其子树
                root_cells = handler.db.list_cells(parent_id=None)
                for root_cell in root_cells:
                    add_cell_to_graph(root_cell, None, 0)
            
            return {
                "success": True,
                "data": {
                    "nodes": nodes,
                    "edges": edges
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/cells/roots")
    async def get_root_cells() -> Dict[str, Any]:
        """获取所有根节点列表（用于下拉选择）"""
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            root_cells = handler.db.list_cells(parent_id=None)
            return {
                "success": True,
                "data": [
                    {
                        "id": cell.id,
                        "title": cell.title,
                        "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                        "progress": cell.get_progress()
                    }
                    for cell in root_cells
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/cells/{cell_id}")
    async def get_cell_detail(cell_id: str) -> Dict[str, Any]:
        """获取单个 Cell 详情"""
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            cell = handler.db.get_cell(cell_id)
            if not cell:
                raise HTTPException(status_code=404, detail="Cell not found")
            
            children = handler.db.get_children(cell_id)
            
            return {
                "success": True,
                "data": {
                    "id": cell.id,
                    "title": cell.title,
                    "description": cell.description,
                    "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                    "workload": cell.workload,
                    "actual_hours": cell.actual_hours,
                    "total_workload": cell.total_workload,
                    "total_hours": cell.total_hours,
                    "progress": cell.get_progress(),
                    "parent_id": cell.parent_id,
                    "children_count": len(children),
                    "is_leaf": len(children) == 0
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/api/cells/{cell_id}")
    async def update_cell(cell_id: str, request: CellUpdateRequest) -> Dict[str, Any]:
        """
        更新 Cell
        
        Args:
            cell_id: Cell ID
            request: 更新请求
            
        Returns:
            更新后的 Cell 数据
        """
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            cell = handler.db.get_cell(cell_id)
            if not cell:
                raise HTTPException(status_code=404, detail="Cell not found")
            
            # 构建更新参数
            update_kwargs = {}
            if request.title is not None:
                update_kwargs['title'] = request.title
            if request.description is not None:
                update_kwargs['description'] = request.description
            if request.status is not None:
                update_kwargs['status'] = request.status
                # 如果状态变为 completed，记录完成时间
                if request.status == 'completed' and cell.status.value != 'completed':
                    update_kwargs['completed_at'] = datetime.now()
            if request.workload is not None:
                update_kwargs['workload'] = request.workload
            if request.actual_hours is not None:
                update_kwargs['actual_hours'] = request.actual_hours
            
            if handler.manager.update_cell(cell_id, **update_kwargs):
                updated_cell = handler.db.get_cell(cell_id)
                return {
                    "success": True,
                    "data": {
                        "id": updated_cell.id,
                        "title": updated_cell.title,
                        "description": updated_cell.description,
                        "status": updated_cell.status.value if hasattr(updated_cell.status, 'value') else str(updated_cell.status),
                        "progress": updated_cell.get_progress(),
                        "workload": updated_cell.workload,
                        "actual_hours": updated_cell.actual_hours,
                        "total_workload": updated_cell.total_workload,
                        "total_hours": updated_cell.total_hours
                    }
                }
            else:
                raise HTTPException(status_code=500, detail="Update failed")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/api/cells")
    async def create_cell(request: CellCreateRequest) -> Dict[str, Any]:
        """
        创建新 Cell
        
        Args:
            request: 创建请求
            
        Returns:
            创建的 Cell 数据
        """
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            cell = handler.manager.create_cell(
                title=request.title,
                description=request.description or "",
                parent_id=request.parent_id,
                workload=request.workload or 0.0
            )
            
            if cell:
                return {
                    "success": True,
                    "data": {
                        "id": cell.id,
                        "title": cell.title,
                        "description": cell.description,
                        "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                        "progress": cell.get_progress(),
                        "workload": cell.workload,
                        "actual_hours": cell.actual_hours,
                        "parent_id": cell.parent_id
                    }
                }
            else:
                raise HTTPException(status_code=500, detail="Create failed")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/api/cells/{cell_id}/move")
    async def move_cell(cell_id: str, request: CellMoveRequest) -> Dict[str, Any]:
        """
        移动 Cell（改变父子关系）
        
        Args:
            cell_id: 要移动的 Cell ID
            request: 移动请求，包含 new_parent_id（None 表示移动到根节点）
            
        Returns:
            移动后的 Cell 数据
        """
        try:
            # 使用全局处理器
            handler = _route_handler
            print(f"DEBUG: move_cell called, handler={handler}, cell_id={cell_id}, new_parent_id={request.new_parent_id}")
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            cell = handler.db.get_cell(cell_id)
            if not cell:
                raise HTTPException(status_code=404, detail="Cell not found")
            
            # 执行移动（循环引用检查在 move_cell 内部处理）
            if handler.manager.move_cell(cell_id, request.new_parent_id):
                # 重新获取更新后的 cell
                moved_cell = handler.db.get_cell(cell_id)
                return {
                    "success": True,
                    "data": {
                        "id": moved_cell.id,
                        "title": moved_cell.title,
                        "status": moved_cell.status.value if hasattr(moved_cell.status, 'value') else str(moved_cell.status),
                        "progress": moved_cell.get_progress(),
                        "workload": moved_cell.workload,
                        "actual_hours": moved_cell.actual_hours,
                        "parent_id": moved_cell.parent_id,
                        "level": moved_cell.level
                    }
                }
            else:
                raise HTTPException(status_code=500, detail="Move failed")
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(f"Move cell error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/api/cells/{cell_id}")
    async def delete_cell(cell_id: str) -> Dict[str, Any]:
        """
        删除 Cell
        
        Args:
            cell_id: 要删除的 Cell ID
            
        Returns:
            删除结果
        """
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            cell = handler.db.get_cell(cell_id)
            if not cell:
                raise HTTPException(status_code=404, detail="Cell not found")
            
            # 检查是否有子节点
            children = handler.db.get_children(cell_id)
            if children:
                # 级联删除：先删除所有子节点
                for child in children:
                    handler.manager.delete_cell(child.id)
            
            # 删除节点
            if handler.manager.delete_cell(cell_id):
                return {
                    "success": True,
                    "message": "Cell deleted successfully"
                }
            else:
                raise HTTPException(status_code=500, detail="Delete failed")
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(f"Delete cell error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/stats/completed-dates")
    async def get_completed_dates() -> Dict[str, Any]:
        """获取所有有完成记录的日期列表"""
        try:
            handler = _route_handler
            dates = handler.db.get_completed_dates()
            return {
                "success": True,
                "dates": dates
            }
        except Exception as e:
            import traceback
            print(f"Get completed dates error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/stats/completed-by-date")
    async def get_completed_by_date(date: str) -> Dict[str, Any]:
        """
        获取指定日期完成的叶子节点
        
        Args:
            date: 日期字符串，格式为 'YYYY-MM-DD'
        """
        try:
            handler = _route_handler
            cells = handler.db.get_completed_leaf_cells_by_date(date)
            
            # 获取每个 cell 的根任务信息
            result = []
            for cell in cells:
                # 查找根任务
                root_id = cell.id
                current = cell
                while current.parent_id:
                    parent = handler.db.get_cell(current.parent_id)
                    if parent:
                        root_id = parent.id
                        current = parent
                    else:
                        break
                
                root_cell = handler.db.get_cell(root_id)
                root_title = root_cell.title if root_cell else "未知任务"
                
                result.append({
                    "id": cell.id,
                    "title": cell.title,
                    "actual_hours": cell.actual_hours,
                    "completed_at": cell.completed_at.isoformat() if cell.completed_at else None,
                    "root_id": root_id,
                    "root_title": root_title
                })
            
            # 按根任务分组统计
            root_stats = {}
            for item in result:
                root_id = item["root_id"]
                if root_id not in root_stats:
                    root_stats[root_id] = {
                        "root_title": item["root_title"],
                        "total_hours": 0,
                        "count": 0,
                        "cells": []
                    }
                root_stats[root_id]["total_hours"] += item["actual_hours"]
                root_stats[root_id]["count"] += 1
                root_stats[root_id]["cells"].append(item)
            
            return {
                "success": True,
                "date": date,
                "cells": result,
                "root_stats": root_stats,
                "total_hours": sum(item["actual_hours"] for item in result),
                "total_count": len(result)
            }
        except Exception as e:
            import traceback
            print(f"Get completed by date error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/api/cells/archive-completed")
    async def archive_completed_cells() -> Dict[str, Any]:
        """
        归档所有符合条件的已完成 Cell
        
        归档条件：
        - 状态为 completed
        - 是叶子节点（没有子节点）
        
        Returns:
            归档的 Cell 数量
        """
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            count = handler.manager.archive_completed_cells()
            return {
                "success": True,
                "archived_count": count
            }
        except Exception as e:
            import traceback
            print(f"Archive completed cells error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/api/cells/{cell_id}/archive")
    async def archive_cell(cell_id: str) -> Dict[str, Any]:
        """
        归档单个 Cell
        
        Args:
            cell_id: Cell ID
            
        Returns:
            归档结果
        """
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            if handler.manager.archive_cell(cell_id):
                return {
                    "success": True,
                    "message": "Cell archived successfully"
                }
            else:
                raise HTTPException(status_code=500, detail="Archive failed")
        except Exception as e:
            import traceback
            print(f"Archive cell error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/api/cells/{cell_id}/unarchive")
    async def unarchive_cell(cell_id: str) -> Dict[str, Any]:
        """
        取消归档单个 Cell
        
        Args:
            cell_id: Cell ID
            
        Returns:
            取消归档结果
        """
        try:
            handler = _route_handler
            if not handler:
                raise HTTPException(status_code=500, detail="Route handler not initialized")
            
            if handler.manager.unarchive_cell(cell_id):
                return {
                    "success": True,
                    "message": "Cell unarchived successfully"
                }
            else:
                raise HTTPException(status_code=500, detail="Unarchive failed")
        except Exception as e:
            import traceback
            print(f"Unarchive cell error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    # 注册路由到应用
    app.include_router(router)
