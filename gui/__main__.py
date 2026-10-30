"""GUI 入口，支持 python -m gui（含跨平台单实例锁）"""
import platform
import sys
import os
import flet as ft
from gui.app import main_app

LOCK_FILE = os.path.join(os.path.expanduser("~"), ".doubao_export.lock")

def acquire_lock():
    global lock_fd
    try:
        system = platform.system()
        if system == 'Windows':         
            lock_fd = open(LOCK_FILE, 'w')
            import msvcrt
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:                        
            lock_fd = open(LOCK_FILE, 'w')
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, OSError):
        return False

def main():
    # 打包后限制单实例；开发模式允许多开
    if getattr(sys, 'frozen', False) and not acquire_lock():
        sys.exit(0)
    ft.run(main_app)

if __name__ == "__main__":
    main()