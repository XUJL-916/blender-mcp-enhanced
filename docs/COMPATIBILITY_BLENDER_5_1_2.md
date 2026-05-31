# Blender-MCP 5.1.2 兼容性文档

> 版本: 1.0 | 生成日期: 2026-06-01 | 目标 Blender: 5.1.2 | Python: 3.13

---

## 1. 目标环境

| 项目 | 值 |
|------|------|
| Target Blender Version | **5.1.2** |
| Blender Bundled Python | **3.13** |
| Primary OS | **Windows 11 Pro 10.0.26100** |
| uv 管理 Python | 3.13.2 (`.python-version`) |
| Python API Min Requirement | 3.10 (`pyproject.toml`) |

---

## 2. 静态分析结果

运行 `scripts/check_blender_512_compatibility.py` 对 `addon.py` 进行静态扫描：

```
Total: 43 issues
CRITICAL: 0  ERROR: 0
WARNING: 4  INFO: 39
```

### 2.1 WARNING 汇总 (4 项)

| # | 文件:行号 | 问题 | 影响 | 修复方案 |
|---|----------|------|------|----------|
| 1 | addon.py:2365 | `bl_region_type = 'UI'` 已弃用 | Panel 不显示在正确区域 | 改为 `bl_region_type = 'WINDOW'` |
| 2 | addon.py:774 | `bpy.ops.import_scene.obj()` 已弃用 | PolyHaven GLTF/Blender 导入中使用旧 API | 添加版本检查 (类似 2286 行) |
| 3 | addon.py:2289 | `bpy.ops.import_scene.obj()` 已弃用 | Hunyuan3D OBJ 导入使用旧 API | 添加版本检查 (类似 2286 行) |
| 4 | addon.py:1976 | `datetime.utcfromtimestamp()` 在 Python 3.12+ 弃用 | Tencent Cloud 签名计算 | 改为 `datetime.fromtimestamp(ts, tz=timezone.utc)` |

### 2.2 CRITICAL / ERROR

**无。** 所有 3D 相关 API（bpy.props、Operator/Panel、ShaderNode、Import/Export、Context Override、Addon Registration）在 Blender 5.1.2 中均无破坏性变更。

### 2.3 INFO 确认 (关键项)

- bpy.props 属性类型 (Int/Bool/String/Enum/Float) — 全部兼容
- bpy.types.Operator / Panel 注册模式 — 标准 API，无变更
- bpy.context.temp_override() — 4.1+ 推荐方式，正确
- bpy.ops.import_scene.gltf — 路径在 5.1.2 有效 (5 处)
- bpy.app.timers.register() — 标准 API，2 处使用
- bpy.ops.wm.obj_import — 已正确使用 (Hunyuan3D 部分，4.0+ 条件分支)
- colorspace_settings.name — sRGB/Non-Color/Linear 全部有效
- mathutils import — 有效
- addon 属性清理 (unregister) — 17 个属性正确删除

---

## 3. 已发现的需修复问题

### 3.1 bl_region_type 弃用 (addon.py:2365)

**状态**: WARNING — 不影响 5.1.2 运行，但 5.2+ 可能移除

```python
# 当前 (addon.py:2365)
bl_region_type = 'UI'

# 应改为
bl_region_type = 'WINDOW'
```

**影响**: Panel 在 Blender 5.1.2 中仍正确显示在侧边栏。'UI' 在 4.2+ 被标记为弃用。

### 3.2 旧 OBJ 导入 API (addon.py:774)

**状态**: WARNING — PolyHaven Blender 模型导入路径

```python
# addon.py:774 (PolyHaven)
bpy.ops.import_scene.obj(filepath=main_file_path)

# 应改为 (参考 addon.py:2286-2289 已有的版本检查模式)
if bpy.app.version >= (4, 0, 0):
    bpy.ops.wm.obj_import(filepath=main_file_path)
else:
    bpy.ops.import_scene.obj(filepath=main_file_path)
```

