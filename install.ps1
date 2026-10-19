# CBLhomemonitor - Instalador Windows (Suporta Release Standalone .exe e Codigo-Fonte)
$ErrorActionPreference = "Continue"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       CBLhomemonitor - Instalador do Sistema" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

# Localizar executavel compilado (na raiz da Release ou em dist\CBLhomemonitor)
$exeRoot = Join-Path $AppDir "CBLhomemonitor.exe"
$exeDist = Join-Path $AppDir "dist\CBLhomemonitor\CBLhomemonitor.exe"
$exePath = $null

if (Test-Path $exeRoot) {
    $exePath = $exeRoot
} elseif (Test-Path $exeDist) {
    $exePath = $exeDist
}

if ($exePath) {
    # ==========================================================
    # MODO 1: RELEASE STANDALONE (.EXE COMPILADO)
    # Nao requer Python nem requirements.txt instalados no PC!
    # ==========================================================
    Write-Host "[1/3] Versao Standalone detectada:" -ForegroundColor Yellow
    Write-Host "      $exePath" -ForegroundColor Green

    Write-Host "[2/3] Preparando arquivos de configuracao..." -ForegroundColor Yellow
    $workDir = Split-Path -Parent $exePath
    $cfgFile = Join-Path $workDir "config.json"
    $cfgExample = Join-Path $workDir "config.example.json"
    if ((-not (Test-Path $cfgFile)) -and (Test-Path $cfgExample)) {
        Copy-Item $cfgExample $cfgFile -Force
        Write-Host "      Arquivo config.json inicial criado." -ForegroundColor Green
    } else {
        Write-Host "      Configuracao pronta." -ForegroundColor Green
    }
} else {
    # ==========================================================
    # MODO 2: CODIGO-FONTE (DESENVOLVEDOR / SCRIPT PYTHON)
    # ==========================================================
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

    $reqFile = Join-Path $AppDir "requirements.txt"
    if (Test-Path $reqFile) {
        Write-Host "[2/4] Instalando dependencias do projeto..." -ForegroundColor Yellow
        python -m pip install -r "$reqFile" --quiet --no-warn-script-location
        Write-Host "      Dependencias verificadas com sucesso!" -ForegroundColor Green
    }

    $iconScript = Join-Path $AppDir "create_icon.py"
    if (Test-Path $iconScript) {
        Write-Host "[3/4] Gerando icones do sistema..." -ForegroundColor Yellow
        python "$iconScript"
    }
}

# Criar atalhos na Area de Trabalho e Menu Iniciar
Write-Host "[*] Criando atalhos na Area de Trabalho e Menu Iniciar..." -ForegroundColor Yellow

$ws = New-Object -ComObject WScript.Shell
$desk = [System.Environment]::GetFolderPath('Desktop')
$progs = [System.Environment]::GetFolderPath('Programs')

# Localizar icone (.ico) em todas as posicoes possiveis
$icoCandidates = @(
    (Join-Path $AppDir "static\img\icon.ico"),
    (Join-Path $AppDir "_internal\static\img\icon.ico"),
    (Join-Path $AppDir "dist\CBLhomemonitor\_internal\static\img\icon.ico")
)
$icoPath = $null
foreach ($candidate in $icoCandidates) {
    if (Test-Path $candidate) {
        $icoPath = $candidate
        break
    }
}
if ((-not $icoPath) -and $exePath) {
    $icoPath = $exePath
}

if ($exePath) {
    $target = $exePath
    $args = ""
    $workDir = Split-Path -Parent $exePath
} else {
    $pywPath = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
    if (-not $pywPath) { $pywPath = (Get-Command python -ErrorAction SilentlyContinue).Source }
    $target = $pywPath
    $args = "`"" + (Join-Path $AppDir "tray_app.py") + "`""
    $workDir = $AppDir
}

# Atalho na Area de Trabalho
$s1 = $ws.CreateShortcut((Join-Path $desk "CBLhomemonitor.lnk"))
$s1.TargetPath = $target
$s1.Arguments = $args
$s1.WorkingDirectory = $workDir
if ($icoPath) { $s1.IconLocation = $icoPath }
$s1.Description = "CBLhomemonitor - Monitor de Rede Residencial MikroTik"
$s1.Save()

# Atalho no Menu Iniciar
$s2 = $ws.CreateShortcut((Join-Path $progs "CBLhomemonitor.lnk"))
$s2.TargetPath = $target
$s2.Arguments = $args
$s2.WorkingDirectory = $workDir
if ($icoPath) { $s2.IconLocation = $icoPath }
$s2.Description = "CBLhomemonitor - Monitor de Rede Residencial MikroTik"
$s2.Save()

Write-Host "      Atalhos criados com sucesso!" -ForegroundColor Green

# Iniciar o servico
Write-Host "[*] Iniciando o CBLhomemonitor na Barra de Tarefas..." -ForegroundColor Yellow
if ($exePath) {
    Start-Process -FilePath $exePath -WorkingDirectory $workDir
} else {
    Start-Process -FilePath $target -ArgumentList "tray_app.py" -WorkingDirectory $AppDir
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  [OK] CBLhomemonitor Instalado e Iniciado com Sucesso!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host "- O icone do sistema esta ativo ao lado do relogio do Windows."
Write-Host "- Clique com o botao direito nele para Iniciar, Parar ou Configurar."
Write-Host "- Abrindo o painel web em http://localhost:8000..."
Write-Host ""

Start-Sleep -Seconds 3
Start-Process "http://localhost:8000"
