import os
import sys
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from PIL import Image, ImageTk

from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

import pandas as pd

from database.db_manager import DATA_DIR, connection
from database.stats import get_database_stats

from ingestion.customers_csv import load_customers
from ingestion.products_csv import load_products
from ingestion.pdf_sales import load_sales, PeriodExistsError


# Design tokens: (light, dark) tuples follow the active appearance mode
FONT = "Segoe UI"
MONO = "Consolas"

APP_NAME = "La Unión · Gestor de Ventas"

# PyInstaller unpacks bundled files into sys._MEIPASS
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
LOGO_PATH = BASE_DIR / "Logo-D_KM-qWO.png"

# Brand palette sampled from the La Unión logo
BRAND_GREEN = "#102E1E"
BRAND_GREEN_LIGHT = "#1F5C3D"
BRAND_RED = "#A21E1C"
BRAND_RED_HOVER = "#861816"
BRAND_GOLD = "#BF9C5D"
BRAND_GOLD_HOVER = "#D1B17A"
BRAND_OLIVE = "#68653E"

ACCENT = BRAND_RED
ACCENT_HOVER = BRAND_RED_HOVER
SELECT = ("#1F5C3D", "#2E7A52")
SELECT_HOVER = ("#17472F", "#256544")

BG = ("#F6F2EA", "#0C1A12")
SURFACE = ("#FFFFFF", "#142519")
BORDER = ("#E6DCC8", "#26402F")
TEXT = ("#1C2A21", "#F3EEE3")
MUTED = ("#6E6A5E", "#A4B0A3")
HEADING_BG = ("#F1E9D9", "#102E1E")
HEADING_TEXT = (BRAND_GREEN, BRAND_GOLD)
ROW_ALT = ("#FBF8F2", "#182C20")

SIDEBAR_BG = BRAND_GREEN
SIDEBAR_HOVER = "#1B4630"
SIDEBAR_ACTIVE = BRAND_GOLD
SIDEBAR_ACTIVE_HOVER = BRAND_GOLD_HOVER
SIDEBAR_TEXT = "#F3EDE0"
SIDEBAR_MUTED = "#8FA597"

SUCCESS = "#2E8B57"
WARNING = "#D08C1A"
ERROR = "#C62828"
INFO = "#B08A48"

KPI_CARDS = [
    ("customers", "Clientes", "👥", BRAND_GREEN_LIGHT),
    ("products", "Productos", "📦", BRAND_RED),
    ("sales", "Líneas de venta", "🧾", BRAND_GOLD),
    ("last_period", "Último periodo", "📅", BRAND_OLIVE),
]

# Whitelist of browsable tables: display name -> (sql table, column labels)
TABLES = {
    "Clientes": ("customers", {
        "customer_id": "ID cliente",
        "legal_name": "Razón social",
        "parent_customer_name": "Grupo cliente",
        "customer_name": "Nombre cliente",
        "city": "Ciudad",
        "registration_date": "Fecha alta",
        "fiscal_period": "Periodo fiscal",
        "payment_terms": "Condiciones de pago",
        "sales_rep": "Comercial",
    }),
    "Productos": ("products", {
        "product_id": "ID producto",
        "reference_code": "Referencia",
        "product_name": "Nombre producto",
        "product_type": "Tipo",
        "units_per_case": "Uds./caja",
        "product_group": "Grupo",
        "shelf_life_days": "Vida útil (días)",
        "product_family": "Familia",
        "exportation_type": "Tipo exportación",
        "order_format": "Formato pedido",
    }),
    "Ventas": ("sales", {
        "period": "Periodo",
        "year": "Año",
        "month": "Mes",
        "customer_id": "ID cliente",
        "product_id": "ID producto",
        "units": "Unidades",
        "kg": "Kg",
        "avg_price": "Precio medio",
        "amount": "Importe",
        "source_file": "Archivo origen",
    }),
}

PAGE_SIZE = 200

TABULAR_FILETYPES = [("Excel o CSV", "*.xlsx *.xlsm *.csv")]


def fmt_number(value, decimals=0):

    text = f"{value:,.{decimals}f}"

    return text.replace(",", "X").replace(".", ",").replace("X", ".")


