import sys

from database.schema import create_tables

from ui.main_window import MainWindow


def main():

    if sys.platform == "win32":
        import ctypes

        # Lets Windows show the app's own icon in the taskbar instead of Python's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LaUnion.GestorVentas")

    create_tables()

    app = MainWindow()

    app.mainloop()


if __name__ == "__main__":
    main()