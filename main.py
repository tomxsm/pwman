import sys

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tom.pwman.app")
    except Exception:
        pass

from gui import App

if __name__ == "__main__":
    App().mainloop()