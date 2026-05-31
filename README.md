# Blender-MCP Enhanced

> **版本**: 1.5.5-enh | **迭代日期**: 2026-06-01 | **Target**: Blender 5.1.2 | **Python**: 3.13 | **作者**: XUJL | Shenzhen University (SZU)

---

<!-- Logo -->
<p align="center">
  <img src="assets/logo.svg" alt="Blender-MCP Enhanced Logo" width="700">
</p>

<p align="center">
  <a href="https://github.com/XUJL-916/blender-mcp-enhanced">
    <img src="https://img.shields.io/github/v/release/XUJL-916/blender-mcp-enhanced?style=flat-square&color=22d3ee" alt="Version">
  </a>
  <a href="https://github.com/XUJL-916/blender-mcp-enhanced/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  </a>
  <a href="https://github.com/XUJL-916/blender-mcp-enhanced/stargazers">
    <img src="https://img.shields.io/github/stars/XUJL-916/blender-mcp-enhanced?style=flat-square&color=f59e0b" alt="Stars">
  </a>
  <a href="https://github.com/XUJL-916/blender-mcp-enhanced/pulse">
    <img src="https://img.shields.io/github/commit-activity/m/XUJL-916/blender-mcp-enhanced?style=flat-square&color=8b5cf6" alt="Commits">
  </a>
</p>

---

## 🚀 概述

