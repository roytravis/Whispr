# Cara Menjalankan Parakeet Clone

## Prasyarat
- Windows 10/11
- [uv](https://docs.astral.sh/uv/) sudah terinstall
- PowerShell

## Setup (pertama kali)
```powershell
cd C:\parakeet-clone
uv sync
```

## Menjalankan Program
```powershell
cd C:\parakeet-clone
.\run.ps1
```

## Catatan Penting

**JANGAN gunakan** `uv run python main.py` — akan membuka Python REPL, bukan menjalankan program.
Ini adalah bug uv trampoline di Windows yang tidak meneruskan argumen ke Python.

`run.ps1` mem-bypass masalah ini dengan memanggil CPython asli langsung dan mengarahkan `PYTHONPATH` ke venv.

## Jika Menambah Dependency Baru
1. Tambahkan dependency di `pyproject.toml`
2. Jalankan `uv sync`
3. Jalankan `.\run.ps1` seperti biasa
