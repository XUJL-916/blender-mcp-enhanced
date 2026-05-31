# Blender-MCP Enhanced 用户指南

> **版本**: 1.5.5-enh | **目标 Blender**: 5.1.2 | **Python**: 3.13+

本文档面向普通使用者，帮助你从零开始安装、配置并使用 Blender-MCP Enhanced。如果你遇到问题，请先阅读第五节的快速排查；详细解决方案请见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。

---

## 目录

1. [安装步骤](#1-安装步骤)
   - 1.1 安装 uv 包管理器
   - 1.2 安装项目依赖
   - 1.3 安装 Blender 插件 (Addon)
2. [配置](#2-配置)
   - 2.1 环境变量
   - 2.2 Claude Desktop 集成配置
   - 2.3 配置文件模板
3. [启动与连接](#3-启动与连接)
   - 3.1 启动 MCP 服务
   - 3.2 在 Blender 中连接
4. [基本使用](#4-基本使用)
   - 4.1 创建对象
   - 4.2 编辑材质
   - 4.3 渲染
   - 4.4 导入/导出模型
5. [常见问题快速排查](#5-常见问题快速排查)
6. [版本信息与兼容性](#6-版本信息与兼容性)

---

## 1. 安装步骤

### 1.1 安装 uv 包管理器

uv 是一个快速 Python 包管理器，blender-mcp 依赖它来运行。

**Windows:**

在 PowerShell 中运行：

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装完成后，关闭并重新打开终端（或使用 cmd 的 git-bash）验证：

```bash
uv --version
```

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装完成后刷新环境变量：

```bash
source ~/.bashrc    # 如果你用 bash
# 或
source ~/.zshrc     # 如果你用 zsh
```

验证安装：

```bash
uv --version
```

### 1.2 安装项目依赖

进入项目目录并安装：

```bash
cd C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main
uv venv
```

**Windows (使用 git-bash):**

```bash
uv pip install -p .venv/Scripts/python.exe -e .
```

**macOS / Linux:**

```bash
uv pip install -p .venv/bin/python -e .
```

> **提示**: 安装过程中如遇到网络超时，可设置国内镜像源：
> ```bash
> uv pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -e .
> ```

### 1.3 安装 Blender 插件 (Addon)

1. 打开 Blender（已验证版本 5.1.2，也兼容 4.x 系列）
2. 进入菜单：**Edit > Preferences > Add-ons**
3. 点击右上角 **"Install..."** 按钮
4. 选择项目根目录下的 **`addon.py`** 文件
5. 在列表中找到 **"Interface: Blender MCP"**，勾选以启用
6. 设置会自动保存，关闭 Preferences

> **注意**: addon.py 约 2668 行，是 Blender 侧的核心插件，负责执行实际的 3D 场景操作。

---

## 2. 配置

### 2.1 环境变量

blender-mcp 通过环境变量进行配置。常用变量如下：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BLENDER_HOST` | localhost | Blender 服务地址，通常保持默认 |
| `BLENDER_PORT` | 9876 | TCP 端口号，确保未被占用 |
| `DISABLE_TELEMETRY` | (空) | 设为 `true` 可完全关闭遥测数据收集 |
| `HYPER3D_API_KEY` | (空) | Hyper3D Rodin 模型生成 API 密钥 |
| `HUNYUAN3D_SECRET_ID` | (空) | 混元 3D 模型生成 API 密钥 |
| `SKETCHFAB_API_KEY` | (空) | Sketchfab 模型搜索与下载 API 密钥 |

**设置环境变量：**

**Windows (PowerShell):**

```powershell
$env:BLENDER_PORT="9876"
$env:DISABLE_TELEMETRY="true"
```

**Windows (永久设置):**

```powershell
# 系统级
[System.Environment]::SetEnvironmentVariable("BLENDER_PORT", "9876", "Machine")
```

**macOS / Linux (bash/zsh):**

```bash
export BLENDER_PORT="9876"
export DISABLE_TELEMETRY="true"
```

如需永久生效，将 `export` 行加入 `~/.bashrc` 或 `~/.zshrc`。

**Windows (git-bash):**

```bash
# 临时
export BLENDER_PORT="9876"

# 永久，加入 ~/.bash_profile 或 ~/.bashrc
echo 'export BLENDER_PORT="9876"' >> ~/.bashrc
```

### 2.2 Claude Desktop 配置

如果你使用 Claude Desktop（或支持 MCP 的 AI 客户端），需要添加 blender-mcp 服务配置。

在 Claude Desktop 配置目录中创建或编辑 `claude_desktop_config.json`（Windows 路径通常为 `C:\Users\admin\AppData\Local\Claude\claude_desktop_config.json`），添加以下内容：

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

> **提示**: 你也可以将配置放在项目根目录的 `claude_desktop_config.json` 中，部分 AI 客户端支持本地配置。

### 2.3 配置文件模板

如需更详细的配置，可创建 `.env` 文件放在项目根目录：

```bash
# Blender-MCP 配置 (.env)
BLENDER_HOST=localhost
BLENDER_PORT=9876
DISABLE_TELEMETRY=true

# API 密钥（按需填写）
# HYPER3D_API_KEY=your_key_here
# HUNYUAN3D_SECRET_ID=your_secret_id_here
# SKETCHFAB_API_KEY=your_api_key_here
```

> 环境变量优先于 `.env` 文件中的设置。

---

## 3. 启动与连接

### 3.1 启动 MCP 服务

打开终端，进入项目目录：

```bash
cd C:/Users/admin/Desktop/WorkSpcae/blender-mcp-main
```

启动 MCP 服务：

```bash
uvx blender-mcp
```

启动成功后，你会看到类似如下输出：

```
Blender-MCP server running on localhost:9876
```

> **注意**: 此时 Blender 必须先已打开并加载了 addon.py 插件。MCP 服务会等待 Blender 侧的连接。

### 3.2 在 Blender 中连接

1. 确保 Blender 已打开
2. 按 **N 键** 打开侧边栏
3. 找到 **"Blender-MCP"** 标签页
4. 点击 **"Connect to Claude"** 按钮（或对应连接按钮）
5. 看到绿色状态指示灯或连接成功提示

连接成功后，你可以通过 AI 客户端（Claude、Hermes Agent、VS Code 等）发送指令，Blender 会自动执行。

> **提示**: 如果连接失败，请确认：
> - Blender 已启动且 addon 已启用
> - MCP 服务（`uvx blender-mcp`）正在运行
> - BLENDER_HOST 和 BLENDER_PORT 两端一致

---

## 4. 基本使用

通过 AI 客户端（Claude Desktop、Hermes Agent 等）与 Blender 交互，以下是常用操作流程示例。

### 4.1 创建对象

**创建基本几何体：**

- 立方体 (Cube)
- 球体 (Sphere)
- 圆柱体 (Cylinder)
- 平面 (Plane)

**创建光源：**

- 点光源 (Point)
- 太阳光 (Sun)
- 聚光灯 (Spot)
- 区域光 (Area)

**创建相机：**

- 标准相机

**操作示例（自然语言指令）：**

```
在场景中创建一个立方体，位置为 (0, 0, 0)，大小为 2
添加一个点光源，亮度设为 100W
添加一个相机，对准立方体
```

**常用变换操作：**

- 移动：`set_object_location(对象名, x, y, z)`
- 旋转：`set_object_rotation(对象名, 旋转角度)`
- 缩放：`set_object_scale(对象名, 缩放比例)`
- 批量变换：`batch_set_transform(对象列表, 变换参数)`

**其他操作：**

- 删除对象、选择/取消选择、聚焦到某对象
- 设置父子层级关系
- 创建/管理集合 (Collections)
- 对齐到世界坐标轴：`align_to_world_axis(对象名, 轴)`
- 吸附到网格：`snap_to_grid(对象名, 网格大小)`
- 设置中心点：`center_object_origin(对象名)`

### 4.2 编辑材质

**创建材质：**

blender-mcp 基于 Principled BSDF 节点创建全功能材质，支持：

- 基础颜色、金属度、粗糙度
- 各向异性、透明度、折射率 (IOR)
- 法线贴图：`set_normal_map(对象名, 图片路径)`
- 置换贴图：`set_displacement(对象名, 图片路径)`

**纹理与节点：**

- 加载图像纹理：`create_image_texture_node(图片路径)`
- 将纹理应用到材质：`set_texture_to_material(材质名, 纹理节点)`
- 程序化纹理：`create_procedural_texture(类型, 参数)`
- 混合多个材质：`mix_shaders(材质1, 材质2, 混合透明度)`

**操作示例：**

```
给场景中所有立方体创建一个红色金属材质，粗糙度 0.2
加载 texture.jpg 作为球体的漫反射贴图
创建一个混合材质，50% 木纹 + 50% 金属
```

### 4.3 渲染

**选择渲染引擎：**

- **Eevee**: 实时渲染，速度快，适合预览
- **Cycles**: 光线追踪，质量高，适合最终输出

**设置渲染输出：**

```
设置渲染输出目录为 D:/renders
设置渲染分辨率为 1920x1080
使用 Cycles 引擎，采样数 128
```

**执行渲染：**

```
渲染当前场景
渲染动画帧 1 到 100
渲染多视角（前、侧、顶）
```

**渲染信息：**

- 查看当前渲染设置
- 查看渲染进度和已保存的图片

### 4.4 导入/导出模型

**支持的导入格式：**

| 格式 | 说明 |
|------|------|
| FBX | 游戏和影视通用格式，支持动画 |
| OBJ | 基础几何体格式 |
| GLB/GLTF | 现代 Web 3D 格式 |
| STL | 3D 打印格式 |
| Blend | Blender 原生格式 |
| CSV | 数据导入 |

**支持的导出格式：**

| 格式 | 说明 |
|------|------|
| FBX | 支持动画导出 |
| GLB/GLTF | 支持动画导出 |
| OBJ | 基础几何体导出 |
| STL | 3D 打印导出 |
| Blend | Blender 原生保存 |

**操作示例：**

```
从 D:/models/character.fbx 导入角色模型，保留动画
将当前场景导出为 D:/output/scene.glb
将动画序列导出为 FBX 格式
```

**外部资产导入：**

blender-mcp 还支持从在线服务导入素材：

- **Poly Haven**: 免费 HDRIs、纹理、模型
- **Sketchfab**: 模型搜索、预览、下载

---

## 5. 常见问题快速排查

### 连接类

**问题：连接失败，提示 "Connection refused"**

- 确认 Blender 已启动且 addon.py 已加载
- 确认 MCP 服务 `uvx blender-mcp` 正在运行
- 检查 BLENDER_HOST 和 BLENDER_PORT 设置是否一致

**问题：MCP 服务启动后无输出**

- 确保在正确的虚拟环境中运行
- 确认 `uvx blender-mcp` 命令可用
- 检查终端是否有 Python 报错

### 渲染类

**问题：渲染速度慢或失败**

- 切换到 Eevee 引擎进行快速预览
- 降低采样数 (建议预览 50-100，最终 200-500)
- 检查 Blender 的渲染设置是否正确

**问题：渲染输出没有图片**

- 检查渲染输出目录是否存在且可写
- 确认渲染已完整执行（查看 Blender 终端输出）

### 导入/导出类

**问题：导入模型后场景为空**

- 确认模型文件路径正确
- 检查模型格式是否受支持
- 在 Blender 中查看 Outliner (大纲视图) 确认导入结果

### 通用

**问题：uvx 命令找不到**

- 确认 uv 已安装：`uv --version`
- 确认当前处于项目的虚拟环境中
- 尝试直接安装：`uv pip install blender-mcp`

**问题：遥测数据收集**

- 设置 `DISABLE_TELEMETRY=true` 环境变量即可完全关闭

> **更多问题排查**: 请参阅 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) 获取详细故障排除指南。

---

## 6. 版本信息与兼容性

### 当前版本

| 项目 | 信息 |
|------|------|
| **项目名称** | Blender-MCP Enhanced |
| **当前版本** | 1.5.5-enh |
| **目标 Blender** | 5.1.2 (已验证) |
| **兼容 Blender** | 4.x 系列 (向后兼容) |
| **Python 版本** | 3.13+ |
| **MCP 协议版本** | mcp>=1.3.0 |
| **最后更新日期** | 2026-06-01 |

### 平台兼容性

| 平台 | 状态 | 备注 |
|------|------|------|
| **Windows 10/11** | 已验证 | 主要测试平台 |
| **macOS** | 支持 | Apple Silicon (M系列) 和 Intel 均可 |
| **Linux** | 支持 | 基于 Ubuntu/Debian 测试 |

### 系统要求

- Blender 4.x 或 5.x（推荐 5.1.2）
- Python 3.10 或更高版本
- uv 包管理器
- 网络连接（用于下载依赖包，可选用于在线素材服务）

### 工具概览

blender-mcp 提供 **31 个 MCP 工具** 和 **40+ 个高级对象操作 API**，覆盖：

- 对象创建与变换 (11 个子模块)
- 材质与节点编辑 (程序化纹理、混合材质)
- 动画与关键帧 (FBX/GLTF 动画导入导出)
- 渲染与快照 (Eevee/Cycles、多视角渲染)
- 资产导入导出 (FBX/OBJ/GLB/STL/Blend/CSV)
- 连接恢复 (电路断路器、自动重连)
- 外部素材 (Poly Haven、Sketchfab、Hyper3D、Hunyuan3D)

### 更多文档

- [API 文档](docs/API_DOCUMENTATION.md) — 完整工具 API 参考
- [兼容性报告](docs/COMPATIBILITY_BLENDER_5_1_2.md) — Blender 5.1.2 兼容性详情
- [Hermes Agent 使用示例](docs/HERMES_USAGE_EXAMPLES.md) — AI 代理集成示例
- [项目状态](PROJECT_STATUS.md) — 功能实现状态与开发记录

### 安全提示

- `execute_blender_code` 工具可执行任意 Blender Python 代码，生产环境请谨慎使用
- 操作前建议保存场景或使用版本控制
- 遥测数据完全匿名，可通过环境变量关闭

---

**许可证**: MIT (基于原始 blender-mcp 项目扩展)

**免责声明**: 本项目为第三方集成，与 Blender 官方无关联。
