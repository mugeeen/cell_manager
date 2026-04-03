# -*- coding: utf-8 -*-
"""
测试 move_cell 功能
"""

import os
import sys

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cell_manager import CellManager, DatabaseManager

# 初始化数据库
data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, 'cells.db')

db = DatabaseManager(db_path)
db.init_tables()
manager = CellManager(db)

# 获取所有根节点
roots = manager.get_root_cells()
print(f"根节点数量: {len(roots)}")

if len(roots) >= 2:
    # 尝试移动第二个根节点到第一个根节点下
    source_id = roots[1].id
    target_id = roots[0].id
    
    print(f"\n尝试移动节点:")
    print(f"  源节点: {roots[1].title} (ID: {source_id})")
    print(f"  目标节点: {roots[0].title} (ID: {target_id})")
    
    try:
        result = manager.move_cell(source_id, target_id)
        print(f"\n移动结果: {result}")
        
        # 检查移动后的状态
        moved_cell = db.get_cell(source_id)
        if moved_cell:
            print(f"\n移动后节点状态:")
            print(f"  标题: {moved_cell.title}")
            print(f"  父节点ID: {moved_cell.parent_id}")
            print(f"  Level: {moved_cell.level}")
    except Exception as e:
        import traceback
        print(f"\n错误: {e}")
        print(traceback.format_exc())
else:
    print("需要至少2个根节点来测试移动功能")
