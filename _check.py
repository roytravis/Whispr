import subprocess, sys, os
os.chdir(r"C:\parakeet-clone")
result = subprocess.run([sys.executable, "-m", "uv", "lock"], capture_output=True, text=True)
with open(r"C:\parakeet-clone\_check_out.txt", "w") as f:
    f.write(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nRC:{result.returncode}\n")