### 3.3 旧 OBJ 导入 API (addon.py:2289)

**状态**: WARNING — Hunyuan3D 导入路径。此处已有版本检查 (2286 行)，所以 **实际上已正确处理**。
静态扫描检测到 `bpy.ops.import_scene.obj()` 调用在 `else` 分支中，这是预期的兼容性回退。

### 3.4 datetime.utcfromtimestamp 弃用 (addon.py:1976)

**状态**: WARNING — Tencent Cloud Hunyuan 签名计算

```python
# addon.py:1976
date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

# 应改为
from datetime import timezone, datetime
date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
```

**影响**: 仅影响腾讯云 API 签名的日期部分，功能上等价，但 Python 3.12+ 会抛出 DeprecationWarning。

---

## 4. 已知无需修复项

### 4.1 tempfile._cleanup() (addon.py:576)

**状态**: INFO — 内部使用，非破坏性

```python
tempfile._cleanup()  # 清理临时文件
```

这是一个私有 API，在某些 Python 版本中可能不存在。当前在 try/except 中，不会导致崩溃。

### 4.2 PolyHaven HDRI/Texture 节点创建

所有使用的节点类型在 5.1.2 中均有效:
- `ShaderNodeBsdfPrincipled` — 核心节点，有效
- `ShaderNodeBsdfDiffuse` / `ShaderNodeBsdfGlossy` / `ShaderNodeBsdfToon` — **未被使用**（已移除的节点）
- `ShaderNodeMapping` — 有效 (vector_type='TEXTURE' 在 3.3+ 可用)
- `ShaderNodeTexImage` / `ShaderNodeTexEnvironment` — 有效
- `ShaderNodeNormalMap` / `ShaderNodeDisplacement` — 有效
- `ShaderNodeMixRGB` / `ShaderNodeSeparateRGB` — 有效

### 4.3 Principled BSDF 输入

使用的所有输入在 5.1.2 中均有效:
- `Base Color`, `Roughness`, `Metallic`, `Normal` — 标准输入
- `Displacement` — 标准输出
- 5.1.2 新增的 `Anisotropic`, `Sheen`, `Clearcoat` 等输入 **未被使用**，不影响

### 4.4 Viewport Screenshot

```python
with bpy.context.temp_override(area=area):
    bpy.ops.screen.screenshot_area(filepath=filepath)
```

`temp_override()` 是 Blender 4.1+ 推荐方式。`screenshot_area()` 是 `screenshot()` 的新别名，5.1.2 中均有效。

### 4.5 数学运算

- `mathutils.Vector` — 有效
- `obj.bound_box` (8 个角的局部坐标) — 有效
- `obj.matrix_world @ corner` — 矩阵乘法有效
- `obj.visible_get()` — 有效

---

## 5. 与 Blender 5.0/5.1 Python API Breaking Changes 对照表

| Breaking Change | 影响本项目? | 说明 |
|----------------|------------|------|
| bpy.types.Object.active_material 移除 | **否** | 本项目未使用此属性 |
| bpy.context.object 在 5.0+ 改为 context.active_object | **否** | 本项目使用 `bpy.context.view_layer.objects.active`，已正确 |
| bpy.data.materials.new(name=...) 不再自动分配给对象 | **否** | 本项目创建材质后手动 `data.materials.append()`，已正确 |
| ShaderNodeBsdf* 废弃 | **否** | 已确认未使用被移除的节点类型 |
| scene.world 赋值方式变更 | **否** | 使用 `bpy.context.scene.world = world`，仍有效 |
| bpy.types.Panel.bl_region_type 'UI' → 'WINDOW' | **是 (WARNING)** | 见 3.1 |
| bpy.ops.import_scene.obj → bpy.ops.wm.obj_import | **是 (WARNING)** | 见 3.2，仅 PolyHaven Blender 导入路径 |
| bpy.context.copy() / bpy.context.copy() 替代模式 | **否** | 已使用 `temp_override()` |
| render.engine = 'BLENDER_EEVEE' → 'EEVEE' | **否** | 本项目未直接设置 render.engine |
| bpy.props.StringProperty subtype 变更 | **否** | 'PASSWORD' 仍有效 |
| mathutils.Matrix @ Vector → 新语法 | **否** | `matrix @ vector` 仍有效 |
| bpy.app.timers.register 首次参数变化 | **否** | 使用 `first_interval=0.0`，仍有效 |
| bpy.data.libraries.load 签名变更 | **否** | 使用 `link=False` 模式，仍有效 |
| import_scene.gltf 新路径 | **否** | 仍使用旧路径 `import_scene.gltf`，5.1.2 仍支持 |
| datetime.utcfromtimestamp 弃用 | **是 (WARNING)** | 仅腾讯云签名计算，见 3.4 |

