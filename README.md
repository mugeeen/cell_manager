# Cell Manager - AstrBot 任务管理插件

一个功能强大的任务管理系统，支持无限递归的父子关系、漂亮的树形可视化和 macOS 风格的时间统计界面。

## 特性

- ✅ **无限层级**：支持任意深度的任务分解
- ✅ **工作量跟踪**：自动计算总工作量和进度
- ✅ **时间统计**：记录实际用时，自动汇总，支持按日期查看
- ✅ **树形可视化**：漂亮的 ASCII 树形结构展示
- ✅ **Web 可视化**：React Flow 交互式任务图 + macOS 风格统计界面
- ✅ **自然语言交互**：支持 AI 自然语言理解
- ✅ **命令交互**：传统的命令方式
- ✅ **任务归档**：支持归档已完成的任务

## 安装

1. 将 `astrbot_plugin_cell_manager` 文件夹复制到 AstrBot 的 `data/plugins/` 目录
2. 在 AstrBot WebUI 中重载插件

## 使用方式

### 方式一：自然语言（推荐）

直接和 AI 对话：

```
"帮我创建一个学习Python的任务，工作量10"
"给abc123添加子任务：基础语法，工作量3"
"我完成了abc123任务"
"显示abc123的任务树"
"记录abc123任务花了5小时"
"开始执行abc123任务"
"归档已完成的任务"
```

### 方式二：命令方式

| 命令 | 说明 | 示例 |
|------|------|------|
| `/cell` | 显示帮助 | `/cell` |
| `/cell_create` | 创建任务 | `/cell_create 学习Python 10` |
| `/cell_add` | 添加子任务 | `/cell_add abc123 基础语法 3` |
| `/cell_done` | 标记完成 | `/cell_done abc123` |
| `/cell_doing` | 标记进行中 | `/cell_doing abc123` |
| `/cell_todo` | 重置为待办 | `/cell_todo abc123` |
| `/cell_urgent` | 标记紧急 | `/cell_urgent abc123` |
| `/cell_tree` | 显示任务树 | `/cell_tree abc123` |
| `/cell_progress` | 查看进度 | `/cell_progress abc123` |
| `/cell_hours` | 记录用时 | `/cell_hours abc123 5` |
| `/cell_archive` | 归档任务 | `/cell_archive abc123` |
| `/cell_unarchive` | 取消归档 | `/cell_unarchive abc123` |
| `/cell_archive_all` | 归档所有已完成 | `/cell_archive_all` |

> 注意：由于任务量可能很大，不再提供列出所有任务的命令。请使用自然语言方式查询任务，如"有什么任务？"、"搜索Python相关的任务"。

### 方式三：Web 可视化界面

启动 AstrBot 后，访问以下地址：

- **React Flow 交互式任务图**：`http://<your-bot-host>:<port>/cell_manager/react-flow`
  - 拖拽创建节点
  - 拖拽连线建立父子关系
  - 自动布局
  - 实时编辑任务属性
  - 进度可视化（背景填充）

- **时间统计仪表盘**：`http://<your-bot-host>:<port>/cell_manager/stats`
  - macOS 风格设计
  - 按日期查看完成的任务
  - 环形图展示时间分布
  - 任务列表详情

## 状态图标

- `[ ]` 待办 (todo)
- `[>]` 进行中 (in_progress)
- `[!]` 紧急 (urgent)
- `[X]` 已完成 (completed)

## 示例输出

```
==================================================
  学习 Python 项目
==================================================

`-- [ ] 学习 Python [------------] 0% (工作量:10.0)
    |-- [ ] 数据结构 [####--------] 37% (工作量:4.0, 耗时:5.0h)
    |   |-- [X] 列表与元组 [############] 100%
    |   |-- [>] 字典与集合 [######------] 50%
    |   `-- [ ] 类与对象 [------------] 0%
    `-- [ ] 基础语法 [#######-----] 66% (工作量:3.0, 耗时:4.5h)
        |-- [X] 变量与类型 [############] 100%
        `-- [>] 函数 [######------] 50%
```

## 核心概念

### Cell（任务单元）

- **叶子节点**：可以设置 workload 和 actual_hours
- **非叶子节点**：自动汇总子节点的 total_workload 和 total_hours
- **进度计算**：加权平均算法，完成的子节点工作量 / 总工作量

### 自动级联更新

当子任务变更时，父任务会自动更新：
- 总工作量自动重新计算
- 进度自动重新计算
- 总耗时自动重新计算

### 任务归档

- 已归档的任务不会显示在默认视图中
- 可以单独查看已归档任务
- 支持批量归档所有已完成的任务

## 项目结构

```
astrbot_plugin_cell_manager/
├── README.md              # 本文件
├── metadata.yaml          # 插件元数据
├── requirements.txt       # 依赖（Python 标准库，无需额外安装）
├── main.py               # 插件入口
├── cell_manager/         # 核心模块
│   ├── __init__.py
│   ├── models.py         # 数据模型
│   ├── database.py       # 数据库操作
│   ├── manager.py        # 业务逻辑
│   └── visualizer.py     # 可视化
├── web/                  # Web 路由
│   ├── __init__.py
│   └── routes.py         # API 路由
└── templates/            # HTML 模板
    ├── react_flow.html   # React Flow 可视化
    └── stats.html        # 时间统计界面
```

## 数据存储

插件数据存储在 AstrBot 的 `data/plugin_data/cell_manager/` 目录下：
- `cells.db` - SQLite 数据库文件

这样设计的好处是：插件更新或重装时，数据不会丢失。

## 版本历史

### v1.2.0
- 添加任务归档功能
- 添加 macOS 风格的时间统计界面
- 简化状态系统（4个状态）
- 优化进度计算算法（加权平均）

### v1.1.0
- 添加 React Flow 可视化界面
- 添加 Web API
- 支持拖拽创建和连接节点

### v1.0.0
- 初始版本
- 基础任务管理功能
- 自然语言交互
