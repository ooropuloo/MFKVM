# Dot-source to get the private ESP-IDF v6.1 environment in this process only.
# The machine's IDF_TOOLS_PATH points at another project's install, so it is overridden here, never globally.
Remove-Item Env:MSYSTEM -ErrorAction SilentlyContinue
# Override with MFKVM_IDF_PATH, MFKVM_IDF_TOOLS_PATH, MFKVM_PYTHON_DIR. The D:\tools defaults are only where this build was made.
$env:IDF_PATH = if ($env:MFKVM_IDF_PATH) { $env:MFKVM_IDF_PATH } else { "D:\tools\esp-idf-v6.1" }
$env:IDF_TOOLS_PATH = if ($env:MFKVM_IDF_TOOLS_PATH) { $env:MFKVM_IDF_TOOLS_PATH } else { "D:\tools\espressif" }
# Reuse compile results across the variants. Does not change the output.
$env:IDF_CCACHE_ENABLE = "1"
$env:CCACHE_DIR = "$($env:IDF_TOOLS_PATH -replace '\\', '/')/ccache"
# ESP-IDF 6.1 needs a newer Python than the machine default 3.9; this one is only used to create its venv.
$py = if ($env:MFKVM_PYTHON_DIR) { $env:MFKVM_PYTHON_DIR } else { "$env:APPDATA\uv\python\cpython-3.11.13-windows-x86_64-none" }
$env:PATH = "$py;$env:PATH"
if (-not $env:IDF_ENV_SKIP_EXPORT) {
    . "$env:IDF_PATH\export.ps1" | Out-Null
}
