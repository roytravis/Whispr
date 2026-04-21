$python = "C:\Users\Roy\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none\python.exe"
$env:VIRTUAL_ENV = "C:\parakeet-clone\.venv"
$env:PYTHONPATH = "C:\parakeet-clone\.venv\Lib\site-packages"

Write-Host "Installing assemblyai into venv..."
& $python -m pip install assemblyai --target "C:\parakeet-clone\.venv\Lib\site-packages"
Write-Host "Done. Now run: .\run.ps1"
