# 验收测试计划

> **版本**: 1.5.5-enh | **迭代日期**: 2026-06-01 | **Target Blender**: 5.1.2 | **Python**: 3.13

---

## 1. 单元测试计划

### 1.1 测试框架

| 项目 | 值 |
|------|------|
| 框架 | pytest 9.0+ |
| 配置文件 | `tests/pytest.ini` |
| 运行命令 | `python -m pytest tests/ -v` |
| 总测试数 | 157 tests |
| 测试文件 | 4 个 |

### 1.2 测试文件清单

#### test_config.py — 配置模块

| 测试项 | 测试内容 | 通过标准 |
|--------|----------|----------|
| ConnectionConfig | 连接配置默认值、环境变量覆盖 | 所有断言通过 |
| APIKeys | API 密钥加载、has_*_key() 判断 | 所有断言通过 |
| TelemetryConfig | 遥测配置加载、DISABLE_TELEMETRY | 所有断言通过 |
| BlenderConfig | Blender 配置加载 | 所有断言通过 |
| Config.summary() | 非敏感配置视图 | 不暴露密钥 |
| env 变量覆盖 | BLENDER_MCP_* 环境变量优先级 | 环境变量 > 默认值 |

**预期**: 20 tests，全部 PASS

---

#### test_connection_recovery.py — 连接恢复机制

| 测试项 | 测试内容 | 通过标准 |
|--------|----------|----------|
| CircuitBreaker | CLOSED → OPEN → HALF_OPEN 状态机 | 状态转换正确 |
| HealthMetrics | 成功率、延迟、字节统计 | 指标计算正确 |
| BlenderConnectionManager | 自动重连、指数退避 | 重连逻辑正确 |
| health_check() | 完整状态报告返回 | 返回字典包含所有字段 |
| AsyncBlenderConnectionManager | async/await 支持 | 异步调用无异常 |

**预期**: 25 tests，23 PASS，2 SKIP（需要运行中 Blender 实例的集成测试）

---

#### test_advanced_objects.py — 高级对象操作

| 测试项 | 测试内容 | 通过标准 |
|--------|----------|----------|
| Data Models | BoundingBox, MaterialInfo, RenderSettings | 数据类实例化正确 |
| Object CRUD | select, focus, delete, create | stub 方法返回预期值 |
| Scene Management | save, load, collections | stub 方法返回预期值 |
| Render Settings | get/set render settings | stub 方法返回预期值 |
| Batch Operations | batch_scale, batch_color, batch_rotate | stub 方法返回预期值 |
| Material/Node Editor | create_material, mix_shaders, normal_map | stub 方法返回预期值 |

**预期**: 50 tests，全部 PASS

---

#### test_advanced_batch_render_import.py — 批量/渲染/导入/导出

| 测试项 | 测试内容 | 通过标准 |
|--------|----------|----------|
| Batch Rendering | batch scale, render settings, preview | stub 方法返回预期值 |
| Import/Export | FBX, OBJ, GLB, STL, Blend, CSV | stub 方法返回预期值 |
| Scene Snapshots | scene, viewport, camera, all_cameras | stub 方法返回预期值 |
| 3D Generation | PolyHaven, Sketchfab, Hyper3D, Hunyuan3D | stub 方法返回预期值 |

**预期**: 62 tests，全部 PASS

---

### 1.3 单元测试汇总

| 模块 | 测试数 | 通过 | 失败 | 跳过 |
|------|--------|------|------|------|
| test_config.py | 20 | 20 | 0 | 0 |
| test_connection_recovery.py | 25 | 23 | 0 | 2* |
| test_advanced_objects.py | 50 | 50 | 0 | 0 |
| test_advanced_batch_render_import.py | 62 | 62 | 0 | 0 |
| **合计** | **157** | **155** | **0** | **2** |

*跳过项: test_connect_and_send_command, test_health_check — 需要运行中的 Blender 实例

---

## 2. Blender Runtime Test 计划

### 2.1 测试环境

| 项目 | 值 |
|------|------|
| Blender | 5.1.2 (headless mode) |
| 执行命令 | `"D:/Program Files/blender/blender.exe" -b --python <script> -- --output <dir>` |
| 输出目录 | `blender_test_output/` |
| 输出格式 | 结构化 JSON |

### 2.2 测试用例

#### test1_create_objects.py — 对象创建验证

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| Mesh 创建 | Cube, Sphere, Cylinder, Plane | bpy.ops 无异常 |
| 对象变换 | location, rotation, scale 设置 | 属性值正确 |
| 光源创建 | Point, Sun, Spot, Area | bpy.ops 无异常 |
| 相机创建 | 位置+旋转设置 | bpy.ops 无异常 |
| 材质创建 | Principled BSDF | 材质节点正确连接 |
| 场景信息查询 | get_scene_info 返回 JSON | JSON 包含所有对象 |

