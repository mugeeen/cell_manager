# -*- coding: utf-8 -*-
"""
Cell Manager WebUI 处理器
适配 AstrBot 的 register_web_api API
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 获取当前目录路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(CURRENT_DIR), 'templates')


class WebUIHandler:
    """WebUI 请求处理器"""
    
    def __init__(self, manager, db):
        self.manager = manager
        self.db = db
    
    def _get_template(self, filename: str) -> str:
        """读取模板文件"""
        filepath = os.path.join(TEMPLATE_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"<h1>Error loading template: {e}</h1>"
    
    def _json_response(self, data: Dict[str, Any], status: int = 200) -> Dict[str, Any]:
        """创建 JSON 响应"""
        return {
            "type": "json",
            "status": status,
            "body": json.dumps(data, ensure_ascii=False, default=str)
        }
    
    def _html_response(self, html: str, status: int = 200) -> Dict[str, Any]:
        """创建 HTML 响应"""
        return {
            "type": "html",
            "status": status,
            "body": html
        }
    
    # ==================== 页面路由 ====================
    
    async def serve_react_flow(self, request) -> Dict[str, Any]:
        """React Flow 可视化页面"""
        html = self._get_template('react_flow.html')
        return self._html_response(html)
    
    async def serve_stats(self, request) -> Dict[str, Any]:
        """时间统计页面"""
        html = self._get_template('stats.html')
        return self._html_response(html)
    
    # ==================== API 路由 ====================
    
    async def api_get_cells_graph(self, request) -> Dict[str, Any]:
        """获取 Cell 图形数据"""
        try:
            # 获取查询参数
            query_params = request.get('query_params', {})
            root_id = query_params.get('root_id')
            include_archived = query_params.get('include_archived', 'false').lower() == 'true'
            
            nodes = []
            edges = []
            
            def add_cell_to_graph(cell, parent_id=None, level=0):
                """递归添加 Cell 到图形"""
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
            
            return self._json_response({
                "success": True,
                "data": {"nodes": nodes, "edges": edges}
            })
            
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_get_root_cells(self, request) -> Dict[str, Any]:
        """获取所有根节点列表"""
        try:
            root_cells = self.db.list_cells(parent_id=None)
            return self._json_response({
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
            })
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_get_cell_detail(self, request) -> Dict[str, Any]:
        """获取单个 Cell 详情"""
        try:
            cell_id = request.get('path_params', {}).get('cell_id')
            if not cell_id:
                return self._json_response({
                    "success": False,
                    "error": "Missing cell_id"
                }, status=400)
            
            cell = self.db.get_cell(cell_id)
            if not cell:
                return self._json_response({
                    "success": False,
                    "error": "Cell not found"
                }, status=404)
            
            children = self.db.get_children(cell_id)
            
            return self._json_response({
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
            })
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_update_cell(self, request) -> Dict[str, Any]:
        """更新 Cell"""
        try:
            cell_id = request.get('path_params', {}).get('cell_id')
            if not cell_id:
                return self._json_response({
                    "success": False,
                    "error": "Missing cell_id"
                }, status=400)
            
            cell = self.db.get_cell(cell_id)
            if not cell:
                return self._json_response({
                    "success": False,
                    "error": "Cell not found"
                }, status=404)
            
            # 解析请求体
            body = json.loads(request.get('body', '{}'))
            
            update_kwargs = {}
            if 'title' in body:
                update_kwargs['title'] = body['title']
            if 'description' in body:
                update_kwargs['description'] = body['description']
            if 'status' in body:
                update_kwargs['status'] = body['status']
                if body['status'] == 'completed' and cell.status.value != 'completed':
                    update_kwargs['completed_at'] = datetime.now()
            if 'workload' in body:
                update_kwargs['workload'] = body['workload']
            if 'actual_hours' in body:
                update_kwargs['actual_hours'] = body['actual_hours']
            
            if self.manager.update_cell(cell_id, **update_kwargs):
                updated_cell = self.db.get_cell(cell_id)
                return self._json_response({
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
                })
            else:
                return self._json_response({
                    "success": False,
                    "error": "Update failed"
                }, status=500)
                
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_create_cell(self, request) -> Dict[str, Any]:
        """创建新 Cell"""
        try:
            body = json.loads(request.get('body', '{}'))
            
            cell = self.manager.create_cell(
                title=body.get('title', ''),
                description=body.get('description', ''),
                parent_id=body.get('parent_id'),
                workload=body.get('workload', 0.0)
            )
            
            if cell:
                return self._json_response({
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
                })
            else:
                return self._json_response({
                    "success": False,
                    "error": "Create failed"
                }, status=500)
                
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_move_cell(self, request) -> Dict[str, Any]:
        """移动 Cell"""
        try:
            cell_id = request.get('path_params', {}).get('cell_id')
            if not cell_id:
                return self._json_response({
                    "success": False,
                    "error": "Missing cell_id"
                }, status=400)
            
            body = json.loads(request.get('body', '{}'))
            new_parent_id = body.get('new_parent_id')
            
            cell = self.db.get_cell(cell_id)
            if not cell:
                return self._json_response({
                    "success": False,
                    "error": "Cell not found"
                }, status=404)
            
            if self.manager.move_cell(cell_id, new_parent_id):
                moved_cell = self.db.get_cell(cell_id)
                return self._json_response({
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
                })
            else:
                return self._json_response({
                    "success": False,
                    "error": "Move failed"
                }, status=500)
                
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_delete_cell(self, request) -> Dict[str, Any]:
        """删除 Cell"""
        try:
            cell_id = request.get('path_params', {}).get('cell_id')
            if not cell_id:
                return self._json_response({
                    "success": False,
                    "error": "Missing cell_id"
                }, status=400)
            
            cell = self.db.get_cell(cell_id)
            if not cell:
                return self._json_response({
                    "success": False,
                    "error": "Cell not found"
                }, status=404)
            
            # 级联删除子节点
            children = self.db.get_children(cell_id)
            for child in children:
                self.manager.delete_cell(child.id)
            
            if self.manager.delete_cell(cell_id):
                return self._json_response({
                    "success": True,
                    "message": "Cell deleted successfully"
                })
            else:
                return self._json_response({
                    "success": False,
                    "error": "Delete failed"
                }, status=500)
                
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_get_completed_dates(self, request) -> Dict[str, Any]:
        """获取所有有完成记录的日期列表"""
        try:
            dates = self.db.get_completed_dates()
            return self._json_response({
                "success": True,
                "dates": dates
            })
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_get_completed_by_date(self, request) -> Dict[str, Any]:
        """获取指定日期完成的叶子节点"""
        try:
            query_params = request.get('query_params', {})
            date = query_params.get('date')
            
            if not date:
                return self._json_response({
                    "success": False,
                    "error": "Missing date parameter"
                }, status=400)
            
            cells = self.db.get_completed_leaf_cells_by_date(date)
            
            result = []
            for cell in cells:
                # 查找根任务
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
            
            return self._json_response({
                "success": True,
                "date": date,
                "cells": result,
                "root_stats": root_stats,
                "total_hours": sum(item["actual_hours"] for item in result),
                "total_count": len(result)
            })
            
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_archive_completed_cells(self, request) -> Dict[str, Any]:
        """归档所有符合条件的已完成 Cell"""
        try:
            count = self.manager.archive_completed_cells()
            return self._json_response({
                "success": True,
                "archived_count": count
            })
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_archive_cell(self, request) -> Dict[str, Any]:
        """归档单个 Cell"""
        try:
            cell_id = request.get('path_params', {}).get('cell_id')
            if not cell_id:
                return self._json_response({
                    "success": False,
                    "error": "Missing cell_id"
                }, status=400)
            
            if self.manager.archive_cell(cell_id):
                return self._json_response({
                    "success": True,
                    "message": "Cell archived successfully"
                })
            else:
                return self._json_response({
                    "success": False,
                    "error": "Archive failed"
                }, status=500)
                
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def api_unarchive_cell(self, request) -> Dict[str, Any]:
        """取消归档单个 Cell"""
        try:
            cell_id = request.get('path_params', {}).get('cell_id')
            if not cell_id:
                return self._json_response({
                    "success": False,
                    "error": "Missing cell_id"
                }, status=400)
            
            if self.manager.unarchive_cell(cell_id):
                return self._json_response({
                    "success": True,
                    "message": "Cell unarchived successfully"
                })
            else:
                return self._json_response({
                    "success": False,
                    "error": "Unarchive failed"
                }, status=500)
                
        except Exception as e:
            return self._json_response({
                "success": False,
                "error": str(e)
            }, status=500)