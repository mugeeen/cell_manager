# -*- coding: utf-8 -*-
"""
Cell Manager WebUI 独立服务器
基于 FastAPI 提供任务管理 Web 界面
整合 v1.2.0 的所有功能
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# 尝试导入 AstrBot 日志，失败则使用标准日志
try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger("cell_manager_webui")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)


# 获取模板目录
CURRENT_DIR = Path(__file__).parent
TEMPLATE_DIR = CURRENT_DIR.parent / 'templates'


# Pydantic 请求模型
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
    new_parent_id: Optional[str] = None


class WebUIServer:
    """Cell Manager WebUI 独立服务器"""
    
    def __init__(self, manager, db, config: dict = None):
        """
        初始化 WebUI 服务器
        
        Args:
            manager: CellManager 实例
            db: DatabaseManager 实例
            config: 配置字典，包含 host, port 等
        """
        self.manager = manager
        self.db = db
        self.config = config or {}
        self.host = self.config.get('host', '0.0.0.0')
        self.port = self.config.get('port', 8082)
        
        # 创建 FastAPI 应用
        self._app = FastAPI(
            title="Cell Manager WebUI",
            description="任务管理系统 Web 界面",
            version="1.3.0"
        )
        
        # 设置中间件
        self._setup_middleware()
        
        # 设置路由
        self._setup_routes()
        
        logger.info(f"WebUIServer 初始化完成，将运行在 {self.host}:{self.port}")
    
    def _setup_middleware(self):
        """设置中间件"""
        # 允许跨域
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _get_template(self, filename: str) -> str:
        """读取模板文件"""
        try:
            template_path = TEMPLATE_DIR / filename
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取模板文件失败 {filename}: {e}")
            return f"<h1>错误</h1><p>无法加载模板: {filename}</p>"
    
    def _setup_routes(self):
        """设置路由"""
        
        # 页面路由
        @self._app.get("/", response_class=HTMLResponse)
        async def serve_react_flow():
            """React Flow 可视化页面（主页）"""
            return HTMLResponse(content=self._get_template('react_flow.html'))
        
        @self._app.get("/stats", response_class=HTMLResponse)
        async def serve_stats():
            """时间统计页面"""
            return HTMLResponse(content=self._get_template('stats.html'))
        
        @self._app.get("/visualizer", response_class=HTMLResponse)
        async def serve_visualizer():
            """旧版可视化页面"""
            return HTMLResponse(content=self._get_template('visualizer.html'))
        
        # API 路由 - 图形数据
        @self._app.get("/api/cells/graph")
        async def api_get_cells_graph(root_id: str = None, include_archived: bool = False):
            """获取 Cell 图形数据"""
            try:
                nodes = []
                edges = []
                
                def add_cell_to_graph(cell, parent_id=None, level=0):
                    is_archived = self.manager.is_archived(cell)
                    
                    if not include_archived and is_archived:
                        return
                    
                    status_colors = {
                        'todo': '#9e9e9e',
                        'in_progress': '#2196f3',
                        'urgent': '#f44336',
                        'completed': '#4caf50'
                    }
                    
                    children = self.db.get_children(cell.id)
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
                            "progress": self.manager.get_progress(cell.id),
                            "level": level,
                            "is_leaf": is_leaf,
                            "is_archived": is_archived,
                            "tags": cell.tags if hasattr(cell, 'tags') else []
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
                    
                    for child in children:
                        add_cell_to_graph(child, cell.id, level + 1)
                
                if root_id:
                    root_cell = self.db.get_cell(root_id)
                    if root_cell:
                        add_cell_to_graph(root_cell, None, 0)
                else:
                    root_cells = self.db.list_cells(parent_id=None)
                    for root_cell in root_cells:
                        add_cell_to_graph(root_cell, None, 0)
                
                return {"success": True, "data": {"nodes": nodes, "edges": edges}}
            except Exception as e:
                logger.error(f"获取图形数据失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 根节点列表
        @self._app.get("/api/cells/roots")
        async def api_get_root_cells():
            """获取根节点列表"""
            try:
                root_cells = self.db.list_cells(parent_id=None)
                return {
                    "success": True,
                    "data": [
                        {
                            "id": cell.id,
                            "title": cell.title,
                            "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                            "progress": cell.get_progress() if hasattr(cell, 'get_progress') else cell.progress
                        }
                        for cell in root_cells
                    ]
                }
            except Exception as e:
                logger.error(f"获取根节点失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 任务详情
        @self._app.get("/api/cells/{cell_id}")
        async def api_get_cell_detail(cell_id: str):
            """获取任务详情"""
            try:
                cell = self.db.get_cell(cell_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                children = self.db.get_children(cell_id)
                
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
                        "progress": cell.get_progress() if hasattr(cell, 'get_progress') else cell.progress,
                        "parent_id": cell.parent_id,
                        "children_count": len(children),
                        "is_leaf": len(children) == 0
                    }
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"获取任务详情失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 创建任务
        @self._app.post("/api/cells")
        async def api_create_cell(request: CellCreateRequest):
            """创建任务"""
            try:
                if not request.title:
                    raise HTTPException(status_code=400, detail="标题不能为空")
                
                cell = self.manager.create_cell(
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
                            "progress": cell.get_progress() if hasattr(cell, 'get_progress') else cell.progress,
                            "workload": cell.workload,
                            "actual_hours": cell.actual_hours,
                            "parent_id": cell.parent_id
                        }
                    }
                else:
                    raise HTTPException(status_code=500, detail="创建失败")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"创建任务失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 更新任务
        @self._app.put("/api/cells/{cell_id}")
        async def api_update_cell(cell_id: str, request: CellUpdateRequest):
            """更新任务"""
            try:
                cell = self.db.get_cell(cell_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                # 构建更新参数
                update_kwargs = {}
                if request.title is not None:
                    update_kwargs['title'] = request.title
                if request.description is not None:
                    update_kwargs['description'] = request.description
                if request.status is not None:
                    update_kwargs['status'] = request.status
                    # 如果状态变为 completed，记录完成时间
                    if request.status == 'completed':
                        cell_status = cell.status.value if hasattr(cell.status, 'value') else str(cell.status)
                        if cell_status != 'completed':
                            update_kwargs['completed_at'] = datetime.now()
                if request.workload is not None:
                    update_kwargs['workload'] = request.workload
                if request.actual_hours is not None:
                    update_kwargs['actual_hours'] = request.actual_hours
                
                if self.manager.update_cell(cell_id, **update_kwargs):
                    updated_cell = self.db.get_cell(cell_id)
                    return {
                        "success": True,
                        "data": {
                            "id": updated_cell.id,
                            "title": updated_cell.title,
                            "description": updated_cell.description,
                            "status": updated_cell.status.value if hasattr(updated_cell.status, 'value') else str(updated_cell.status),
                            "progress": updated_cell.get_progress() if hasattr(updated_cell, 'get_progress') else updated_cell.progress,
                            "workload": updated_cell.workload,
                            "actual_hours": updated_cell.actual_hours,
                            "total_workload": updated_cell.total_workload,
                            "total_hours": updated_cell.total_hours
                        }
                    }
                else:
                    raise HTTPException(status_code=500, detail="更新失败")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"更新任务失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 删除任务
        @self._app.delete("/api/cells/{cell_id}")
        async def api_delete_cell(cell_id: str):
            """删除任务"""
            try:
                cell = self.db.get_cell(cell_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                # 检查是否有子节点，级联删除
                children = self.db.get_children(cell_id)
                if children:
                    for child in children:
                        self.manager.delete_cell(child.id)
                
                if self.manager.delete_cell(cell_id):
                    return {"success": True, "message": "删除成功"}
                else:
                    raise HTTPException(status_code=500, detail="删除失败")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"删除任务失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 移动任务
        @self._app.post("/api/cells/{cell_id}/move")
        async def api_move_cell(cell_id: str, request: CellMoveRequest):
            """移动任务"""
            try:
                cell = self.db.get_cell(cell_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                if self.manager.move_cell(cell_id, request.new_parent_id):
                    moved_cell = self.db.get_cell(cell_id)
                    return {
                        "success": True,
                        "data": {
                            "id": moved_cell.id,
                            "title": moved_cell.title,
                            "status": moved_cell.status.value if hasattr(moved_cell.status, 'value') else str(moved_cell.status),
                            "progress": moved_cell.get_progress() if hasattr(moved_cell, 'get_progress') else moved_cell.progress,
                            "workload": moved_cell.workload,
                            "actual_hours": moved_cell.actual_hours,
                            "parent_id": moved_cell.parent_id,
                            "level": moved_cell.level
                        }
                    }
                else:
                    raise HTTPException(status_code=400, detail="移动失败，可能是循环依赖")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"移动任务失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 归档任务
        @self._app.post("/api/cells/{cell_id}/archive")
        async def api_archive_cell(cell_id: str):
            """归档任务"""
            try:
                if self.manager.archive_cell(cell_id):
                    return {"success": True, "message": "归档成功"}
                else:
                    raise HTTPException(status_code=500, detail="归档失败")
            except Exception as e:
                logger.error(f"归档任务失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 取消归档任务
        @self._app.post("/api/cells/{cell_id}/unarchive")
        async def api_unarchive_cell(cell_id: str):
            """取消归档任务"""
            try:
                if self.manager.unarchive_cell(cell_id):
                    return {"success": True, "message": "取消归档成功"}
                else:
                    raise HTTPException(status_code=500, detail="取消归档失败")
            except Exception as e:
                logger.error(f"取消归档任务失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 归档所有已完成任务
        @self._app.post("/api/cells/archive-completed")
        async def api_archive_completed_cells():
            """归档所有已完成任务"""
            try:
                count = self.manager.archive_completed_cells()
                return {"success": True, "archived_count": count}
            except Exception as e:
                logger.error(f"归档已完成任务失败: {e}")
                return {"success": False, "message": str(e)}
        
        # API 路由 - 统计
        @self._app.get("/api/stats/completed-dates")
        async def api_get_completed_dates():
            """获取完成日期列表"""
            try:
                dates = self.db.get_completed_dates()
                return {"success": True, "dates": dates}
            except Exception as e:
                logger.error(f"获取完成日期失败: {e}")
                return {"success": False, "message": str(e)}
        
        @self._app.get("/api/stats/completed-by-date")
        async def api_get_completed_by_date(date: str):
            """获取指定日期完成的任务"""
            try:
                cells = self.db.get_completed_leaf_cells_by_date(date)
                
                # 获取每个 cell 的根任务信息
                result = []
                for cell in cells:
                    root_id = cell.id
                    current = cell
                    while current.parent_id:
                        parent = self.db.get_cell(current.parent_id)
                        if parent:
                            root_id = parent.id
                            current = parent
                        else:
                            break
                    
                    root_cell = self.db.get_cell(root_id)
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
                logger.error(f"获取指定日期完成任务失败: {e}")
                return {"success": False, "message": str(e)}
    
    async def start(self):
        """启动服务器"""
        try:
            logger.info(f"🚀 启动 WebUI 服务器: {self.host}:{self.port}")
            config = uvicorn.Config(
                self._app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
            self._server = uvicorn.Server(config)
            await self._server.serve()
        except Exception as e:
            logger.error(f"启动 WebUI 服务器失败: {e}")
            raise
    
    async def stop(self):
        """停止服务器"""
        try:
            if hasattr(self, '_server'):
                self._server.should_exit = True
                logger.info("WebUI 服务器已停止")
        except Exception as e:
            logger.error(f"停止 WebUI 服务器失败: {e}")
