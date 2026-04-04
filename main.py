# -*- coding: utf-8 -*-
"""
Cell Manager - AstrBot 插件
任务管理系统，支持无限递归的父子关系和漂亮的树形可视化
支持自然语言交互（LLM Tool）
"""

import os
from typing import Optional, Any

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

# 导入 Cell Manager 核心模块
from .cell_manager import CellManager, DatabaseManager, CellStatus, ViewMode, visualize_tree

# 导入 Web 路由
from .web import WebUIHandler


@register("astrbot_plugin_cell_manager", "Cell Manager Team", "任务管理系统，支持无限递归的父子关系和漂亮的树形可视化", "v1.3.0")
class CellManagerPlugin(Star):
    """Cell Manager AstrBot 插件"""
    
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        
        # 初始化数据库 - 使用 AstrBot 的 plugin_data 目录
        plugin_data_dir = get_astrbot_plugin_data_path()
        data_dir = os.path.join(plugin_data_dir, 'cell_manager')
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, 'cells.db')
        
        self.db = DatabaseManager(db_path)
        self.db.init_tables()
        self.manager = CellManager(self.db)
        
        # WebUI 处理器
        self.webui_handler = None
        
        # 注册 WebUI 路由
        webui_config = self.config.get("webui_settings", {})
        if webui_config.get("enabled", True):
            self._register_webui()
        
        logger.info(f"Cell Manager 插件已初始化，数据库: {db_path}")
    
    def _register_webui(self):
        """注册 WebUI 路由到 AstrBot"""
        try:
            self.webui_handler = WebUIHandler(self.manager, self.db)
            
            # 尝试使用 register_web_route (AstrBot >= 4.0)
            # 如果不可用，则使用 register_web_api
            if hasattr(self.context, 'register_web_route'):
                register_func = self.context.register_web_route
            elif hasattr(self.context, 'register_web_api'):
                register_func = self.context.register_web_api
            else:
                logger.warning("⚠️ AstrBot 不支持 WebUI 路由注册，跳过 WebUI 初始化")
                return
            
            # 注册主页面路由
            register_func(
                path="/cell_manager",
                method="GET",
                handler=self.webui_handler.serve_react_flow,
                name="Cell Manager - React Flow 可视化"
            )
            
            # 注册统计页面
            register_func(
                path="/cell_manager/stats",
                method="GET",
                handler=self.webui_handler.serve_stats,
                name="Cell Manager - 时间统计"
            )
            
            # 注册 API 路由
            register_func(
                path="/cell_manager/api/cells/graph",
                method="GET",
                handler=self.webui_handler.api_get_cells_graph,
                name="获取任务图形数据"
            )
            
            register_func(
                path="/cell_manager/api/cells/roots",
                method="GET",
                handler=self.webui_handler.api_get_root_cells,
                name="获取根节点列表"
            )
            
            register_func(
                path="/cell_manager/api/cells/{cell_id}",
                method="GET",
                handler=self.webui_handler.api_get_cell_detail,
                name="获取任务详情"
            )
            
            register_func(
                path="/cell_manager/api/cells/{cell_id}",
                method="PUT",
                handler=self.webui_handler.api_update_cell,
                name="更新任务"
            )
            
            register_func(
                path="/cell_manager/api/cells",
                method="POST",
                handler=self.webui_handler.api_create_cell,
                name="创建任务"
            )
            
            register_func(
                path="/cell_manager/api/cells/{cell_id}/move",
                method="POST",
                handler=self.webui_handler.api_move_cell,
                name="移动任务"
            )
            
            register_func(
                path="/cell_manager/api/cells/{cell_id}",
                method="DELETE",
                handler=self.webui_handler.api_delete_cell,
                name="删除任务"
            )
            
            register_func(
                path="/cell_manager/api/stats/completed-dates",
                method="GET",
                handler=self.webui_handler.api_get_completed_dates,
                name="获取完成日期列表"
            )
            
            register_func(
                path="/cell_manager/api/stats/completed-by-date",
                method="GET",
                handler=self.webui_handler.api_get_completed_by_date,
                name="获取指定日期完成的任务"
            )
            
            register_func(
                path="/cell_manager/api/cells/archive-completed",
                method="POST",
                handler=self.webui_handler.api_archive_completed_cells,
                name="归档所有已完成任务"
            )
            
            register_func(
                path="/cell_manager/api/cells/{cell_id}/archive",
                method="POST",
                handler=self.webui_handler.api_archive_cell,
                name="归档任务"
            )
            
            register_func(
                path="/cell_manager/api/cells/{cell_id}/unarchive",
                method="POST",
                handler=self.webui_handler.api_unarchive_cell,
                name="取消归档任务"
            )
            
            logger.info("✅ Cell Manager WebUI 路由已注册到 AstrBot")
            
        except Exception as e:
            logger.error(f"❌ 注册 WebUI 路由失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def terminate(self):
        """插件卸载时调用"""
        if self.db:
            self.db.close()
        logger.info("Cell Manager 插件已卸载")
    
    # ==================== 核心命令 ====================
    
    @filter.command("cell")
    async def cell_help(self, event: AstrMessageEvent):
        '''显示 Cell Manager 帮助信息'''
        help_text = """📋 Cell Manager 任务管理系统

命令列表:
/cell create <标题> [工作量] - 创建根任务
/cell tree <任务ID> - 显示任务树
/cell done <任务ID> - 标记任务为已完成
/cell doing <任务ID> - 标记任务为进行中
/cell todo <任务ID> - 标记任务为待办
/cell urgent <任务ID> - 标记任务为紧急
/cell add <父任务ID> <子任务标题> [工作量] - 添加子任务
/cell delete <任务ID> - 删除任务
/cell hours <任务ID> <小时数> - 记录实际用时
/cell progress <任务ID> - 查看任务进度
/cell archive <任务ID> - 归档任务
/cell unarchive <任务ID> - 取消归档
/cell archive-all - 归档所有已完成任务

Web 可视化界面:
访问 AstrBot 管理面板 (http://<服务器IP>:6185) 即可使用可视化界面

状态图标:
[ ] 待办  [>] 进行中  [!] 紧急  [X] 已完成
"""
        yield event.plain_result(help_text)
    
    @filter.command("cell_create")
    async def create_cell(self, event: AstrMessageEvent, title: str, workload: float = 0.0):
        '''创建新任务'''
        try:
            cell = self.manager.create_cell(title=title, workload=workload)
            result = f"✅ 任务创建成功！\n"
            result += f"ID: {cell.id}\n"
            result += f"标题: {cell.title}\n"
            result += f"工作量: {cell.workload}\n"
            result += f"状态: {cell.status.value}"
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 创建失败: {str(e)}")
    
    @filter.command("cell_tree")
    async def show_tree(self, event: AstrMessageEvent, cell_id: str = ""):
        '''显示任务树'''
        try:
            if not cell_id:
                # 如果没有指定ID，显示帮助
                yield event.plain_result("请提供任务ID: /cell_tree <任务ID>")
                return
            
            tree = self.manager.get_tree(cell_id)
            if not tree:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
                return
            
            # 使用可视化器显示树
            visual_output = visualize_tree(
                tree, 
                mode=ViewMode.COMPACT,
                title=tree.get('title', '任务树')
            )
            
            yield event.plain_result(visual_output)
        except Exception as e:
            yield event.plain_result(f"❌ 显示失败: {str(e)}")
    
    @filter.command("cell_done")
    async def mark_done(self, event: AstrMessageEvent, cell_id: str):
        '''标记任务为已完成'''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.COMPLETED)
            if success:
                # 自动更新进度
                progress = self.manager.get_progress(cell_id)
                yield event.plain_result(f"✅ 任务已标记为完成！当前进度: {progress:.1f}%")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.command("cell_doing")
    async def mark_doing(self, event: AstrMessageEvent, cell_id: str):
        '''标记任务为进行中'''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.IN_PROGRESS)
            if success:
                yield event.plain_result(f"▶️ 任务已开始！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.command("cell_todo")
    async def mark_todo(self, event: AstrMessageEvent, cell_id: str):
        '''标记任务为待办'''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.TODO)
            if success:
                yield event.plain_result(f"⭕ 任务已重置为待办！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.command("cell_urgent")
    async def mark_urgent(self, event: AstrMessageEvent, cell_id: str):
        '''标记任务为紧急'''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.URGENT)
            if success:
                yield event.plain_result(f"🚨 任务已标记为紧急！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.command("cell_add")
    async def add_child(self, event: AstrMessageEvent, parent_id: str, title: str, workload: float = 0.0):
        '''添加子任务'''
        try:
            cell = self.manager.create_cell(title=title, parent_id=parent_id, workload=workload)
            yield event.plain_result(f"✅ 子任务创建成功！\nID: {cell.id}\n标题: {title}")
        except Exception as e:
            yield event.plain_result(f"❌ 创建失败: {str(e)}")
    
    @filter.command("cell_delete")
    async def delete_cell(self, event: AstrMessageEvent, cell_id: str):
        '''删除任务'''
        try:
            success = self.manager.delete_cell(cell_id)
            if success:
                yield event.plain_result(f"🗑️ 任务已删除！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 删除失败: {str(e)}")
    
    @filter.command("cell_hours")
    async def set_hours(self, event: AstrMessageEvent, cell_id: str, hours: float):
        '''记录实际用时'''
        try:
            success = self.manager.set_actual_hours(cell_id, hours)
            if success:
                yield event.plain_result(f"⏱️ 已记录 {hours} 小时！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 记录失败: {str(e)}")
    
    @filter.command("cell_progress")
    async def show_progress(self, event: AstrMessageEvent, cell_id: str = ""):
        '''查看任务进度'''
        try:
            if not cell_id:
                yield event.plain_result("请提供任务ID: /cell_progress <任务ID>")
                return
            
            progress = self.manager.get_progress(cell_id)
            stats = self.manager.get_tree_progress(cell_id)
            
            if not stats:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
                return
            
            result = f"📊 {stats.get('root_title', 'Unknown')}\n"
            result += f"整体进度: {progress:.1f}%\n"
            result += f"任务数: {stats.get('completed_cells', 0)}/{stats.get('total_cells', 0)} 完成\n"
            result += f"工作量: {stats.get('completed_workload', 0):.1f}/{stats.get('total_workload', 0):.1f}"
            
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    
    @filter.command("cell_archive")
    async def archive_cell_cmd(self, event: AstrMessageEvent, cell_id: str):
        '''归档任务'''
        try:
            success = self.manager.archive_cell(cell_id)
            if success:
                yield event.plain_result(f"📦 任务已归档！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 归档失败: {str(e)}")
    
    @filter.command("cell_unarchive")
    async def unarchive_cell_cmd(self, event: AstrMessageEvent, cell_id: str):
        '''取消归档任务'''
        try:
            success = self.manager.unarchive_cell(cell_id)
            if success:
                yield event.plain_result(f"📂 任务已取消归档！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.command("cell_archive_all")
    async def archive_all_completed(self, event: AstrMessageEvent):
        '''归档所有已完成的任务'''
        try:
            count = self.manager.archive_completed_cells()
            yield event.plain_result(f"📦 已归档 {count} 个已完成的任务！")
        except Exception as e:
            yield event.plain_result(f"❌ 归档失败: {str(e)}")
    
    # ==================== LLM Tools (自然语言支持) ====================
    
    @filter.llm_tool("cell_create_task")
    async def llm_create_task(self, event: AstrMessageEvent, title: str, workload: float = 0.0) -> MessageEventResult:
        '''创建一个新任务。当用户想要创建任务、添加任务、新建任务时调用。
        
        Args:
            title(string): 任务标题
            workload(number): 预计工作量（可选，默认为0）
        '''
        try:
            cell = self.manager.create_cell(title=title, workload=workload)
            result = f"✅ 任务创建成功！\nID: {cell.id}\n标题: {cell.title}"
            if workload > 0:
                result += f"\n工作量: {workload}"
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 创建失败: {str(e)}")
    
    @filter.llm_tool("cell_add_subtask")
    async def llm_add_subtask(self, event: AstrMessageEvent, parent_id: str, title: str, workload: float = 0.0) -> MessageEventResult:
        '''添加子任务到指定父任务。当用户想要添加子任务、分解任务时调用。
        
        Args:
            parent_id(string): 父任务ID
            title(string): 子任务标题
            workload(number): 预计工作量（可选，默认为0）
        '''
        try:
            cell = self.manager.create_cell(title=title, parent_id=parent_id, workload=workload)
            yield event.plain_result(f"✅ 子任务创建成功！\nID: {cell.id}\n标题: {title}\n父任务: {parent_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 创建失败: {str(e)}")
    
    @filter.llm_tool("cell_complete_task")
    async def llm_complete_task(self, event: AstrMessageEvent, cell_id: str) -> MessageEventResult:
        '''标记任务为已完成。当用户说完成了某个任务、标记任务完成时调用。
        
        Args:
            cell_id(string): 任务ID
        '''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.COMPLETED)
            if success:
                progress = self.manager.get_progress(cell_id)
                yield event.plain_result(f"✅ 任务已标记为完成！当前进度: {progress:.1f}%")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.llm_tool("cell_show_tree")
    async def llm_show_tree(self, event: AstrMessageEvent, cell_id: str) -> MessageEventResult:
        '''显示任务树结构。当用户想要查看任务树、显示任务结构时调用。
        
        Args:
            cell_id(string): 根任务ID
        '''
        try:
            tree = self.manager.get_tree(cell_id)
            if not tree:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
                return
            
            visual_output = visualize_tree(
                tree,
                mode=ViewMode.COMPACT,
                title=tree.get('title', '任务树')
            )
            yield event.plain_result(visual_output)
        except Exception as e:
            yield event.plain_result(f"❌ 显示失败: {str(e)}")
    
    @filter.llm_tool("cell_show_progress")
    async def llm_show_progress(self, event: AstrMessageEvent, cell_id: str) -> MessageEventResult:
        '''查看任务进度统计。当用户想要查看进度、了解完成情况时调用。
        
        Args:
            cell_id(string): 任务ID
        '''
        try:
            progress = self.manager.get_progress(cell_id)
            stats = self.manager.get_tree_progress(cell_id)
            
            if not stats:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
                return
            
            result = f"📊 {stats.get('root_title', 'Unknown')}\n"
            result += f"整体进度: {progress:.1f}%\n"
            result += f"任务数: {stats.get('completed_cells', 0)}/{stats.get('total_cells', 0)} 完成\n"
            result += f"工作量: {stats.get('completed_workload', 0):.1f}/{stats.get('total_workload', 0):.1f}"
            
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    
    @filter.llm_tool("cell_record_hours")
    async def llm_record_hours(self, event: AstrMessageEvent, cell_id: str, hours: float) -> MessageEventResult:
        '''记录任务的实际用时。当用户说花了多少时间、记录时间时调用。
        
        Args:
            cell_id(string): 任务ID
            hours(number): 实际用时（小时）
        '''
        try:
            success = self.manager.set_actual_hours(cell_id, hours)
            if success:
                yield event.plain_result(f"⏱️ 已记录 {hours} 小时！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 记录失败: {str(e)}")
    
    @filter.llm_tool("cell_start_task")
    async def llm_start_task(self, event: AstrMessageEvent, cell_id: str) -> MessageEventResult:
        '''将任务标记为进行中。当用户说要开始某个任务时调用。
        
        Args:
            cell_id(string): 任务ID
        '''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.IN_PROGRESS)
            if success:
                yield event.plain_result(f"▶️ 任务已开始！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.llm_tool("cell_list_tasks")
    async def llm_list_tasks(self, event: AstrMessageEvent) -> MessageEventResult:
        '''列出所有根任务。当用户想要查看所有任务、列出任务、有什么任务时调用。
        
        这是获取任务ID的主要方式。在需要操作任务前，先调用此工具获取可用的任务ID。
        '''
        try:
            root_cells = self.manager.get_root_cells()
            
            if not root_cells:
                yield event.plain_result("📭 暂无任务。使用 cell_create_task 创建新任务。")
                return
            
            result = "📋 任务列表:\n\n"
            
            # 简化状态图标
            status_icons = {
                CellStatus.TODO: "[ ]",
                CellStatus.IN_PROGRESS: "[>]",
                CellStatus.URGENT: "[!]",
                CellStatus.COMPLETED: "[X]"
            }
            
            for cell in root_cells:
                icon = status_icons.get(cell.status, "[ ]")
                progress = cell.get_progress()
                result += f"{icon} {cell.title}\n"
                result += f"   ID: {cell.id} | 进度: {progress:.0f}%"
                if cell.workload > 0:
                    result += f" | 工作量: {cell.workload:.1f}h"
                result += "\n\n"
            
            yield event.plain_result(result.strip())
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    
    @filter.llm_tool("cell_search_tasks")
    async def llm_search_tasks(self, event: AstrMessageEvent, keyword: str) -> MessageEventResult:
        '''搜索任务。当用户提到查找任务、搜索某个任务、找某个任务时调用。
        
        通过关键词搜索任务标题和描述，帮助用户找到特定任务。
        
        Args:
            keyword(string): 搜索关键词
        '''
        try:
            cells = self.manager.search_cells(keyword)
            
            if not cells:
                yield event.plain_result(f"🔍 未找到包含 '{keyword}' 的任务")
                return
            
            result = f"🔍 搜索结果 ({len(cells)} 个):\n\n"
            
            # 简化状态图标
            status_icons = {
                CellStatus.TODO: "[ ]",
                CellStatus.IN_PROGRESS: "[>]",
                CellStatus.URGENT: "[!]",
                CellStatus.COMPLETED: "[X]"
            }
            
            for cell in cells:
                icon = status_icons.get(cell.status, "[ ]")
                progress = cell.get_progress()
                result += f"{icon} {cell.title}\n"
                result += f"   ID: {cell.id} | 进度: {progress:.0f}%"
                if cell.parent_id:
                    result += f" | 父任务: {cell.parent_id[:8]}..."
                result += "\n\n"
            
            yield event.plain_result(result.strip())
        except Exception as e:
            yield event.plain_result(f"❌ 搜索失败: {str(e)}")
