# 精细化建模工具

Blender-MCP 提供 8 个可组合的结构化建模工具。所有修改工具都会返回操作结果；拓扑和修改器操作还会返回前后统计。

## 工具

- `mesh_edit`：按顶点、边、面索引执行挤出、内插、倒角、细分、环切、合并、法线修复、删除和三角化。
- `modifier_control`：添加、配置、应用或移除 Blender 修改器，可传入修改器属性字典。
- `sculpt_refine`：体素重网格、多级细分和平滑。
- `mesh_quality`：检查或修复非流形边、边界边、松散元素、退化面、法线和 N 边面。
- `uv_tools`：智能展开、常规展开、立方体投影和 UV 岛打包。
- `pbr_material`：创建并分配 Principled BSDF 节点材质，支持颜色、粗糙度、金属度和法线贴图。
- `model_checkpoint`：创建、恢复、列出或删除隐藏网格检查点。
- `modeling_recipe`：按顺序执行多个建模工具；任一步失败时可自动恢复检查点。

## 推荐流程

1. 使用 `mesh_quality(action="inspect")` 检查输入模型。
2. 使用 `model_checkpoint(action="create")` 保存操作前状态。
3. 使用 `modeling_recipe` 执行可重复的参数化步骤。
4. 再次运行质量检查，并根据结果选择修复或恢复检查点。

## 配方示例

```json
{
  "checkpoint_name": "hard_surface_pass_01",
  "rollback_on_error": true,
  "steps": [
    {
      "tool": "modifier_control",
      "params": {
        "object_name": "Housing",
        "modifier_type": "SOLIDIFY",
        "name": "Shell 2mm",
        "settings": {"thickness": 0.002}
      }
    },
    {
      "tool": "modifier_control",
      "params": {
        "object_name": "Housing",
        "modifier_type": "BEVEL",
        "name": "Edge 0.8mm",
        "settings": {"width": 0.0008, "segments": 3}
      }
    },
    {
      "tool": "mesh_quality",
      "params": {"object_name": "Housing", "action": "inspect"}
    }
  ]
}
```

索引编辑依赖当前网格拓扑。前一步改变拓扑后，后续步骤应重新读取对象信息或重新确定索引。
