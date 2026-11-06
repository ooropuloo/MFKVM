# Build one espkvm variant with the private ESP-IDF install. All environment changes stay in this process.
#   pwsh -File idf_build.ps1 -Name firebeetle -Defaults "sdkconfig.defaults;boards/firebeetle2_p4.defaults"
# Writes logs/build_<Name>.log and logs/build_<Name>.exit (the idf.py exit code).
param(
    [Parameter(Mandatory)][string]$Name,
    [Parameter(Mandatory)][string]$Defaults,
    [string]$Tree = (Join-Path $PSScriptRoot "..\espkvm")
)
$fw = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force "$fw\logs" | Out-Null
$log = "$fw\logs\build_$Name.log"
$exitFile = "$fw\logs\build_$Name.exit"
Remove-Item $exitFile -ErrorAction SilentlyContinue

. "$PSScriptRoot\idf_env.ps1"
Set-Location $Tree
$dir = "build.$Name"
& python -u "$env:IDF_PATH\tools\idf.py" -B $dir -D "SDKCONFIG=$dir/sdkconfig" -D "SDKCONFIG_DEFAULTS=$Defaults" build *> $log
$code = $LASTEXITCODE
Set-Content -Path $exitFile -Value $code
"exit=$code"
exit $code
