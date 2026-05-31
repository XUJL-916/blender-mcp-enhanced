# Blender-MCP Enhanced

<!-- Logo -->
<p align="center">
  <img src="assets/logo.svg" alt="Blender-MCP Enhanced Logo" width="700">
</p>

> **版本**: 1.5.5-enh | **迭代日期**: 2026-06-01 | **Target Blender**: 5.1.2 | **Python**: 3.13 | **状态**: CONDITIONAL PASS | **作者**: XUJL | Shenzhen University (SZU)

---

## 🚀 概述

Blender-MCP Enhanced 是在 [Siddharth Ahuja](https://github.com/ahujasid/blender-mcp) 开源项目 **blender-mcp** 基础上开发的完整增强版本。在保留原始 MCP 协议桥接能力的前提下，本项目对配置管理、连接可靠性、高级对象操作、渲染自动化、资产导入/导出、场景快照以及测试覆盖等核心领域进行了系统性扩展和重构。

本项目定位为 **Blender 与 Hermes/Claude AI 之间的中介插件** — 通过 Model Context Protocol (MCP) 将 AI 代理与 Blender 的 bpy API 解耦，使 AI 代理（如 Claude、Hermes Agent）能够通过标准化的 MCP 工具协议，在 Blender 中完成从场景搭建、材质编辑、动画制作到渲染输出的完整 3D 创作流程自动化。

### 🔗 快速链接

| 资源 | 链接 |
|------|------|
| 原始项目 | [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) |
| 本仓库 | 本仓库 (1.5.5-enh) |
| 📐 架构流程图 | [Excalidraw — Architecture](https://excalidraw.com/#json=zIvTDiyrpYaAK85fSsdr0,odzXSNVxzsSV9nPW26Aw0Q) |
| 🔄 使用流程图 | [Excalidraw — Usage Flow](https://excalidraw.com/#json=PE0XOJtDUczYBDY7aH__s,S_pb4fqdOhm-9KJS6RSxuw) |

---

### 🖼️ 演示

![Blender-MCP 演示场景](assets/demo_scene.png)

_上图：由 Blender-MCP 自动创建的 3D 场景 — 三点布光、Principled BSDF 材质、EEVEE 引擎渲染_

---

## 🏗️ 架构概览

```
[AI Client: Claude / Cursor / VS Code / Hermes Agent]
           │  MCP (stdio, uvx blender-mcp)
           ▼
[src/blender_mcp/server.py]     ← FastMCP 工具定义层 (31 tools)
           │  TCP Socket (JSON, localhost:9876)
           ▼
[addon.py]                       ← Blender 内部插件层 (2668 行)
           │  bpy API
           ▼
[Blender 5.1.2 场景引擎]
```

**两层通信**: MCP 层 (stdio) 与 TCP 层 (JSON) 解耦，AI 客户端不直接操作 Blender。

📊 [查看交互式架构图 →](https://excalidraw.com/#json=zIvTDiyrpYaAK85fSsdr0,odzXSNVxzsSV9nPW26Aw0Q)

---

## ✨ 核心功能模块

| # | 模块 | 方法数 | 状态 |
|---|------|--------|------|
| 1 | 高级对象操作 (创建/变换/查询/批量) | 50+ | ✅ 已实现 |
| 2 | 材质与节点编辑器 (Principled BSDF/纹理/节点树) | 30+ | ✅ 已实现 |
| 3 | 动画与关键帧 (FBX/OBJ/GLB 导入导出) | 15+ | ✅ 已实现 |
| 4 | 渲染与场景快照 (Eevee/Cycles/多视角) | 15+ | ✅ 已实现 |
| 5 | 数据导入/导出 (FBX/OBJ/GLB/STL/Blend/CSV) | 13 | ✅ 已实现 |
| 6 | 连接恢复机制 (电路断路器+自动重连) | 6 | ✅ 已实现 |
| 7 | 外部资产 (PolyHaven/Sketchfab/Hyper3D/Hunyuan3D) | 15+ | ✅ 已实现 |

**代码统计**: 约 6,851 行 Python，385 方法 / 64 函数 / 41 类。

---

## 🚀 快速开始

### 前置要求

- Blender 5.1.2 (已验证, 向后兼容 4.x)
- Python 3.13+ (Blender 内置 Python)
- uv 包管理器

### 安装

```bash
# 1. 安装 uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. 安装项目
cd blender-mcp-main
uv venv
uv pip install -p .venv/Scripts/python.exe -e .

# 3. 启动 MCP 服务
uvx blender-mcp
```

### 配置 Claude Desktop

编辑 `claude_desktop_config.json`：

```json
{
    "mcpServers": {
        "blender": {
            "command": "uvx",
            "args": ["blender-mcp"]
        }
    }
}
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BLENDER_HOST` | localhost | Socket 地址 |
| `BLENDER_PORT` | 9876 | Socket 端口 |
| `DISABLE_TELEMETRY` | (未设置) | 完全关闭遥测 |
| `HYPER3D_API_KEY` | (未设置) | Hyper3D API 密钥 |
| `HUNYUAN3D_SECRET_ID` | (未设置) | Hunyuan3D API 密钥 |

详细配置见 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)

---

## 📖 如何使用

### 一、完整使用流程（从零开始）

📊 [查看交互式使用流程图 →](https://excalidraw.com/#json=PE0XOJtDUczYBDY7aH__s,S_pb4fqdOhm-9KJS6RSxuw)

```
第 1 步: 安装 uv 包管理器          → 一行命令搞定
第 2 步: 安装项目依赖               → uv venv + pip install
第 3 步: 安装 Blender 插件          → addon.py 拖入 Blender
第 4 步: 启动 MCP 服务             → uvx blender-mcp
第 5 步: Blender 中点击连接         → N 侧边栏 → "Connect to Claude"
第 6 步: 用 AI 客户端发送指令       → 自然语言操作 3D 场景
```

### 二、逐步详解

#### 步骤 1: 安装 uv

```powershell
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

验证：
```bash
uv --version
# 应输出类似: uv 0.x.x
```

#### 步骤 2: 安装项目

```bash
cd blender-mcp-main
uv venv
uv pip install -p .venv/Scripts/python.exe -e .
# macOS / Linux: uv pip install -p .venv/bin/python -e .
```

如遇网络超时，使用国内镜像：
```bash
uv pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -e .
```

#### 步骤 3: 安装 Blender 插件

1. 打开 Blender（推荐 5.1.2）
2. **Edit > Preferences > Add-ons**
3. 点击 **Install...**
4. 选择项目根目录的 `addon.py`
5. 搜索 "Blender MCP"，**勾选启用**
6. 关闭 Preferences（设置自动保存）

> addon.py 约 2668 行，是 Blender 侧的核心插件，负责执行 3D 场景操作。

#### 步骤 4: 启动 MCP 服务

打开**新终端**，进入项目目录：
```bash
cd blender-mcp-main
uvx blender-mcp
```

看到 `Blender-MCP server running on localhost:9876` 表示启动成功。

**重要**: MCP 服务必须与 Blender 同时运行，但请先启动 Blender 并加载插件，再启动 MCP 服务。

#### 步骤 5: 在 Blender 中连接

1. Blender 按 **N 键** 打开侧边栏
2. 找到 **"Blender-MCP"** 标签页
3. 点击 **"Connect to Claude"** 按钮
4. 看到绿色状态提示 = 连接成功

#### 步骤 6: 用 AI 客户端操作 Blender

配置你的 AI 客户端（如 Claude Desktop、Hermes Agent、VS Code），然后通过自然语言指令操作 Blender。

### 三、AI 客户端配置

#### Claude Desktop

编辑 `claude_desktop_config.json`：
```json
{
    "mcpServers": {
        "blender": {
            "command": "uvx",
            "args": ["blender-mcp"]
        }
    }
}
```

Windows 路径通常为 `C:\Users\admin\AppData\Local\Claude\claude_desktop_config.json`

#### Hermes Agent

在 Hermes Agent 会话中直接使用 `terminal` 工具：
```
# 启动 MCP 服务
终端运行: uvx blender-mcp

# 然后通过其他工具调用 Blender 操作
```

#### VS Code / Cursor

在扩展配置中添加 MCP server 配置，同上 JSON 格式。

### 四、常用操作示例

#### 创建场景

```
创建 3 个立方体，排成一行
添加一个球体在中间
设置三点布光
添加相机对准场景
```

#### 材质编辑

```
给所有物体创建金属材质，颜色为红色，粗糙度 0.3
加载 texture.jpg 作为地面纹理
```

#### 渲染

```
使用 Eevee 引擎渲染当前场景
设置输出路径为 D:/renders
分辨率 1920x1080
```

#### 导入导出

```
导入 D:/models/character.fbx
导出当前场景为 output.glb
```

### 五、验证安装

#### 检查安装状态

```bash
# 1. uv 安装
uv --version

# 2. 项目依赖
python -c "import blender_mcp; print('OK')"

# 3. MCP 服务
uvx blender-mcp  # 应启动无报错

# 4. 一键测试
powershell scripts/run_all_tests.ps1
```

#### 检查连接

1. Blender 侧：侧边栏显示绿色连接状态
2. MCP 侧：终端显示 server running
3. AI 客户端：可以调用 Blender 相关工具

### 六、环境变量配置

```bash
# 临时设置（当前终端）
set BLENDER_PORT=9876
set DISABLE_TELEMETRY=true

# 永久设置（Windows）
[System.Environment]::SetEnvironmentVariable("BLENDER_PORT", "9876", "Machine")

# macOS / Linux
export BLENDER_PORT=9876
export DISABLE_TELEMETRY=true
```

常用变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| BLENDER_HOST | localhost | Socket 地址 |
| BLENDER_PORT | 9876 | Socket 端口 |
| DISABLE_TELEMETRY | (空) | 关闭遥测 |
| HYPER3D_API_KEY | (空) | Hyper3D 模型生成 |
| HUNYUAN3D_SECRET_ID | (空) | 混元 3D 生成 |

详细见 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)。

---

## ✅ 测试状态

| 类别 | 测试数 | 通过 | 失败 | 跳过 |
|------|--------|------|------|------|
| 单元测试 | 157 | 155 | 0 | 2 |
| Runtime Test (已执行) | 3 | 3 | 0 | 0 |
| 兼容性检查 | 42 | 42 | 0 | 0 |

```bash
# 运行全部测试
python -m pytest tests/ -v

# Blender Runtime 测试
powershell scripts/run_blender_runtime_tests.ps1

# 一键测试 (单元测试 + 兼容性 + 项目分析)
powershell scripts/run_all_tests.ps1
```

---

## 📚 文档导航

| 文档 | 说明 |
|------|------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 用户安装、配置、启动指南 |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | 架构、模块、扩展、测试 |
| [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) | 完整 API 文档 (853 行) |
| [docs/HERMES_USAGE_EXAMPLES.md](docs/HERMES_USAGE_EXAMPLES.md) | Hermes Agent 调用示例 |
| [docs/ACCEPTANCE_TEST_PLAN.md](docs/ACCEPTANCE_TEST_PLAN.md) | 验收测试计划 |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | 常见问题与故障排除 |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 开发迭代记录与功能状态 |

---

## 🔒 安全说明

- `execute_blender_code` 允许执行任意 Python 代码，生产环境请谨慎使用
- Poly Haven 集成会下载模型文件，可在 Blender Addon 中关闭
- 遥测完全匿名，`DISABLE_TELEMETRY=true` 可完全关闭

---

## 📜 许可证

本项目基于原始 blender-mcp 项目 (MIT 许可证) 扩展开发。原始项目由 [Siddharth Ahuja](https://x.com/sidahuj) 创建。

---

## ⚠️ 免责声明

本项目为第三方集成，与 Blender 官方无关联。
