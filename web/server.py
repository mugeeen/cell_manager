# -*- coding: utf-8 -*-
"""
Cell Manager WebUI 独立服务器
基于 FastAPI 提供任务管理 Web 界面
"""

import asyncio
from typing import Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from astrbot.api import logger


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
        
        self.host = self.config.get("host", "0.0.0.0")
        self.port = int(self.config.get("port", 8082))
        
        self._app = FastAPI(title="Cell Manager WebUI", version="1.3.0")
        self._setup_routes()
        self._setup_middleware()
        
        self._server: Optional[uvicorn.Server] = None
        self._server_task: Optional[asyncio.Task] = None
        
        # 获取模板目录
        from .handler import TEMPLATE_DIR
        self.template_dir = TEMPLATE_DIR
    
    def _setup_middleware(self):
        """设置中间件"""
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _get_template(self, filename: str) -> str:
        """读取模板文件"""
        filepath = Path(self.template_dir) / filename
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"<h1>Error loading template: {e}</h1>"
    
    def _setup_routes(self):
        """设置路由"""
        
        @self._app.get("/", response_class=HTMLResponse)
        async def index():
            """首页 - React Flow 可视化"""
            return self._get_template('react_flow.html')
        
        @self._app.get("/stats", response_class=HTMLResponse)
        async def stats():
            """统计页面"""
            return self._get_template('stats.html')
        
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
                            "progress": cell.progress,
                            "is_leaf": is_leaf,
                            "is_archived": is_archived,
                            "level": level
                        }
                    }
                    nodes.append(node)
                    
                    if parent_id:
                        edges.append({
                            "data": {
                                "source": parent_id,
                                "target": cell.id
                            }
                        })
                    
                    for child in children:
                        add_cell_to_graph(child, cell.id, level + 1)
                
                if root_id:
                    root = self.manager.get_cell(root_id)
                    if root:
                        add_cell_to_graph(root)
                else:
                    roots = self.manager.get_root_cells()
                    for root in roots:
                        add_cell_to_graph(root)
                
                return {"nodes": nodes, "edges": edges}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/api/cells/roots")
        async def api_get_root_cells():
            """获取根节点列表"""
            try:
                roots = self.manager.get_root_cells()
                return [
                    {
                        "id": cell.id,
                        "title": cell.title,
                        "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                        "progress": cell.progress,
                        "workload": cell.workload
                    }
                    for cell in roots
                ]
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/api/cells/{cell_id}")
        async def api_get_cell_detail(cell_id: str):
            """获取任务详情"""
            try:
                cell = self.manager.get_cell(cell_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                children = self.manager.get_child_cells(cell_id)
                
                return {
                    "id": cell.id,
                    "title": cell.title,
                    "description": cell.description,
                    "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                    "progress": cell.progress,
                    "workload": cell.workload,
                    "actual_hours": cell.actual_hours,
                    "created_at": cell.created_at.isoformat() if cell.created_at else None,
                    "updated_at": cell.updated_at.isoformat() if cell.updated_at else None,
                    "completed_at": cell.completed_at.isoformat() if cell.completed_at else None,
                    "parent_id": cell.parent_id,
                    "children_count": len(children),
                    "is_archived": self.manager.is_archived(cell)
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/api/cells")
        async def api_create_cell(request: Request):
            """创建任务"""
            try:
                data = await request.json()
                title = data.get("title")
                effort = data.get("effort", 1)
                parent_id = data.get("parent_id")
                
                if not title:
                    raise HTTPException(status_code=400, detail="标题不能为空")
                
                cell = self.manager.create_cell(title=title, effort=effort, parent_id=parent_id)
                
                return {
                    "id": cell.id,
                    "title": cell.title,
                    "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                    "workload": cell.workload
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.put("/api/cells/{cell_id}")
        async def api_update_cell(cell_id: str, request: Request):
            """更新任务"""
            try:
                data = await request.json()
                cell = self.manager.update_cell(cell_id, **data)
                
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                return {
                    "id": cell.id,
                    "title": cell.title,
                    "status": cell.status.value if hasattr(cell.status, 'value') else str(cell.status),
                    "progress": cell.progress
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.delete("/api/cells/{cell_id}")
        async def api_delete_cell(cell_id: str):
            """删除任务"""
            try:
                success = self.manager.delete_cell(cell_id)
                if not success:
                    raise HTTPException(status_code=404, detail="任务不存在")
                return {"success": True}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/api/cells/{cell_id}/move")
        async def api_move_cell(cell_id: str, request: Request):
            """移动任务"""
            try:
                data = await request.json()
                new_parent_id = data.get("new_parent_id")
                
                cell = self.manager.move_cell(cell_id, new_parent_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                return {"success": True, "id": cell.id, "parent_id": cell.parent_id}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/api/cells/{cell_id}/archive")
        async def api_archive_cell(cell_id: str):
            """归档任务"""
            try:
                cell = self.manager.archive_cell(cell_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                return {"success": True, "id": cell.id, "is_archived": True}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/api/cells/{cell_id}/unarchive")
        async def api_unarchive_cell(cell_id: str):
            """取消归档任务"""
            try:
                cell = self.manager.unarchive_cell(cell_id)
                if not cell:
                    raise HTTPException(status_code=404, detail="任务不存在")
                return {"success": True, "id": cell.id, "is_archived": False}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/api/cells/archive-completed")
        async def api_archive_completed_cells():
            """归档所有已完成任务"""
            try:
                count = self.manager.archive_all_completed()
                return {"success": True, "archived_count": count}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/api/stats/completed-dates")
        async def api_get_completed_dates():
            """获取完成日期列表"""
            try:
                dates = self.manager.get_completed_dates()
                return {"dates": dates}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/api/stats/completed-by-date")
        async def api_get_completed_by_date(date: str):
            """获取指定日期完成的任务"""
            try:
                cells = self.manager.get_completed_by_date(date)
                return [
                    {
                        "id": cell.id,
                        "title": cell.title,
                        "actual_hours": cell.actual_hours,
                        "completed_at": cell.completed_at.isoformat() if cell.completed_at else None
                    }
                    for cell in cells
                ]
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    async def start(self):
        """启动 WebUI 服务器"""
        if self._server_task and not self._server_task.done():
            logger.warning("Cell Manager WebUI 服务已经在运行")
            return
        
        config = uvicorn.Config(
            app=self._app,
            host=self.host,
            port=self.port,
            log_level="info",
            loop="asyncio"
        )
        self._server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(self._server.serve())
        
        # 等待服务启动
        for _ in range(50):
            if getattr(self._server, "started", False):
                logger.info(f"✅ Cell Manager WebUI 已启动: http://{self.host}:{self.port}")
                return
            if self._server_task.done():
                error = self._server_task.exception()
                raise RuntimeError(f"WebUI 启动失败: {error}") from error
            await asyncio.sleep(0.1)
        
        logger.warning("Cell Manager WebUI 启动耗时较长，仍在后台启动中")
    
    async def stop(self):
        """停止 WebUI 服务器"""
        if self._server:
            self._server.should_exit = True
        if self._server_task:
            await self._server_task
        self._server = None
        self._server_task = None
        logger.info("Cell Manager WebUI 已停止")
