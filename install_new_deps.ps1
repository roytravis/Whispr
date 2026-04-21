$venvPython = "C:\parakeet-clone\.venv\Scripts\python.exe"

Write-Host "Installing markdown and Pygments into venv..." -ForegroundColor Cyan
& $venvPython -m pip install markdown Pygments
Write-Host ""
Write-Host "Done! Now run: .\run.ps1" -ForegroundColor Green
