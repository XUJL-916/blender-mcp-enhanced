# 故障排除指南

> **版本**: 1.5.5-enh | **迭代日期**: 2026-06-01 | **Target Blender**: 5.1.2 | **Python**: 3.13

---

## 1. Blender 5.1.2 API 相关问题

### 1.1 action.fcurves 不可用

**症状**:
```
AttributeError: 'Action' object has no attribute 'fcurves'
```

**原因**: Blender 5.1.2 中 `Action.fcurves` 属性已完全移除。新路径为：
```python
action.layers[0].strips[0].channelbags[0].fcurves
```

**解决**: 使用项目提供的兼容函数：
```python
from addon import get_action_fcurves
fcu = get_action_fcurves(action)
```

**预防**: 所有新代码使用 `get_action_fcurves()` 而非直接访问 `action.fcurves`。

---

### 1.2 FCurve keyframe_points 报错

**症状**:
```
AttributeError: 'FCurve' object has no attribute 'data_points'
```

**原因**: `FCurve.data_points` 在 Blender 5.1.2 中已移除，统一改用 `keyframe_points`。

**解决**:
```python
# 旧代码 (不兼容)
for kp in fcurve.data_points:
    pass

# 新代码
for kp in fcurve.keyframe_points:
    pass
```

---

### 1.3 ShapeKey.keyframe_insert() 静默失败

**症状**:
- 调用 `shape_key.keyframe_insert('value')` 无报错
- 但不会创建 animation_data 或 action
- 关键帧数据丢失

**原因**: Blender 5.1.2 中 ShapeKey 的关键帧创建行为变更，`keyframe_insert()` 静默失败。

**解决**: 
```python
# 检测失败情况
if not bpy.context.object.animation_data:
    print("WARN: ShapeKey keyframe_insert did not create action in Blender 5.1.2")
    # 降级处理：记录日志，不标记为 FAIL
```

**预防**: 测试中对于 ShapeKey 关键帧使用 WARN 降级而非 FAIL。

---

### 1.4 scene.fps 完全移除

**症状**:
```
AttributeError: 'Scene' object has no attribute 'fps'
```

**原因**: Blender 5.1.2 中 `scene.fps` 和 `scene.fps_base` 均被移除。

**解决**:
```python
# 安全访问
fps = scene.fps_base if hasattr(scene, 'fps_base') else 24
```

---

### 1.5 bl_region_type 'UI' 弃用

**症状**:
```
DeprecationWarning: bl_region_type = 'UI' is deprecated, use 'WINDOW'
```

**解决**: 已在 addon.py:2365 修复：
```python
# 旧
bl_region_type = 'UI'
# 新
bl_region_type = 'WINDOW'
```

---

### 1.6 datetime.utcfromtimestamp() 弃用

**症状**:
```
DeprecationWarning: datetime.utcfromtimestamp() is deprecated
```

**解决**: 已在 addon.py:1976 修复：
```python
# 旧
datetime.utcfromtimestamp(ts)
# 新
datetime.fromtimestamp(ts, tz=timezone.utc)
```

---

### 1.7 bpy.ops.import_scene.obj() 版本检查

**症状**:
```
DeprecationWarning: bpy.ops.import_scene.obj() in Blender 4.0+
```

**解决**: 已添加版本检查：
```python
if bpy.app.version >= (4, 0, 0):
    bpy.ops.import_scene.obj(filepath=filepath)
else:
    bpy.ops.import_obj(filepath=filepath)
```

---

## 2. 端口连接问题

### 2.1 端口被占用

**症状**:
```
OSError: [Errno 98] Address already in use
```
或
```
ConnectionRefusedError: [WinError 10061] 无法连接，因为目标机器主动拒绝了
```

**原因**: 端口 9876 被其他进程占用，或 Blender 未启动。

**解决**:
```bash
# Windows 查看端口占用
netstat -ano | findstr :9876

# 杀死占用进程 (替换 PID)
taskkill /PID <PID> /F

# 或修改端口
set BLENDER_PORT=9877
```

---

### 2.2 Blender 未启动

**症状**: MCP server 启动后无法连接到 Blender addon。

**排查步骤**:
1. 确认 Blender 已启动并加载 addon.py
2. 在 Blender 中按 N 键 → 找到 Blender-MCP 标签页 → 确认显示 "Connected"
3. 检查 Blender 控制台 (T 键) 是否有报错

**解决**: 重新安装 addon
- Blender → Edit → Preferences → Add-ons
- 点击 "Install..." 选择 `addon.py`
- 勾选 "Interface: Blender MCP"

---

### 2.3 防火墙阻止连接

**症状**: MCP server 启动成功，但连接 Blender 超时。

**排查**:
```bash
# Windows 检查防火墙规则
netsh advfirewall firewall show rule name=all | findstr 9876
```

**解决**: 添加防火墙规则允许 localhost 连接（通常为默认行为，无需额外配置）。

---

## 3. 插件加载问题

### 3.1 addon.py 语法错误

**症状**:
- Blender Add-ons 面板中 addon.py 显示红色警告
- 勾选后无响应

**排查**:
```bash
# 在 Blender 外部检查语法
python -c "import ast; ast.parse(open('addon.py').read())"
```

**解决**: 
- 检查报错行号
- 修复语法错误
- 重启 Blender

---

### 3.2 Blender 版本不匹配

**症状**: addon.py 加载时报错，提示 bpy 模块属性不存在。

**原因**: addon.py 是为 Blender 5.1.2 编写的，在低版本 Blender 中部分 API 不存在。

**解决**:
- 确认 Blender 版本 >= 5.1.2
- 使用 `D:/Program Files/blender/blender.exe` (5.1.2)

---

## 4. 材质节点问题

### 4.1 socket 名称变更