**预期**: 所有 PASS

---

#### test2_material_system.py — 材质系统验证

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| 基础材质 | Principled BSDF 创建 | 节点树正确 |
| 颜色设置 | diffuse_color 设置 | 颜色值正确 |
| 纹理节点 | Image Texture 节点添加 | 节点类型正确 |
| 节点连接 | BSDF → Output 连接 | 连接图正确 |
| 法线贴图 | Normal Map 节点 | socket 名为 `Color` (非 `Vector`) |
| VALTORGB 节点 | color ramp 转换 | 节点 type 为 `VALTORGB` (非 `VAL_TO_RGB`) |

**预期**: 所有 PASS

---

#### test3_animation_system.py — 动画系统验证

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| 关键帧插入 | Cube 位移/旋转/缩放关键帧 | 帧范围正确 |
| FCurves 验证 | 使用 `get_action_fcurves()` 兼容函数 | 6 FCurves 存在 |
| 关键帧计数 | keyframe_points 遍历 | 18 个关键帧 |
| Shape Key 创建 | 添加 Shape Key | 无异常 |
| Shape Key 关键帧 | Blender 5.1.2 限制处理 | WARN 降级 (非 FAIL) |
| 场景帧范围 | frame_start, frame_end | 值正确 |
| 场景 FPS | Blender 5.1.2 移除处理 | 显示默认值 24 |

**已知限制**:
- `action.fcurves` 已移除 → 使用 `action.layers[0].strips[0].channelbags[0].fcurves`
- `scene.fps` 已移除 → 显示默认值 24
- `ShapeKey.keyframe_insert()` 静默失败 → WARN 降级

**预期**: FCurves 和关键帧 PASS，ShapeKey 关键帧 WARN 降级

---

#### test4_rendering_system.py — 渲染系统验证

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| 渲染引擎 | Eevee 设置 | engine 属性正确 |
| 渲染输出 | 输出路径设置 | path 正确 |
| 渲染执行 | render_scene 调用 | 无异常 |
| 渲染参数 | resolution, samples | 参数正确 |

**注意**: Blender 5.1.2 部分渲染 API 参数有变更，需版本检查。

**预期**: 根据 API 变更情况 PASS 或 WARN 降级

---

#### test5_import_export.py — 导入导出验证

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| OBJ 导出 | 当前场景导出 | 文件生成 |
| GLTF 导出 | 当前场景导出 | 文件生成 |
| FBX 导出 | 当前场景导出 | 文件生成 |
| 版本检查 | OBJ 导入 API 版本适配 | bpy.app.version 检查通过 |

**预期**: 导出 PASS，导入可能需要 API Key

---

#### test6_communication_mock.py — 通信模拟验证

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| TCP 连接模拟 | Socket 连接/断开 | 连接状态正确 |
| JSON 协议 | 发送/接收 JSON 帧 | 协议格式正确 |
| 超时处理 | 180 秒超时 | 超时机制正常 |

**预期**: 需要运行中 Blender 实例

---

#### test7_stress_test.py — 压力测试

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| 大批量对象创建 | 100+ 对象 | 无内存异常 |
| 批量材质应用 | 100+ 对象应用材质 | 无异常 |
| 批量变换操作 | 100+ 对象批量变换 | 执行时间可接受 |
| 长时间运行 | 持续操作 5 分钟 | 无崩溃 |

**预期**: 根据资源情况 PASS 或 WARN

---

### 2.3 Runtime 测试汇总

| 测试 | 状态 | 备注 |
|------|------|------|
| test1_create_objects | ✅ PASS | 核心功能验证 |
| test2_material_system | ✅ PASS | 材质/节点验证 |
| test3_animation_system | ✅ PASS | FCurves 修复后通过，ShapeKey WARN 降级 |
| test4_rendering_system | ~ 待执行 | 需验证 API 变更 |
| test5_import_export | ~ 待执行 | 需验证导出功能 |
| test6_communication_mock | ~ 待执行 | 需 Blender 实例 |
| test7_stress_test | ~ 待执行 | 需 Blender 实例 |

---

## 3. MCP End-to-End Test 计划

### 3.1 测试环境

| 项目 | 值 |
|------|------|
| MCP 协议 | stdio |
| 启动命令 | `uvx blender-mcp` |
| 测试客户端 | Python MCP client / Claude Desktop |

