# Release Checklist — Blender-MCP Enhanced v1.5.5

> **日期**: 2026-06-01 | **版本**: 1.5.5-enh | **目标**: Blender 5.1.2 | **作者**: XUJL | SZU
>
> **规则**: 任何代码提交、文档提交、图片提交、README 修改，在 Push 之前**必须**完整执行本清单。

---

## 1. 代码质量

- [ ] 所有 Python 文件头部包含 XUJL/SZU 版权注释
- [ ] 代码通过 `flake8` 或 `pylint` 静态检查（无新增 ERROR/WARNING）
- [ ] 所有导入语句按标准顺序（stdlib → third-party → local）
- [ ] 没有硬编码密钥（检查 `addon.py`、`server.py`、`advanced_objects.py`）
- [ ] `config.py.example` 与 `config_new.py` 配置模型一致
- [ ] 所有 `TODO` / `FIXME` / `HACK` 标记已处理或记录在案

## 2. 单元测试

- [ ] `pytest tests/ -v` 全部通过（当前: 155/157 通过，2 跳过需 Blender 实例）
- [ ] 新增代码覆盖新增的单元测试
- [ ] 兼容性检查脚本 `scripts/check_blender_512_compatibility.py` 通过
- [ ] 测试报告中所有 "SKIP" 项有明确原因说明

## 3. 图片与资源验证

- [ ] README 中**所有**图片路径使用相对路径（`assets/xxx.png` 或 `docs/xxx.png`）
- [ ] 所有图片在本地 `assets/` 目录下存在且非空（>1KB）
- [ ] 图片文件名使用小写 + 下划线（kebab-case / snake_case 一致性）
- [ ] 图片尺寸合理：封面图 <500KB，功能图 <1MB，截图 <2MB
- [ ] 图片内容与当前版本功能描述一致（非过时截图）
- [ ] 所有图片在 GitHub Pages 上可正常显示（路径无大小写问题、无中文）
- [ ] 暗色/亮色主题下图片可见（不使用纯白背景配亮色图片）

## 4. 文档完整性

- [ ] README 首页 30 秒内传达项目目标
- [ ] README "快速开始" 部分可一步到位完成安装
- [ ] README 所有代码块命令可真实运行（无伪命令）
- [ ] 所有文档链接（Markdown `[text](path)`）指向存在的文件
- [ ] 外部链接（GitHub、Blender、MCP 等）可访问
- [ ] `docs/` 目录下每篇文档有实际内容，无空文件
- [ ] `PROJECT_STATUS.md` 功能状态与实际代码一致
- [ ] `TERMS_AND_CONDITIONS.md` 法律条款完整

## 5. 安装流程验证

- [ ] `uv venv` 创建虚拟环境成功
- [ ] `uv pip install -p .venv/Scripts/python.exe -e .` 安装成功（Windows）
- [ ] `uv pip install -p .venv/bin/python -e .` 安装成功（macOS/Linux）
- [ ] `python -m pytest tests/ -v` 可执行
- [ ] `uvx blender-mcp` 可启动（假设 Blender 插件已安装）
- [ ] 一键测试脚本 `scripts/run_all_tests.ps1` 可执行

## 6. 配置与密钥

- [ ] `config.py` 在 `.gitignore` 中（不提交本地配置）
- [ ] `config.py.example` 包含所有必需配置项的模板
- [ ] 所有外部 API Key 的获取方法在文档中有说明
- [ ] 环境变量（`BLENDER_HOST`、`BLENDER_PORT` 等）在 README 中列出

## 7. Git 与版本

- [ ] 当前分支为 `main`（无未合并的 `feature/` 分支）
- [ ] 远程 `origin/main` 可正常拉取（无冲突）
- [ ] 所有文件 `user.name = "Jianglian Xu"` / `user.email = "XUJL-916@users.noreply.github.com"`
- [ ] Git credential 配置正确（`manager` 或 `selector`，无警告）
- [ ] `CHANGELOG.md` 或 `PROJECT_STATUS.md` 已更新本次变更摘要
- [ ] `pyproject.toml` 版本号与当前版本一致

## 8. 安全审计

- [ ] 无硬编码密钥（`grep -r "sk-" . --include="*.py"` 无结果）
- [ ] 无敏感信息泄露（`.env` 文件、个人 API Key、Token）
- [ ] `execute_blender_code` 的安全警告已在 README 中注明
- [ ] `.gitignore` 排除 `.venv/`、`__pycache__/`、`.DS_Store`、`*.pyc`、`config.py`

## 9. 发布前最终检查

- [ ] `git status` 显示工作目录干净（无未 tracked 文件）
- [ ] `git diff main origin/main --stat` 确认本次提交范围
- [ ] 所有新文件已 `git add`
- [ ] Commit message 遵循约定格式（`feat:`, `docs:`, `fix:`, `refactor:` 前缀）
- [ ] 推送前最后一次 `git pull origin main`（避免冲突）
- [ ] 推送后检查 GitHub 页面：README 渲染正常、图片加载成功、所有链接有效

---

## 执行示例

```bash
# 完整发布检查流程
./scripts/run_all_tests.ps1           # 步骤 2: 全部测试
python scripts/check_blender_512_compatibility.py  # 步骤 2: 兼容性
git add -A                             # 步骤 7: 暂存所有更改
git status                             # 步骤 1 & 8: 确认无未 tracked 文件
git diff --cached --stat               # 步骤 7: 确认提交范围
git commit -m "docs: update README with v1.5.5 content"  # 步骤 7: 提交
git push origin main                   # 步骤 9: 推送
```

---

## 变更日志 (v1.5.5-enh)

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-06-01 | README 重写 | 完整重构为专业开源项目 README，添加 4 张渲染图、架构图、快速开始指南 |
| 2026-06-01 | 代码头部 | 所有 Python 文件添加 XUJL/SZU 版权头（方案 C） |
| 2026-06-01 | Git 修复 | 修正所有 commit 作者信息为 Jianglian Xu (XUJL-916) |
| 2026-06-01 | 渲染截图 | 新增 4 张 Blender 5.1.2 渲染图（对象/材质/动画/架构） |
| 2026-06-01 | Release Checklist | 新增 v1.5.5 发布检查清单 |
| 2026-06-01 | Logo | 新增 SVG Logo（带旋转动画和电路线装饰） |
