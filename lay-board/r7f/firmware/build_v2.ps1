# Builds one P4 KVM Mini variant from clean, on an espkvm checkout with patches/0001 and 0002 applied. Compile only. Does not flash.
#   pwsh -File build_v2.ps1 -Name v2r7_rev3 -Rev3
#   pwsh -File build_v2.ps1 -Name v2r7_pre3
# Needs boards/p4_kvm_mini.defaults in the checkout. Refuses an existing build directory, because its sdkconfig would beat the defaults.
# Writes logs/build_<Name>.log and logs/build_<Name>.exit next to this script. All environment changes stay in this process.
param(
    [Parameter(Mandatory)][string]$Name,
    [switch]$Rev3,
    [string]$Tree = "D:\git\p4-kvm-box\v3\firmware\espkvm"
)
$logs = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs "build_$Name.log"
$exitFile = Join-Path $logs "build_$Name.exit"
Remove-Item $exitFile -ErrorAction SilentlyContinue
$dir = "build.$Name"
if (Test-Path (Join-Path $Tree $dir)) { Write-Output "REFUSED: $dir exists"; exit 3 }
if (-not (Test-Path (Join-Path $Tree "boards\p4_kvm_mini.defaults"))) { Write-Output "REFUSED: copy p4_kvm_mini.defaults to boards\ first"; exit 3 }
$defaults = "sdkconfig.defaults;boards/moduledevkit_p4.defaults;" + $(if ($Rev3) { "boards/moduledevkit_p4_rev3.defaults;" } else { "" }) + "boards/p4_kvm_mini.defaults"

. "D:\git\p4-kvm-box\v3\firmware\scripts\idf_env.ps1"
Set-Location $Tree
& python -u "$env:IDF_PATH\tools\idf.py" -B $dir -D "SDKCONFIG=$dir/sdkconfig" -D "SDKCONFIG_DEFAULTS=$defaults" build *> $log
$code = $LASTEXITCODE
Set-Content -Path $exitFile -Value $code
"exit=$code"
exit $code