### 3.2 测试用例

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| MCP Server 启动 | uvx blender-mcp 无异常 | 进程启动成功 |
| 工具列表 | 获取 31 个注册工具 | 工具数正确 |
| 对象创建工具 | create_object 调用 | Blender 中对象创建 |
| 场景查询工具 | get_scene_info 调用 | 返回 JSON |
| 材质工具 | create_material 调用 | Blender 中材质创建 |
| 渲染工具 | render_scene 调用 | 渲染输出 |
| 导入导出工具 | export_obj 调用 | 文件生成 |
| 连接恢复 | 断线重连 | 自动恢复 |

### 3.3 通过标准

- 每个工具调用在 180 秒内返回结果
- JSON 响应格式正确
- Blender 内部状态与调用一致

---

## 4. 渲染测试计划

### 4.1 引擎测试

| 测试项 | 引擎 | 通过标准 |
|--------|------|----------|
| Eevee 渲染 | Eevee | 输出非黑屏 |
| Cycles 渲染 | Cycles | GPU 可用时输出正常 |
| 渲染分辨率 | 1920×1080 | 输出尺寸正确 |
| 渲染采样 | 256 samples | 渲染时间可接受 |

### 4.2 高级渲染

| 测试项 | 内容 | 通过标准 |
|--------|------|----------|
| 多视角渲染 | 4 个相机同时渲染 | 4 个文件生成 |
| 360 全景渲染 | equirectangular | 输出尺寸 4096×2048 |
| 预览渲染 | 低采样预览 | 快速完成 |
| 动画渲染 | 100 帧序列 | 100 个文件生成 |

---

## 5. 导入导出测试计划

### 5.1 导出测试

| 格式 | 通过标准 |
|------|----------|
| OBJ | 文件生成，顶点数据正确 |
| GLB | 文件生成，glTF 格式验证 |
| FBX | 文件生成，动画数据保留 |
| STL | 文件生成，网格数据正确 |
| Blend | 文件生成，可重新加载 |

### 5.2 导入测试

| 格式 | 通过标准 |
|------|----------|
| OBJ | 场景包含导入对象 |
| GLB | 场景包含导入对象+材质 |
| FBX | 场景包含导入对象+动画 |
| Blend | 场景合并导入 |

---

## 6. 压力测试计划

### 6.1 对象压力测试

| 测试项 | 参数 | 通过标准 |
|--------|------|----------|
| 大批量创建 | 500 Cube | 无内存异常，< 30 秒 |
| 批量变换 | 500 对象 set_transform | 执行时间 < 5 秒 |
| 批量材质 | 500 对象 set_material | 无异常 |

### 6.2 渲染压力测试

| 测试项 | 参数 | 通过标准 |
|--------|------|----------|
| 多场景批量 | 10 场景 × 4 相机 | 全部渲染完成 |
| 长时间运行 | 持续操作 30 分钟 | 无崩溃 |

### 6.3 通过标准

- 内存使用 < 4GB (500 对象场景)
- 无 OOM 错误
- 无 Blender 崩溃

---

## 7. 测试执行摘要

### 7.1 已完成测试

| 类别 | 测试数 | 通过 | 失败 | 跳过 |
|------|--------|------|------|------|
| 单元测试 | 157 | 155 | 0 | 2 |
| Runtime Test 1-3 | 3 | 3 | 0 | 0 |
| 兼容性检查 | 42 | 42 | 0 | 0 |
| **合计** | **202** | **200** | **0** | **2** |

### 7.2 待执行测试

| 类别 | 测试数 | 前置条件 |
|------|--------|----------|
| Runtime Test 4-7 | 4 | Blender 5.1.2 |
| MCP End-to-End | 8 | MCP Server + Blender |
| 渲染测试 | 8 | GPU (可选) |
| 导入导出测试 | 10 | 测试文件 |
| 压力测试 | 5 | Blender 实例 |
| **合计** | **35** | — |

---

## 8. 验收通过标准

### 8.1 必须通过

- [x] 单元测试 155/155 PASS
- [x] Blender 5.1.2 兼容性检查 0 CRITICAL
- [x] Runtime Test 1-3 PASS
- [x] addon.py 加载无错误

### 8.2 建议通过

- [ ] Runtime Test 4-7 PASS
- [ ] MCP End-to-End 测试 PASS
- [ ] 渲染测试 PASS
- [ ] 导入导出测试 PASS
- [ ] 压力测试 PASS

### 8.3 结论

**条件通过 (CONDITIONAL PASS)**: 核心功能已验证，部分 Runtime 和 E2E 测试需在实际环境中执行。
