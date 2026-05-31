# Blender-MCP Developer Guide

> 版本: 1.5.5 | 目标 Blender: 5.1.2 | Python: 3.10+ | MCP SDK: FastMCP

---

## Table of Contents

1. [项目架构概述](#1-项目架构概述)
2. [模块职责说明](#2-模块职责说明)
3. [扩展接口说明](#3-扩展接口说明)
4. [测试方法与测试目录结构](#4-测试方法与测试目录结构)
5. [Blender 5.1.2 API 兼容性注意事项](#5-blender-512-api-兼容性注意事项)
6. [代码规范与贡献指南](#6-代码规范与贡献指南)
7. [调试方法](#7-调试方法)

---

## 1. 项目架构概述

Blender-MCP 采用 **MCP 层 + TCP 层** 的双层架构。MCP 侧运行在外部 Python 进程（通常是 Claude Desktop 或 MCP 客户端中），TCP 侧运行在 Blender 内部作为插件。

### 1.1 架构总览

```
+---------------------------------------------------------------+
|                      MCP Client (外部进程)                      |
|          (Claude Desktop / Cursor / 自定义客户端)               |
+--------------------------+------------------------------------+
                           |  MCP Protocol (JSON-RPC over SSE/stdio)
                           v
+---------------------------------------------------------------+
|                    MCP Server 层 (src/blender_mcp/)            |
|                                                               |
|   +-------------------------------------------------------+   |
|   |  server.py  — FastMCP 服务端                          |   |
|   |  - 31 MCP Tools (get_scene_info, create_box, ...)      |   |
|   |  - 1 MCP Prompt (asset_creation_strategy)              |   |
|   |  - BlenderConnection 管理 TCP 连接生命周期              |   |
|   |  - @telemetry_tool 装饰器注入遥测                        |   |
|   +---------------------------+---------------------------+   |
|                               |                             |   |
|   +---------------------------v---------------------------+   |
|   |  connection_recovery.py — 连接恢复 / 熔断器           |   |
|   |  - CircuitBreaker ( CLOSED -> OPEN -> HALF_OPEN )      |   |
|   |  - HealthMetrics, BlenderConnectionManager             |   |
|   +-------------------------------------------------------+   |
|                                                               |
|   +---------------------------+-------------------------------+   |
|   |  advanced_objects.py — 高级对象操作 API 封装               |   |
|   |  - BoundingBox, MaterialInfo, RenderSettings               |   |
|   |  - AdvancedObjectOperations (save, collection, render...)  |   |
|   +-----------------------------------------------------------+   |
|                                                               |
|   +-----------------------------------------------------------+   |
|   |  config_new.py — 集中化配置管理                             |   |
|   |  - ConnectionConfig / APIKeys / TelemetryConfig / Config   |   |
|   +-----------------------------------------------------------+   |
|                                                               |
|   +-----------------------------------------------------------+   |
|   |  telemetry.py / telemetry_decorator.py — 遥测              |   |
|   +-----------------------------------------------------------+   |
+---------------------------------------------------------------+
                           |  JSON over TCP (socket)
                           v
+---------------------------------------------------------------+
|                    TCP 服务端层 (addon.py, Blender 内部)       |
|                                                               |
|   +-------------------------------------------------------+   |
|   |  BlenderMCPServer                                      |   |
|   |  - socket.bind + listen(1)                              |   |
|   |  - _server_loop: accept -> 新线程 -> _handle_client     |   |
|   |  - _handle_client: 接收 JSON -> execute_command         |   |
|   |  - execute_command: 命令路由到内部 handler              |   |
|   +---------------------------+---------------------------+   |
|                               |                             |   |
|   +---------------------------v---------------------------+   |
|   |  Blender 内置 API 调用层 (bpy)                         |   |
|   |  - get_scene_info / get_object_info / get_viewport_    |   |
|   |    screenshot / execute_code                           |   |
|   |  - PolyHaven / Hyper3D(Rodin) / Sketchfab / Hunyuan3D  |   |
|   |  - Blender 5.x FCurves 兼容性层 (get_action_fcurves)   |   |
|   +-------------------------------------------------------+   |
|                                                               |
|   +-------------------------------------------------------+   |
|   |  Blender Addon UI 组件                                 |   |
|   |  - BLENDERMCP_AddonPreferences (Add-ons 设置面板)       |   |
|   |  - BLENDERMCP_PT_Panel (侧边栏面板)                    |   |
|   |  - BLENDERMCP_OT_StartServer / StopServer              |   |
|   +-------------------------------------------------------+   |
+---------------------------------------------------------------+
```

### 1.2 通信协议

MCP 层与 TCP 层之间使用 **JSON over TCP** 协议：

```
请求格式:
{
  "type": "<command_type>",
  "params": { ... }
}

响应格式 (成功):
{
  "status": "success",
  "result": { ... }
}

响应格式 (失败):
{
  "status": "error",
  "message": "Error description"
}
```

**默认端口**: 9876 (localhost)
**超时设置**: 180.0 秒
**数据编码**: UTF-8 JSON

### 1.3 数据流向

```
MCP Client
    |
    |-- [1] MCP Request (tool call)
    v
server.py 的 @mcp.tool() 函数
    |
    |-- [2] blender.send_command("command_type", params)
    v
BlenderConnection.send_command()
    |
    |-- [3] JSON 写入 TCP socket
    v
addon.py BlenderMCPServer._handle_client()
    |-- [4] json.loads() -> command dict
    |-- [5] execute_command(command) -> 路由到 handler
    |-- [6] handler(**params) -> 调用 bpy API
    |-- [7] 结果编码 JSON -> socket.sendall()
    v
响应回传 MCP Client
```

### 1.4 线程模型

```
Blender 进程:
  Main Thread (Blender GUI/事件循环)
    |-- bpy.app.timers.register(execute_wrapper)  <--- 所有 bpy 操作在此执行
    |
  Server Thread (addon.py 启动)
    |-- socket.listen() -> accept() -> _server_loop
    |
  Client Handler Thread (每个客户端一个)
    |-- socket.recv() -> json.loads() -> bpy.app.timers.register()

MCP Server 进程 (外部):
  asyncio event loop
    |-- 所有 tool 函数在 asyncio 上下文中调用
    |-- 通过同步 socket 与 Blender 通信
```

**关键规则**: 所有 `bpy` API 调用必须在 Blender 主线程执行，通过 `bpy.app.timers.register(execute_wrapper, first_interval=0.0)` 实现。

---

## 2. 模块职责说明

### 2.1 核心模块

#### addon.py (Blender 侧插件)

**位置**: `addon.py`
**行数**: 2763 行
**作用**: Blender 内置插件，实现 MCP 协议的 TCP 服务端。

```
addon.py 内部结构:
|-- Blender 5.x FCurves 兼容层 (L44-L105)
|   |-- get_action_fcurves(action)      -- 统一获取 FCurves (4.x/5.x)
|   |-- get_action_keyframe_count()     -- 统一统计关键帧数量
|
|-- BlenderMCPServer (L136-L365)
|   |-- __init__(host, port)
|   |-- start() / stop()                 -- TCP 服务器生命周期
|   |-- _server_loop()                   -- 接受连接 (后台线程)
|   |-- _handle_client()                 -- 处理客户端 JSON 请求
|   |-- execute_command()                -- 命令路由分发
|       |-- 基础 handlers (get_scene_info, execute_code, ...)
|       |-- PolyHaven handlers (条件启用)
|       |-- Hyper3D handlers (条件启用)
|       |-- Sketchfab handlers (条件启用)
|       |-- Hunyuan3D handlers (条件启用)
|
|-- 业务逻辑方法 (L368-L2570)
|   |-- get_scene_info()                 -- 场景信息
|   |-- get_object_info()                -- 对象详情
|   |-- get_viewport_screenshot()        -- 截图
|   |-- execute_code()                   -- 执行 Python 代码
|   |-- get_polyhaven_status()           -- PolyHaven 状态
|   |-- create_rodin_job() ...           -- Hyper3D 集成
|   |-- create_hunyuan_job() ...         -- Hunyuan3D 集成
|   |-- search_sketchfab_models() ...    -- Sketchfab 集成
|
|-- Blender Addon UI 组件 (L2500-L2763)
|   |-- BLENDERMCP_AddonPreferences      -- Add-ons 面板设置
|   |-- BLENDERMCP_PT_Panel              -- View3D 侧边栏面板
|   |-- BLENDERMCP_OT_StartServer        -- 启动按钮
|   |-- BLENDERMCP_OT_StopServer         -- 停止按钮
|   |-- BLENDERMCP_OT_SetFreeTrial...    -- 设置 API Key
|   |-- register() / unregister()        -- 插件注册入口
```

**关键特征**:
- 通过 `bpy.props` 注册 15+ 个场景属性（端口、开关、API Key 等）
- 所有 bpy 操作通过 `bpy.app.timers.register(..., first_interval=0.0)` 调度到主线程
- 支持条件启用集成 (PolyHaven / Hyper3D / Sketchfab / Hunyuan3D)
- 使用 `mathutils` 计算 AABB 包围盒

#### server.py (MCP 服务端)

**位置**: `src/blender_mcp/server.py`
**行数**: 1185 行
**作用**: FastMCP 服务端，提供 31 个 MCP Tools 给 AI 客户端调用。

```
server.py 内部结构:
|-- BlenderConnection (L30-L169)
|   |-- connect() / disconnect()
|   |-- receive_full_response()          -- 分块接收 + JSON 完整性检测
|   |-- send_command()                   -- 发送 JSON 命令，接收响应
|
|-- server_lifespan() (L172-L205)
|   |-- 启动: 记录遥测 + 预连接 Blender
|   |-- 关闭: 断开连接
|
|-- get_blender_connection() (L219-L251)
|   |-- 全局单例模式，连接失效时自动重建
|   |-- 首次连接时检测 PolyHaven 状态
|
|-- 31 MCP Tools (L254-L1086)
|   |-- 场景操作: get_scene_info, get_object_info
|   |-- 截图: get_viewport_screenshot
|   |-- 代码执行: execute_blender_code
|   |-- 对象创建: create_box, create_sphere, create_cylinder, ...
|   |-- 对象变换: move_object, rotate_object, scale_object, set_active_object
|   |-- 场景管理: add_material, clear_scene, set_view_camera
|   |-- 渲染: set_render_settings, render_scene
|   |-- 集成工具: get_polyhaven_categories, search_polyhaven_assets, ...
|   |-- Hyper3D: generate_hyper3d_model_via_text, generate_hyper3d_model_via_images, ...
|   |-- Hunyuan3D: generate_hunyuan3d_model, poll_hunyuan_job_status, ...
|   |-- 状态查询: get_hyper3d_status, get_sketchfab_status, get_hunyuan3d_status
|
|-- asset_creation_strategy() (L1089-L1177)
    |-- MCP Prompt: 定义资产创建策略指南
```

**工具注册模式**:

```python
@telemetry_tool("tool_name")
@mcp.tool()
def tool_function(ctx: Context, param1: str, param2: int = 0) -> str:
    """Tool description (用于 MCP 协议的 Tool 元数据)"""
    try:
        blender = get_blender_connection()
        result = blender.send_command("command_type", {"param1": param1, "param2": param2})
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"Error: {str(e)}"
```

#### advanced_objects.py (高级对象操作)

**位置**: `src/blender_mcp/advanced_objects.py`
**行数**: 2204 行
**作用**: 高级对象操作 API 封装，提供高级数据结构和使用方式。

```
数据结构:
|-- BoundingBox              -- AABB 包围盒 (width/height/depth/volume/center)
|-- MaterialInfo             -- 材质信息 (名称/节点数/颜色/metallic/roughness/纹理节点)
|-- RenderSettings           -- 渲染配置 (引擎/分辨率/FPS/帧范围/采样/输出格式)

类:
|-- AdvancedObjectOperations
    |-- save_scene(filepath)           -- 保存场景
    |-- load_scene(filepath)           -- 加载场景
    |-- create_collection(name)        -- 创建集合
    |-- set_render_settings(**kwargs)  -- 设置渲染参数
    |-- render_scene()                 -- 执行渲染
    |-- get_object_materials(obj_name) -- 获取对象材质
    |-- set_object_material(...)       -- 设置对象材质
    |-- get_scene_bounding_box()       -- 获取场景包围盒
    |-- batch_create_objects()         -- 批量创建对象
    |-- set_camera_view(obj_name)      -- 设置相机视角
```

**注意**: 此模块当前以 Stub 形式实现，主要用于数据模型定义和未来扩展。

#### config_new.py (配置管理)

**位置**: `src/blender_mcp/config_new.py`
**行数**: 223 行
**作用**: 集中化配置管理，支持文件 + 环境变量双重配置。

```
配置类:
|-- ConnectionConfig            -- TCP 连接配置
|   |-- host: "localhost"
|   |-- port: 9876
|   |-- timeout: 180.0
|   |-- max_retries: 3
|   |-- retry_delay: 1.0
|   |-- from_env()              -- 从环境变量加载
|
|-- APIKeys                     -- 第三方 API Key
|   |-- hyper3d_api_key / fal_api_key
|   |-- hunyuan3d_secret_id / secret_key
|   |-- polyhaven_api_key
|   |-- sketchfab_api_key
|   |-- supabase_url / anon_key
|
|-- TelemetryConfig             -- 遥测配置
|-- FeatureFlags                -- 功能开关
|-- BlenderConfig               -- 组合配置
|-- Config                      -- 顶层配置单例
```

**环境变量优先级**: 环境变量始终覆盖配置文件。

```bash
export BLENDER_HOST="192.168.1.100"
export BLENDER_PORT="9999"
export BLENDER_MCP_TIMEOUT="60.0"
export BLENDER_MCP_MAX_RETRIES="5"
export BLENDER_MCP_RETRY_DELAY="2.5"
export BLENDER_MCP_HYPER3D_API_KEY="your_key"
```

#### connection_recovery.py (连接恢复)

**位置**: `src/blender_mcp/connection_recovery.py`
**行数**: 426 行
**作用**: 自动重连、健康检查、熔断器模式。

```
类:
|-- CircuitState (Enum)
|   |-- CLOSED     -- 正常操作
|   |-- OPEN       -- 频繁失败，停止尝试
|   |-- HALF_OPEN  -- 测试服务是否恢复
|
|-- CircuitBreaker
|   |-- failure_threshold: 5       -- 触发熔断的失败次数
|   |-- recovery_timeout: 30.0     -- 恢复超时 (秒)
|   |-- record_success()
|   |-- record_failure()
|   |-- can_execute()              -- 检查是否允许执行
|
|-- HealthMetrics
|   |-- total_requests / success_count / failure_count
|   |-- avg_latency_ms / p99_latency_ms
|   |-- record_request(duration_ms, success)
|
|-- BlenderConnectionManager           -- 同步连接管理器
|-- AsyncBlenderConnectionManager      -- 异步连接管理器
|-- create_connection_manager()        -- 工厂函数
```

#### telemetry.py (遥测采集)

**位置**: `src/blender_mcp/telemetry.py`
**行数**: 342 行
**作用**: 匿名遥测数据采集，上报 Supabase。

```
事件类型:
|-- STARTUP / TOOL_EXECUTION / PROMPT_SENT / CONNECTION / ERROR

TelemetryCollector:
|-- _is_disabled()                     -- 通过环境变量禁用
|-- _get_or_create_uuid()              -- 持久化客户 UUID
|-- record_startup()                   -- 启动事件
|-- record_tool_usage()                -- 工具使用事件
|-- _send_event()                      -- 异步发送 (Supabase)
```

#### telemetry_decorator.py (遥测装饰器)

**位置**: `src/blender_mcp/telemetry_decorator.py`
**行数**: 65 行
**作用**: `@telemetry_tool("tool_name")` 装饰器，自动记录工具调用耗时和状态。

### 2.2 入口文件

#### main.py

**位置**: `main.py`
**行数**: 8 行
**作用**: 程序入口，调用 `server_main()`。

### 2.3 工具脚本

| 文件 | 作用 |
|------|------|
| `scripts/project_analyzer.py` | 项目分析工具 |
| `scripts/check_blender_512_compatibility.py` | Blender 5.1.2 兼容性静态扫描 |
| `scripts/check_compatibility.py` | 通用兼容性检查 |

---

## 3. 扩展接口说明

### 3.1 添加新工具 (MCP 层)

在 `src/blender_mcp/server.py` 中按以下模式添加：

```python
# 1. 在 server.py 末尾添加新工具函数
@telemetry_tool("my_new_tool")     # 遥测装饰器 (可选但推荐)
@mcp.tool()
def my_new_tool(
    ctx: Context,
    param1: str,              # 参数描述由 docstring 提供
    param2: int = 0,          # 有默认值的参数
) -> str:
    """
    Tool 描述 (出现在 MCP 协议的 tool 元数据中)

    Parameters:
    - param1: 参数1的描述
    - param2: 参数2的描述 (默认: 0)

    Returns: 返回字符串结果
    """
    try:
        blender = get_blender_connection()
        # 如果 Blender 侧已有 handler，直接转发:
        result = blender.send_command("my_new_command", {
            "param1": param1,
            "param2": param2,
        })
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in my_new_tool: {str(e)}")
        return f"Error: {str(e)}"
```

**如果 Blender 侧也需要新 handler**，在 `addon.py` 的 `BlenderMCPServer` 类中添加：

```python
# 2. 在 execute_command() 的 handlers 字典中添加
def _execute_command_internal(self, command):
    cmd_type = command.get("type")
    params = command.get("params", {})

    handlers = {
        # ... 现有 handlers ...
        "my_new_command": self.my_new_blender_handler,  # 新增
    }

    handler = handlers.get(cmd_type)
    if handler:
        result = handler(**params)
        return {"status": "success", "result": result}
```

### 3.2 添加新工具 (Blender 侧 — 独立方法)

```python
# 在 BlenderMCPServer 类中添加:
def my_new_blender_handler(self, param1: str, param2: int = 0):
    """Handler 实际逻辑，所有 bpy API 调用在此执行"""
    try:
        # 所有 bpy 操作
        obj = bpy.data.objects.new(param1, None)
        bpy.context.scene.collection.objects.link(obj)

        return {
            "created": True,
            "object_name": param1,
            "param2": param2,
        }
    except Exception as e:
        print(f"Error in my_new_blender_handler: {str(e)}")
        raise
```

### 3.3 条件启用集成 (如 Hyper3D / PolyHaven)

```python
# Blender 侧 (addon.py):
if bpy.context.scene.blendermcp_use_hyper3d:
    handlers.update({
        "my_hyper3d_feature": self.my_hyper3d_handler,
    })

# MCP 侧 (server.py):
@telemetry_tool("my_hyper3d_feature")
@mcp.tool()
def my_hyper3d_feature(ctx: Context, ...) -> str:
    try:
        blender = get_blender_connection()
        result = blender.send_command("my_hyper3d_feature", {...})
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"
```

### 3.4 扩展 addon.py

#### 3.4.1 添加新的 Scene 属性

```python
# 在 register() 中添加 (L2500+):
bpy.types.Scene.blendermcp_my_new_flag = bpy.props.BoolProperty(
    name="My New Flag",
    description="Enable my new feature",
    default=False,
)
```

#### 3.4.2 添加新的 Operator

```python
class BLENDERMCP_OT_MyNewOperator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "blendermcp.my_new_operator"
    bl_label = "My New Operator"

    def execute(self, context):
        # 业务逻辑
        self.report({'INFO'}, "Done!")
        return {'FINISHED'}
```

然后在 `register()` / `unregister()` 中注册/注销。

#### 3.4.3 添加新的 Panel

```python
class BLENDERMCP_PT_MyPanel(bpy.types.Panel):
    bl_label = "My Panel"
    bl_idname = "BLENDERMCP_PT_MY_PANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'       # Blender 5.x 使用 WINDOW 而非 UI
    bl_category = "BlenderMCP"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        row.prop(scene, "blendermcp_my_new_flag")
```

### 3.5 扩展 advanced_objects.py

在 `AdvancedObjectOperations` 类中添加新方法：

```python
class AdvancedObjectOperations:
    # ... 现有方法 ...

    def my_new_operation(self, obj_name: str) -> Dict[str, Any]:
        """New high-level operation."""
        import bpy
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            raise ValueError(f"Object not found: {obj_name}")

        # 业务逻辑
        return {"status": "ok", "object": obj_name}
```

---

## 4. 测试方法与测试目录结构

### 4.1 测试目录结构

```
tests/
|-- __init__.py
|-- test_config.py                  -- Config 模块单元测试 (ConnectionConfig, APIKeys, ...)
|-- test_advanced_objects.py        -- AdvancedObjectOperations 数据模型测试 (BoundingBox, MaterialInfo, ...)
|-- test_connection_recovery.py     -- 连接恢复模块测试 (CircuitBreaker, HealthMetrics, ...)
|-- test_fcurves_compatibility.py   -- Blender 5.x FCurves 兼容性层测试
|-- test_advanced_batch_render_import.py  -- 高级批量渲染导入测试
|-- fix_tests.py                    -- 测试修复脚本
|
|-- runtime/                        -- 需要在 Blender 中运行的集成测试
    |-- test_runner.py              -- 回归测试运行器 (阶段4)
    |-- main_test_runner.py         -- 主测试入口
    |-- run_tests.py                -- 测试执行脚本
    |-- generate_reports.py         -- 测试报告生成
    |-- test1_create_objects.py     -- 阶段1: 对象创建 (Cube, Sphere, Collection, Parent)
    |-- test2_material_system.py    -- 阶段2: 材质系统
    |-- test3_animation_system.py   -- 阶段3: 动画系统
    |-- test4_render_system.py      -- 阶段4: 渲染系统
    |-- test5_import_export.py      -- 阶段5: 导入导出
    |-- test6_mcp_communication.py  -- 阶段6: MCP 通信
    |-- test7_stress_test.py        -- 阶段7: 压力测试
```

### 4.2 测试类型

| 类型 | 位置 | 要求 | 运行方式 |
|------|------|------|----------|
| **单元测试** | `tests/*.py` | 无需 Blender | `python -m pytest tests/ -v` |
| **集成测试** | `tests/runtime/test*.py` | 需要 Blender 5.1.2 | `blender -b --python test_*.py` |
| **回归测试** | `tests/runtime/test_runner.py` | 需要 Blender | `python tests/runtime/test_runner.py` |

### 4.3 运行测试

```bash
# 运行所有单元测试 (157 tests)
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_config.py -v
python -m pytest tests/test_connection_recovery.py -v
python -m pytest tests/test_advanced_objects.py -v
python -m pytest tests/test_fcurves_compatibility.py -v

# 运行特定类
python -m pytest tests/test_config.py::TestConnectionConfig -v

# 运行特定方法
python -m pytest tests/test_config.py::TestConnectionConfig::test_default_values -v

# 带覆盖率
python -m pytest tests/ -v --cov=blender_mcp --cov-report=term-missing

# 过滤失败用例
python -m pytest tests/ -v --tb=short
```

### 4.4 单元测试示例

```python
# test_config.py 示例: 测试环境变量加载
def test_from_env_custom_values(self):
    with patch.dict(os.environ, {
        "BLENDER_HOST": "192.168.1.100",
        "BLENDER_PORT": "9999",
        "BLENDER_MCP_TIMEOUT": "60.0",
    }):
        cfg = ConnectionConfig.from_env()
        assert cfg.host == "192.168.1.100"
        assert cfg.port == 9999
        assert cfg.timeout == 60.0
```

```python
# test_connection_recovery.py 示例: 测试熔断器
def test_opens_after_threshold(self):
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.current_state == CircuitState.CLOSED   # 未达阈值
    cb.record_failure()
    assert cb.current_state == CircuitState.OPEN     # 达到阈值，熔断
```

```python
# test_fcurves_compatibility.py 示例: FCurves 兼容性 (纯 Python mock)
class TestFCurvesCompatibility:
    def test_legacy_fcurves_access(self):
        """Blender 4.x: action.fcurves 直接访问"""
        fake_action = MockFCurveAction()
        fake_action._fcurves = [_FakeFCurve("location", 0, 5)]
        assert len(get_action_fcurves(fake_action)) == 5
```

---

## 5. Blender 5.1.2 API 兼容性注意事项

### 5.1 已识别的兼容性问题

基于 `scripts/check_blender_512_compatibility.py` 的静态扫描结果：

```
Total: 43 issues
CRITICAL: 0  ERROR: 0
WARNING: 4   INFO: 39
```

### 5.2 WARNING 项 (4 项)

| # | 位置 | 问题 | 修复方案 |
|---|------|------|----------|
| 1 | `addon.py:2365` | `bl_region_type = 'UI'` 已弃用 | 改为 `bl_region_type = 'WINDOW'` |
| 2 | `addon.py:774` | `bpy.ops.import_scene.obj()` 已弃用 | 添加版本检查 (参考 L2286 行) |
| 3 | `addon.py:2289` | `bpy.ops.import_scene.obj()` 已弃用 | 同上 |
| 4 | `addon.py:1976` | `datetime.utcfromtimestamp()` 在 Python 3.12+ 弃用 | 改为 `datetime.fromtimestamp(ts, tz=timezone.utc)` |

### 5.3 Blender 5.x FCurves 兼容层

Blender 5.1+ 中 `action.fcurves` 被移除，替换为分层结构：

```python
# Blender 4.x 旧路径:
#   action.fcurves  -> list of FCurve objects

# Blender 5.x+ 新路径:
#   action.layers[0].strips[0].channelbags[0].fcurves

# 项目统一兼容层 (addon.py L57-L104):
def get_action_fcurves(action):
    """统一获取 FCurves，兼容 4.x 和 5.x+"""
    if action is None:
        return []

    # 先尝试旧路径
    try:
        legacy = action.fcurves
        if hasattr(legacy, "__iter__"):
            return list(legacy)
    except AttributeError:
        pass

    # 再尝试新路径
    try:
        bags = action.layers[0].strips[0].channelbags[0].fcurves
        if bags:
            return list(bags)
    except (AttributeError, IndexError, TypeError):
        pass

    return []
```

### 5.4 Blender 5.x Panel 区域类型

```python
# Blender 4.x (旧):
class MyPanel(bpy.types.Panel):
    bl_region_type = 'UI'    # 已弃用

# Blender 5.x (新):
class MyPanel(bpy.types.Panel):
    bl_region_type = 'WINDOW'  # 推荐
```

### 5.5 Python 3.13 兼容性

```python
# 旧 (Python 3.12+ 弃用):
ts = datetime.utcfromtimestamp(epoch)

# 新 (推荐):
from datetime import datetime, timezone
ts = datetime.fromtimestamp(epoch, tz=timezone.utc)
```

### 5.6 无破坏性变更的 API

以下 Blender API 在 5.1.2 中保持向后兼容:
- `bpy.props` (IntProperty, BoolProperty, StringProperty, EnumProperty)
- `bpy.types.Operator` / `bpy.types.Panel` / `bpy.types.AddonPreferences`
- `bpy.data.objects` / `bpy.data.materials` / `bpy.data.collections`
- `bpy.ops.import_scene.gltf` / `bpy.ops.export_scene.gltf`
- `bpy.app.timers.register()`
- Addon 注册机制 (`register()` / `unregister()`)

---

## 6. 代码规范与贡献指南

### 6.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `config_new.py`, `connection_recovery.py` |
| 类 | PascalCase | `BlenderMCPServer`, `CircuitBreaker` |
| 函数 | snake_case | `get_action_fcurves()`, `send_command()` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_HOST`, `DEFAULT_PORT` |
| 私有方法 | 下划线前缀 | `_execute_command_internal()` |
| 场景属性 | blendermcp_ 前缀 | `blendermcp_use_polyhaven` |
| Operator ID | blendermcp_ 前缀 | `blendermcp.my_new_operator` |

### 6.2 文档规范

每个模块/类/函数必须有 docstring:

```python
def my_function(param1: str, param2: int = 0) -> str:
    """
    函数描述 (一行)

    详细说明 (可选)。

    Parameters
    ----------
    param1 : str
        参数1的描述
    param2 : int, optional
        参数2的描述 (默认: 0)

    Returns
    -------
    str
        返回值的描述

    Raises
    ------
    ValueError
        当...时抛出
    """
```

### 6.3 错误处理

```python
# 推荐: 记录 + 抛出/返回错误
try:
    result = blender.send_command("command", params)
    return json.dumps(result, indent=2)
except Exception as e:
    logger.error(f"Error in my_tool: {str(e)}")
    return f"Error: {str(e)}"

# 禁止: 静默吞掉异常
# except Exception:
#     pass
```

### 6.4 日志规范

```python
import logging
logger = logging.getLogger("blender-mcp.module_name")

logger.info("操作成功")
logger.warning("可能的非致命问题")
logger.error("操作失败", exc_info=True)  # 包含堆栈
logger.debug("调试信息")
```

### 6.5 配置管理规范

1. **禁止**将 `config.py` 提交到版本控制 (包含 API Key)
2. **使用** `config.py.example` 作为模板
3. **优先**使用环境变量覆盖:

```bash
export BLENDER_MCP_HYPER3D_API_KEY="your_key"
```

4. Blender 侧配置存储在 `bpy.types.Scene.blendermcp_*` 属性中

### 6.6 线程安全规范

```python
# 在 Blender 主线程执行 bpy 操作
def execute_wrapper():
    # 所有 bpy API 调用在此
    obj = bpy.data.objects.new("MyObject", None)
    bpy.context.scene.collection.objects.link(obj)
    return None  # 必须返回 None

bpy.app.timers.register(execute_wrapper, first_interval=0.0)
```

**关键规则**: 绝不允许在非主线程直接调用 bpy API。

### 6.7 提交规范

```
feat: 添加 create_cylinder 工具
fix: 修复 Blender 5.x FCurves 访问错误
docs: 更新开发者指南
test: 添加连接恢复单元测试
refactor: 重组 server.py 工具注册
perf: 优化 JSON 响应解析
```

---

## 7. 调试方法

### 7.1 Blender 端调试

#### 7.1.1 控制台输出

Blender 的 Python 控制台 (Toggle Console: `Window -> Toggle System Console`):

```
在 addon.py 中添加:
print(f"[DEBUG] Received command: {command}")
print(f"[DEBUG] Handler result: {result}")
```

#### 7.1.2 使用 logging 模块

```python
import logging
logger = logging.getLogger("blender-mcp.addon")

logger.info("Handler started")
logger.debug(f"Params: {params}")
logger.error(f"Error: {str(e)}", exc_info=True)
```

#### 7.1.3 使用 breakpoint()

```python
def my_handler(self, param1):
    breakpoint()  # Python 3.7+, 进入 pdb
    # 或使用 traceback
    import traceback
    traceback.print_exc()
```

### 7.2 MCP 端调试

#### 7.2.1 日志配置

```python
# server.py 已配置:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BlenderMCPServer")

# 提升日志级别到 DEBUG:
logger.setLevel(logging.DEBUG)
```

#### 7.2.2 手动 TCP 调试

使用 `nc` (Netcat) 或 `telnet` 直接连接 Blender TCP 端口:

```bash
# Linux/macOS:
echo '{"type":"get_scene_info","params":{}}' | nc localhost 9876

# Windows (PowerShell):
echo '{"type":"get_scene_info","params":{}}' | nc -w 5 localhost 9876

# 或使用 Python:
python -c "
import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 9876))
s.sendall(json.dumps({'type': 'get_scene_info', 'params': {}}).encode())
print(s.recv(8192).decode())
s.close()
"
```

#### 7.2.3 MCP 调试工具

```bash
# 使用 mcp-inspector 调试 MCP 协议
npx @modelcontextprotocol/inspector

# 直接运行 server.py 测试
cd src/blender_mcp
python -m server

# 或使用 main.py
cd ..
python main.py
```

### 7.3 连接问题排查

```
问题: MCP Server 无法连接 Blender
排查步骤:

1. 确认 Blender 已启动且插件已加载
   - 在 Blender 侧边栏查看 BlenderMCP 面板
   - 确认 "Server Running" 状态为 True
   - 检查控制台输出 "BlenderMCP server started on localhost:9876"

2. 确认端口可访问
   - 检查防火墙设置
   - 尝试 nc localhost 9876

3. 确认环境变量
   - 检查 BLENDER_HOST / BLENDER_PORT 设置

4. 查看日志
   - MCP 侧: logging 输出
   - Blender 侧: System Console
```

### 7.4 常见问题排查表

| 症状 | 可能原因 | 解决方法 |
|------|----------|----------|
| `Connection refused` | Blender 未启动插件 | 在 Blender 中启用插件并点击 Start |
| `Timeout waiting for response` | 操作耗时过长 | 简化请求 / 增加 timeout |
| `Invalid JSON response` | Blender 侧异常 | 检查 Blender System Console |
| `Unknown command type` | MCP 工具未注册对应 handler | 在 addon.py handlers 字典中添加 |
| `bpy 属性不存在` | 版本兼容性 | 使用 `hasattr()` 检查或兼容层 |
| 面板不显示 | `bl_region_type = 'UI'` 已弃用 | 改为 `'WINDOW'` |

### 7.5 性能调试

```python
# 添加耗时测量
import time

def timed_handler(self, param):
    start = time.time()
    try:
        result = self._do_work(param)
        return result
    finally:
        elapsed = time.time() - start
        logger.info(f"[PERF] Handler took {elapsed:.3f}s")

# 监控连接健康
from blender_mcp.connection_recovery import HealthMetrics
metrics = HealthMetrics()
metrics.record_request(elapsed * 1000, success=True)
```

### 7.6 测试环境搭建

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行单元测试
python -m pytest tests/ -v

# 3. 检查兼容性
python scripts/check_blender_512_compatibility.py

# 4. 运行回归测试 (需要 Blender)
python tests/runtime/test_runner.py
```

---

## 附录 A: 项目文件索引

```
blender-mcp-main/
|-- addon.py                        -- Blender 侧插件 (2763 行)
|-- main.py                         -- 入口点 (8 行)
|
|-- src/blender_mcp/
|   |-- __init__.py                 -- 包入口，版本 0.1.0
|   |-- server.py                   -- MCP 服务端 (1185 行, 31 tools)
|   |-- advanced_objects.py         -- 高级对象操作 API (2204 行)
|   |-- config_new.py               -- 配置管理 (223 行)
|   |-- connection_recovery.py      -- 连接恢复/熔断器 (426 行)
|   |-- telemetry.py                -- 遥测采集 (342 行)
|   |-- telemetry_decorator.py      -- 遥测装饰器 (65 行)
|
|-- tests/
|   |-- test_config.py              -- Config 测试 (231 行)
|   |-- test_advanced_objects.py    -- Advanced Objects 测试 (336 行)
|   |-- test_connection_recovery.py -- 连接恢复测试 (258 行)
|   |-- test_fcurves_compatibility.py -- FCurves 兼容性测试 (335 行)
|   |-- test_advanced_batch_render_import.py -- 批量渲染测试
|   |-- runtime/                    -- 运行时集成测试 (7 个 test_*.py)
|
|-- docs/
|   |-- DEVELOPER_GUIDE.md          -- 本文档
|   |-- USER_GUIDE.md               -- 用户指南
|   |-- API_DOCUMENTATION.md        -- API 文档
|   |-- COMPATIBILITY_BLENDER_5_1_2.md -- 兼容性说明
|   |-- PERFORMANCE_REPORT.md       -- 性能报告
|
|-- scripts/
|   |-- check_blender_512_compatibility.py -- 兼容性扫描
|   |-- check_compatibility.py      -- 通用检查
|   |-- project_analyzer.py         -- 项目分析
```

## 附录 B: 默认配置速查

| 配置项 | 默认值 | 环境变量 |
|--------|--------|----------|
| 主机 | `localhost` | `BLENDER_HOST` |
| 端口 | `9876` | `BLENDER_PORT` |
| 超时 | `180.0s` | `BLENDER_MCP_TIMEOUT` |
| 最大重试 | `3` | `BLENDER_MCP_MAX_RETRIES` |
| 重试延迟 | `1.0s` | `BLENDER_MCP_RETRY_DELAY` |
| Hyper3D 模式 | `MAIN_SITE` | 无 (通过 UI 设置) |
| 遥测 | 启用 (可禁用) | `BLENDER_MCP_TELEMETRY_DISABLED` |
