# -*- coding: utf-8 -*-
"""
Cell Manager WebUI 本地测试服务器
独立运行，无需启动整个 AstrBot
"""

import os
import sys
import asyncio

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cell_manager import CellManager, DatabaseManager
from web.server import WebUIServer

def init_test_data(manager):
    """初始化测试数据"""
    # 检查是否已有数据
    roots = manager.get_root_cells()
    if roots:
        print(f"已有 {len(roots)} 个根节点，跳过测试数据创建")
        return
    
    print("创建测试数据...")
    
    # 创建根任务
    root1 = manager.create_cell(title="学习 Python", workload=100)
    root2 = manager.create_cell(title="开发项目", workload=200)
    
    # 为 root1 添加子任务
    if root1:
        child1 = manager.create_cell(title="基础语法", parent_id=root1.id, workload=20)
        child2 = manager.create_cell(title="面向对象", parent_id=root1.id, workload=30)
        child3 = manager.create_cell(title="Web 框架", parent_id=root1.id, workload=50)
        
        if child1:
            # 添加孙任务
            manager.create_cell(title="变量和数据类型", parent_id=child1.id, workload=5)
            manager.create_cell(title="控制流", parent_id=child1.id, workload=5)
            manager.create_cell(title="函数", parent_id=child1.id, workload=10)
        
        if child2:
            manager.create_cell(title="类和对象", parent_id=child2.id, workload=15)
            manager.create_cell(title="继承和多态", parent_id=child2.id, workload=15)
    
    # 为 root2 添加子任务
    if root2:
        child4 = manager.create_cell(title="需求分析", parent_id=root2.id, workload=30)
        child5 = manager.create_cell(title="编码实现", parent_id=root2.id, workload=120)
        child6 = manager.create_cell(title="测试部署", parent_id=root2.id, workload=50)
        
        if child5:
            manager.create_cell(title="前端开发", parent_id=child5.id, workload=60)
            manager.create_cell(title="后端开发", parent_id=child5.id, workload=60)
    
    print("测试数据创建完成！")

async def main():
    """主函数"""
    print("=" * 50)
    print("Cell Manager WebUI 测试服务器启动中...")
    print("=" * 50)
    
    # 初始化数据库
    data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'cells.db')
    
    db = DatabaseManager(db_path)
    db.init_tables()
    manager = CellManager(db)
    
    # 创建测试数据
    init_test_data(manager)
    
    # 创建并启动 WebUI 服务器
    webui_server = WebUIServer(
        manager=manager,
        db=db,
        config={"host": "0.0.0.0", "port": 8082}
    )
    
    print(f"\n数据库: {db_path}")
    print("\n访问地址:")
    print("  - WebUI 界面: http://localhost:8082/")
    print("  - API 文档:   http://localhost:8082/docs")
    print("=" * 50)
    
    # 启动服务器
    try:
        await webui_server.start()
    except asyncio.CancelledError:
        print("\n服务器已停止")
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止服务器...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已安全停止")