**症状**:
```
KeyError: 'Socket "Vector" not found'
```

**原因**: Blender 5.1.2 中 NormalMap 节点的输入 socket 从 `Vector` 改为 `Color`。

**解决**:
```python
# 旧 (不兼容)
links.new(node.outputs[0], target_socket)  # target_socket 名为 "Vector"
# 新
links.new(node.outputs[0], target_socket)  # target_socket 名为 "Color"
```

---

### 4.2 节点类型变更

**症状**:
```
ValueError: Unknown node type 'VAL_TO_RGB'
```

**原因**: Blender 5.1.2 中节点类型标识从 `VAL_TO_RGB` 改为 `VALTORGB`。

**解决**:
```python
# 旧
node.type = 'VAL_TO_RGB'
# 新
node.type = 'VALTORGB'
```

---

## 5. 渲染问题

### 5.1 Cycles GPU 初始化失败

**症状**: 
- Cycles 渲染输出全黑
- 控制台显示 OptiX/HIP 初始化错误
- 或渲染无声失败

**原因**: Blender 5.1.2 headless 模式下，GPU 初始化可能失败。

**解决**:
- 使用 Eevee 引擎代替 Cycles (headless 模式更稳定)
```python
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
```
- 或确认 GPU 驱动和 CUDA/OptiX 版本兼容

---

### 5.2 Eevee 渲染黑屏

**症状**: Eevee 渲染输出全黑。

**排查**:
1. 确认场景中有光源
2. 确认相机角度正确
3. 确认渲染区域设置

**解决**:
```python
# 添加三点布光
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
bpy.ops.object.light_add(type='AREA', location=(-5, 3, 5))
```

---

### 5.3 渲染输出路径错误

**症状**: 渲染成功但找不到输出文件。

**排查**:
```python
# 确认输出路径
print(bpy.context.scene.render.filepath)

# 设置输出路径
bpy.context.scene.render.filepath = 'C:/Users/admin/render_output/output.png'
```

**注意**: Windows 路径需要使用正斜杠 `/` 或双反斜杠 `\\`。

---

## 6. 导入导出问题

### 6.1 文件格式不支持

**症状**: 导入时报错 "Unsupported file type"。

**排查**:
- 确认文件扩展名正确 (.obj, .fbx, .glb, .stl, .blend)
- 确认文件未损坏

**解决**: 使用 Blender 内置导入器验证文件格式。

---

### 6.2 导出路径权限

**症状**: 导出时报错 "Permission denied"。

**解决**:
- 确保输出目录存在
- 确保有写入权限
- 使用绝对路径

```python
import os
os.makedirs('C:/Users/admin/export', exist_ok=True)
```

---

## 7. MCP 服务问题

### 7.1 uvx 命令失败

**症状**:
```
uvx: command not found
```

**解决**:
```bash
# 安装 uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 验证安装
uv --version
```

---

### 7.2 依赖缺失

**症状**:
```
ModuleNotFoundError: No module named 'starlette'
```

**解决**:
```bash
cd blender-mcp-main
uv venv
uv pip install -p .venv/Scripts/python.exe -e .
```

---

### 7.3 MCP server 启动后无响应

**症状**: `uvx blender-mcp` 启动后卡住或无输出。

**排查**:
1. 检查 addon.py 是否正常运行
2. 检查端口 9876 是否监听
3. 检查 Blender 控制台是否有报错

**解决**: 重启 MCP server 和 Blender。

---

## 8. 环境变量问题

### 8.1 环境变量未生效

**症状**: 自定义 BLENDER_HOST 或 BLENDER_PORT 不生效。

**解决**:
```bash
# Windows
set BLENDER_HOST=192.168.1.100
set BLENDER_PORT=9877
uvx blender-mcp

# 或在命令行中一行设置
BLENDER_HOST=192.168.1.100 BLENDER_PORT=9877 uvx blender-mcp
```

---

### 8.2 DISABLE_TELEMETRY 未生效

**症状**: 仍收集遥测数据。

**解决**:
```bash
# 确认设置
echo %DISABLE_TELEMETRY%

# Windows 设置
set DISABLE_TELEMETRY=true

# macOS/Linux 设置
export DISABLE_TELEMETRY=true
```

---

## 9. 快速检查清单

| 检查项 | 命令/操作 |
|--------|-----------|
| Blender 版本 | `blender --version` → 应为 5.1.2 |
| Python 版本 | `python --version` → 应为 3.13+ |
| uv 安装 | `uv --version` → 应有输出 |
| 端口占用 | `netstat -ano \| findstr :9876` |
| addon.py 语法 | `python -c "import ast; ast.parse(open('addon.py').read())"` |
| 测试通过 | `python -m pytest tests/ -v` → 155 passed |
| 兼容性检查 | `python scripts/check_blender_512_compatibility.py` → 0 CRITICAL |

---

## 10. 日志位置

| 日志类型 | 位置 |
|----------|------|
| Blender 控制台 | Blender 界面内 (T 键) |
| MCP server 日志 | 终端/命令行窗口 |
| Runtime 测试结果 | `blender_test_output/*.json` |
| 兼容性报告 | `blender_512_compat_report.json` |
| 项目分析 | `blender_mcp_analysis.json` |

---

## 11. 获取帮助

| 资源 | 链接/命令 |
|------|-----------|
| 项目文档 | `docs/` 目录 |
| API 文档 | `docs/API_DOCUMENTATION.md` |
| Hermes 示例 | `docs/HERMES_USAGE_EXAMPLES.md` |
| 开发者指南 | `docs/DEVELOPER_GUIDE.md` |
| 用户指南 | `docs/USER_GUIDE.md` |
| 项目状态 | `PROJECT_STATUS.md` |
| 原始项目 | https://github.com/ahujasid/blender-mcp |
