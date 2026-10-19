# CBLhomemonitor - Instalador Windows
$ErrorActionPreference = "Continue"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       CBLhomemonitor - Instalador do Sistema" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

# 1. Verificar Python
Write-Host "[1/4] Verificando instalacao do Python..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[!] Python nao encontrado. Tentando instalar via winget..." -ForegroundColor Red
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Host "[X] Instale o Python em https://www.python.org/downloads/ marcando 'Add python.exe to PATH'." -ForegroundColor Red
        Read-Host "Pressione ENTER para sair..."
        exit 1
    }
}
Write-Host "      Python detectado: $($py.Source)" -ForegroundColor Green

# 2. Instalar dependencias
Write-Host "[2/4] Instalando dependencias do projeto..." -ForegroundColor Yellow
python -m pip install -r requirements.txt --quiet --no-warn-script-location
Write-Host "      Dependencias verificadas com sucesso!" -ForegroundColor Green

# 3. Gerar icones
Write-Host "[3/4] Gerando icones e criando atalhos no Windows..." -ForegroundColor Yellow
python create_icon.py

$ws = New-Object -ComObject WScript.Shell
$desk = [System.Environment]::GetFolderPath('Desktop')
$progs = [System.Environment]::GetFolderPath('Programs')

$exePath = Join-Path $AppDir "dist\CBLhomemonitor\CBLhomemonitor.exe"
$icoPath = Join-Path $AppDir "static\img\icon.ico"
$pywPath = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pywPath) { $pywPath = (Get-Command python -ErrorAction SilentlyContinue).Source }

$target = if (Test-Path $exePath) { $exePath } else { $pywPath }
$args = if (Test-Path $exePath) { "" } else { "`"" + (Join-Path $AppDir "tray_app.py") + "`"" }
$workDir = if (Test-Path $exePath) { Split-Path -Parent $exePath } else { $AppDir }

# Atalho na Area de Trabalho
$s1 = $ws.CreateShortcut((Join-Path $desk "CBLhomemonitor.lnk"))
$s1.TargetPath = $target
$s1.Arguments = $args
$s1.WorkingDirectory = $workDir
$s1.IconLocation = $icoPath
$s1.Description = "CBLhomemonitor - Monitor de Rede Residencial MikroTik"
$s1.Save()

# Atalho no Menu Iniciar
$s2 = $ws.CreateShortcut((Join-Path $progs "CBLhomemonitor.lnk"))
$s2.TargetPath = $target
$s2.Arguments = $args
$s2.WorkingDirectory = $workDir
$s2.IconLocation = $icoPath
$s2.Description = "CBLhomemonitor - Monitor de Rede Residencial MikroTik"
$s2.Save()

Write-Host "      Atalhos criados na Area de Trabalho e Menu Iniciar!" -ForegroundColor Green

# 4. Iniciar o servico
Write-Host "[4/4] Iniciando o CBLhomemonitor na Barra de Tarefas..." -ForegroundColor Yellow
if (Test-Path $exePath) {
    Start-Process -FilePath $exePath -WorkingDirectory $workDir
} else {
    Start-Process -FilePath $pywPath -ArgumentList "tray_app.py" -WorkingDirectory $AppDir
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  [OK] CBLhomemonitor Instalado e Iniciado com Sucesso!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host "- O icone do sistema esta ativo ao lado do relogio do Windows."
Write-Host "- Clique com o botao direito nele para Iniciar, Parar ou Configurar."
Write-Host "- Abrindo o painel web em http://localhost:8000..."
Write-Host ""

Start-Sleep -Seconds 2
Start-Process "http://localhost:8000"
