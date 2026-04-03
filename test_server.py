# -*- coding: utf-8 -*-
"""
Cell Manager Web 可视化测试服务器
独立运行，无需启动整个 AstrBot
"""

import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cell_manager import CellManager, DatabaseManager
from web.routes import setup_routes

# 创建 FastAPI 应用
app = FastAPI(title="Cell Manager Test Server")

# 允许跨域（方便开发调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.on_event("startup")
async def startup():
    """启动时初始化"""
    print("=" * 50)
    print("Cell Manager 测试服务器启动中...")
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
    
    # 注册路由
    setup_routes(app, manager, db)
    
    print(f"\n数据库: {db_path}")
    print("\n访问地址:")
    print("  - 可视化界面: http://localhost:8000/cell_manager/visualizer")
    print("  - API 文档:   http://localhost:8000/docs")
    print("=" * 50)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
