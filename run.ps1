$python = "C:\Users\Roy\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none\python.exe"
$sitePackages = "C:\parakeet-clone\.venv\Lib\site-packages"
$env:VIRTUAL_ENV = "C:\parakeet-clone\.venv"
$env:PYTHONPATH = $sitePackages
& $python main.py
