# Blender-MCP Runtime 测试脚本
# 版本: 1.5.5-enh | 日期: 2026-06-01
# 功能: 调用 Blender 5.1.2 headless 模式执行真实 Runtime 测试

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BlenderPath = "D:/Program Files/blender/blender.exe"
$TestDir = Join-Path $ProjectRoot "tests/runtime"
$OutputDir = Join-Path $ProjectRoot "blender_test_output"

if (-not (Test-Path $BlenderPath)) {
    Write-Host "[ERROR] 找不到 Blender 5.1.2: $BlenderPath" -ForegroundColor Red
    Write-Host "请修改脚本中的 BlenderPath 变量指向正确的 Blender 安装路径。" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $TestDir)) {
    Write-Host "[ERROR] 测试目录不存在: $TestDir" -ForegroundColor Red
    exit 1
}

# 创建输出目录
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Blender-MCP Runtime 测试" -ForegroundColor Cyan
Write-Host "  Blender: $BlenderPath" -ForegroundColor Cyan
Write-Host "  日期: $(Get-Date -Format 'yyyy-MM-dd')" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$BlenderPython = & $BlenderPath -b --python-expr "import sys; print(sys.executable)" 2>$null
if (-not $BlenderPython) {
    Write-Host "[ERROR] 无法启动 Blender，请确认路径正确且 Blender 未正在运行。" -ForegroundColor Red
    exit 1
}

$StartTime = Get-Date
$Results = @{}
$Total = 0
$Passed = 0
$Failed = 0
$Skipped = 0

# 获取测试文件列表
$TestFiles = Get-ChildItem -Path $TestDir -Filter "test*_*.py" | Sort-Object Name

if ($TestFiles.Count -eq 0) {
    Write-Host "[WARN] 在 $TestDir 中未找到测试文件" -ForegroundColor Yellow
    exit 0
}

Write-Host "找到 $($TestFiles.Count) 个测试文件:" -ForegroundColor Cyan
foreach ($f in $TestFiles) {
    Write-Host "  - $($f.Name)" -ForegroundColor DarkGray
}
Write-Host ""

foreach ($TestFile in $TestFiles) {
    $TestName = $TestFile.BaseName
    $Total++
    
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "  运行: $TestName" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    
    $TestPath = $TestFile.FullName
    $JsonOutput = Join-Path $OutputDir "$TestName.json"
    
    # 执行测试
    try {
        $Output = & $BlenderPath -b --python $TestPath -- --output $OutputDir 2>&1 | Out-String
        $ExitCode = $LASTEXITCODE
        
        # 尝试读取 JSON 结果
        $Result = @{
            Name = $TestName
            File = $TestFile.Name
            ExitCode = $ExitCode
            Output = $Output
        }
        
        if (Test-Path $JsonOutput) {
            try {
                $Result.Data = Get-Content $JsonOutput -Raw | ConvertFrom-Json
            } catch {
                $Result.Data = $null
            }
        }
        
        if ($ExitCode -eq 0) {
            Write-Host "[PASS] $TestName" -ForegroundColor Green
            $Results[$TestName] = "PASS"
            $Passed++
        } else {
            Write-Host "[FAIL] $TestName (exit code: $ExitCode)" -ForegroundColor Red
            Write-Host "  输出: $($Output -replace "`n", " | " -replace "`r", "")" -ForegroundColor DarkRed
            $Results[$TestName] = "FAIL"
            $Failed++
        }
        
    } catch {
        Write-Host "[ERROR] $TestName: $($_.Exception.Message)" -ForegroundColor Red
        $Results[$TestName] = "ERROR"
        $Failed++
    }
    
    Write-Host ""
}

# ========== 汇总 ==========
$EndTime = Get-Date
$Duration = ($EndTime - $StartTime).TotalSeconds

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Runtime 测试汇总" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  总耗时: $([math]::Round($Duration, 1)) 秒" -ForegroundColor White
Write-Host "  总计: $Total | PASS: $Passed | FAIL: $Failed | SKIP: $Skipped" -ForegroundColor White
Write-Host ""

Write-Host "  详细结果:" -ForegroundColor White
foreach ($Key in $Results.Keys) {
    $Color = if ($Results[$Key] -eq "PASS") { "Green" } else { "Red" }
    Write-Host "    $($Key): $($Results[$Key])" -ForegroundColor $Color
}

Write-Host ""
if ($Failed -eq 0) {
    Write-Host "[SUCCESS] 所有 Runtime 测试通过！" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[WARNING] $Failed 个 Runtime 测试失败，请检查上述输出。" -ForegroundColor Yellow
    exit 1
}
