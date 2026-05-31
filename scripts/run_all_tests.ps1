# Blender-MCP 一键测试脚本
# 版本: 1.5.5-enh | 日期: 2026-06-01
# 功能: 运行单元测试、兼容性检查、项目分析

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Blender-MCP 一键测试" -ForegroundColor Cyan
Write-Host "  版本: 1.5.5-enh" -ForegroundColor Cyan
Write-Host "  日期: $(Get-Date -Format 'yyyy-MM-dd')" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$StartTime = Get-Date
$AllPassed = $true

# 确保使用项目 venv
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[WARN] .venv 不存在，尝试创建..." -ForegroundColor Yellow
    uv venv
}
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] 无法找到 Python 解释器，请检查 .venv 目录" -ForegroundColor Red
    exit 1
}

# ========== 1. 单元测试 ==========
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "  [1/3] 运行单元测试 (pytest)" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$pytestOutput = & $VenvPython -m pytest tests/ -v --tb=short 2>&1
$pytestExit = $LASTEXITCODE

Write-Host $pytestOutput

if ($pytestExit -ne 0) {
    Write-Host ""
    Write-Host "[FAIL] 单元测试失败 (退出码: $pytestExit)" -ForegroundColor Red
    $AllPassed = $false
} else {
    Write-Host "[PASS] 单元测试全部通过" -ForegroundColor Green
}

# ========== 2. 兼容性检查 ==========
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "  [2/3] 运行 Blender 5.1.2 兼容性检查" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$compatOutput = & $VenvPython scripts/check_blender_512_compatibility.py 2>&1
$compatExit = $LASTEXITCODE

Write-Host $compatOutput

if ($compatExit -ne 0) {
    Write-Host ""
    Write-Host "[WARN] 兼容性检查有警告，请检查上述输出" -ForegroundColor Yellow
} else {
    Write-Host "[PASS] 兼容性检查通过" -ForegroundColor Green
}

# ========== 3. 项目分析 ==========
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "  [3/3] 运行项目分析" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$analysisOutput = & $VenvPython scripts/project_analyzer.py 2>&1
$analysisExit = $LASTEXITCODE

Write-Host $analysisOutput

if ($analysisExit -ne 0) {
    Write-Host ""
    Write-Host "[WARN] 项目分析有警告，请检查上述输出" -ForegroundColor Yellow
} else {
    Write-Host "[PASS] 项目分析完成" -ForegroundColor Green
}

# ========== 汇总 ==========
$EndTime = Get-Date
$Duration = ($EndTime - $StartTime).TotalSeconds

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  测试汇总" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  总耗时: $([math]::Round($Duration, 1)) 秒" -ForegroundColor White
Write-Host "  单元测试: $(if ($pytestExit -eq 0) { 'PASS' } else { 'FAIL' })" -ForegroundColor $(if ($pytestExit -eq 0) { 'Green' } else { 'Red' })
Write-Host "  兼容性检查: $(if ($compatExit -eq 0) { 'PASS' } else { 'PASS (WARNINGS)' })" -ForegroundColor $(if ($compatExit -eq 0) { 'Green' } else { 'Yellow' })
Write-Host "  项目分析: $(if ($analysisExit -eq 0) { 'PASS' } else { 'PASS (WARNINGS)' })" -ForegroundColor $(if ($analysisExit -eq 0) { 'Green' } else { 'Yellow' })

if ($AllPassed) {
    Write-Host ""
    Write-Host "[SUCCESS] 所有测试通过！" -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "[WARNING] 部分测试未通过，请检查上述输出" -ForegroundColor Yellow
    exit 1
}
