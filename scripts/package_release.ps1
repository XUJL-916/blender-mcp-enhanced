# Blender-MCP Release 打包脚本
# 版本: 1.5.5-enh | 日期: 2026-06-01
# 功能: 打包当前项目为 release zip

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputDir = Join-Path $ProjectRoot ".." # 打包到上级目录
$Version = "1.5.5-enh"
$DateStr = Get-Date -Format "yyyyMMdd"
$ZipName = "BlenderMCP_${Version}_${DateStr}.zip"
$ZipPath = Join-Path $OutputDir $ZipName

# 创建临时目录
$TempDir = Join-Path $ProjectRoot ".release_temp"
if (Test-Path $TempDir) {
    Remove-Item $TempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Blender-MCP Release 打包" -ForegroundColor Cyan
Write-Host "  版本: $Version" -ForegroundColor Cyan
Write-Host "  日期: $DateStr" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 排除规则
$ExcludePatterns = @(
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".pyre_cache",
    ".mypy_cache",
    "__pycache__",
    "*.egg-info",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    ".gitignore",
    ".hermes",
    ".vscode",
    "blender_test_output",
    "*.log",
    "*.tmp",
    ".DS_Store"
)

# 复制项目文件到临时目录
Write-Host "[1/3] 复制项目文件..." -ForegroundColor Yellow

$ProjectFiles = Get-ChildItem -Path $ProjectRoot -Force -Recurse -File

$Copied = 0
$Skipped = 0

foreach ($File in $ProjectFiles) {
    # 检查是否应排除
    $RelPath = $File.FullName.Substring($ProjectRoot.Length + 1)
    $Skip = $false
    
    foreach ($Pattern in $ExcludePatterns) {
        if ($RelPath -like "*$Pattern*" -or $File.Name -like $Pattern) {
            $Skip = $true
            break
        }
    }
    
    if ($Skip) {
        $Skipped++
        continue
    }
    
    # 确保目录结构
    $DestFile = Join-Path $TempDir $RelPath
    $DestDir = Split-Path $DestFile -Parent
    if (-not (Test-Path $DestDir)) {
        New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    }
    
    Copy-Item $File.FullName $DestFile -Force
    $Copied++
}

Write-Host "  已复制: $Copied 文件" -ForegroundColor Green
Write-Host "  已跳过: $Skipped 文件/目录" -ForegroundColor DarkGray
Write-Host ""

# 打包 zip
Write-Host "[2/3] 打包 release zip..." -ForegroundColor Yellow

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

try {
    Compress-Archive -Path "$TempDir\*" -DestinationPath $ZipPath -Force
    Write-Host "  打包完成: $ZipPath" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 打包失败: $($_.Exception.Message)" -ForegroundColor Red
    Remove-Item $TempDir -Recurse -Force
    exit 1
}

# 清理临时目录
Write-Host "[3/3] 清理临时文件..." -ForegroundColor Yellow

if (Test-Path $TempDir) {
    Remove-Item $TempDir -Recurse -Force
    Write-Host "  临时目录已清理" -ForegroundColor Green
}

# 汇总
$ZipSize = (Get-Item $ZipPath).Length
$ZipSizeMB = [math]::Round($ZipSize / 1MB, 2)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  打包完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  文件名: $ZipName" -ForegroundColor White
Write-Host "  路径: $ZipPath" -ForegroundColor White
Write-Host "  大小: $ZipSizeMB MB" -ForegroundColor White
Write-Host "  文件数: $Copied" -ForegroundColor White
Write-Host ""
Write-Host "[SUCCESS] Release 打包完成！" -ForegroundColor Green
exit 0