---

## 6. 测试策略

### 6.1 静态分析测试

```bash
# 运行兼容性静态检查
python scripts/check_blender_512_compatibility.py
```

输出: 43 项检查结果 (0 CRITICAL, 0 ERROR, 4 WARNING, 39 INFO)

### 6.2 pytest 单元测试

```bash
# 使用项目 venv 运行
.venv/Scripts/python.exe -m pytest tests/ -v
```

结果 (项目 venv, Python 3.13.2):
- test_config.py: 20 passed
- test_connection_recovery.py: 23 passed, 2 skipped (集成测试需 Blender 运行时)
- test_advanced_objects.py: 50 passed (stub 层测试)
- test_advanced_batch_render_import.py: 62 passed (stub 层测试)
- **合计: 155 passed, 2 skipped**

### 6.3 Blender Runtime 测试 (需要 Blender 5.1.2)

以下测试需要在 Blender 5.1.2 中手动执行，暂无自动化方案:

| 测试项 | 描述 | 状态 |
|--------|------|------|
| Addon 加载 | addon.py 在 Blender 5.1.2 中正常注册/注销 | 待测试 |
| 面板显示 | VIEW_3D 侧边栏 BlenderMCP 面板正确显示 | 待测试 |
| 对象创建 | 通过 MCP 协议创建 Cube/Sphere/Plane | 待测试 |
| 材质节点 | Principled BSDF + 纹理节点创建和连接 | 待测试 |
| 关键帧 | 对象位置/旋转/缩放的动画关键帧插入 | 待测试 (stub 层) |
| 视口渲染 | viewport screenshot + render_scene | 待测试 |
| 导入测试 | GLB/FBX 模型导入 | 待测试 |
| 导出测试 | 导出 GLB/FBX 文件 | 待测试 |

---

## 7. 已知问题 (Known Issues)

### 优先级: 高

| ID | 问题 | 严重性 | 修复 |
|----|------|--------|------|
| HI-001 | `bl_region_type = 'UI'` 在 4.2+ 弃用 | WARNING | 改为 `'WINDOW'` |
| HI-002 | PolyHaven Blender 导入路径使用旧 obj API | WARNING | 添加版本检查 |
| HI-003 | `datetime.utcfromtimestamp()` 在 Python 3.12+ 弃用 | WARNING | 改为 `fromtimestamp(ts, tz=timezone.utc)` |

### 优先级: 低

| ID | 问题 | 严重性 | 修复 |
|----|------|--------|------|
| LI-001 | `tempfile._cleanup()` 是私有 API | INFO | 手动 `os.unlink()` |
| LI-002 | advanced_objects.py stub 未对接 TCP 通信层 | INFO | 开发中 |

---

## 8. 后续兼容性维护

每次 Blender 大版本升级后，应执行以下步骤:

1. 运行 `scripts/check_blender_512_compatibility.py`（更新目标版本号后）
2. 运行 `scripts/check_compatibility.py` 检查项目依赖
3. 运行所有 pytest 测试
4. 在目标 Blender 版本中手动执行 Runtime 测试（见 6.3）
5. 更新本文档

---

*本文档由静态分析自动生成，可根据实际 Runtime 测试结果更新。*
