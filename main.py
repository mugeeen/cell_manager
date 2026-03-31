# -*- coding: utf-8 -*-
"""
Cell Manager - AstrBot 插件
任务管理系统，支持无限递归的父子关系和漂亮的树形可视化
支持自然语言交互（LLM Tool）
"""

import os
from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger

# 导入 Cell Manager 核心模块
from .cell_manager import CellManager, DatabaseManager, CellStatus, ViewMode, visualize_tree


class CellManagerPlugin(Star):
    """Cell Manager AstrBot 插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 初始化数据库
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, 'cells.db')
        
        self.db = DatabaseManager(db_path)
        self.db.init_tables()
        self.manager = CellManager(self.db)
        
        # 注册 LLM Tools（让 AI 可以通过自然语言调用）
        # 使用装饰器方式自动注册，无需手动调用
        
        logger.info(f"Cell Manager 插件已初始化，数据库: {db_path}")
    
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
/cell list - 列出所有根任务
/cell tree [任务ID] - 显示任务树（默认显示第一个根任务）
/cell done <任务ID> - 标记任务为已完成
/cell doing <任务ID> - 标记任务为进行中
/cell todo <任务ID> - 标记任务为待办
/cell pause <任务ID> - 暂停任务
/cell add <父任务ID> <子任务标题> [工作量] - 添加子任务
/cell delete <任务ID> - 删除任务
/cell hours <任务ID> <小时数> - 记录实际用时
/cell progress [任务ID] - 查看任务进度

状态图标:
[ ] 待办  [>] 进行中  [||] 暂停  [X] 已完成  [-] 已取消
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
    
    @filter.command("cell_list")
    async def list_cells(self, event: AstrMessageEvent):
        '''列出所有根任务'''
        try:
            # 获取所有没有父节点的任务（根任务）
            all_cells = []
            # 这里需要添加一个获取所有根任务的方法
            # 暂时使用简单的查询
            result = "📋 根任务列表:\n"
            result += "-" * 40 + "\n"
            
            # 由于没有直接的 get_root_cells 方法，我们暂时显示帮助
            result += "使用 /cell tree 查看任务树\n"
            result += "或使用 /cell create 创建新任务"
            
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    
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
            success = self.manager.update_cell(cell_id, status=CellStatus.DONE)
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
            success = self.manager.update_cell(cell_id, status=CellStatus.DOING)
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
    
    @filter.command("cell_pause")
    async def mark_paused(self, event: AstrMessageEvent, cell_id: str):
        '''暂停任务'''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.PAUSED)
            if success:
                yield event.plain_result(f"⏸️ 任务已暂停！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.command("cell_add")
    async def add_child(self, event: AstrMessageEvent, parent_id: str, title: str, workload: float = 0.0):
        '''添加子任务'''
        try:
            cell = self.manager.create_cell(title=title, parent_id=parent_id, workload=workload)
            result = f"✅ 子任务创建成功！\n"
            result += f"ID: {cell.id}\n"
            result += f"标题: {cell.title}\n"
            result += f"父任务: {parent_id}\n"
            result += f"层级: {cell.level}"
            yield event.plain_result(result)
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
            
            result = f"📊 任务进度: {stats.get('root_title', 'Unknown')}\n"
            result += "-" * 40 + "\n"
            result += f"整体进度: {progress:.1f}%\n"
            result += f"总任务数: {stats.get('total_cells', 0)}\n"
            result += f"已完成: {stats.get('completed_cells', 0)}\n"
            result += f"总工作量: {stats.get('total_workload', 0):.1f}\n"
            result += f"已完成工作量: {stats.get('completed_workload', 0):.1f}"
            
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
    
    # ==================== LLM Tools (自然语言支持) ====================
    
    @filter.llm_tool(name="cell_create_task")
    async def llm_create_task(self, event: AstrMessageEvent, title: str, workload: float = 0.0) -> MessageEventResult:
        '''创建一个新任务。当用户想要创建任务、添加任务、新建任务时调用。
        
        Args:
            title(string): 任务标题
            workload(float): 预计工作量（可选，默认为0）
        '''
        try:
            cell = self.manager.create_cell(title=title, workload=workload)
            result = f"✅ 任务创建成功！\nID: {cell.id}\n标题: {cell.title}"
            if workload > 0:
                result += f"\n工作量: {workload}"
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 创建失败: {str(e)}")
    
    @filter.llm_tool(name="cell_add_subtask")
    async def llm_add_subtask(self, event: AstrMessageEvent, parent_id: str, title: str, workload: float = 0.0) -> MessageEventResult:
        '''添加子任务到指定父任务。当用户想要添加子任务、分解任务时调用。
        
        Args:
            parent_id(string): 父任务ID
            title(string): 子任务标题
            workload(float): 预计工作量（可选，默认为0）
        '''
        try:
            cell = self.manager.create_cell(title=title, parent_id=parent_id, workload=workload)
            yield event.plain_result(f"✅ 子任务创建成功！\nID: {cell.id}\n标题: {title}\n父任务: {parent_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 创建失败: {str(e)}")
    
    @filter.llm_tool(name="cell_complete_task")
    async def llm_complete_task(self, event: AstrMessageEvent, cell_id: str) -> MessageEventResult:
        '''标记任务为已完成。当用户说完成了某个任务、标记任务完成时调用。
        
        Args:
            cell_id(string): 任务ID
        '''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.DONE)
            if success:
                progress = self.manager.get_progress(cell_id)
                yield event.plain_result(f"✅ 任务已标记为完成！当前进度: {progress:.1f}%")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
    
    @filter.llm_tool(name="cell_show_tree")
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
    
    @filter.llm_tool(name="cell_show_progress")
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
    
    @filter.llm_tool(name="cell_record_hours")
    async def llm_record_hours(self, event: AstrMessageEvent, cell_id: str, hours: float) -> MessageEventResult:
        '''记录任务的实际用时。当用户说花了多少时间、记录时间时调用。
        
        Args:
            cell_id(string): 任务ID
            hours(float): 实际用时（小时）
        '''
        try:
            success = self.manager.set_actual_hours(cell_id, hours)
            if success:
                yield event.plain_result(f"⏱️ 已记录 {hours} 小时！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 记录失败: {str(e)}")
    
    @filter.llm_tool(name="cell_start_task")
    async def llm_start_task(self, event: AstrMessageEvent, cell_id: str) -> MessageEventResult:
        '''将任务标记为进行中。当用户说要开始某个任务时调用。
        
        Args:
            cell_id(string): 任务ID
        '''
        try:
            success = self.manager.update_cell(cell_id, status=CellStatus.DOING)
            if success:
                yield event.plain_result(f"▶️ 任务已开始！")
            else:
                yield event.plain_result(f"❌ 未找到任务: {cell_id}")
        except Exception as e:
            yield event.plain_result(f"❌ 操作失败: {str(e)}")
