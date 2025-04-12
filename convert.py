import os
import sys
from subprocess import run, CalledProcessError

def convert_md_to_html(path_to_md):
    if not os.path.exists(path_to_md):
        print(f"Файл {path_to_md} не существует")
        return
    
    path_to_html = path_to_md[:-3] + ".html"
    
    try:
        run(["which", "pandoc"], check=True)
    except CalledProcessError:
        print("pandoc не установлен")
        print("sudo pacman -S pandoc")
        return
    
    try:
        run(["pandoc", "-s", path_to_md, "-o", path_to_html], check=True)
    except CalledProcessError as e:
        print(f"{e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)
    convert_md_to_html(sys.argv[1])