Blender-MCP Enhanced 是在 [Siddharth Ahuja](https://github.com/ahujasid/blender-mcp) 开源项目 **blender-mcp** 基础上开发的完整增强版本。在保留原始 MCP 协议桥接能力的前提下，本项目对配置管理、连接可靠性、高级对象操作、渲染自动化、资产导入/导出、场景快照以及测试覆盖等核心领域进行了系统性扩展和重构。

本项目定位为 **Blender 与 AI Agent（Hermes/Claude/Cursor/VSCoode）之间的中介插件** — 通过 Model Context Protocol (MCP) 将 AI 代理与 Blender 的 bpy API 解耦，使 AI 代理能够通过标准化的 MCP 工具协议，在 Blender 中完成从场景搭建、材质编辑、动画制作到渲染输出的完整 3D 创作流程自动化。

| 维度 | 原始项目 | 本增强版 |
|------|----------|----------|
| MCP 工具数 | ~8 | **31**（覆盖创建、材质、动画、渲染、导入导出） |
| 连接可靠性 | 基础 TCP | **电路断路器 + 自动重连 + 健康检查** |
| 配置管理 | 无 | **完整配置模型 + 环境变量覆盖 + 密钥管理** |
| 测试覆盖 | 无 | **157 个单元测试（155 通过）+ 兼容性静态检查** |
| 兼容性适配 | Blender 3.x | **Blender 5.1.2 + 3.x 向后兼容** |
| 文档 | 基础 | **7 篇专业文档 + Release Checklist** |

---

## 📸 演示

### 对象创建与场景搭建
![对象创建](assets/readme_feature_1_object_creation.png)
_多类型几何体（Torus、Icosphere、Cubes、Cylinder）— Principled BSDF 材质、三点布光、EEVEE 渲染_

### PBR 材质系统
![材质系统](assets/readme_feature_2_material_system.png)
_Glossy / Metallic / Rubber / Glass / Plastic — 完整的 Physically Based Rendering 演示_

### 动画关键帧
![动画系统](assets/readme_feature_3_animation.png)
_轨道运动系统 — 4 颗行星绕中心球体旋转，关键帧驱动 FCurves_

### 系统架构
![架构可视化](assets/readme_feature_4_architecture.png)
_AI Client → MCP Server → Blender Addon → BPy API → Blender Engine 五层架构_

---

## ⚡ 快速开始

**3 分钟安装 + 5 分钟第一次运行**

### 前置要求

- **Blender 5.1.2**（推荐）或 4.x — [下载](https://www.blender.org/download/)
- **uv** 包管理器 — [安装指南](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.10+（Blender 内置）
- Git（可选，用于克隆仓库）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/XUJL-916/blender-mcp-enhanced.git
cd blender-mcp-enhanced

# 2. 创建虚拟环境
uv venv

# 3. 安装项目（Windows）
uv pip install -p .venv/Scripts/python.exe -e .

# macOS / Linux
uv pip install -p .venv/bin/python -e .
```

> **网络超时？** 使用国内镜像：
> ```bash
> uv pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -e .
> ```

### 一键验证安装

```bash
# 测试安装
uv pip install -p .venv/Scripts/python.exe -e . && echo "OK: Project installed"

# 运行单元测试
python -m pytest tests/ -v

# 运行兼容性检查
python scripts/check_blender_512_compatibility.py

# 一键全量测试（单元测试 + 兼容性 + 项目分析）
powershell scripts/run_all_tests.ps1
```

---

## 📖 使用指南

### 第一步：安装 Blender 插件

1. 打开 Blender（推荐 5.1.2）
2. **Edit > Preferences > Add-ons**
3. 点击 **Install...** 按钮
4. 选择项目根目录的 `addon.py`
5. 搜索 **Blender-MCP**，勾选启用
6. 关闭 Preferences（设置自动保存）

> addon.py 约 2668 行，是 Blender 侧的核心插件，负责执行 3D 场景操作。

### 第二步：启动 MCP 服务

打开**新终端**，进入项目目录：

```bash
cd blender-mcp-enhanced
uvx blender-mcp
```

看到 `Blender-MCP server running on localhost:9876` 表示启动成功。

**重要**: MCP 服务必须与 Blender 同时运行，但请先启动 Blender 并加载插件，再启动 MCP 服务。

### 第三步：在 Blender 中连接

1. Blender 按 **N 键** 打开侧边栏
2. 找到 **Blender-MCP** 标签页
3. 点击 **Connect to Claude** 按钮
4. 看到绿色状态提示 = 连接成功

### 第四步：用 AI 客户端操作 Blender

配置你的 AI 客户端（参见下方配置指南），然后通过自然语言指令操作 Blender。

#### 常用操作示例

```
# 创建场景
"创建 3 个立方体排成一行，中间加一个球体，设置三点布光"

# 材质编辑
"给所有物体创建金属材质，颜色为红色，粗糙度 0.3"

# 渲染
"使用 Eevee 引擎渲染当前场景，分辨率 1920x1080，输出到 D:/renders"

# 导入导出
"导入 D:/models/character.fbx，导出当前场景为 output.glb"
```

---

## 🔧 AI 客户端配置

### Claude Desktop

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

- **Windows**: `C:\Users\admin\AppData\Local\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Hermes Agent

在 Hermes Agent 会话中直接使用 `terminal` 工具：

```bash
# 启动 MCP 服务
uvx blender-mcp
```

然后通过其他工具调用 Blender 操作。

### VS Code / Cursor

在 MCP 扩展配置中添加 server 配置，同上 JSON 格式。

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

**两层通信设计**: MCP 层 (stdio) 与 TCP 层 (JSON) 解耦，AI 客户端不直接操作 Blender。

| 层 | 职责 | 关键技术 |
|----|------|----------|
| AI Client | 自然语言指令 | Claude API / Cursor MCP / Hermes Agent |
| MCP Server | 工具定义与调度 | FastMCP, 31 个工具定义 |
| TCP Bridge | 跨进程通信 | JSON-RPC over TCP, localhost:9876 |
| Blender Addon | 场景操作执行 | bpy API, Eevee/Cycles 渲染 |
| Blender Engine | 3D 渲染引擎 | bpy.data, mathutils, 节点编辑器 |

---

## ✨ 核心功能模块

| # | 模块 | 方法数 | 状态 |
|---|------|--------|------|
| 1 | **高级对象操作** (创建/变换/查询/批量) | 50+ | ✅ 已实现 |
| 2 | **材质与节点编辑器** (Principled BSDF/纹理/节点树) | 30+ | ✅ 已实现 |
| 3 | **动画与关键帧** (FBX/OBJ/GLB 导入导出) | 15+ | ✅ 已实现 |
| 4 | **渲染与场景快照** (Eevee/Cycles/多视角) | 15+ | ✅ 已实现 |
| 5 | **数据导入/导出** (FBX/OBJ/GLB/STL/Blend/CSV) | 13 | ✅ 已实现 |
| 6 | **连接恢复机制** (电路断路器+自动重连) | 6 | ✅ 已实现 |
| 7 | **外部资产集成** (PolyHaven/Sketchfab/Hyper3D/Hunyuan3D) | 15+ | ✅ 已实现 |

**代码统计**: 约 6,851 行 Python，385 方法 / 64 函数 / 41 类。

---

## ⚙️ 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BLENDER_HOST` | localhost | Socket 地址 |
| `BLENDER_PORT` | 9876 | Socket 端口 |
| `DISABLE_TELEMETRY` | (未设置) | 完全关闭遥测 |
| `HYPER3D_API_KEY` | (未设置) | Hyper3D API 密钥 |
| `HUNYUAN3D_SECRET_ID` | (未设置) | Hunyuan3D API 密钥 |

---

## ✅ 测试状态

| 类别 | 测试数 | 通过 | 失败 | 跳过 |
|------|--------|------|------|------|
| 单元测试 | 157 | 155 | 0 | 2 |
| 兼容性检查 | 42 | 42 | 0 | 0 |

```bash
# 运行全部测试
python -m pytest tests/ -v

# 一键测试 (单元测试 + 兼容性 + 项目分析)
powershell scripts/run_all_tests.ps1
```

**注意**: 2 个跳过测试（`test_connect_and_send_command`, `test_health_check`）需要运行中的 Blender 实例进行集成测试。

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
| [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) | 发布前检查清单 |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 开发迭代记录与功能状态 |
| [TERMS_AND_CONDITIONS.md](TERMS_AND_CONDITIONS.md) | 使用条款 |

---

## 🔒 安全说明

- `execute_blender_code` 允许执行任意 Python 代码，生产环境请谨慎使用
- PolyHaven 集成会下载模型文件，可在 Blender Addon 中关闭
- 遥测完全匿名，`DISABLE_TELEMETRY=true` 可完全关闭

---

## 📜 许可证

本项目基于原始 blender-mcp 项目 (MIT 许可证) 扩展开发。原始项目由 [Siddharth Ahuja](https://x.com/sidahuj) 创建。

---

## ⚠️ 免责声明

本项目为第三方集成，与 Blender 官方无关联。Blender® 是 Blender Foundation 的注册商标。

---

## 🙏 致谢

- 原始项目: [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)
- Model Context Protocol: [anthropics/mcp](https://github.com/anthropics/mcp)
- Blender: [blender.org](https://www.blender.org)
