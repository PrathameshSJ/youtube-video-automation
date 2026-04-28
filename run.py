import os
import subprocess
import sys

def main():
    venv_dir = "venv"
    if os.name == "nt":
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        python_exe = os.path.join(venv_dir, "bin", "python")
        pip_exe = os.path.join(venv_dir, "bin", "pip")
    
    if not os.path.exists(venv_dir):
        print("--- Creating Virtual Environment ---")
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    
    print("--- Installing/Updating Requirements ---")
    subprocess.run([pip_exe, "install", "-r", "requirements.txt"], check=True)

    print("--- Starting Video Generation ---")
    # Build command list to avoid shell parsing issues
    cmd = [python_exe, "generate_v2.py"] + sys.argv[1:]
    print(f"Executing: {' '.join(cmd)}")
    
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