class MainWindow(ctk.CTk):

    def __init__(self):

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("green")

        super().__init__()

        self.title(APP_NAME)
        self.geometry("1200x720")
        self.minsize(1000, 620)
        self.configure(fg_color=BG)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.kpi_values = {}
        self.nav_buttons = {}

        self.db_table = "Clientes"
        self.db_page = 0
        self.db_total = 0
        self.db_sort = None
        self.db_sort_desc = False
        self._search_job = None
        self._last_search = ""
        self.quick_buttons = []

        self._load_brand_assets()
        self._build_sidebar()
        self._build_main()
        self._style_treeview()
        self._bind_shortcuts()

        self.show_view("dashboard")
        self.load_database_status()
        self._log("Aplicación iniciada", "info")

    # ------------------------------------------------------------------ layout

    def _load_brand_assets(self):

        self._logo = None

        if not LOGO_PATH.exists():
            return

        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.crop(logo.getchannel("A").getbbox())

        self._logo = logo.resize((400, round(400 * logo.height / logo.width)), Image.Resampling.LANCZOS)

        side = max(logo.size)
        icon = Image.new("RGBA", (side, side))
        icon.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2))

        self._icon = ImageTk.PhotoImage(icon.resize((256, 256), Image.Resampling.LANCZOS), master=self)

        # CustomTkinter sets its own window icon shortly after start-up; override it afterwards
        self.after(300, lambda: self.iconphoto(True, self._icon))

    def _build_sidebar(self):

        sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color=SIDEBAR_BG)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(9, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 22))

        if self._logo:
            width = 200
            height = round(width * self._logo.height / self._logo.width)
            image = ctk.CTkImage(light_image=self._logo, dark_image=self._logo, size=(width, height))
            ctk.CTkLabel(brand, image=image, text="").pack()
        else:
            ctk.CTkLabel(
                brand, text="La Unión", text_color=BRAND_GOLD, font=(FONT, 26, "bold")
            ).pack()

        ctk.CTkLabel(
            brand, text="GESTOR DE VENTAS", text_color=SIDEBAR_TEXT,
            font=(FONT, 12, "bold")
        ).pack(pady=(8, 0))

        ctk.CTkFrame(brand, height=2, width=60, corner_radius=1, fg_color=BRAND_GOLD).pack(pady=(6, 0))

        self._sidebar_section(sidebar, "NAVEGACIÓN").grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 8))

        self.nav_buttons["dashboard"] = self._sidebar_button(
            sidebar, "📊   Panel principal", lambda: self.show_view("dashboard")
        )
        self.nav_buttons["dashboard"].grid(row=2, column=0, sticky="ew", padx=14, pady=3)

        self.nav_buttons["database"] = self._sidebar_button(
            sidebar, "🗄   Base de datos", lambda: self.show_view("database")
        )
        self.nav_buttons["database"].grid(row=3, column=0, sticky="ew", padx=14, pady=3)

        self._sidebar_section(sidebar, "IMPORTAR DATOS").grid(row=4, column=0, sticky="ew", padx=28, pady=(24, 8))

        self.customers_button = self._sidebar_button(sidebar, "👥   Clientes", self.load_customers_file)
        self.customers_button.grid(row=5, column=0, sticky="ew", padx=14, pady=3)

        self.products_button = self._sidebar_button(sidebar, "📦   Productos", self.load_products_file)
        self.products_button.grid(row=6, column=0, sticky="ew", padx=14, pady=3)

        self.sales_button = self._sidebar_button(sidebar, "🧾   Ventas (PDF)", self.load_sales_files)
        self.sales_button.grid(row=7, column=0, sticky="ew", padx=14, pady=3)

        self._sidebar_button(sidebar, "📁   Carpeta de datos", self._open_data_folder).grid(
            row=8, column=0, sticky="ew", padx=14, pady=(18, 3)
        )

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=10, column=0, sticky="ew", padx=24, pady=24)

        ctk.CTkLabel(
            footer, text="Apariencia", text_color=SIDEBAR_MUTED,
            font=(FONT, 11, "bold"), anchor="w"
        ).pack(anchor="w", pady=(0, 6))

        modes = {"Claro": "light", "Oscuro": "dark", "Sistema": "system"}

        appearance = ctk.CTkSegmentedButton(
            footer,
            values=list(modes),
            command=lambda label: self._set_appearance(modes[label]),
            font=(FONT, 12),
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color="#0A2015",
            unselected_hover_color=SIDEBAR_HOVER,
            fg_color="#0A2015",
            text_color=SIDEBAR_TEXT,
        )
        appearance.set("Sistema")
        appearance.pack(fill="x")

    def _sidebar_section(self, parent, text):

        return ctk.CTkLabel(
            parent, text=text, text_color=BRAND_GOLD,
            font=(FONT, 11, "bold"), anchor="w"
        )

    def _sidebar_button(self, parent, text, command):

        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            anchor="w",
            height=42,
            corner_radius=10,
            font=(FONT, 14),
            fg_color="transparent",
            hover_color=SIDEBAR_HOVER,
            text_color=SIDEBAR_TEXT,
            text_color_disabled=SIDEBAR_MUTED,
        )

    def _header(self, parent, title, subtitle):

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=title, text_color=TEXT,
            font=(FONT, 28, "bold"), anchor="w"
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text=subtitle, text_color=MUTED,
            font=(FONT, 13), anchor="w"
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        return header

    def _primary_button(self, parent, text, command, width=120):

        return ctk.CTkButton(
            parent, text=text, width=width, height=36, corner_radius=10,
            font=(FONT, 13, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=command
        )

    def _card(self, parent):

        return ctk.CTkFrame(
            parent, fg_color=SURFACE, corner_radius=14,
            border_width=1, border_color=BORDER
        )

    def _build_main(self):

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=32, pady=(28, 0))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.views = {
            "dashboard": self._build_dashboard(main),
            "database": self._build_database_view(main),
        }

        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")

        status = ctk.CTkFrame(main, fg_color="transparent", height=36)
        status.grid(row=1, column=0, sticky="ew", pady=(8, 8))

        self.status_dot = ctk.CTkLabel(status, text="●", text_color=SUCCESS, font=(FONT, 12))
        self.status_dot.pack(side="left")

        self.status_label = ctk.CTkLabel(status, text="Listo", text_color=MUTED, font=(FONT, 12))
        self.status_label.pack(side="left", padx=6)

        ctk.CTkLabel(
            status, text="F5  Actualizar    ·    Ctrl+F  Buscar    ·    Ctrl+C  Copiar filas",
            text_color=MUTED, font=(FONT, 11)
        ).pack(side="right")

        self.progress = ctk.CTkProgressBar(status, width=180, height=6, progress_color=BRAND_GOLD)

    def _build_dashboard(self, parent):

        view = ctk.CTkFrame(parent, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        header = self._header(view, "Panel principal", "Resumen de los datos almacenados en la base de datos")
        header.grid(row=0, column=0, sticky="ew")

        self.refresh_button = self._primary_button(header, "⟳  Actualizar", self._refresh)
        self.refresh_button.grid(row=0, column=1, sticky="e")

        self.updated_label = ctk.CTkLabel(header, text="", text_color=MUTED, font=(FONT, 11))
        self.updated_label.grid(row=1, column=1, sticky="e", pady=(2, 0))

        cards = ctk.CTkFrame(view, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew", pady=(24, 20))

        for i, (key, label, icon, color) in enumerate(KPI_CARDS):
            cards.grid_columnconfigure(i, weight=1, uniform="kpi")
            self._kpi_card(cards, key, label, icon, color).grid(
                row=0, column=i, sticky="nsew",
                padx=(0 if i == 0 else 8, 0 if i == len(KPI_CARDS) - 1 else 8)
            )

        body = ctk.CTkFrame(view, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self._build_quick_actions(body).grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        activity = self._card(body)
        activity.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        activity.grid_columnconfigure(0, weight=1)
        activity.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            activity, text="Actividad", text_color=TEXT,
            font=(FONT, 16, "bold"), anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

        ctk.CTkButton(
            activity, text="Limpiar", width=70, height=28, corner_radius=8,
            font=(FONT, 12), fg_color="transparent", hover_color=BORDER,
            text_color=MUTED, command=self._clear_log
        ).grid(row=0, column=1, sticky="e", padx=16, pady=(16, 8))

        self.log_box = ctk.CTkTextbox(
            activity, font=(MONO, 12), fg_color="transparent",
            text_color=TEXT, wrap="word"
        )
        self.log_box.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.tag_config("success", foreground=SUCCESS)
        self.log_box.tag_config("warning", foreground=WARNING)
        self.log_box.tag_config("error", foreground=ERROR)
        self.log_box.tag_config("info", foreground=INFO)
        self.log_box.configure(state="disabled")

        return view

    def _build_quick_actions(self, parent):

        card = self._card(parent)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Importar datos", text_color=TEXT,
            font=(FONT, 16, "bold"), anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            card, text="Carga o actualiza la información de la base de datos",
            text_color=MUTED, font=(FONT, 12), anchor="w", justify="left", wraplength=280
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(2, 10))

        actions = [
            ("👥", "Clientes", "Excel o CSV con el maestro de clientes", BRAND_GREEN_LIGHT, self.load_customers_file),
            ("📦", "Productos", "Excel o CSV con el catálogo de productos", BRAND_RED, self.load_products_file),
            ("🧾", "Ventas", "Uno o varios PDF de ventas mensuales", BRAND_GOLD, self.load_sales_files),
        ]

        for i, (icon, title, description, color, command) in enumerate(actions):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.grid(row=2 + i, column=0, sticky="ew", padx=16, pady=6)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row, text=icon, width=38, height=38, corner_radius=10,
                fg_color=color, text_color="white", font=(FONT, 16)
            ).grid(row=0, column=0, rowspan=2, padx=(4, 12))

            ctk.CTkLabel(
                row, text=title, text_color=TEXT, font=(FONT, 13, "bold"), anchor="w"
            ).grid(row=0, column=1, sticky="sw")

            ctk.CTkLabel(
                row, text=description, text_color=MUTED, font=(FONT, 11),
                anchor="w", justify="left", wraplength=180
            ).grid(row=1, column=1, sticky="nw")

            button = ctk.CTkButton(
                row, text="Importar", width=84, height=30, corner_radius=8,
                font=(FONT, 12, "bold"), fg_color="transparent", hover_color=BORDER,
                text_color=SELECT, text_color_disabled=MUTED,
                border_width=1, border_color=SELECT, command=command
            )
            button.grid(row=0, column=2, rowspan=2, padx=(8, 4))

            self.quick_buttons.append(button)

        return card

    def _kpi_card(self, parent, key, label, icon, color):

        card = self._card(parent)

        ctk.CTkFrame(card, height=4, corner_radius=2, fg_color=color).pack(
            fill="x", padx=20, pady=(14, 0)
        )

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 0))

        ctk.CTkLabel(
            top, text=icon, width=34, height=34, corner_radius=8,
            fg_color=color, text_color="white", font=(FONT, 15)
        ).pack(side="left")

        ctk.CTkLabel(top, text=label, text_color=MUTED, font=(FONT, 13)).pack(side="left", padx=10)

        value = ctk.CTkLabel(card, text="—", text_color=TEXT, font=(FONT, 30, "bold"), anchor="w")
        value.pack(fill="x", padx=20, pady=(10, 18))

        self.kpi_values[key] = value

        return card

    def _build_database_view(self, parent):

        view = ctk.CTkFrame(parent, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        header = self._header(
            view, "Base de datos",
            "Consulta y busca en cada tabla  ·  Haz clic en una columna para ordenar  ·  Ctrl+C copia las filas seleccionadas"
        )
        header.grid(row=0, column=0, sticky="ew")

        toolbar = ctk.CTkFrame(view, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(20, 12))
        toolbar.grid_columnconfigure(1, weight=1)

        self.table_selector = ctk.CTkSegmentedButton(
            toolbar,
            values=list(TABLES),
            command=self._on_table_change,
            font=(FONT, 13),
            height=36,
            selected_color=SELECT,
            selected_hover_color=SELECT_HOVER,
        )
        self.table_selector.set(self.db_table)
        self.table_selector.grid(row=0, column=0, sticky="w")

        self.search_entry = ctk.CTkEntry(
            toolbar, placeholder_text="🔍  Buscar en la tabla…", height=36,
            corner_radius=10, font=(FONT, 13), border_color=BORDER, fg_color=SURFACE
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(12, 4))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(
            toolbar, text="✕", width=36, height=36, corner_radius=10,
            font=(FONT, 13), fg_color="transparent", hover_color=BORDER,
            text_color=MUTED, command=self._clear_search
        ).grid(row=0, column=2, padx=(0, 12))

        self._primary_button(toolbar, "⟳  Actualizar", self.load_table).grid(row=0, column=3, sticky="e")

        table_card = self._card(view)
        table_card.grid(row=2, column=0, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_card, style="Data.Treeview", show="headings", selectmode="extended")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(12, 0))

        y_scroll = ctk.CTkScrollbar(table_card, orientation="vertical", command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=(12, 0))

        x_scroll = ctk.CTkScrollbar(table_card, orientation="horizontal", command=self.tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        pager = ctk.CTkFrame(view, fg_color="transparent")
        pager.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        self.page_label = ctk.CTkLabel(pager, text="", text_color=MUTED, font=(FONT, 12))
        self.page_label.pack(side="left")

        self.next_button = self._pager_button(pager, "Siguiente ›", lambda: self._change_page(1))
        self.next_button.pack(side="right")

        self.prev_button = self._pager_button(pager, "‹ Anterior", lambda: self._change_page(-1))
        self.prev_button.pack(side="right", padx=8)

        return view

    def _pager_button(self, parent, text, command):

        return ctk.CTkButton(
            parent, text=text, width=100, height=32, corner_radius=8,
            font=(FONT, 12), fg_color=SURFACE, hover_color=BORDER,
            text_color=TEXT, text_color_disabled=MUTED,
            border_width=1, border_color=BORDER, command=command
        )

    def _style_treeview(self):

        dark = ctk.get_appearance_mode() == "Dark"
        idx = 1 if dark else 0

        style = ttk.Style(self)
        style.theme_use("clam")
        style.layout("Data.Treeview", [("Data.Treeview.treearea", {"sticky": "nswe"})])

        style.configure(
            "Data.Treeview",
            background=SURFACE[idx], fieldbackground=SURFACE[idx], foreground=TEXT[idx],
            rowheight=30, borderwidth=0, font=(FONT, 10)
        )
        style.configure(
            "Data.Treeview.Heading",
            background=HEADING_BG[idx], foreground=HEADING_TEXT[idx],
            font=(FONT, 10, "bold"), relief="flat", borderwidth=0, padding=(8, 8)
        )
        style.map("Data.Treeview", background=[("selected", SELECT[idx])], foreground=[("selected", "white")])
        style.map("Data.Treeview.Heading", background=[("active", BORDER[idx])])

        self.tree.tag_configure("odd", background=ROW_ALT[idx])

    def _set_appearance(self, mode):

        ctk.set_appearance_mode(mode)
        self._style_treeview()

    def show_view(self, name):

        self.current_view = name
        self.views[name].tkraise()

        for key, button in self.nav_buttons.items():
            active = key == name
            button.configure(
                fg_color=SIDEBAR_ACTIVE if active else "transparent",
                hover_color=SIDEBAR_ACTIVE_HOVER if active else SIDEBAR_HOVER,
                text_color=SIDEBAR_BG if active else SIDEBAR_TEXT,
                font=(FONT, 14, "bold" if active else "normal"),
            )

        if name == "database":
            self.load_table()

    def _bind_shortcuts(self):

        self.bind("<F5>", lambda _e: self._refresh_current())
        self.bind("<Control-f>", lambda _e: self._focus_search())
        self.search_entry.bind("<Escape>", lambda _e: self._clear_search())
        self.tree.bind("<Control-c>", self._copy_selection)
        self.tree.bind("<Control-a>", lambda _e: self.tree.selection_set(self.tree.get_children()))

    def _refresh_current(self):

        if self.current_view == "database":
            self.load_table()
        else:
            self._refresh()

    def _focus_search(self):

        if self.current_view != "database":
            self.show_view("database")

        self.search_entry.focus_set()

        return "break"

    def _clear_search(self):

        self.search_entry.delete(0, "end")
        self.search_entry.focus_set()
        self.db_page = 0
        self.load_table()

    def _copy_selection(self, _event=None):

        items = self.tree.selection()

        if not items:
            return "break"

        _, labels = TABLES[self.db_table]
        columns = self.tree["columns"]

        lines = ["\t".join(labels.get(c, c) for c in columns)]
        lines += ["\t".join(str(v) for v in self.tree.item(i, "values")) for i in items]

        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self._set_status(f"{fmt_number(len(items))} fila(s) copiadas al portapapeles")

        return "break"

    # ------------------------------------------------------------------ helpers

    def _log(self, message, level="info"):

        icons = {"info": "•", "success": "✓", "warning": "!", "error": "✕"}
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{timestamp}  ")
        self.log_box.insert("end", f"{icons[level]}  {message}\n", level)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _open_data_folder(self):

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(DATA_DIR)

    def _import_buttons(self):

        return (self.customers_button, self.products_button, self.sales_button, self.refresh_button, *self.quick_buttons)

    def _set_busy(self, message):

        for button in self._import_buttons():
            button.configure(state="disabled")

        self.status_dot.configure(text_color=WARNING)
        self.progress.set(0)
        self.progress.pack(side="right", padx=(0, 16))
        self.configure(cursor="watch")
        self._set_status(message)

    def _set_status(self, message, progress=None):

        self.status_label.configure(text=message)

        if progress is not None:
            self.progress.set(progress)

        self.update_idletasks()

    def _set_idle(self):

        for button in self._import_buttons():
            button.configure(state="normal")

        self.progress.pack_forget()
        self.status_dot.configure(text_color=SUCCESS)
        self.status_label.configure(text="Listo")
        self.configure(cursor="")

    def _refresh(self):

        self.load_database_status()
        self._log("Panel actualizado", "info")

    def _after_import(self):

        self.load_database_status()

        if self.current_view == "database":
            self.load_table()

    def _confirm_replace(self, table, label):

        with connection() as conn:
            existing = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

        if existing == 0:
            return True

        replace = messagebox.askyesno(
            "Datos existentes",
            f"Ya hay {fmt_number(existing)} {label} cargados.\n\n¿Quieres reemplazarlos?"
        )

        if not replace:
            self._log(f"Importación de {label} cancelada", "warning")

        return replace

    def _run_import(self, label, action):

        self._set_busy(f"Importando {label}…")

        try:
            action()
        except Exception as e:
            self._set_idle()
            self._log(f"Error al cargar {label}: {e}", "error")
            messagebox.showerror("Error", f"No se pudieron cargar los {label}.\n\n{e}")
            return

        self._set_idle()
        self._after_import()
        self._log(f"{label.capitalize()} cargados correctamente", "success")
        messagebox.showinfo("Importación completada", f"{label.capitalize()} cargados correctamente")

    # ------------------------------------------------------------------ dashboard

    def load_database_status(self):

        stats = get_database_stats()

        for key, *_ in KPI_CARDS:
            value = stats[key]

            if value is None or (isinstance(value, float) and pd.isna(value)):
                text = "—"
            elif key == "last_period":
                text = str(value)
            else:
                text = fmt_number(int(value))

            self.kpi_values[key].configure(text=text)

        self.updated_label.configure(text=f"Actualizado a las {datetime.now():%H:%M:%S}")

    # ------------------------------------------------------------------ database view

    def _on_table_change(self, name):

        self.db_table = name
        self.db_page = 0
        self.db_sort = None
        self.db_sort_desc = False
        self.load_table()

    def _on_search(self, _event=None):

        if self.search_entry.get().strip() == self._last_search:
            return

        if self._search_job:
            self.after_cancel(self._search_job)

        def run():
            self.db_page = 0
            self.load_table()

        self._search_job = self.after(300, run)

    def _change_page(self, delta):

        self.db_page += delta
        self.load_table()

    def _sort_by(self, column):

        if self.db_sort == column:
            self.db_sort_desc = not self.db_sort_desc
        else:
            self.db_sort = column
            self.db_sort_desc = False

        self.db_page = 0
        self.load_table()

    def load_table(self):

        table, labels = TABLES[self.db_table]
        search = self.search_entry.get().strip()
        self._last_search = search

        with connection() as conn:
            info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            columns = [row[1] for row in info]
            numeric = {row[1] for row in info if row[2].upper() in ("REAL", "INTEGER", "FLOAT")}

            where, params = "", []

            if search:
                # Escape LIKE wildcards so '%' and '_' are searched literally
                pattern = search.replace("!", "!!").replace("%", "!%").replace("_", "!_")
                where = " WHERE " + " OR ".join(f'CAST("{c}" AS TEXT) LIKE ? ESCAPE \'!\'' for c in columns)
                params = [f"%{pattern}%"] * len(columns)

            order = ""

            if self.db_sort in columns:
                direction = "DESC" if self.db_sort_desc else "ASC"

                if table == "sales" and self.db_sort == "period":
                    order = f' ORDER BY "year" {direction}, "month" {direction}'
                else:
                    order = f' ORDER BY "{self.db_sort}" {direction}'

            self.db_total = conn.execute(f'SELECT COUNT(*) FROM "{table}"{where}', params).fetchone()[0]

            max_page = max(0, (self.db_total - 1) // PAGE_SIZE)
            self.db_page = min(max(self.db_page, 0), max_page)

            select = ", ".join(f'"{c}"' for c in columns)
            rows = conn.execute(
                f'SELECT {select} FROM "{table}"{where}{order} LIMIT ? OFFSET ?',
                params + [PAGE_SIZE, self.db_page * PAGE_SIZE]
            ).fetchall()

        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=columns)

        for col in columns:
            label = labels.get(col, col)

            if col == self.db_sort:
                label += " ▼" if self.db_sort_desc else " ▲"

            self.tree.heading(col, text=label, command=lambda c=col: self._sort_by(c))
            self.tree.column(
                col, width=max(110, len(label) * 9 + 30), minwidth=80, stretch=False,
                anchor="e" if col in numeric else "w"
            )

        for i, row in enumerate(rows):
            values = [self._format_cell(v) for v in row]
            self.tree.insert("", "end", values=values, tags=("odd",) if i % 2 else ())

        if self.db_total == 0:
            self.page_label.configure(text="No hay registros" + (" que coincidan con la búsqueda" if search else ""))
        else:
            start = self.db_page * PAGE_SIZE + 1
            end = start + len(rows) - 1
            self.page_label.configure(
                text=f"Mostrando {fmt_number(start)}–{fmt_number(end)} de {fmt_number(self.db_total)} registros"
            )

        self.prev_button.configure(state="normal" if self.db_page > 0 else "disabled")
        self.next_button.configure(state="normal" if (self.db_page + 1) * PAGE_SIZE < self.db_total else "disabled")

    @staticmethod
    def _format_cell(value):

        if value is None:
            return ""

        if isinstance(value, float):
            return fmt_number(value, 0 if value.is_integer() else 2)

        return value

    # ------------------------------------------------------------------ imports

    def load_customers_file(self):

        file_path = filedialog.askopenfilename(
            title="Selecciona el archivo de clientes",
            filetypes=TABULAR_FILETYPES
        )

        if not file_path or not self._confirm_replace("customers", "clientes"):
            return

        self._run_import("clientes", lambda: load_customers(file_path))

    def load_products_file(self):

        file_path = filedialog.askopenfilename(
            title="Selecciona el archivo de productos",
            filetypes=TABULAR_FILETYPES
        )

        if not file_path or not self._confirm_replace("products", "productos"):
            return

        self._run_import("productos", lambda: load_products(file_path))

    def load_sales_files(self):

        file_paths = filedialog.askopenfilenames(
            title="Selecciona uno o varios PDF de ventas",
            filetypes=[("Archivos PDF", "*.pdf")]
        )

        if not file_paths:
            return

        total = len(file_paths)
        loaded, skipped, failed = [], [], []

        self._set_busy(f"Importando ventas (0/{total})…")

        try:
            for i, path in enumerate(file_paths):
                name = Path(path).name
                self._set_status(f"Importando ventas ({i + 1}/{total}): {name}", i / total)

                try:
                    df = load_sales(path, replace_existing=False)

                except PeriodExistsError as e:
                    choice = messagebox.askyesnocancel(
                        "Periodo existente",
                        f"{name}\n\nEl periodo {e.period} ya está cargado. ¿Quieres reemplazarlo?\n\n"
                        "Sí: reemplazar\nNo: omitir este archivo\nCancelar: detener la importación"
                    )

                    if choice is None:
                        skipped.extend(Path(p).name for p in file_paths[i:])
                        self._log(f"Importación detenida. {total - i} archivo(s) sin procesar", "warning")
                        break

                    if not choice:
                        skipped.append(name)
                        self._log(f"{name}: omitido (periodo {e.period} ya cargado)", "warning")
                        continue

                    try:
                        df = load_sales(path, replace_existing=True)
                    except Exception as err:
                        failed.append((name, err))
                        self._log(f"{name}: {err}", "error")
                        continue

                except Exception as err:
                    failed.append((name, err))
                    self._log(f"{name}: {err}", "error")
                    continue

                loaded.append(name)
                self._log(f"{name}: {fmt_number(len(df))} líneas cargadas", "success")

            self._set_status("Finalizando…", 1)

        finally:
            self._set_idle()

        self._after_import()

        summary = (
            f"Archivos cargados: {len(loaded)}\n"
            f"Archivos omitidos: {len(skipped)}\n"
            f"Archivos con error: {len(failed)}"
        )

        if failed:
            details = "\n".join(f"• {name}: {err}" for name, err in failed)
            messagebox.showwarning("Importación con errores", f"{summary}\n\n{details}")
        else:
            messagebox.showinfo("Importación completada", summary)
