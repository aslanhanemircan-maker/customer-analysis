# -*- coding: utf-8 -*-
import os
import sys
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, filedialog
try:
      from tkcalendar import DateEntry
      _HAS_TKCALENDAR = True
except Exception:
      DateEntry = None
      _HAS_TKCALENDAR = False   # Yüklü değilse fallback olarak Entry kullanılacak
      
from data_ops import load_and_clean_data, tr_lower, CHURN_COL, CHURNED_MRR_COL, EFFECTIVE_MRR_COL, RISK_COL, CURRENT_MRR_COL, BASE_MRR_FALLBACK_COL, get_point_key, get_limit_removed_keys, is_risk_allowed
from analysis import calculate_kmeans_labels, calculate_pareto_mask, calculate_regression_line
from utils import (
    external_resource_path, 
    enable_per_monitor_dpi_awareness, 
    force_baseline_scaling, 
    show_splash, 
    splash_set,
    center_on_screen,
    parse_number_entry,
    parse_optional_number,
    validate_float,
    maximize_main_window
)

from ui_components import (
    set_tooltip, 
    create_collapsible_stat_card, 
    center_over_parent,
    ask_export_scope
)

CHURN_X_COLOR = 'red' 
CHURN_DATE_COL = 'Churn Date'
       
# ========================== Handbook Image Loader ==========================
HANDBOOK_IMAGES = {} # Önbellek

def load_handbook_image(filename, width=None):
      """
      Assets klasöründen görsel yükler, yeniden boyutlandırır (opsiyonel) ve önbelleğe alır.
      Modern görünüm için görsellerin yüksek kaliteli olması önemlidir.
      """
      if filename in HANDBOOK_IMAGES:
            return HANDBOOK_IMAGES[filename]

      path = external_resource_path("assets", filename)
      if not os.path.exists(path):
            return None

      try:
            # PIL (Pillow) kullanarak modern yeniden boyutlandırma
            # Eğer PIL yüklü değilse standart PhotoImage denenir (kalite düşebilir)
            try:
                  from PIL import Image, ImageTk
                  pil_img = Image.open(path)
                  if width:
                        # En boy oranını koruyarak yeniden boyutlandır
                        aspect = pil_img.height / pil_img.width
                        height = int(width * aspect)
                        pil_img = pil_img.resize((width, height), Image.LANCZOS) # Yüksek kalite filtre
                   
                  tk_img = ImageTk.PhotoImage(pil_img)
                  HANDBOOK_IMAGES[filename] = tk_img
                  return tk_img
            except ImportError:
                  # Fallback: Standart Tkinter (boyutlandırma yapamaz)
                  tk_img = tk.PhotoImage(file=path)
                  HANDBOOK_IMAGES[filename] = tk_img
                  return tk_img
      except Exception:
            return None
# ===========================================================================       

def preload_handbook_images():
      """
      Handbook görsellerini uygulama açılırken hafızaya yükler.
      Böylece butona basıldığında bekleme yapmaz.
      """
      # Handbook içinde kullandığınız tüm dosya isimleri
      files_to_preload = [
            "hb_graph_reading.png",  
            "hb_risk_map.png",  
            "hb_regression.png",
            "hb_settings_limit.png",  
            "hb_settings_reverse.png",  
            "hb_settings_exc_mode.png",
            "hb_settings_arrows.png",  
            "hb_settings_axis.png",  
            "hb_settings_risk.png",
            "hb_settings_graph.png",  
            "hb_churn_view.png"
      ]
       
      for f in files_to_preload:
            # Genişlik (width) handbook içindekiyle aynı olmalı (850)
            # Böylece cache tam eşleşir.
            load_handbook_image(f, width=850)

# --- GLOBAL TOOLTIP YÖNETİCİSİ ---
_tt_win = None
_tt_lbl = None

PAD_RATIO = 0.1   # fit_to_data padding yüzdesi

# ---- Küçük ayarlar (isteklerin) ----
EXTRA_SPLASH_HEIGHT = 0   # Splash'i biraz daha uzun yap
SPLASH_Y_OFFSET = 0         # Splash'ı çok hafif yukarı kaydır
SIDEBAR_EXTRA_WIDTH = 62 # Sağdaki frame'i biraz genişlet

# ========================== Windows DPI / Ölçekleme (Sabit 96 DPI Referansı) ==========================
_IS_WINDOWS = sys.platform.startswith("win")

settings_state = {
      "mode": "no_limit",
      "mrr_min": None,
      "mrr_max": None,
      "growth_min": None,
      "growth_max": None,
      "raw_mrr_min": "",
      "raw_mrr_max": "",
      "raw_growth_min": "",
      "raw_growth_max": "",

      "reverse_effect": False,
      "use_updated_exc_license_values": False,
      "show_difference_arrows": False,

      "fixed_axis": False,
      "fixed_center": None,

      "draw_growth_zero": True,
      "swap_axes": False,

      "risk_view_enabled": True,
      "risk_show_no": True,
      "risk_show_low": True,
      "risk_show_med": True,
      "risk_show_high": True,
      "risk_show_booked": True,

      "show_avg_labels": True,
      "activate_risk_colormap": False,

      "risk_cmap_weighted": True,
      "risk_cmap_weight_power": 1.0,

      "activate_search_box": False,

      "churn_enabled": True,
      "show_only_churn": False,

      "age_filter_mode": "0-Current",
      "divide_by_age": True,

      # YENİ: Sector Avg noktalarının üstünde müşteri sayısını gösterme ayarı
      "show_sector_counts_above_avg": True,

      # YENİ: Regresyon ayarları
      "fix_regression_line": False,           # Çizgiyi sabitleme ayarı
      "fixed_regression_params": None,      # Sabitlenen m ve b değerlerini tutacak sözlük
}

# ========================== Ana Uygulama (Lazy Import ile) ==========================
# 1) Uygulama başında DPI awareness (OS bitmap scaling kapansın)
enable_per_monitor_dpi_awareness()

# Önce ana root'u yarat, gizle ve splash aç
root = tk.Tk()
# 2) %100 ölçek referansına kilitle (96 DPI) — DİNAMİK DEĞİŞTİRME!
force_baseline_scaling(root, baseline_dpi=96)
root.withdraw()

splash, pbar, splash_title_lbl, splash_sub_lbl = show_splash(
      root,
      title_text="Loading…",
      subtitle_text="Checking for data.xlsx"
)
splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=5)

# --- Excel dosyası seçimi / Otomatik açma mantığı ---
default_xlsx = external_resource_path("assets", "data.xlsx")
file_path = default_xlsx if os.path.exists(default_xlsx) else None
if file_path:
      splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=12, sub="Found data.xlsx next to the app")
else:
      splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=10, sub="Waiting for Excel file selection…")
      file_path = filedialog.askopenfilename(
            parent=splash,
            title="Excel dosyasını seçin",
            filetypes=[("Excel Files", "*.xlsx *.xls")],
            initialdir=os.path.dirname(default_xlsx)
      )
      if not file_path:
            try:
                  splash.destroy()
                  root.destroy()
            except Exception:
                  pass
            raise SystemExit("Dosya seçilmedi.")

# === LAZY IMPORT: Ağır kütüphaneleri splash göründükten ve dosya yolu belli olduktan sonra yükle ===
splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=14, sub="Loading libraries…")
import pandas as pd
import numpy as np 

splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=16, sub="Reading workbook & Processing…")

# Tüm o karmaşık işleri artık tek satırda yapıyoruz:
try:
    df = load_and_clean_data(file_path)
except Exception as e:
    # Hata olursa ekrana basıp kapatalım
    import tkinter.messagebox
    tkinter.messagebox.showerror("Data Error", str(e))
    sys.exit()
# ============================================================================
# Matplotlib ve alt bileşenleri de ancak şimdi yükleniyor
splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=38, sub="Initializing plotting engine…")
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.legend as mlegend

try:
    import sklearn
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from mpl_toolkits.axes_grid1 import make_axes_locatable # Marjinal grafikler için

# --- ANALYTICS STATE ---
# Bu değişkenler hangi modun aktif olduğunu tutacak
analytics_state = {
      "mode": "none",           # "none", "kmeans", "pareto"
      "show_marginals": False,
      "kmeans_k": 3,            # Küme sayısı
      "marginal_artists": [] # Temizlik için referanslar
}
from matplotlib.patches import Patch, Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import to_rgb

# (İsteğe bağlı küçük hız optimizasyonu: font ailesi sabitleme)
try:
      matplotlib.rcParams['font.family'] = 'Segoe UI'
except Exception:
    
      pass
splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=55, sub="Preparing user interface…")

# --- Kesişim noktası (başlangıç fallback) ---
center_x, center_y = 1876, 16.91

# --- Varsayılan zoom aralığı (fallback) ---
zoom_x_range = 2000
zoom_y_range = 20

# --- Sektör renkleri ---
sectors = df['Company Sector'].unique()
cmap = plt.get_cmap('tab20', len(sectors))
color_map = {sector: cmap(i) for i, sector in enumerate(sectors)}

# ========================== RISK Sabitleri & Durumları (YENİ) ==========================
RISK_COL = 'Customer Risk'
RISK_VALUES = ["HIGH RISK", "MEDIUM RISK", "LOW RISK", "NO RISK", "BOOKED CHURN"]   # <<< BOOKED CHURN eklendi
RISK_COLOR = {
      "NO RISK": (0.62, 0.65, 0.69),   # soluk gri
      "LOW RISK": "limegreen",
      "MEDIUM RISK": "gold",
      "HIGH RISK": "crimson",
      "BOOKED CHURN": "purple",           # <<< yeni renk
}

AVG_RED = (0.80, 0.10, 0.10)   # Avg için farklı tonda kırmızı

def is_risk_view_active(selected_sector: str) -> bool:
      """Risk görünümü: sadece belirli bir sektör seçiliyken ve checkbox açıksa."""
      if RISK_COL not in df.columns:
            return False
      return (settings_state.get("risk_view_enabled", False) and selected_sector not in ("Sector Avg", "All"))

# Ana pencere özellikleri
root.title("MRR Growth Analitik Düzlem")
root.geometry("1600x900")   # başlangıç boyutu (hemen sonra maksimize edeceğiz)

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)   # sol: grafik
root.grid_columnconfigure(1, weight=0)   # sağ: yan panel (genişlik sabitlenecek)

# Sol: Matplotlib Figure
fig, ax = plt.subplots(figsize=(10, 7))
canvas = FigureCanvasTkAgg(fig, master=root)
canvas_widget = canvas.get_tk_widget()
canvas_widget.grid(row=0, column=0, sticky="nsew", padx=(10, 10))
fig.subplots_adjust(left=0.1, right=0.82)

# ======= Sol üst: Settings butonu + Fixed banner =======
SETTINGS_BTN_X = 10
SETTINGS_BTN_Y = 8

style = ttk.Style()
try:
      style.configure("Settings.TButton", font=("Segoe UI", 8), padding=(10, 4), width=12, height=9)
except Exception:
      pass
try:
      style.configure("Export.TButton", font=("Segoe UI", 8), padding=(10, 4), width=12, height=9)
except Exception:
      pass
try:
      # Toolbar arka planını butonların arka planıyla hizala
      btn_bg = style.lookup("TButton", "background", default="")
      style.configure("Toolbar.TFrame", background="white")
      style.configure("Toolbar.TLabel", background="white")
      # Entry'yi düz (flat) ve daha dolgun yap
      style.configure("Toolbar.TEntry", padding=(8, 6), relief="flat")
except Exception:
      pass

# ========================== NEW/CHURN: Settings kontrolünde kullanacağımız durum ==========================
# Churn ana şalteri: varsayılan True (aktif)
# Not: Tk BooleanVar henüz burada oluşturulmadı; settings_state kaynak alırız.
# =========================================================================================================

settings_win = None
def open_settings(event=None):
      global settings_win
      if settings_win is not None and settings_win.winfo_exists():
            settings_win.deiconify(); settings_win.lift(); settings_win.focus_force(); return
      settings_win = tk.Toplevel(root)
      settings_win.title("Settings")
      settings_win.transient(root)
      settings_win.grab_set()
      settings_win.focus_force()
      center_over_parent(settings_win, root, 760, 640)

      # ========================================================================
      # 1. BÖLÜM: TÜM DEĞİŞKENLERİ EN BAŞTA TANIMLIYORUZ (Global Scope İçin)
      # ========================================================================
       
      # --- Limit Variables ---
      limit_mode = tk.StringVar(value=settings_state["mode"])
      mrr_min_var = tk.StringVar(value=settings_state["raw_mrr_min"])
      mrr_max_var = tk.StringVar(value=settings_state["raw_mrr_max"])
      growth_min_var = tk.StringVar(value=settings_state["raw_growth_min"])
      growth_max_var = tk.StringVar(value=settings_state["raw_growth_max"])
      age_filter_var = tk.StringVar(value=settings_state.get("age_filter_mode", "0-Current"))
      divide_by_age_var = tk.BooleanVar(value=settings_state.get("divide_by_age", True))

      # --- License / Axis Variables ---
      reverse_var = tk.BooleanVar(value=settings_state.get("reverse_effect", False))
      fixed_axis_var = tk.BooleanVar(value=settings_state.get("fixed_axis", False))
      draw_zero_var = tk.BooleanVar(value=True) # Varsayılan True
      if "draw_growth_zero" in settings_state:
            draw_zero_var.set(settings_state["draw_growth_zero"])
      swap_axes_var = tk.BooleanVar(value=settings_state.get("swap_axes", False))

      # --- Risk Variables ---
      risk_enabled_var = tk.BooleanVar(value=settings_state.get("risk_view_enabled", True))
      risk_show_no_var = tk.BooleanVar(value=settings_state.get("risk_show_no", True))
      risk_show_low_var = tk.BooleanVar(value=settings_state.get("risk_show_low", True))
      risk_show_med_var = tk.BooleanVar(value=settings_state.get("risk_show_med", True))
      risk_show_high_var = tk.BooleanVar(value=settings_state.get("risk_show_high", True))
      risk_show_booked_var = tk.BooleanVar(value=settings_state.get("risk_show_booked", True))

      # --- Graph Variables ---
      show_avg_labels_var = tk.BooleanVar(value=settings_state.get("show_avg_labels", True))
      show_sector_counts_var = tk.BooleanVar(value=settings_state.get("show_sector_counts_above_avg", False))
      risk_cmap_var = tk.BooleanVar(value=settings_state.get("activate_risk_colormap", False))
      risk_cmap_weighted_var = tk.BooleanVar(value=settings_state.get("risk_cmap_weighted", True))
      risk_cmap_power_var = tk.StringVar(value=str(settings_state.get("risk_cmap_weight_power", 1.0)))
      search_box_var = tk.BooleanVar(value=settings_state.get("activate_search_box", False))
      regression_var = tk.BooleanVar(value=settings_state.get("show_regression_line", False))
       
      # --- YENİ: Fix Regression Değişkeni (En üstte tanımlı olduğu için hata vermez) ---
      fix_reg_var = tk.BooleanVar(value=settings_state.get("fix_regression_line", False))

      # Hata mesajı için (Graph Settings sekmesinde merkezde uyarı göstereceğiz)
      nonlocal_error_target = {"label": None, "var": None}  

      def on_close_btn():
            try:
                  settings_win.grab_release()
            except Exception:
                  pass
            settings_win.destroy()

      def on_save():
            # Graph Settings -> risk cmap aktif değilse weight power doğrulamasını atla
            if nonlocal_error_target["var"] is not None:
                  nonlocal_error_target["var"].set("")
            # --- weight power parse & kontrol (SADECE risk cmap aktifse) ---
            if risk_cmap_var.get():
                  try:
                        entered = risk_cmap_power_var.get().strip()
                  except Exception:
                        entered = ""
                  if entered == "":
                        val = settings_state.get("risk_cmap_weight_power", 1.0)
                  else:
                        val = parse_number_entry(entered)
                  if not (0.0 <= float(val) <= 3.0):
                        # Geçersiz -> sekmede kırmızı uyarı metni göster, pencereyi kapatma
                        if nonlocal_error_target["var"] is not None:
                              nonlocal_error_target["var"].set("Enter a valid value (0–3)")
                        try:
                              power_entry.focus_set()
                              power_entry.selection_range(0, tk.END)
                        except Exception:
                              pass
                        return
            else:
                  # risk cmap kapalıysa mevcut değeri koru
                  val = settings_state.get("risk_cmap_weight_power", 1.0)

            undo_stack.append(('LIMIT', settings_state.copy()))

            # Limit modu
            settings_state["mode"] = limit_mode.get()
            # AGE FILTER → HER ZAMAN KAYDEDİLSİN
            settings_state["age_filter_mode"] = age_filter_var.get()
            settings_state["divide_by_age"] = divide_by_age_var.get()
            if settings_state["mode"] == "limit":
                  settings_state["raw_mrr_min"] = (mrr_min_var.get() or "").strip()
                  settings_state["raw_mrr_max"] = (mrr_max_var.get() or "").strip()
                  settings_state["raw_growth_min"] = (growth_min_var.get() or "").strip()
                  settings_state["raw_growth_max"] = (growth_max_var.get() or "").strip()
                   
                  settings_state["mrr_min"] = parse_optional_number(settings_state["raw_mrr_min"])
                  settings_state["mrr_max"] = parse_optional_number(settings_state["raw_mrr_max"])
                  settings_state["growth_min"] = parse_optional_number(settings_state["raw_growth_min"])
                  settings_state["growth_max"] = parse_optional_number(settings_state["raw_growth_max"])
            else:
                  settings_state["raw_mrr_min"] = settings_state["raw_mrr_max"] = ""
                  settings_state["raw_growth_min"] = settings_state["raw_growth_max"] = ""
                  settings_state["mrr_min"] = settings_state["mrr_max"] = None
                  settings_state["growth_min"] = settings_state["growth_max"] = None

            # License (Reverse)
            settings_state["reverse_effect"] = bool(reverse_var.get())

            # Axis settings — merkez kilidi, y=0 çizgisi ve eksen swap
            settings_state["fixed_axis"] = bool(fixed_axis_var.get())
            if settings_state["fixed_axis"]:
                  settings_state["fixed_center"] = (center_x, center_y)   # orijinal metrikte saklanır
            else:
                  settings_state["fixed_center"] = None
            settings_state["draw_growth_zero"] = bool(draw_zero_var.get())
            settings_state["swap_axes"] = bool(swap_axes_var.get())

            # Customer Risk settings (YENİ)
            settings_state["risk_view_enabled"] = bool(risk_enabled_var.get())
            settings_state["risk_show_no"]   = bool(risk_show_no_var.get())
            settings_state["risk_show_low"] = bool(risk_show_low_var.get())
            settings_state["risk_show_med"] = bool(risk_show_med_var.get())
            settings_state["risk_show_high"]= bool(risk_show_high_var.get())
            settings_state["risk_show_booked"]   = bool(risk_show_booked_var.get())

            # Graph Settings
            settings_state["show_avg_labels"] = bool(show_avg_labels_var.get())
            # YENİ: Sector Avg noktalarının üstünde müşteri sayısını göster
            settings_state["show_sector_counts_above_avg"] = bool(show_sector_counts_var.get())
            settings_state["activate_risk_colormap"] = bool(risk_cmap_var.get())
            settings_state["risk_cmap_weighted"] = bool(risk_cmap_weighted_var.get())
            settings_state["risk_cmap_weight_power"] = float(val)

            # YENİ: Regresyon çizgisi
            settings_state["show_regression_line"] = bool(regression_var.get())
            # Regresyon kapandıysa, filtreyi de kapat
            if not settings_state["show_regression_line"]:
                  settings_state["regression_filter"] = "none"
                  try:
                        reg_filter_var.set("none")
                  except Exception:
                        pass

            # NEW/SEARCH: search box ayarı
            settings_state["activate_search_box"] = bool(search_box_var.get())
             
            # ================= YENİ FIX REGRESSION KAYIT MANTIĞI (DÜZELTİLDİ) =================
            # Regresyon çizgisi gösterimi açık mı?
            settings_state["show_regression_line"] = bool(regression_var.get())
             
            # Sabitleme kutusu işaretli mi?
            is_fixed_now = bool(fix_reg_var.get())
            settings_state["fix_regression_line"] = is_fixed_now

            if is_fixed_now:
                  # EĞER SABİTLEME AÇIKSA:
                  # Şu an halihazırda hafızada bir kayıt yoksa VEYA kullanıcı yeni sabitleme yapıyorsa
                  # O anki canlı hesaplanmış değerleri (current_regression_line) alıp 'fixed' olarak sakla.
                   
                  # Sadece m (eğim) varsa kopyala (yani çizgi hesaplanabilmişse)
                  if current_regression_line.get('m') is not None:
                        settings_state["fixed_regression_params"] = current_regression_line.copy()
                   
                  # Eğer ekranda çizgi yoksa ama kullanıcı sabitlemeye çalıştıysa,  
                  # eski kayıt varsa onu koru, yoksa yapacak bir şey yok (None kalır).
            else:
                  # Sabitleme kapalıysa hafızayı temizle ki sürekli yeniden hesaplansın
                  settings_state["fixed_regression_params"] = None
                   
            # Regresyon kapandıysa filtreyi de sıfırla
            if not settings_state["show_regression_line"]:
                  settings_state["regression_filter"] = "none"
                  try:
                        reg_filter_var.set("none")
                  except Exception:
                        pass
            # =================================================================================
            # =====================================================================

            # Filtre/çizim on_license_filter() -> redraw
            on_license_filter()   # mevcut davranış
            # search bar görünürlüğünü uygula
            toggle_search_bar_visibility()
            # YENİ: regresyon butonlarının görünürlüğünü uygula
            toggle_regression_buttons_visibility()

            try:
                  settings_win.grab_release()
            except Exception:
                  pass
            settings_win.destroy()

      nb = ttk.Notebook(settings_win)

      # --- Tab 1: Limit Options
      tab_limit = ttk.Frame(nb); nb.add(tab_limit, text="Limit Options")
      tab_limit.columnconfigure(0, weight=1)
      tab_limit.rowconfigure(0, weight=0)   # No Limit / Limit radio
      tab_limit.rowconfigure(1, weight=0)   # Ranges
      tab_limit.rowconfigure(2, weight=0)   # Filter by Age
      tab_limit.rowconfigure(3, weight=1)   # spacer
      tab_limit.rowconfigure(4, weight=0)   # Save / Close buttons

      # --- No Limit / Limit radio butonları ---
      radios_frame = ttk.Frame(tab_limit)
      radios_frame.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))

      rb_no = ttk.Radiobutton(radios_frame, text="No Limit", value="no_limit", variable=limit_mode)
      rb_yes = ttk.Radiobutton(radios_frame, text="Limit",      value="limit",      variable=limit_mode)
      rb_no.grid(row=0, column=0, padx=(0, 16), pady=4, sticky="w")
      rb_yes.grid(row=0, column=1, padx=(0, 16), pady=4, sticky="w")

      # --- Ranges labelframe ---
      entries_frame = ttk.LabelFrame(tab_limit, text="Ranges", padding=8)
       
      vcmd = (root.register(validate_float), "%P")

      # Giriş widget referanslarını tutmak için
      entries_controls = {"e1": None, "e2": None, "e3": None, "e4": None,
                                    "l1": None, "l2": None, "l3": None, "l4": None}

      def build_entries_grid():
            for w in entries_frame.winfo_children():
                  w.destroy()

            # Ranges frame'i Limit tab'ında row=1'e yerleştiriyoruz
            entries_frame.grid(row=1, column=0, sticky="we", padx=10, pady=(4, 8))

            entries_controls["l1"] = ttk.Label(entries_frame, text="MRR Min Value:")
            entries_controls["l1"].grid(row=0, column=0, sticky="w", padx=(4,6), pady=4)
            entries_controls["e1"] = ttk.Entry(entries_frame, textvariable=mrr_min_var,
                                                                 width=14, justify="center",
                                                                 validate="key", validatecommand=vcmd)
            entries_controls["e1"].grid(row=0, column=1, sticky="w", padx=(0,10), pady=4)

            entries_controls["l2"] = ttk.Label(entries_frame, text="MRR Max Value:")
            entries_controls["l2"].grid(row=0, column=2, sticky="w", padx=(16,6), pady=4)
            entries_controls["e2"] = ttk.Entry(entries_frame, textvariable=mrr_max_var,
                                                                 width=14, justify="center",
                                                                 validate="key", validatecommand=vcmd)
            entries_controls["e2"].grid(row=0, column=3, sticky="w", padx=(0,10), pady=4)

            entries_controls["l3"] = ttk.Label(entries_frame, text="Growth Min (%):")
            entries_controls["l3"].grid(row=1, column=0, sticky="w", padx=(4,6), pady=4)
            entries_controls["e3"] = ttk.Entry(entries_frame, textvariable=growth_min_var,
                                                                 width=14, justify="center",
                                                                 validate="key", validatecommand=vcmd)
            entries_controls["e3"].grid(row=1, column=1, sticky="w", padx=(0,10), pady=4)

            entries_controls["l4"] = ttk.Label(entries_frame, text="Growth Max (%):")
            entries_controls["l4"].grid(row=1, column=2, sticky="w", padx=(16,6), pady=4)
            entries_controls["e4"] = ttk.Entry(entries_frame, textvariable=growth_max_var,
                                                                 width=14, justify="center",
                                                                 validate="key", validatecommand=vcmd)
            entries_controls["e4"].grid(row=1, column=3, sticky="w", padx=(0,10), pady=4)

            for c in range(4):
                  entries_frame.grid_columnconfigure(c, weight=0)

      def set_entries_enabled_state(enabled: bool):
            state = "normal" if enabled else "disabled"
            for key in ("e1","e2","e3","e4"):
                  w = entries_controls.get(key)
                  if w is not None:
                        try:
                              w.configure(state=state)
                        except Exception:
                              pass

      def update_entries_visibility(*_):
            # Görünür kalsın, sadece enable/disable değişsin
            if not entries_controls["e1"]:
                  build_entries_grid()
            set_entries_enabled_state(limit_mode.get() == "limit")

      update_entries_visibility()
      limit_mode.trace_add("write", lambda *args: update_entries_visibility())

      # =========== Filter by Age LabelFrame ===========

      age_frame = ttk.LabelFrame(tab_limit, text="Filter by Age", padding=8)
      age_frame.grid(row=2, column=0, sticky="w", padx=10, pady=(4, 8))

      rb_age_01   = ttk.Radiobutton(age_frame, text="(0-1)",            value="0-1",           variable=age_filter_var)
      rb_age_02   = ttk.Radiobutton(age_frame, text="(0-2)",            value="0-2",           variable=age_filter_var)
      rb_age_12   = ttk.Radiobutton(age_frame, text="(1-2)",            value="1-2",           variable=age_filter_var)
      rb_age_cur = ttk.Radiobutton(age_frame, text="(0-Current)",   value="0-Current", variable=age_filter_var)

      rb_age_01.grid (row=0, column=0, padx=(4, 10), pady=2, sticky="w")
      rb_age_02.grid (row=0, column=1, padx=(0, 10), pady=2, sticky="w")
      rb_age_12.grid (row=0, column=2, padx=(0, 10), pady=2, sticky="w")
      rb_age_cur.grid(row=0, column=3, padx=(0,   4), pady=2, sticky="w")

      chk_divide_age = ttk.Checkbutton(
            age_frame,
            text="Divide by Age",
            variable=divide_by_age_var
      )
      chk_divide_age.grid(row=1, column=0, columnspan=4, sticky="w", padx=(4, 0), pady=(6, 2))

      # --- Limit tabında Save / Close butonları ---
      btns1 = ttk.Frame(tab_limit)
      btns1.grid(row=4, column=0, sticky="ew", padx=10, pady=10)
      btns1.columnconfigure(0, weight=1)
      btns1.columnconfigure(1, weight=1)
      ttk.Button(btns1, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
      ttk.Button(btns1, text="Save",   command=on_save).grid(row=0, column=1, sticky="e")
       
      # --- Tab 2: License Options (Reverse effect)
      tab_license = ttk.Frame(nb); nb.add(tab_license, text="License Options")
      tab_license.columnconfigure(0, weight=1); tab_license.rowconfigure(0, weight=1); tab_license.rowconfigure(1, weight=0)
      lic_inner = ttk.Frame(tab_license, padding=10); lic_inner.grid(row=0, column=0, sticky="nsew")
      reverse_cb = ttk.Checkbutton(lic_inner, text="Reverse effect", variable=reverse_var)
      reverse_cb.grid(row=0, column=0, sticky="w", padx=2, pady=2)
      btns2 = ttk.Frame(tab_license); btns2.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
      btns2.columnconfigure(0, weight=1); btns2.columnconfigure(1, weight=1)
      ttk.Button(btns2, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
      ttk.Button(btns2, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

      # --- Tab 3: Axis Settings
      tab_axis = ttk.Frame(nb); nb.add(tab_axis, text="Axis Settings")
      tab_axis.columnconfigure(0, weight=1); tab_axis.rowconfigure(0, weight=1); tab_axis.rowconfigure(1, weight=0)
      axis_inner = ttk.Frame(tab_axis, padding=10); axis_inner.grid(row=0, column=0, sticky="nsew")
      fixed_axis_cb = ttk.Checkbutton(axis_inner, text="Fixed axis (lock center lines only)", variable=fixed_axis_var)
      fixed_axis_cb.grid(row=0, column=0, sticky="w", padx=2, pady=6)
      draw_zero_cb = ttk.Checkbutton(axis_inner, text="Draw growth=0 line", variable=draw_zero_var)
      draw_zero_cb.grid(row=1, column=0, sticky="w", padx=2, pady=6)
      swap_axes_cb = ttk.Checkbutton(axis_inner, text="Swap axes (X↔Y)", variable=swap_axes_var)
      swap_axes_cb.grid(row=2, column=0, sticky="w", padx=2, pady=6)
      btns3 = ttk.Frame(tab_axis); btns3.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
      btns3.columnconfigure(0, weight=1); btns3.columnconfigure(1, weight=1)
      ttk.Button(btns3, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
      ttk.Button(btns3, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

      # --- Tab 4: Customer Risk
      tab_risk = ttk.Frame(nb); nb.add(tab_risk, text="Customer Risk")
      tab_risk.columnconfigure(0, weight=1); tab_risk.rowconfigure(0, weight=1); tab_risk.rowconfigure(1, weight=0)
      risk_inner = ttk.Frame(tab_risk, padding=10); risk_inner.grid(row=0, column=0, sticky="nsew")
       
      cb_pad_y = 6
      risk_master_cb = ttk.Checkbutton(risk_inner, text="Show Risk Statement", variable=risk_enabled_var)
      risk_master_cb.grid(row=0, column=0, sticky="w", padx=2, pady=cb_pad_y)
       
      risk_opts = ttk.LabelFrame(risk_inner, text="Show / Hide by Risk", padding=8)
      risk_opts.grid(row=1, column=0, sticky="nw", padx=2, pady=cb_pad_y)
       
      cb_no        = ttk.Checkbutton(risk_opts, text="Show NO RISK",              variable=risk_show_no_var)
      cb_low      = ttk.Checkbutton(risk_opts, text="Show LOW RISK",            variable=risk_show_low_var)
      cb_med      = ttk.Checkbutton(risk_opts, text="Show MEDIUM RISK",        variable=risk_show_med_var)
      cb_hi        = ttk.Checkbutton(risk_opts, text="Show HIGH RISK",           variable=risk_show_high_var)
      cb_booked = ttk.Checkbutton(risk_opts, text="Show BOOKED CHURN",      variable=risk_show_booked_var)  
       
      cb_no.grid      (row=0, column=0, sticky="w", padx=4, pady=cb_pad_y)
      cb_low.grid     (row=1, column=0, sticky="w", padx=4, pady=cb_pad_y)
      cb_med.grid     (row=2, column=0, sticky="w", padx=4, pady=cb_pad_y)
      cb_hi.grid      (row=3, column=0, sticky="w", padx=4, pady=cb_pad_y)
      cb_booked.grid(row=4, column=0, sticky="w", padx=4, pady=cb_pad_y)  

      def _apply_risk_opts_state():
            state = tk.NORMAL if risk_enabled_var.get() else tk.DISABLED
            for w in (cb_no, cb_low, cb_med, cb_hi, cb_booked):
                  w.configure(state=state)
      _apply_risk_opts_state()
      risk_enabled_var.trace_add("write", lambda *_: _apply_risk_opts_state())

      btns4 = ttk.Frame(tab_risk); btns4.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
      btns4.columnconfigure(0, weight=1); btns4.columnconfigure(1, weight=1)
      ttk.Button(btns4, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
      ttk.Button(btns4, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

      # --- Tab 5: Graph Settings
      tab_graph = ttk.Frame(nb); nb.add(tab_graph, text="Graph Settings")
      tab_graph.columnconfigure(0, weight=1)
      tab_graph.rowconfigure(0, weight=1)
      tab_graph.rowconfigure(1, weight=0)
      graph_inner = ttk.Frame(tab_graph, padding=10); graph_inner.grid(row=0, column=0, sticky="nsew")
      cb_pad_y = 6

      chk_avg_labels = ttk.Checkbutton(graph_inner, text="Show sector name under AVG points", variable=show_avg_labels_var)
      chk_avg_labels.grid(row=0, column=0, sticky="w", padx=2, pady=cb_pad_y)

      chk_sector_counts = ttk.Checkbutton(
            graph_inner,
            text="Show sector customer counts above AVG points",
            variable=show_sector_counts_var
      )
      chk_sector_counts.grid(row=1, column=0, sticky="w", padx=2, pady=cb_pad_y)

      chk_risk_cmap = ttk.Checkbutton(graph_inner, text="Activate customer risk color map", variable=risk_cmap_var)
      chk_risk_cmap.grid(row=2, column=0, sticky="w", padx=2, pady=cb_pad_y)

      chk_risk_weighted = ttk.Checkbutton(graph_inner, text="Distance-weighted quadrant colors", variable=risk_cmap_weighted_var)
      chk_risk_weighted.grid(row=3, column=0, sticky="w", padx=2, pady=cb_pad_y)

      weight_power_label = ttk.Label(graph_inner, text="Weight power (0–3):")
      weight_power_label.grid(row=4, column=0, sticky="w", padx=2, pady=cb_pad_y)
      vcmd = (root.register(validate_float), "%P")
      power_entry = ttk.Entry(graph_inner, width=8, textvariable=risk_cmap_power_var, justify="center", validate="key", validatecommand=vcmd)
      power_entry.grid(row=4, column=0, sticky="e", padx=8, pady=cb_pad_y)

      chk_search_box = ttk.Checkbutton(graph_inner, text="Activate search box", variable=search_box_var)
      chk_search_box.grid(row=5, column=0, sticky="w", padx=2, pady=cb_pad_y)

      chk_regression = ttk.Checkbutton(graph_inner, text="Show regression line", variable=regression_var)
      chk_regression.grid(row=6, column=0, sticky="w", padx=2, pady=cb_pad_y)
       
      # YENİ: FIX REGRESSION CHECKBOX (Burada değişkeni tekrar tanımlamıyoruz, en tepeyi kullanıyoruz)
      chk_fix_reg = ttk.Checkbutton(graph_inner, text="Fix Regression Line", variable=fix_reg_var)
      chk_fix_reg.grid(row=7, column=0, sticky="w", padx=2, pady=6)

      # Checkbox aktiflik durumunu yönet
      def _toggle_fix_reg_state(*_):
            if regression_var.get():
                  chk_fix_reg.state(["!disabled"])
            else:
                  chk_fix_reg.state(["disabled"])
                   
      regression_var.trace_add("write", _toggle_fix_reg_state)
      _toggle_fix_reg_state()

      graph_err_var = tk.StringVar(value="")
      graph_err_lbl = ttk.Label(tab_graph, textvariable=graph_err_var, foreground="red", anchor="center")
      graph_err_lbl.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
      nonlocal_error_target["label"] = graph_err_lbl
      nonlocal_error_target["var"] = graph_err_var

      def apply_risk_cmap_controls_state(*_):
            enabled = risk_cmap_var.get()
            chk_risk_weighted.configure(state=(tk.NORMAL if enabled else tk.DISABLED))
            try:
                  power_entry.configure(state=(tk.NORMAL if enabled else tk.DISABLED))
            except Exception:
                  pass
      apply_risk_cmap_controls_state()
      risk_cmap_var.trace_add("write", apply_risk_cmap_controls_state)

      btns5 = ttk.Frame(tab_graph); btns5.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
      btns5.columnconfigure(0, weight=1); btns5.columnconfigure(1, weight=1)
      ttk.Button(btns5, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
      ttk.Button(btns5, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

      # =============== Tab 6 — Churn Settings =================
      tab_churn = ttk.Frame(nb); nb.add(tab_churn, text="Churn Settings")
      tab_churn.columnconfigure(0, weight=1)
      tab_churn.rowconfigure(0, weight=1)
      tab_churn.rowconfigure(1, weight=0)

      churn_inner = ttk.Frame(tab_churn, padding=10); churn_inner.grid(row=0, column=0, sticky="nsew")

      ttk.Label(churn_inner, text="Start Date:").grid(row=0, column=0, sticky="w", padx=2, pady=(4, 6))
      if _HAS_TKCALENDAR:
           churn_start_entry = DateEntry(
                 churn_inner,
                 width=16,
                 date_pattern="yyyy-mm-dd",
                 state="readonly",
                 showweeknumbers=False,
                 firstweekday="monday",
                 locale="tr_TR"
           )
      else:
            churn_start_var = tk.StringVar(value="")
            churn_start_entry = ttk.Entry(churn_inner, textvariable=churn_start_var, width=18, justify="center")
      churn_start_entry.grid(row=0, column=1, sticky="w", padx=(6, 12), pady=(4, 6))

      ttk.Label(churn_inner, text="End Date:").grid(row=1, column=0, sticky="w", padx=2, pady=(0, 8))
      if _HAS_TKCALENDAR:
            churn_end_entry = DateEntry(
                 churn_inner,
                 width=16,
                 date_pattern="yyyy-mm-dd",
                 state="readonly",
                 showweeknumbers=False,
                 firstweekday="monday",
                 locale="tr_TR"
            )
      else:
           churn_end_var = tk.StringVar(value="")
           churn_end_entry = ttk.Entry(churn_inner, textvariable=churn_end_var, width=18, justify="center")
      churn_end_entry.grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(0, 8))

      try:
            tab_index = nb.index(tab_churn)
            nb.tab(tab_index, state=("normal" if settings_state.get("churn_enabled", True) else "disabled"))
      except Exception:
            pass

      btns6 = ttk.Frame(tab_churn); btns6.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
      btns6.columnconfigure(0, weight=1); btns6.columnconfigure(1, weight=1)
      ttk.Button(btns6, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
      ttk.Button(btns6, text="Save",   command=on_save).grid(row=0, column=1, sticky="e")
      # ====================================================================

      def update_license_tab_state(*_):
            try:
                  nb.tab(1, state="normal" if license_var.get() == "Exc." else "disabled")
            except Exception:
                  pass

      update_license_tab_state()
      license_var.trace_add("write", update_license_tab_state)

      nb.pack(fill="both", expand=True, padx=12, pady=12)

      # --- ODAK KONTROLÜ ---
      focus_sentinel = tk.Frame(settings_win, width=1, height=1, highlightthickness=0, bd=0, takefocus=1)
      focus_sentinel.place(x=0, y=0, width=1, height=1)
      try: focus_sentinel.lower()
      except: pass

      focus_guard = {"active": False}
      def _activate_guard(duration_ms=200):
            focus_guard["active"] = True
            settings_win.after(duration_ms, lambda: focus_guard.update(active=False))

      def _on_focusin(e):
            if not focus_guard["active"]: return
            w = e.widget
            try:
                  if w is not focus_sentinel and w.winfo_toplevel() is settings_win:
                        settings_win.after_idle(lambda: focus_sentinel.focus_set())
            except Exception: pass

      settings_win.bind("<FocusIn>", _on_focusin, add=True)

      def _defocus_initial():
            _activate_guard(220)
            try: settings_win.focus_force()
            except: pass
            settings_win.after_idle(lambda: focus_sentinel.focus_set())

      settings_win.after_idle(_defocus_initial)

      def _on_tab_changed(event):
            _activate_guard(220)
            settings_win.after_idle(lambda: focus_sentinel.focus_set())

      nb.bind("<<NotebookTabChanged>>", _on_tab_changed, add=True)

# Settings butonu
settings_btn = ttk.Button(root, text="⚙️ Settings", style="Settings.TButton", command=open_settings)
settings_btn.place(x=SETTINGS_BTN_X, y=SETTINGS_BTN_Y)
# --- SETTINGS'in SAĞINA EXCEL EXPORT BUTONU ---
_excel_icon = None
def _load_excel_icon():
      global _excel_icon
      try:
            icon_path = external_resource_path("assets", "excel_icon.png")
            if os.path.exists(icon_path):
                  _excel_icon = tk.PhotoImage(file=icon_path)
      except Exception:
            _excel_icon = None

_load_excel_icon()

def _gather_current_view_dataframe(only_selected=False):
      """
      Mevcut grafikte görünen veriyi DataFrame olarak hazırlar.
      only_selected=True ise SADECE 'selection_state' içindeki noktaları filtreler.
      """
      x_col = get_plot_x_col()
       
      # 1. Gizli noktaları filtrele
      hidden = set().union(manual_removed, license_removed, get_limit_removed_keys(df, settings_state))
      base_df = df[~df.apply(lambda r: get_point_key(r, settings_state) in hidden, axis=1)].copy()

      # 2. Temel filtreler (Churn, Age)
      base_df = _apply_churn_filters(base_df)
      base_df = _apply_age_filters(base_df)
       
      # 3. Kolon ayarlamaları
      age_growth_col = get_growth_source_col_for_age_mode()
      if age_growth_col in base_df.columns:
            base_df['MRR Growth (%)'] = base_df[age_growth_col].astype(float) * 100.0

      age_base_mrr_col = get_base_mrr_col_for_age_mode()
      if age_base_mrr_col in base_df.columns:
            base_df[EFFECTIVE_MRR_COL] = base_df[age_base_mrr_col].astype(float)

      if (CHURN_COL in base_df.columns) and (CHURNED_MRR_COL in base_df.columns):
            churn_mask_loc = base_df[CHURN_COL].astype(str).str.upper().eq("CHURN")
            base_df.loc[churn_mask_loc, EFFECTIVE_MRR_COL] = base_df.loc[churn_mask_loc, CHURNED_MRR_COL].astype(float)

      exc_col_src = get_exc_mrr_col_for_age_mode()
      if exc_col_src in base_df.columns:
            base_df['Exc. License MRR'] = base_df[exc_col_src].astype(float)
       
      # 4. Regresyon filtresi
      base_df = _apply_regression_filter(base_df, x_col)

      # ---------------------------------------------------------
      # [YENİ] SEÇİM FİLTRESİ (NORMAL MÜŞTERİLER İÇİN ÖN HAZIRLIK)
      # ---------------------------------------------------------
      if only_selected and sector_combobox.get() != "Sector Avg":
            # Normal modda seçimler get_point_key(row, settings_state) (tuple) olarak tutulur.
            # Sadece bu key'e sahip satırları tut.
            target_keys = selection_state.get("selected_keys", set())
            if not target_keys:
                  # Seçim yoksa boş dataframe döndür
                  return pd.DataFrame()
             
            # Apply ile kontrol (biraz yavaş olabilir ama güvenlidir)
            base_df = base_df[base_df.apply(lambda r: get_point_key(r, settings_state) in target_keys, axis=1)]

      selected_sector = sector_combobox.get()

      # MERKEZ HESAPLAMA
      if settings_state.get("fixed_axis", False) and settings_state.get("fixed_center") is not None:
            eff_center_x, eff_center_y = settings_state["fixed_center"]
      else:
            if len(base_df) > 0:
                  eff_center_x = base_df[x_col].astype(float).mean()
                  eff_center_y = base_df['MRR Growth (%)'].astype(float).mean()
            else:
                  eff_center_x = 0
                  eff_center_y = 0
       
      plot_cx, plot_cy = to_plot_coords(eff_center_x, eff_center_y)

      # --- SENARYO A: SECTOR AVG SEÇİLİYSE ---
      if selected_sector == "Sector Avg":
            summary_rows = []
            target_keys = selection_state.get("selected_keys", set())

            for sector in sectors:
                  # Eğer sadece seçililer isteniyorsa ve bu sektör seçili değilse atla
                  # Sector Avg modunda keyler "SEC_AVG|Teknoloji" formatındadır.
                  if only_selected:
                        sec_key = f"SEC_AVG|{sector}"
                        if sec_key not in target_keys:
                              continue

                  sec_df = base_df[base_df['Company Sector'] == sector]
                  if len(sec_df) == 0:
                        continue
                   
                  count = len(sec_df)
                  try:
                        avg_mrr = sec_df[x_col].astype(float).mean()
                  except:
                        avg_mrr = sec_df[EFFECTIVE_MRR_COL].astype(float).mean()
                         
                  avg_growth = sec_df['MRR Growth (%)'].astype(float).mean()
                  total_mrr = sec_df[EFFECTIVE_MRR_COL].astype(float).sum()
                   
                  px, py = to_plot_coords(avg_mrr, avg_growth)
                   
                  if px >= plot_cx and py >= plot_cy:     q_str = "(+,+)"
                  elif px < plot_cx and py >= plot_cy:   q_str = "(-,+)"
                  elif px < plot_cx and py < plot_cy:     q_str = "(-,-)"
                  else:                                                  q_str = "(+,-)"

                  summary_rows.append({
                        "Company Sector": sector,
                        "Customer Count": count,
                        "Average MRR": avg_mrr,
                        "Average Growth (%)": avg_growth,
                        "Total MRR": total_mrr,
                        "Quadrant": q_str
                  })
                   
            return pd.DataFrame(summary_rows)

      # --- SENARYO B: NORMAL MÜŞTERİ LİSTESİ EXPORT ---
      # base_df yukarıda zaten only_selected'a göre filtrelendi.
       
      if selected_sector != "All":
            base_df = base_df[base_df['Company Sector'] == selected_sector]
       
      # Risk filtresi (Export için)
      if is_risk_view_active(selected_sector) and (RISK_COL in base_df.columns):
            base_df = base_df[base_df[RISK_COL].astype(str).str.upper().apply(lambda val: is_risk_allowed(val, settings_state))]

      # Çıktı DataFrame'i
      out = pd.DataFrame()
      if 'Customer' in base_df.columns:
            out['Customer'] = base_df['Customer']
      out['Company Sector'] = base_df['Company Sector']
      out['MRR Value'] = base_df[x_col].astype(float)
      out['MRR Growth (%)'] = base_df['MRR Growth (%)'].astype(float)
       
      if 'License Percent' in base_df.columns:
            out['License Percent'] = base_df['License Percent']

      if CHURN_COL in base_df.columns:
            out[CHURN_COL] = base_df[CHURN_COL]
      if CHURNED_MRR_COL in base_df.columns:
            out[CHURNED_MRR_COL] = base_df[CHURNED_MRR_COL]
      if RISK_COL in base_df.columns:
            out[RISK_COL] = base_df[RISK_COL]

      # Quadrant Hesapla
      qs = []
      for xv, yv in zip(out['MRR Value'].values, out['MRR Growth (%)'].values):
            px, py = to_plot_coords(float(xv), float(yv))
            if px >= plot_cx and py >= plot_cy:     qs.append("(+,+)")
            elif px < plot_cx and py >= plot_cy:   qs.append("(-,+)")
            elif px < plot_cx and py < plot_cy:     qs.append("(-,-)")
            else:                                                  qs.append("(+,-)")
      out['Quadrant'] = qs
       
      return out

      # Risk show/hide uygulanacak mı?
      def _risk_allowed(risk_val: str) -> bool:
            risk_val = (str(risk_val or "")).strip().upper()
            if risk_val == "NO RISK":        return settings_state.get("risk_show_no", True)
            if risk_val == "LOW RISK":      return settings_state.get("risk_show_low", True)
            if risk_val == "MEDIUM RISK": return settings_state.get("risk_show_med", True)
            if risk_val == "HIGH RISK":     return settings_state.get("risk_show_high", True)
            if risk_val == "BOOKED CHURN":   return settings_state.get("risk_show_booked", True)
            return True

      if selected_sector not in ("All", "Sector Avg"):
            base_df = base_df[base_df['Company Sector'] == selected_sector]
            if is_risk_view_active(selected_sector) and (RISK_COL in base_df.columns):
                  base_df = base_df[base_df[RISK_COL].astype(str).str.upper().apply(_risk_allowed)]

      # YENİ: Regresyon filtresini uygula
      base_df = _apply_regression_filter(base_df, x_col)

      # Merkez (aynı mantık)
      if settings_state.get("fixed_axis", False) and settings_state.get("fixed_center") is not None:
            eff_center_x, eff_center_y = settings_state["fixed_center"]
      else:
            if len(base_df) > 0:
                  eff_center_x = base_df[x_col].astype(float).mean()
                  eff_center_y = base_df['MRR Growth (%)'].astype(float).mean()
            else:
                  eff_center_x = df[x_col].astype(float).mean()
                  eff_center_y = df['MRR Growth (%)'].astype(float).mean()

      plot_cx, plot_cy = to_plot_coords(eff_center_x, eff_center_y)

      # Çıktı sütunlarını hazırla
      out = pd.DataFrame()
      if 'Customer' in base_df.columns:
            out['Customer'] = base_df['Customer']
      out['Company Sector'] = base_df['Company Sector']
      out['MRR Value'] = base_df[x_col].astype(float)
      out['MRR Growth (%)'] = base_df['MRR Growth (%)'].astype(float)
      if 'License Percent' in base_df.columns:
            out['License Percent'] = base_df['License Percent']

      # ======================= NEW/CHURN: export'a churn bilgisini de ekle =======================
      if CHURN_COL in base_df.columns:
            out[CHURN_COL] = base_df[CHURN_COL]
      if CHURNED_MRR_COL in base_df.columns:
            out[CHURNED_MRR_COL] = base_df[CHURNED_MRR_COL]
      # ==========================================================================================

      if RISK_COL in base_df.columns:
            out[RISK_COL] = base_df[RISK_COL]

      # Quadrant (plot koordinatlarına göre)
      qs = []
      for xv, yv in zip(out['MRR Value'].values, out['MRR Growth (%)'].values):
            px, py = to_plot_coords(float(xv), float(yv))
            if px >= plot_cx and py >= plot_cy:     qs.append("(+,+)")
            elif px < plot_cx and py >= plot_cy:   qs.append("(-,+)")
            elif px < plot_cx and py < plot_cy:     qs.append("(-,-)")
            else:                                                  qs.append("(+,-)")
      out['Quadrant'] = qs
      return out

def _export_to_excel():
      """ Save As diyalogu açar, seçim varsa kullanıcıya sorar. """
       
      # 1. Seçim var mı kontrol et
      selected_count = len(selection_state.get("selected_keys", []))
      export_mode = "all" # Varsayılan davranış

      if selected_count > 0:
            # Seçim varsa kullanıcıya sor
            user_choice = ask_export_scope(root, selected_count)
            if user_choice is None:
                  return # İptal etti veya pencereyi kapattı
            export_mode = user_choice

      # 2. Dosya konumu seç
      try:
            initial_dir = os.path.dirname(file_path) if file_path else os.getcwd()
      except Exception:
            initial_dir = os.getcwd()

      default_name = "Selected_Data.xlsx" if export_mode == "selected" else "Chart_Data.xlsx"

      save_path = filedialog.asksaveasfilename(
            parent=root,
            title="Dışa aktarılacak Excel konumunu seçin",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialdir=initial_dir,
            initialfile=default_name
      )
      if not save_path:
            return  

      try:
            # 3. Veriyi topla (only_selected parametresini kullanarak)
            is_selected_only = (export_mode == "selected")
            data = _gather_current_view_dataframe(only_selected=is_selected_only)

            if data.empty:
                  tk.messagebox.showwarning("Uyarı", "Dışa aktarılacak veri bulunamadı.")
                  return

            # 4. Yaz
            try:
                  with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                        data.to_excel(writer, index=False, sheet_name="Chart Data")
            except Exception:
                  with pd.ExcelWriter(save_path) as writer:
                        data.to_excel(writer, index=False, sheet_name="Chart Data")

      except Exception as e:
            err = tk.Toplevel(root)
            err.title("Export error")
            err.transient(root)
            center_over_parent(err, root, 400, 150)
            tk.Label(err, text="Export failed:\n"+str(e), fg="red", wraplength=350).pack(expand=True, padx=20, pady=20)
            ttk.Button(err, text="Close", command=err.destroy).pack(pady=(0,10))


# Excel butonu (ikon varsa image, yoksa metin)
if _excel_icon is not None:
      excel_btn = ttk.Button(root, image=_excel_icon, command=_export_to_excel, style="Export.TButton")
else:
      excel_btn = ttk.Button(root, text="📗 Export", command=_export_to_excel, style="Export.TButton")


def _place_excel_btn_next_to_settings():
      # Settings butonu genişliğini öğrendikten sonra hemen sağına koy
      try:
            root.update_idletasks()
            sx = SETTINGS_BTN_X + settings_btn.winfo_width() + 1
            excel_btn.place(x=sx, y=SETTINGS_BTN_Y)
      except Exception:
            # Yine de bir yere koy
            excel_btn.place(x=SETTINGS_BTN_X + 120, y=SETTINGS_BTN_Y)

root.after_idle(_place_excel_btn_next_to_settings)

# (Devamı — arama çubuğu, fixed banner, update_plot ve yan panel oluşturma vb. kodlar aşağıdaki pencerelerde)
SEARCH_Y_OFFSET = 40   # settings/excel butonlarının altı

search_frame = ttk.Frame(root, style="Toolbar.TFrame")
is_focus_held = False

# YENİ: Focus modu değişkeni
search_focus_var = tk.BooleanVar(value=False)
def _on_focus_toggle():
      # Butona basıldığında aramayı tekrar tetikle ki mod devreye girsin
      _on_search_return()
style.configure("Focus.TButton", font=("Segoe UI", 10, "bold"))       
search_label = ttk.Label(search_frame, text="Search customer:", style="Toolbar.TLabel")
search_var = tk.StringVar()
search_entry = ttk.Entry(search_frame, textvariable=search_var, width=128, style="Toolbar.TEntry")
search_list = tk.Listbox(search_frame, height=3, width=130, activestyle="dotbox", relief="flat", borderwidth=1, highlightthickness=2)
btn_focus = ttk.Button(search_frame, text="Single Mode", width=10, style="Toolbutton")  
btn_focus.grid(row=0, column=2, padx=(0, 8), pady=(6, 6), sticky="w")

# --- BUTON OLAYLARI (EVENTS) ---
def _on_focus_press(event):
      global is_focus_held
      # Eğer arama kutusu boşsa işlem yapma
      if not search_var.get().strip():
            return
      is_focus_held = True
      # Zoom bozulmasın (preserve_zoom=True), veri fit edilmesin (fit_to_data=False)
      update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)

def _on_focus_release(event):
      global is_focus_held
      is_focus_held = False
      # Her şeyi geri getir, yine zoom bozulmasın
      update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)

# Basma (Button-1) ve Bırakma (ButtonRelease-1) olaylarını bağlıyoruz
btn_focus.bind("<Button-1>", _on_focus_press)
btn_focus.bind("<ButtonRelease-1>", _on_focus_release)
try:
      search_list.configure(bg="white")
except Exception:
      pass
search_info = tk.Label(search_frame, text="", bg="white", fg="black", anchor="w")

search_label.grid(row=0, column=0, padx=(8, 8), pady=(6, 6), sticky="w")
search_entry.grid(row=0, column=1, padx=(0, 4), pady=(6, 6), sticky="w")
search_info.grid (row=0, column=2, padx=(0, 8),   pady=(6, 6), sticky="w")
search_info.grid(row=0, column=3, padx=(0, 8), pady=(6, 6), sticky="w")
search_list.grid_remove()

search_frame.grid_columnconfigure(1, weight=0)
search_frame.grid_columnconfigure(2, weight=1)

highlight_overlay_artists = []   # vurgulama overlay scatter’ları
def _position_search_frame():
    """Arama çubuğunu Handbook butonunun sağına konumlandırır."""
    try:
        root.update_idletasks()
        # Handbook butonunun konumunu ve genişliğini al
        hx = handbook_btn.winfo_x()
        hw = handbook_btn.winfo_width()
        hy = handbook_btn.winfo_y()
        
        # Eğer buton henüz çizilmediyse (width=1 gelirse) varsayılan bir yer ver
        if hw < 5: 
            hw = 90
            hx = SETTINGS_BTN_X + 200 # Tahmini bir yer
            
        # Handbook'un 12 piksel sağına koy
        sx = hx + hw + 12
        
        # Dikey hizalama (Butonlarla aynı hizada olması için hafif ayar gerekebilir)
        # Genelde butonlar biraz yüksek olduğu için search_frame'i 2-3 piksel yukarı/aşağı oynatabilirsin.
        sy = hy 
        
        search_frame.place(x=sx, y=sy)
        search_frame.lift()
    except Exception:
        # Hata olursa güvenli bir yere koy
        search_frame.place(x=450, y=SETTINGS_BTN_Y)


def toggle_search_bar_visibility():
      if settings_state.get("activate_search_box", False):
            _position_search_frame()
            search_frame.place()
            search_frame.lift()
      else:
            try:
                  search_frame.place_forget()
            except Exception:
                  pass
            _clear_highlight_overlays()


def _clear_highlight_overlays():
      for art in highlight_overlay_artists:
            try:
                  art.remove()
            except Exception:
                  pass
      highlight_overlay_artists.clear()
      canvas.draw_idle()


def _update_search_list(prefix: str):
      search_list.delete(0, tk.END)
      prefix = (prefix or "").strip().casefold()
      if not prefix:
            search_info.config(text="")
            try:
                  search_list.grid_remove()
            except Exception:
                  pass
            _clear_highlight_overlays()
            return

      try:
            search_list.grid(row=1, column=1, padx=(0, 12), pady=(0, 8))
      except Exception:
            pass

      names = _visible_customer_names_starting_with(prefix)
      for name in names[:50]:
            search_list.insert(tk.END, name)

      count = search_list.size()
      search_info.config(text=f"{count} match")


def _visible_customer_names_starting_with(prefix_cf: str):
      """
      Arama kutusu için aday listesi oluşturur.
      - Sector Avg modu: Sektör isimlerini ("Technology Avg" gibi) döndürür.
      - Diğer modlar: Görünür müşteri isimlerini döndürür.
      """
      current_mode = sector_combobox.get()
       
      # --- SENARYO 1: SECTOR AVG MODU ---
      if current_mode == "Sector Avg":
            # Sadece ekranda var olan (verisi olan) sektörleri bul
            # sectors değişkeni globalde zaten var ama boş sektörleri elemek için
            # visible_df mantığına bakabiliriz veya direkt 'sectors' listesini kullanabiliriz.
             
            candidates = []
            for sec in sectors:
                  # Sadece verisi olan sektörleri listeye ekle (opsiyonel optimizasyon)
                  if not df[df['Company Sector'] == sec].empty:
                        candidates.append(f"{sec} Avg")
             
            # Filtrele ve döndür
            return [c for c in candidates if tr_lower(c).startswith(prefix_cf)]

      # --- SENARYO 2: MÜŞTERİ ARAMA MODU (ESKİ MANTIK) ---
      hidden = set().union(manual_removed, license_removed, get_limit_removed_keys(df, settings_state))
       
      # visible_df oluştur (filtrelenmiş veri)
      vis_df = df[~df.apply(lambda r: get_point_key(r, settings_state) in hidden, axis=1)].copy()

      vis_df = _apply_churn_filters(vis_df)
      vis_df = _apply_age_filters(vis_df)
      vis_df = _apply_regression_filter(vis_df, get_plot_x_col())

      if current_mode not in ("All", "Sector Avg"):
            vis_df = vis_df[vis_df['Company Sector'] == current_mode]
            if is_risk_view_active(current_mode) and (RISK_COL in vis_df.columns):
                    vis_df = vis_df[vis_df[RISK_COL].astype(str).str.upper().apply(lambda val: is_risk_allowed(val, settings_state))]

      if 'Customer' not in vis_df.columns:
            return []
       
      names = vis_df['Customer'].dropna().astype(str)
      return [n for n in names if tr_lower(n).startswith(prefix_cf)]


def _highlight_matches(prefix: str):
      _clear_highlight_overlays()
      prefix_cf = (prefix or "").strip().casefold()
      if not prefix_cf:
            return

      if is_focus_held:
            return

      is_sector_avg_mode = (sector_combobox.get() == "Sector Avg")

      # --- SENARYO 1: SECTOR AVG MODU (BÜYÜK NOKTALARI PARLAT) ---
      if is_sector_avg_mode:
            for sc, _ in scatter_points:
                  label = sc.get_label() or ""
                   
                  # Label tam eşleşiyor mu veya arama ile başlıyor mu?
                  # Listbox'tan seçilince tam isim gelir (örn: "Finance Avg")
                  # Elle yazılınca prefix gelir (örn: "Fin")
                  if tr_lower(label).startswith(prefix_cf):
                         
                        # Koordinatı al (Scatter tek bir nokta içerir)
                        offsets = sc.get_offsets()
                        if len(offsets) > 0:
                              px, py = offsets[0]
                               
                              # Eksenler takas edilmişse düzelt (gerçi offsets ekran koordinatıdır, gerekmez ama kontrol)
                              # Matplotlib offsets zaten plot edilmiş X,Y'dir.
                               
                              # Neon Efekti (Daha büyük radius çünkü Avg noktaları büyük)
                              ov1 = ax.scatter([px], [py], s=1200, c='#00FF00', alpha=0.2, edgecolors='none', zorder=9)
                              ov2 = ax.scatter([px], [py], s=600, c='#00FF00', alpha=0.4, edgecolors='none', zorder=9)
                              ov3 = ax.scatter([px], [py], s=300, c='white', alpha=0.9, edgecolors='#00FF00', linewidth=2, zorder=10)
                              highlight_overlay_artists.extend([ov1, ov2, ov3])
             
            canvas.draw_idle()
            return

      # --- SENARYO 2: NORMAL MÜŞTERİ MODU (ESKİ KOD) ---
      for sc, sd in scatter_points:
            label = sc.get_label() or ""
             
            # Avg noktalarını atla (Normal modda avg noktası varsa bile müşteri arıyoruz)
            if label.endswith(" Avg"):  
                  continue
                   
            if 'Customer' not in sd.columns: continue

            mask = sd['Customer'].astype(str).str.casefold().str.startswith(prefix_cf)
            if not mask.any(): continue

            x_col = get_plot_x_col()
            xs = []; ys = []
            for _, row in sd[mask].iterrows():
                  try:
                        xv = float(row[x_col])
                  except:
                        xv = float(row.get(EFFECTIVE_MRR_COL, row.get(BASE_MRR_FALLBACK_COL)))
                  yv = float(row['MRR Growth (%)'])
                  px, py = to_plot_coords(xv, yv)
                  xs.append(px); ys.append(py)

            if xs:
                  # Neon Efekti (Müşteri için daha küçük)
                  ov1 = ax.scatter(xs, ys, s=500, c='#00FF00', alpha=0.2, edgecolors='none', zorder=9)
                  ov2 = ax.scatter(xs, ys, s=200, c='#00FF00', alpha=0.4, edgecolors='none', zorder=9)
                  ov3 = ax.scatter(xs, ys, s=50, c='white', alpha=0.9, edgecolors='#00FF00', linewidth=1, zorder=10)
                  highlight_overlay_artists.extend([ov1, ov2, ov3])

      canvas.draw_idle()

def _on_search_key_press(event):
      """
      Tuşa basıldığı an çalışır (KeyPress).
      Bozuk karakterleri (Ý, Þ, Ð) yakalar, engeller ve doğrusunu yazar.
      """
      # Düzeltilecek karakterler listesi: { "Bozuk": "Düzgün" }
      corrections = {
            "Ý": "İ",
            "Þ": "Ş",
            "Ð": "Ğ"
      }

      # Eğer basılan tuş (event.char) listemizde varsa
      if event.char in corrections:
            correct_char = corrections[event.char]
             
            # 1. İmlecin olduğu yere manuel olarak doğru harfi ekle
            search_entry.insert(tk.INSERT, correct_char)
             
            # 2. Arama listesini anında güncelle (Lag olmaması için)
            # Entry'ye insert yaptığımız an search_var güncellenir, onu alıp filtreliyoruz
            current_val = search_var.get()
            _update_search_list(tr_lower(current_val))
             
            # 3. Tkinter'ın bozuk karakteri yazmasını ENGELLE
            return "break"
       
def _on_search_key_release(event=None):
      # Yön tuşları ve Enter aramayı tetiklemesin
      if event and event.keysym in ("Down", "Up", "Return"):
            return

      # Sadece mevcut değeri alıp aramayı güncellemek yeterli
      raw_val = search_var.get()
      normalized_val = tr_lower(raw_val)
      _update_search_list(normalized_val)

# 2. Yeni: Arama kutusundayken AŞAĞI YÖN tuşuna basınca
def _on_entry_down_arrow(event):
      # Eğer liste görünürse ve içi doluysa
      if search_list.winfo_viewable() and search_list.size() > 0:
            search_list.focus_set()            # Odağı listeye ver
            search_list.selection_clear(0, tk.END)  
            search_list.selection_set(0)     # İlk elemanı seç
            search_list.activate(0)            # İlk elemanı aktif et (görsel olarak)
            return "break" # Olayı burada bitir

# 3. Yeni: Listbox üzerindeyken ENTER tuşuna basınca
def _on_listbox_return(event):
      cs = search_list.curselection()
      if cs:
            # Seçili olanı al
            selected_text = search_list.get(cs)
            # Entry'ye yaz
            search_var.set(selected_text)
             
            # --- DÜZELTME BURADA: ---
            # Listeyi güncelle ki "1 match" yazsın ve liste tek satıra düşsün
            _update_search_list(tr_lower(selected_text))
            # ------------------------

            # Vurgulama (Highlight) fonksiyonunu çağır
            _highlight_matches(selected_text)
             
            # Odağı tekrar Entry'ye ver
            search_entry.focus_set()
            # İmleci sona götür
            search_entry.icursor(tk.END)
      return "break"

def _on_listbox_up_arrow(event):
      """Listbox'ta en üstteyken yukarı basınca Arama Kutusuna dön."""
      try:
            selection = search_list.curselection()
             
            # Eğer bir seçim varsa ve seçilen index 0 (en üst) ise
            if selection and selection[0] == 0:
                  # 1. Listbox seçimini temizle (görsel olarak odak çıktığını belli etmek için)
                  search_list.selection_clear(0, tk.END)
                   
                  # 2. Odağı arama kutusuna ver
                  search_entry.focus_set()
                   
                  # 3. İmleci metnin en sonuna koy
                  search_entry.icursor(tk.END)
                   
                  # 4. Event'i durdur (Listbox yukarı gitmeye çalışmasın)
                  return "break"
                   
      except Exception:
            pass       

def _on_search_return(event=None):
      term = (search_var.get() or "").strip()
       
      # Eğer Focus (🎯) butonu basılıysa:
      if search_focus_var.get():
            # Grafiği yenile (Sadece o müşteriyi gösterecek şekilde)
            # fit_to_data=True diyerek direkt o müşteriye zoom yapmasını sağlıyoruz
            update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)
            # Listeyi gizle
            try: search_list.grid_remove()
            except: pass
             
      # Eğer Focus kapalıysa (Eski usul highlight):
      else:
            if not term:
                  _clear_highlight_overlays()
                  return
            _highlight_matches(term)


def _on_search_list_double_click(event=None):
      try:
            sel = search_list.get(search_list.curselection())
      except Exception:
            sel = None
      if sel:
            search_var.set(sel)
            _highlight_matches(sel)

search_entry.bind("<Return>", _on_search_return)
search_entry.bind("<KeyPress>", _on_search_key_press)
search_list.bind("<Double-Button-1>", _on_search_list_double_click)
# --- Mevcut Bindings Güncellemeleri ---
search_entry.bind("<KeyRelease>", _on_search_key_release)
search_entry.bind("<Return>", _on_search_return) # Entry'de Enter'a basınca (Normal arama)

# --- YENİ EKLENENLER ---
# 1. Entry üzerindeyken Aşağı Ok -> Listeye geç
search_entry.bind("<Down>", _on_entry_down_arrow)
search_list.bind("<Up>", _on_listbox_up_arrow)

# 2. Listbox üzerindeyken Enter -> Seçimi al ve kutuya koy
search_list.bind("<Return>", _on_listbox_return)

# (Opsiyonel) Kullanıcı mouse ile çift tıklarsa da aynısı olsun
search_list.bind("<Double-Button-1>", lambda e: _on_listbox_return(e))    

# --- Fixed Axes banner (butonun hemen altında) ---
fixed_banner = tk.Label(
      root,
      text="",
      bg="white",                     # Beyaz zemin
      fg="#2c3e50",                  # Koyu lacivert/gri tonu (daha profesyonel)
      font=("Segoe UI", 9),      # Okunaklı font
      justify="left",
      relief="solid",               # İnce çerçeve
      borderwidth=1,
      padx=12, pady=6               # İçeriden boşluk (ferah görünüm için)
)
fixed_banner.place_forget()   # Başlangıçta gizli

def update_fixed_banner():
      """
      Aktif filtreleri yan yana gösterir. Regresyon durumu eklendi.
      """
      active_items = []

      # 1. Fixed Axis Durumu
      if settings_state.get("fixed_axis", False):
            active_items.append("FIXED AXES ACTIVE")

      # 2. Limit Seçenekleri
      if settings_state.get("mode") == "limit":
            m_min = settings_state.get("mrr_min")
            m_max = settings_state.get("mrr_max")
            g_min = settings_state.get("growth_min")
            g_max = settings_state.get("growth_max")

            if m_min is not None: active_items.append(f"MRR Min: {m_min:,.0f}")
            if m_max is not None: active_items.append(f"MRR Max: {m_max:,.0f}")
            if g_min is not None: active_items.append(f"Growth Min: %{g_min:.1f}")
            if g_max is not None: active_items.append(f"Growth Max: %{g_max:.1f}")

      # 3. Filter by Age
      age_mode = settings_state.get("age_filter_mode", "0-Current")
      if age_mode != "0-Current":
            clean_age = age_mode.replace("(", "").replace(")", "")
            active_items.append(f"Age: {clean_age}")

      # 4. License Reverse
      if settings_state.get("reverse_effect", False):
            active_items.append("Rev. License")

      # 5. Regresyon Filtresi (Above/Below)
      reg_filt = settings_state.get("regression_filter", "none")
      if reg_filt == "above":
            active_items.append("Filter: Above Trend")
      elif reg_filt == "below":
            active_items.append("Filter: Below Trend")

      # =================== YENİ: REGRESYON DURUMU ===================
      if settings_state.get("show_regression_line", False):
            # Eğer sabitlenmişse belirt
            if settings_state.get("fix_regression_line", False):
                  # Hafızadaki eğim değerini alıp gösterebiliriz
                  params = settings_state.get("fixed_regression_params", {})
                  m_val = params.get("m")
                  if m_val is not None:
                        # Eğimi 4 basamak gösterelim
                        active_items.append(f"Trend Line: FIXED (Slope={m_val:.4f})")
                  else:
                        active_items.append("Trend Line: FIXED")
            else:
                  # Sabit değilse sadece açık olduğunu belirt (Opsiyonel, çok kalabalık olmasın dersen kaldırabilirsin)
                  # active_items.append("Trend Line: Auto")
                  pass
      # ==============================================================

      # --- Görüntüleme ---
      if not active_items:
            fixed_banner.place_forget()
      else:
            separator = "     |     "
            final_text = separator.join(active_items)
             
            fixed_banner.config(text=final_text)
            reposition_top_left_ui()
            fixed_banner.lift()
def reposition_top_left_ui():
      """Banner'ı üstteki butonların (Settings/Export/Handbook) hemen altına hizalar."""
      try:
            root.update_idletasks()
            bx = SETTINGS_BTN_X
            by = SETTINGS_BTN_Y
            bh = settings_btn.winfo_height()
            if bh < 20: bh = 30
                   
            # Butonların biraz daha altına (8px boşluk)
            banner_y = by + bh + 8  
            fixed_banner.place(x=bx, y=banner_y)
            fixed_banner.lift()
      except Exception:
            pass

# ====================================================================================

# ========================== YENİ: Regresyon Filtre Butonları ==========================
try:
      # Toggle buton stili (basılı kalma efekti için)
      style.configure("Reg.TButton", font=("Segoe UI", 10), padding=(4, 4), width=2)
      style.map("Reg.TButton",
            foreground=[("disabled", "#999999"), ("active", "#000000")],
            background=[("disabled", "#d9d9d9"), ("active", "#e8e8e8"), ("selected", "#c0d0ff")] # 'selected' basılı durumu
      )
except Exception:
      pass

reg_filter_var = tk.StringVar(value="none") # "none", "above", "below"

reg_btn_up = ttk.Button(root, text="⬆", style="Reg.TButton", command=lambda: _on_reg_filter_click("above"))
reg_btn_down = ttk.Button(root, text="⬇", style="Reg.TButton", command=lambda: _on_reg_filter_click("below"))

def trigger_auto_zoom():
      """Grafiği mevcut seçim için otomatik olarak fit_to_data yap."""
      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)
       
      # --- DÜZELTME: Auto-zoom sonrası seçili noktaları tekrar boya ---
      draw_selection_highlights()
       
def _on_reg_filter_click(clicked_mode: str):
      current_mode = reg_filter_var.get()
    
      if current_mode == clicked_mode:
            # Zaten seçili olan butona basıldı -> kapat (none)
            new_mode = "none"
      else:
            # Diğer butona basıldı -> onu aç
            new_mode = clicked_mode
    
      reg_filter_var.set(new_mode)
      settings_state["regression_filter"] = new_mode
    
      # Butonların "selected" durumunu güncelle
      if new_mode == "above":
            reg_btn_up.state(["selected"])
            reg_btn_down.state(["!selected"])
      elif new_mode == "below":
            reg_btn_up.state(["!selected"])
            reg_btn_down.state(["selected"])
      else:
            reg_btn_up.state(["!selected"])
            reg_btn_down.state(["!selected"])
    
      # Değişikliği uygulamak için grafiği yeniden çiz
      update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)


def _position_regression_buttons():
      """Butonları grafiğin sağ alt köşesine hizala."""
      # --- GÜVENLİK KİLİDİ ---
      # Eğer Sector Avg seçiliyse, birisi bu fonksiyonu yanlışlıkla çağırsa bile
      # butonları yerleştirme. İşlemi iptal et.
      try:
            if sector_combobox.get() == "Sector Avg":
                  return
      except Exception:
            pass
      # -----------------------

      try:
            root.update_idletasks()
            cx = canvas_widget.winfo_x()
            cy = canvas_widget.winfo_y()
            cw = canvas_widget.winfo_width()
            ch = canvas_widget.winfo_height()
            bw = reg_btn_up.winfo_width()
            bh = reg_btn_up.winfo_height()
             
            # Eğer boyutlar henüz hesaplanmadıysa varsayılan değer ver ki hata vermesin
            if bw < 5: bw = 20
            if bh < 5: bh = 20

            x = cx + cw - bw - 10
            y_down = cy + ch - bh - 10
            y_up = y_down - bh - 2  
             
            reg_btn_up.place(x=x, y=y_up)
            reg_btn_down.place(x=x, y=y_down)
            reg_btn_up.lift()
            reg_btn_down.lift()
      except Exception:
            pass

def toggle_regression_buttons_visibility():
      # 1. Ayar açık mı?
      is_reg_active = settings_state.get("show_regression_line", False)
       
      # 2. Sektör "Sector Avg" mi?
      try:
            is_sector_avg = (sector_combobox.get() == "Sector Avg")
      except Exception:
            is_sector_avg = False

      # KURAL: Regresyon AÇIKSA ve Sektör "Sector Avg" DEĞİLSE göster.
      if is_reg_active and not is_sector_avg:
            _position_regression_buttons()
      else:
            # Aksi takdirde ZORLA GİZLE
            try:
                  reg_btn_up.place_forget()
                  reg_btn_down.place_forget()
            except Exception:
                  pass
# =================================================================================
zoom_btn = ttk.Button(
      root,
      text="🔍",
      width=2,
      command=trigger_auto_zoom
)

def _position_zoom_button():
      """Zoom butonunu grafiğin (canvas_widget) sağ üst köşesine hizala."""
      try:
            root.update_idletasks()
            cx = canvas_widget.winfo_x()
            cy = canvas_widget.winfo_y()
            cw = canvas_widget.winfo_width()
            bw = zoom_btn.winfo_width()
            x = cx + cw - bw - 10
            y = cy + 10
            zoom_btn.place(x=x, y=y)
            zoom_btn.lift()
      except Exception:
            pass

root.after_idle(_position_zoom_button)

def _on_root_configure(e):
      if 'settings_state' not in globals():
            return

      update_fixed_banner()
      if settings_state.get("activate_search_box", False):
            _position_search_frame()
      _position_zoom_button()
       
      # --- BURASI ÖNEMLİ ---
      # Sadece toggle fonksiyonunu çağırıyoruz.  
      # O fonksiyon gerekli kontrolleri yapıp gizlemesi gerekiyorsa gizleyecek.
      toggle_regression_buttons_visibility()

root.bind("<Configure>", _on_root_configure)

# ===== Sağ YAN PANEL =====
sidebar = ttk.Frame(root)
sidebar.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
sidebar.grid_rowconfigure(0, weight=1)    
sidebar.grid_rowconfigure(1, weight=0)    
sidebar.grid_rowconfigure(2, weight=0)    
sidebar.grid_columnconfigure(0, weight=1)

# ÜST: Kontroller
controls_frame = ttk.Frame(sidebar)
controls_frame.grid(row=0, column=0, sticky="nsew")

# 1. Sektör Seçimi
lbl_select = tk.Label(controls_frame, text="Select Sector:")
lbl_select.pack(anchor="w", padx=10, pady=(0, 5))

sector_options = ["Sector Avg"] + list(sectors) + ["All"]
sector_combobox = ttk.Combobox(controls_frame, values=sector_options, state="readonly")
sector_combobox.current(0)
sector_combobox.pack(fill="x", padx=10, pady=(0, 15))

# ---------------------------------------------------------
# BÖLÜM 1: ACTIVE CUSTOMERS (AKORDİYON KUTU)
# ---------------------------------------------------------
# Helper fonksiyonu kullanarak kartı oluşturuyoruz
# ---------------------------------------------------------
frame_active_stats, total_label, total_mrr_label, sector_count_label = create_collapsible_stat_card(
      controls_frame, title_bg="#e6f3ff" # Hafif mavi başlık (Active)
)
frame_active_stats.pack(fill="x", padx=10, pady=(0, 10)) # pady 20 yerine 10 yaptık, birbirine yaklaşsın

# ---------------------------------------------------------
# BÖLÜM 2: CHURN STATISTICS (AKORDİYON KUTU - YENİ İSİMLENDİRME)
# ---------------------------------------------------------
# Hemen Active Stats'ın altına ekliyoruz.
frame_churn_stats, churn_customer_label, churn_total_label, churn_sector_label = create_collapsible_stat_card(
      controls_frame, title_bg="#ffe6e6" # Hafif kırmızı başlık (Churn)
)
# Başlangıçta pack ediyoruz, visibility fonksiyonu yönetse de yerini rezerve edelim
frame_churn_stats.pack(fill="x", padx=10, pady=(0, 10))

# --- Churn Ratio Label ---
churn_ratio_label = ttk.Label(
      controls_frame,
      text="",
      font=("Arial", 10, "bold"),
      foreground="red",
      justify="center"
)
churn_ratio_label.pack(pady=(0, 10))

# ---------------------------------------------------------
# REFLOW MANTIĞI GÜNCELLEMESİ
# ---------------------------------------------------------
# Eski _reflow_right_panel_for_selection fonksiyonu label'ları grid ile yönetiyordu.
# Artık pack kullanıyoruz ve container yapısı değişti. Bu fonksiyonu basitleştirelim.

def _reflow_right_panel_for_selection(sel: str):
      """
      Yeni yapıda reflow: Sektör seçiliyse detay listesi (sector_count_label) içeriği değişir,
      ancak açılır/kapanır yapı sayesinde UI bozulmaz.
      Burada sadece 'Tek Sektör' seçildiğinde churn kutusunu gizleyip gizlemeyeceğimize karar verebiliriz.
      """
      # Mevcut yapıda "Sector Avg" veya "All" değilse detay listesini temizlemek isteyebilirsin.
      # Ancak "List Breakdown" özelliği tek sektör için anlamsız olacağından,
      # update_plot içinde tek sektör seçiliyse listeye boş string atamak yeterlidir.
      pass  

def _apply_churn_labels_visibility():
      """Churn kutusunun (frame_churn_stats) görünürlüğünü yönetir."""
      show = bool(churn_enabled_var.get() or churn_only_var.get())
       
      if show:
            frame_churn_stats.pack(fill="x", padx=10, pady=(0, 10), after=frame_active_stats)
            # Ratio label'ı da göster
            try:
                  if churn_ratio_label.cget("text"):  
                        churn_ratio_label.pack(pady=(0, 10), after=frame_churn_stats)
            except: pass
      else:
            frame_churn_stats.pack_forget()
            churn_ratio_label.pack_forget()

# Spacer (En alta itmek için boşluk)
bottom_spacer = ttk.Frame(controls_frame)
bottom_spacer.pack(fill="both", expand=True)


# =================== NEW/CHURN: Sağ panelde Churn Options ===================
def _on_churn_toggle():
      # Eğer şu anda License Exc. ise, Include'ye basınca otomatik Inc.'e dön
      if license_var.get() == "Exc." and churn_enabled_var.get():
            on_license_select_v1()   # Inc.'e çevir
      # Include işaretlenirse Show Only otomatik kapansın
      if churn_enabled_var.get():
            churn_only_var.set(False)

      settings_state["churn_enabled"] = bool(churn_enabled_var.get())
      settings_state["show_only_churn"] = bool(churn_only_var.get())

      _apply_churn_labels_visibility()
      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)


def _on_only_churn_toggle():
      # Eğer şu anda License Exc. ise, Show Only'ye basınca otomatik Inc.'e dön
      if license_var.get() == "Exc." and churn_only_var.get():
            on_license_select_v1()

      if churn_only_var.get():
            churn_enabled_var.set(False)

      settings_state["churn_enabled"] = bool(churn_enabled_var.get())
      settings_state["show_only_churn"] = bool(churn_only_var.get())

      _apply_churn_labels_visibility()
      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)


churn_enabled_var = tk.BooleanVar(value=True)
churn_only_var     = tk.BooleanVar(value=False)

churn_frame = ttk.LabelFrame(sidebar, text="Churn Options", padding=8)
churn_frame.grid(row=1, column=0, sticky="sew", padx=10, pady=(0, 6))
churn_frame.grid_columnconfigure(0, weight=1)

churn_ratio_label = ttk.Label(
      churn_frame,
      text="",
      font=("Arial", 11, "bold"),
      justify="left"
)
churn_ratio_label.grid(row=0, column=0, sticky="w", padx=4, pady=(0, 4))

churn_cb = ttk.Checkbutton(
      churn_frame,
      text="Include Churned Customers",
      variable=churn_enabled_var,
      command=_on_churn_toggle
)
churn_cb.grid(
      row=1, column=0,
      sticky="w",
      padx=4, pady=(0, 2)
)

churn_only_cb = ttk.Checkbutton(
      churn_frame,
      text="Show Only Churned Customers",
      variable=churn_only_var,
      command=_on_only_churn_toggle
)
churn_only_cb.grid(
      row=2, column=0,
      sticky="w",
      padx=4, pady=(0, 2)
)

# =================== NEW: ADVANCED ANALYTICS PANEL ===================
analytics_frame = ttk.LabelFrame(sidebar, text="Advanced Analytics (Beta)", padding=8)
analytics_frame.grid(row=3, column=0, sticky="sew", padx=10, pady=(10, 6))

# Değişkenler
an_mode_var = tk.StringVar(value="none")
an_marginal_var = tk.BooleanVar(value=False)

def apply_analytics():
      analytics_state["mode"] = an_mode_var.get()
      analytics_state["show_marginals"] = bool(an_marginal_var.get())
       
      # Eğer Pareto açıksa, koyu tema iyidir ama şimdilik sadece grafiği yenileyelim
      update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)

# 1. Marjinal Grafikler (Toggle)
chk_marg = ttk.Checkbutton(analytics_frame, text="Show Marginal Histograms",  
                                         variable=an_marginal_var, command=apply_analytics)
chk_marg.grid(row=0, column=0, sticky="w", padx=2, pady=2)

# 2. Mod Seçimi (Radio Buttons)
lbl_modes = ttk.Label(analytics_frame, text="AI Analysis Mode:", font=("Segoe UI", 9, "bold"))
lbl_modes.grid(row=1, column=0, sticky="w", padx=2, pady=(6,2))

rb_none = ttk.Radiobutton(analytics_frame, text="None (Standard View)", value="none",  
                                       variable=an_mode_var, command=apply_analytics)
rb_kmeans = ttk.Radiobutton(analytics_frame, text="K-Means Clustering (3 Groups)", value="kmeans",  
                                          variable=an_mode_var, command=apply_analytics)
rb_pareto = ttk.Radiobutton(analytics_frame, text="Pareto Analysis (Top %20)", value="pareto",  
                                          variable=an_mode_var, command=apply_analytics)

rb_none.grid(row=2, column=0, sticky="w", padx=10)
rb_kmeans.grid(row=3, column=0, sticky="w", padx=10)
rb_pareto.grid(row=4, column=0, sticky="w", padx=10)

if not _HAS_SKLEARN:
      rb_kmeans.configure(state="disabled", text="K-Means (sklearn not found)")
# =====================================================================
# ================================================================================================

# Spacer
controls_frame.grid_rowconfigure(8, weight=1)
controls_frame.grid_columnconfigure(0, weight=1)

scatter_points = []
sector_churn_stats_cache = {}
last_annotation = None

# =====================================================
# DURUM & UNDO
# =====================================================
manual_removed = set()
license_removed = set()
# YENİ: Regresyon filtresi tarafından gizlenen noktalar (anahtar olarak point_key kullanır)
regression_removed = set()
# YENİ: Mevcut görünüm için hesaplanan regresyon çizgisi (eğim, kesişim)
current_regression_line = {'m': None, 'b': None}


active_legends = []


undo_stack = []

# =====================================================
# Yardımcılar
# =====================================================
def remove_existing_legends():
      for child in list(ax.get_children()):
            if isinstance(child, mlegend.Legend):
                  try:
                        child.remove()
                  except Exception:
                        pass
      active_legends.clear()

# --- Age filter modları ---
AGE_MODE_0_CURRENT = "0-Current"
AGE_MODE_0_1         = "0-1"
AGE_MODE_0_2         = "0-2"
AGE_MODE_1_2         = "1-2"

def get_age_filter_mode():
      """Settings içindeki aktif yaş filtresi modu."""
      return settings_state.get("age_filter_mode", AGE_MODE_0_CURRENT)


def _apply_age_filters(df_in: pd.DataFrame) -> pd.DataFrame:
      """
      Yaş filtresine göre satırları filtreler:
      - 0-Current: hiç filtre yok (herkes görünür)
      - 0-1: DoesCustomerCompleteItsFirstYear = Yes olmalı
      - 0-2 / 1-2: DoesCustomersCompleteItsSecondYear = Yes olmalı
      """
      mode = get_age_filter_mode()
      df_out = df_in.copy()

      if mode == AGE_MODE_0_1:
            col = "DoesCustomerCompleteItsFirstYear"
            if col in df_out.columns:
                  mask = df_out[col].astype(str).str.upper().eq("YES")
                  df_out = df_out[mask]

      elif mode in (AGE_MODE_0_2, AGE_MODE_1_2):
            col = "DoesCustomersCompleteItsSecondYear"
            if col in df_out.columns:
                  mask = df_out[col].astype(str).str.upper().eq("YES")
                  df_out = df_out[mask]

      return df_out


def get_growth_source_col_for_age_mode():
      """
      Aktif yaş filtresine göre hangi growth kolonunu kullanacağımızı döndürür.
      """
      mode = get_age_filter_mode()

      if mode == AGE_MODE_0_1:
            return "MRR Growth (0-1)"
      elif mode == AGE_MODE_0_2:
            return "MRR Growth (0-2)"
      elif mode == AGE_MODE_1_2:
            return "MRR Growth(1-2)"     # Excel’deki tam kolon adın buysa aynen böyle bırak
      else:
            # 0-Current
            if "MRR Growth (0-today)" in df.columns:
                  return "MRR Growth (0-today)"
            return "MRR Growth"


def get_base_mrr_col_for_age_mode():
      """
      X eksenindeki baz MRR kolonunu yaş moduna göre seç.
      """
      mode = get_age_filter_mode()

      if mode == AGE_MODE_0_1:
            return "First Year Ending MRR"
      elif mode in (AGE_MODE_0_2, AGE_MODE_1_2):
            return "Second Year Ending MRR"
      else:
            # 0-Current
            return CURRENT_MRR_COL if CURRENT_MRR_COL in df.columns else BASE_MRR_FALLBACK_COL


def get_exc_mrr_col_for_age_mode():
      """
      Exc. License MRR için yaş moduna göre kaynak sütun.
      """
      mode = get_age_filter_mode()

      if mode == AGE_MODE_0_1:
            return "First Year Ending Exc. License MRR"
      elif mode in (AGE_MODE_0_2, AGE_MODE_1_2):
            return "Second Year Ending Exc. License MRR"
      else:
            return "Exc. License MRR"


def _apply_churn_filters(df_in: pd.DataFrame) -> pd.DataFrame:
      """Include / Show Only durumuna göre churn satırlarını filtreler."""
      if CHURN_COL not in df_in.columns:
            return df_in

      churn_enabled = settings_state.get("churn_enabled", True)
      show_only = settings_state.get("show_only_churn", False)

      col = df_in[CHURN_COL].astype(str).str.upper()

      if show_only:
            return df_in[col.eq("CHURN")]
      elif not churn_enabled:
            return df_in[~col.eq("CHURN")]
      else:
            return df_in


def _apply_regression_filter(df_in: pd.DataFrame, x_col: str) -> pd.DataFrame:
      """
      YENİ: Varsa, hesaplanmış regresyon çizgisine göre filtreler (above/below).
      Çizgi hesaplanmamışsa (None) veya filtre "none" ise değişiklik yapmaz.
      """
      filter_mode = settings_state.get("regression_filter", "none")
      m = current_regression_line.get('m')
      b = current_regression_line.get('b')

      if filter_mode == "none" or m is None or b is None:
            regression_removed.clear() # Filtre kapalıyken eski gizlenenleri temizle
            return df_in

      if settings_state.get("swap_axes", False):
            # Eksenler ters (Y=MRR, X=Growth)
            # y = mx + b -> (MRR) = m*(Growth) + b
            # Bizim y değerimiz (MRR) = row[x_col]
            # Bizim x değerimiz (Growth) = row['MRR Growth (%)']
            x_data = df_in['MRR Growth (%)'].astype(float)
            y_data = df_in[x_col].astype(float)
      else:
            # Normal (Y=Growth, X=MRR)
            # y = mx + b -> (Growth) = m*(MRR) + b
            # Bizim x değerimiz (MRR) = row[x_col]
            # Bizim y değerimiz (Growth) = row['MRR Growth (%)']
            x_data = df_in[x_col].astype(float)
            y_data = df_in['MRR Growth (%)'].astype(float)
    
      # y_pred = m*x + b (çizginin y'si)
      y_pred = m * x_data + b
    
      if filter_mode == "above":
            # Sadece (y_data > y_pred) olanlar kalsın
            mask = (y_data >= y_pred)
      elif filter_mode == "below":
            # Sadece (y_data < y_pred) olanlar kalsın
            mask = (y_data <= y_pred)
      else:
            mask = True # Hepsini tut
    
      # Gizlenenleri regression_removed set'ine ekle (undo vb için değil, sadece takip)
      regression_removed.clear()
      if mask is not True:
            removed_df = df_in[~mask]
            for _, row in removed_df.iterrows():
                  regression_removed.add(get_point_key(row, settings_state))
    
      return df_in[mask]
def get_plot_x_col():
      use_updated = (
            settings_state.get("use_updated_exc_license_values", False)
            and license_var.get() == "Exc."
      )
      updated_col = 'Exc. License MRR'
      if use_updated and (updated_col in df.columns or updated_col in df):
            return updated_col
      return EFFECTIVE_MRR_COL


def get_updated_y_col_if_any():
      candidates = [
            'Exc. License Growth (%)',
            'Updated Growth (%)',
            'MRR Growth Updated (%)',
            'New MRR Growth (%)',
            'Growth Updated (%)'
      ]
      for c in candidates:
            if c in df.columns:
                  return c
      return None


def to_plot_coords(x_mrr, y_growth):
      if settings_state.get("swap_axes", False):
            return (y_growth, x_mrr)
      return (x_mrr, y_growth)


def compute_fit_limits(selected_sector, x_col, visible_df, pad_ratio=PAD_RATIO, eff_center=None, extra_points=None):
      xs = []; ys = []
      if selected_sector == "Sector Avg":
            for sector in sectors:
                  sd = visible_df[visible_df['Company Sector'] == sector]
                  if len(sd) == 0:
                        continue
                  avg_x = float(sd[x_col].astype(float).mean())
                  avg_y = float(sd['MRR Growth (%)'].astype(float).mean())
                  px, py = to_plot_coords(avg_x, avg_y)
                  xs.append(px); ys.append(py)
      else:
            if selected_sector == "All":
                  sd = visible_df
            else:
                  sd = visible_df[visible_df['Company Sector'] == selected_sector]
            if len(sd) > 0:
                  for xv, yv in zip(sd[x_col].astype(float).values, sd['MRR Growth (%)'].astype(float).values):
                        px, py = to_plot_coords(float(xv), float(yv))
                        xs.append(px); ys.append(py)

      if eff_center is not None:
            cx, cy = eff_center
            px, py = to_plot_coords(cx, cy)
            xs.append(float(px)); ys.append(float(py))

      if extra_points:
            for ex, ey in extra_points:
                  xs.append(float(ex)); ys.append(float(ey))

      if not xs or not ys:
            return None

      xmin, xmax = min(xs), max(xs)
      ymin, ymax = min(ys), max(ys)
      xspan = xmax - xmin
      yspan = ymax - ymin
      if xspan == 0: xspan = max(abs(xmax) * 0.02, 1.0)
      if yspan == 0: yspan = max(abs(ymax) * 0.02, 1.0)
      xpad = xspan * pad_ratio
      ypad = yspan * pad_ratio
      return (xmin - xpad, xmax + xpad, ymin - ypad, ymax + ypad)
# =====================================================
# Çizim / etkileşim
# =====================================================

def update_plot(selected_sector, preserve_zoom=True, fit_to_data=False):
      global last_annotation, center_x, center_y

      # settings_state ile Churn checkbox senkronu
      settings_state["churn_enabled"] = bool(churn_enabled_var.get())
      settings_state["show_only_churn"] = bool(churn_only_var.get())
      # YENİ: Regresyon filtresi durumunu global state'e yansıt
      settings_state["regression_filter"] = reg_filter_var.get()

      x_col = get_plot_x_col()

      if preserve_zoom:
            try:
                  cur_xlim = ax.get_xlim(); cur_ylim = ax.get_ylim()
            except Exception:
                  cur_xlim = cur_ylim = None
      else:
            cur_xlim = cur_ylim = None

      if last_annotation:
            try:
                  last_annotation.remove()
            except Exception:
                  pass
            last_annotation = None

      ax.clear()
      # --- YAMA BAŞLANGIÇ: Eski marjinal grafikleri temizle ---
      for art in analytics_state["marginal_artists"]:
            try: art.remove()
            except: pass
      analytics_state["marginal_artists"].clear()
      # --- YAMA BİTİŞ ---
      remove_existing_legends()
      scatter_points.clear()
      _clear_highlight_overlays()   # yeni çizimde eski highlight overlaylerini temizle

      hidden = set().union(manual_removed, license_removed, get_limit_removed_keys(df, settings_state))

      # ================= YENİ: HOLD-TO-FOCUS MANTIĞI (GÜNCELLENDİ) =================
      # Eğer butona BASILI TUTULUYORSA (is_focus_held == True)
      if is_focus_held:
            term = search_var.get().strip().casefold()
            if term:
                  is_sector_avg_mode = (selected_sector == "Sector Avg")
                   
                  for _, row in df.iterrows():
                        if is_sector_avg_mode:
                              # Sector Avg modundaysak: "Technology Avg" gibi bir yapı arıyoruz.
                              # Row'un sektörünü alıp sonuna " Avg" ekleyip kontrol ediyoruz.
                              sec_name = str(row.get('Company Sector', '')).strip()
                              # Arama yaparken "Technology Avg" diye arıyoruz, o yüzden karşılaştırma stringi bu olmalı:
                              lbl_to_check = f"{sec_name} Avg".casefold()
                               
                              if not lbl_to_check.startswith(term):
                                    hidden.add(get_point_key(row, settings_state))
                        else:
                              # Normal Müşteri Modu: Müşteri adına bak
                              c_name = str(row.get('Customer', '')).strip().casefold()
                              if not c_name.startswith(term):
                                    hidden.add(get_point_key(row, settings_state))
      # =============================================================================

      visible_df_base = df[~df.apply(
            lambda r: get_point_key(r, settings_state) in hidden, axis=1
      )].copy()
      stats_df = visible_df_base.copy()
       
      # ============== NEW/CHURN: Include / Show Only mantığı ==============
      visible_df_base = _apply_churn_filters(visible_df_base)
      stats_df   = _apply_churn_filters(stats_df)
      # =====================================================================

      # ============== NEW/AGE: yaş filtresi & yaşa göre kolon seçimi ==============
      visible_df_base = _apply_age_filters(visible_df_base)
      stats_df     = _apply_age_filters(stats_df)

      age_growth_col = get_growth_source_col_for_age_mode()
      if age_growth_col in visible_df_base.columns:
            visible_df_base['MRR Growth (%)'] = visible_df_base[age_growth_col].astype(float) * 100.0
            if age_growth_col in stats_df.columns:
                  stats_df['MRR Growth (%)'] = stats_df[age_growth_col].astype(float) * 100.0

      age_base_mrr_col = get_base_mrr_col_for_age_mode()
      if age_base_mrr_col in visible_df_base.columns:
            visible_df_base[EFFECTIVE_MRR_COL] = visible_df_base[age_base_mrr_col].astype(float)
            if age_base_mrr_col in stats_df.columns:
                  stats_df[EFFECTIVE_MRR_COL] = stats_df[age_base_mrr_col].astype(float)

      # churn ise MRR'i Churned MRR ile değiştir
      if (CHURN_COL in visible_df_base.columns) and (CHURNED_MRR_COL in visible_df_base.columns):
            churn_mask_loc = visible_df_base[CHURN_COL].astype(str).str.upper().eq("CHURN")
            visible_df_base.loc[churn_mask_loc, EFFECTIVE_MRR_COL] = visible_df_base.loc[churn_mask_loc, CHURNED_MRR_COL].astype(float)

      # Exc. License MRR’i yaş moduna göre doldur (Exc. görünümünde kullanılacak)
      exc_src = get_exc_mrr_col_for_age_mode()
      if exc_src in visible_df_base.columns:
            visible_df_base['Exc. License MRR'] = visible_df_base[exc_src].astype(float)
      # =====================================================================

      # ===================== YENİ: REGRESYON HESAPLAMA (Çizimden Önce) =====================
      # Regresyon çizgisi, SADECE "Sector Avg" DIŞINDAKİ görünümlerde ve ayar açıksa hesaplanır.
      # Ve _apply_regression_filter'dan ÖNCE hesaplanır.
    
      current_regression_line['m'] = None
      current_regression_line['b'] = None

      # Başlangıçta sıfırla (eğer sabit değilse)
      if not settings_state.get("fix_regression_line", False):
            current_regression_line['m'] = None
            current_regression_line['b'] = None

      # A) EĞER SABİTLEME AÇIKSA VE ELİMİZDE PARAMETRE VARSA:
      if settings_state.get("fix_regression_line", False) and settings_state.get("fixed_regression_params"):
            # Hesaplanmış veriyi direkt kullan, yeni hesap yapma
            saved_params = settings_state["fixed_regression_params"]
            current_regression_line['m'] = saved_params.get('m')
            current_regression_line['b'] = saved_params.get('b')
       
      # B) YOKSA VE REGRESYON AÇIKSA: NORMAL HESAPLAMA YAP
      elif settings_state.get("show_regression_line", False) and selected_sector != "Sector Avg":
            
            # Geçici bir kopya al
            temp_df_for_line = visible_df_base.copy()
            if selected_sector != "All":
                temp_df_for_line = temp_df_for_line[temp_df_for_line['Company Sector'] == selected_sector]
            
            # Risk filtresi varsa uygula
            if is_risk_view_active(selected_sector) and (RISK_COL in temp_df_for_line.columns):
                 temp_df_for_line = temp_df_for_line[temp_df_for_line[RISK_COL].astype(str).str.upper().apply(lambda val: is_risk_allowed(val, settings_state))]
    
            # --- YENİ: Hesabı 'analysis.py' içindeki fonksiyona yaptır ---
            res = calculate_regression_line(
                temp_df_for_line, 
                x_col, 
                swap_axes=settings_state.get("swap_axes", False)
            )
            current_regression_line['m'] = res['m']
            current_regression_line['b'] = res['b']
            # ------------------------------------------------------------

      # ===================== /REGRESYON HESAPLAMA =====================

      # ===================== YENİ: REGRESYON FİLTRESİ UYGULAMA =====================
      # Çizgi hesaplandıktan sonra, EĞER 'above' veya 'below' seçiliyse,
      # visible_df'i filtrele.
      visible_df = _apply_regression_filter(visible_df_base, x_col)
      # ===================== /REGRESYON FİLTRESİ =====================

      total_customers = 0
      sector_stats_for_counts = {}

      if settings_state.get("fixed_axis", False) and settings_state.get("fixed_center") is not None:
            eff_center_x, eff_center_y = settings_state["fixed_center"]
      else:
            # ÖNEMLİ: Merkez (center) çizgileri, regresyon filtresinden etkilenmeyen
            # visible_df_base'e göre hesaplanmalı.
            if len(visible_df_base) > 0:
                  try:
                        center_x = visible_df_base[x_col].astype(float).mean()
                  except Exception:
                        center_x = visible_df_base[EFFECTIVE_MRR_COL].astype(float).mean()
                  center_y = visible_df_base['MRR Growth (%)'].astype(float).mean()
            else:
                  try:
                        center_x = df[x_col].astype(float).mean()
                  except Exception:
                        center_x = df[EFFECTIVE_MRR_COL].astype(float).mean()
                  center_y = df['MRR Growth (%)'].astype(float).mean()
            eff_center_x, eff_center_y = center_x, center_y

      plot_cx, plot_cy = to_plot_coords(eff_center_x, eff_center_y)
      # Arrow’larda kullanılacak baz MRR kolonu (yaş moduna göre)
      base_col_for_arrow = get_base_mrr_col_for_age_mode()
      if base_col_for_arrow not in df.columns:
            base_col_for_arrow = BASE_MRR_FALLBACK_COL

      show_arrows_flag = (
            license_var.get() == "Exc."
            and settings_state.get("use_updated_exc_license_values", False)
            and settings_state.get("show_difference_arrows", False)
            and ('Exc. License MRR' in visible_df.columns)
            and selected_sector != "Sector Avg"
      )
      extra_points_for_fit = []

      if not (fit_to_data and not show_arrows_flag):
            if not (preserve_zoom and cur_xlim is not None and cur_ylim is not None):
                  cur_xlim = (plot_cx - zoom_x_range, plot_cx + zoom_x_range)
                  cur_ylim = (plot_cy - zoom_y_range, plot_cy + zoom_y_range)

      def _risk_allowed(risk_val: str) -> bool:
            risk_val = (str(risk_val or "")).strip().upper()
            if risk_val == "NO RISK":        return settings_state.get("risk_show_no", True)
            if risk_val == "LOW RISK":      return settings_state.get("risk_show_low", True)
            if risk_val == "MEDIUM RISK": return settings_state.get("risk_show_med", True)
            if risk_val == "HIGH RISK":     return settings_state.get("risk_show_high", True)
            if risk_val == "BOOKED CHURN":   return settings_state.get("risk_show_booked", True)
            return True

      risk_active = is_risk_view_active(selected_sector)
      show_avg_labels = settings_state.get("show_avg_labels", True) and (selected_sector == "Sector Avg")

      if selected_sector == "Sector Avg":
            avg_points = []
             
            # 1. HIZLI YÖNTEM: Tek tek filtrelemek yerine GroupBy kullanıyoruz
            # visible_df_base zaten filtrelenmiş temiz veridir
            grouped = visible_df_base.groupby('Company Sector')
             
            for sector, sd in grouped:
                  # İstatistikler
                  count = len(sd)
                  total_customers += count

                  # Sektör Toplam MRR
                  try:
                        sec_mrr = sd[EFFECTIVE_MRR_COL].astype(float).sum()
                  except:
                        sec_mrr = 0.0
                   
                  sector_stats_for_counts[sector] = (count, sec_mrr)

                  # Sektör Ortalama Noktası
                  try:
                        avg_x = sd[x_col].astype(float).mean()
                  except:
                        avg_x = sd[EFFECTIVE_MRR_COL].astype(float).mean()
                   
                  avg_y = sd['MRR Growth (%)'].astype(float).mean()
                   
                  px, py = to_plot_coords(avg_x, avg_y)

                  # Noktayı Çiz
                  sc = ax.scatter(px, py, color=color_map.get(sector, 'gray'), s=250, marker='o',
                                          edgecolors='black', label=f"{sector} Avg", zorder=3, clip_on=True)
                  scatter_points.append((sc, sd))
                  avg_points.append((sector, px, py, color_map.get(sector, 'gray'), count))
                   
                  # --- TOOLTIP İÇİN HESAPLAMA (CACHE DOLDURMA) ---
                  # Churn oranını şimdi hesaplayıp saklıyoruz.
                  # Böylece mouse gezdirirken tekrar hesap yapmayacağız.
                  churn_pct = None
                  churn_cnt = 0
                  if settings_state.get("churn_enabled", True) and (CHURN_COL in sd.columns):
                        try:
                              churn_mask = sd[CHURN_COL].astype(str).str.upper().eq("CHURN")
                              churn_cnt = int(churn_mask.sum())
                              # Oran hesabı (Adet bazlı mı MRR bazlı mı? Genelde MRR istenir ama tooltipte basitçe adet oranı da olabilir)
                              # Basitlik için Adet Oranı:
                              if count > 0:
                                    churn_pct = (churn_cnt / count) * 100.0
                              else:
                                    churn_pct = 0.0
                        except:
                              pass
                   
                  sector_churn_stats_cache[sector] = {
                        "churn_pct": churn_pct,
                        "churn_count": churn_cnt,
                        "total_count": count
                  }

            # --- Sector isim label'ı (Çakışma önleyici algoritma) ---
            # (Bu kısım aynen kalabilir veya istenirse iptal edilebilir, ama GroupBy ile veri azaldığı için hızlı çalışacaktır)
            if show_avg_labels and avg_points:
                  xs = [p[1] for p in avg_points]; ys = [p[2] for p in avg_points]
                  if xs and ys: # Liste boş değilse
                        xspan = max(max(xs) - min(xs), 1e-9)
                        yspan = max(max(ys) - min(ys), 1e-9)
                        dx_thr = xspan * 0.04; dy_thr = yspan * 0.04
                        placement = {p[0]: 'below' for p in avg_points}
                        n = len(avg_points)
                        # O(N^2) döngü - Sektör sayısı az olduğu için (max 20-30) sorun yaratmaz
                        for i in range(n):
                              si, xi, yi, *_ = avg_points[i]
                              for j in range(i+1, n):
                                    sj, xj, yj, *_ = avg_points[j]
                                    if abs(xi - xj) <= dx_thr and abs(yi - yj) <= dy_thr:
                                          if abs(xi - xj) >= abs(yi - yj):
                                                if xi < xj:
                                                      placement[si] = 'left'; placement[sj] = 'right'
                                                else:
                                                      placement[si] = 'right'; placement[sj] = 'left'
                                          else:
                                                placement[si] = 'right'; placement[sj] = 'right'
                         
                        for sector_name, px, py, _col, _cnt in avg_points:
                              place = placement.get(sector_name, 'below')
                              xytext_map = {'left': (-10, 0), 'right': (10, 0), 'below': (0, -10)}
                              ha_map = {'left': 'right', 'right': 'left', 'below': 'center'}
                              va_map = {'left': 'center', 'right': 'center', 'below': 'top'}
                               
                              ax.annotate(sector_name, xy=(px, py), xytext=xytext_map[place],  
                                                textcoords="offset points",
                                                ha=ha_map[place], va=va_map[place], fontsize=9, zorder=6)

            # --- Sector Avg üstünde sayı gösterimi ---
            if settings_state.get("show_sector_counts_above_avg", False) and avg_points:
                  for _, px, py, _, cnt in avg_points:
                        ax.annotate(f"# {cnt}", xy=(px, py), xytext=(0, 10), textcoords="offset points",
                                          ha="center", va="bottom", fontsize=9, fontweight="bold", color="black", zorder=7)

      else:
            for sector in sectors:
                  if selected_sector == "All" or sector == selected_sector:
                        # ÖNEMLİ: Çizilecek noktalar (sd_base) *filtreli* visible_df'ten gelir
                        sd_base = visible_df[visible_df['Company Sector'] == sector]
                        if len(sd_base) == 0:
                              continue

                        # Sector Avg/All altındaki oranlar için, *filtresiz* visible_df_base üzerinden MRR & count
                        sd_for_stat = visible_df_base[visible_df_base['Company Sector'] == sector]
                        if len(sd_for_stat) > 0:
                              try:
                                    sec_mrr_stat = sd_for_stat[EFFECTIVE_MRR_COL].astype(float).sum()
                              except Exception:
                                    sec_mrr_stat = 0.0
                              sector_stats_for_counts[sector] = (len(sd_for_stat), sec_mrr_stat)

                        # Risk filtresi (varsa)
                        if risk_active and (RISK_COL in sd_base.columns):
                              sd = sd_base[sd_base[RISK_COL].astype(str).str.upper().apply(_risk_allowed)]
                        else:
                              sd = sd_base

                        if len(sd) == 0:
                              continue

                        # Toplam müşteri sayısı, regresyon filtresinden etkilenen sd'ye göre değil,
                        # *filtresiz* visible_df_base'e göre hesaplanmalı (eğer risk filtresi uygulanmadıysa)
                        if not risk_active:
                              sd_for_count = visible_df_base[visible_df_base['Company Sector'] == sector]
                              total_customers += len(sd_for_count)
                        else:
                              # Risk aktifse, risk filtresi uygulanmış (sd) kullanılır
                              total_customers += len(sd)

                        # ============== NEW/CHURN: churn satırlarını ayır ==============
                        churn_enabled_flag = settings_state.get("churn_enabled", True)
                        show_only = settings_state.get("show_only_churn", False)

                        if CHURN_COL in sd.columns:
                              col = sd[CHURN_COL].astype(str).str.upper()
                              if show_only:
                                    churn_mask = col.eq("CHURN")
                              else:
                                    churn_mask = churn_enabled_flag & col.eq("CHURN")
                        else:
                              churn_mask = sd.index == -1   # hiçbir satır churn değil say

                        sd_churn = sd[churn_mask]
                        sd_norm   = sd[~churn_mask]
                        # =================================================================

                        px_list, py_list, colors_list = [], [], []

                        # Normal (churn olmayan) noktalar
                        if len(sd_norm) > 0:
                              # 1. Önce Analytics Verilerini Hesapla (Eğer Mod Açıksa)
                              ana_labels = None
                              ana_mask = None
                               
                              if analytics_state["mode"] == "kmeans":
                                    ana_labels = calculate_kmeans_labels(visible_df_base, x_col, k=analytics_state["kmeans_k"])
                              elif analytics_state["mode"] == "pareto":
                                    ana_mask = calculate_pareto_mask(visible_df_base, x_col)

                              px_list, py_list, colors_list = [], [], []
                               
                              # K-Means renk paleti (Canlı renkler)
                              kmeans_colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']

                              for idx, row in sd_norm.iterrows():
                                    try:
                                          xv = float(row[x_col])
                                    except Exception:
                                          xv = float(row.get(EFFECTIVE_MRR_COL, row.get(BASE_MRR_FALLBACK_COL)))
                                    yv = float(row['MRR Growth (%)'])
                                    px, py = to_plot_coords(float(xv), float(yv))
                                    px_list.append(px); py_list.append(py)
                                     
                                    # --- RENK BELİRLEME MANTIĞI ---
                                    final_color = color_map[sector] # Varsayılan: Sektör rengi

                                    # A) Risk Modu Açıksa
                                    if risk_active and (RISK_COL in row) and analytics_state["mode"] == "none":
                                            rname = str(row[RISK_COL]).strip().upper()
                                            final_color = RISK_COLOR.get(rname, final_color)
                                     
                                    # B) K-Means Modu Açıksa (Risk'i ezer)
                                    elif analytics_state["mode"] == "kmeans" and ana_labels is not None:
                                          # visible_df_base ile senkronize index bulmamız lazım
                                          # Basit çözüm: visible_df_base içindeki sırasını bul (biraz yavaş ama güvenli)
                                          try:
                                                loc_idx = visible_df_base.index.get_loc(idx)
                                                label_val = ana_labels[loc_idx]
                                                final_color = kmeans_colors[label_val % len(kmeans_colors)]
                                          except:
                                                pass # Hata olursa sektör rengi kalsın
                                     
                                    # C) Pareto Modu Açıksa (Hepsini ezer)
                                    elif analytics_state["mode"] == "pareto" and ana_mask is not None:
                                          try:
                                                is_top_20 = ana_mask.loc[idx]
                                                if is_top_20:
                                                      final_color = "#00FF00" # Parlak Yeşil (Nakit İnekleri)
                                                else:
                                                      final_color = "#444444" # Sönük Gri
                                          except:
                                                pass

                                    colors_list.append(final_color)
                               
                              # ÇİZİM (Scatter) - Artık 'c=colors_list' kullanıyoruz
                              sc = ax.scatter(px_list, py_list, c=colors_list, s=80, alpha=0.90,
                                                      edgecolors='black', linewidths=0.8,  
                                                      label=sector, zorder=5, clip_on=True)
                              scatter_points.append((sc, sd_norm))

                       # ============== NEW/CHURN: churn olanlar X marker ile ==============
                        if len(sd_churn) > 0:
                              cx_list, cy_list = [], []
                              for _, row in sd_churn.iterrows():
                                    try:
                                          xv = float(row[x_col])
                                    except Exception:
                                            xv = float(row.get(EFFECTIVE_MRR_COL, row.get(BASE_MRR_FALLBACK_COL)))
                                    yv = float(row['MRR Growth (%)'])
                                    px, py = to_plot_coords(float(xv), float(yv))
                                    cx_list.append(px); cy_list.append(py)
                              scx = ax.scatter(cx_list, cy_list, s=90, marker='x',
                                       linewidths=2.0, color=CHURN_X_COLOR,
                                       label=sector, zorder=6, clip_on=True)
                              scatter_points.append((scx, sd_churn))
                        # =================================================================

                        if show_arrows_flag:
                              old_px, old_py, new_px = [], [], []
                              for _, r in sd.iterrows():
                                    try:
                                          x0 = float(r[base_col_for_arrow])
                                          x1 = float(r['Exc. License MRR'])
                                          y = float(r['MRR Growth (%)'])
                                    except Exception:
                                          continue
                                    p0x, p0y = to_plot_coords(x0, y)
                                    p1x, p1y = to_plot_coords(x1, y)
                                    old_px.append(p0x); old_py.append(p0y); new_px.append(p1x)
                                    extra_points_for_fit.append((p0x, p0y))
                                    extra_points_for_fit.append((p1x, p1y))

                                    if get_updated_y_col_if_any() is not None:
                                          try:
                                                y_new = float(r[get_updated_y_col_if_any()])
                                                x_for_y = float(r[get_plot_x_col()])
                                                q0x, q0y = to_plot_coords(x_for_y, y)
                                                q1x, q1y = to_plot_coords(x_for_y, y_new)
                                                extra_points_for_fit.append((q0x, q0y))
                                                extra_points_for_fit.append((q1x, q1y))
                                          except Exception:
                                                pass

                              if old_px:
                                    ax.scatter(old_px, old_py, color=color_map[sector], s=60, alpha=0.35,
                                                     edgecolors='none', zorder=3, label="_nolegend_", clip_on=True)
                                    for p0x, p0y, p1x in zip(old_px, old_py, new_px):
                                          if p0x != p1x:
                                                ann = ax.annotate(
                                                      "", xy=(p1x, p0y), xytext=(p0x, p0y),
                                                      arrowprops=dict(arrowstyle="->", lw=0.9, alpha=0.5, clip_on=True)
                                                )
                                                try:
                                                      ann.set_clip_on(True)
                                                      if hasattr(ann, "arrow_patch") and ann.arrow_patch is not None:
                                                            ann.arrow_patch.set_clip_on(True)
                                                except Exception:
                                                      pass

                              if get_updated_y_col_if_any() is not None:
                                    for _, r in sd.iterrows():
                                          try:
                                                y_old = float(r['MRR Growth (%)'])
                                                y_new = float(r[get_updated_y_col_if_any()])
                                                if y_old != y_new:
                                                      x_for_y_arrow = float(r[x_col])
                                                      q0x, q0y = to_plot_coords(x_for_y_arrow, y_old)
                                                      q1x, q1y = to_plot_coords(x_for_y_arrow, y_new)
                                                      ann2 = ax.annotate(
                                                            "", xy=(q1x, q1y), xytext=(q0x, q0y),
                                                            arrowprops=dict(arrowstyle="->", lw=0.8, alpha=0.45, clip_on=True)
                                                      )
                                                      try:
                                                            ann2.set_clip_on(True)
                                                            if hasattr(ann2, "arrow_patch") and ann2.arrow_patch is not None:
                                                                  ann2.arrow_patch.set_clip_on(True)
                                                      except Exception:
                                                            pass
                                          except Exception:
                                                pass

            if selected_sector != "All":
                  # AVG noktası, *filtresiz* visible_df_base'e göre hesaplanmalı
                  sd_for_avg = visible_df_base[visible_df_base['Company Sector'] == selected_sector]
                  if len(sd_for_avg) > 0:
                        try:
                              avg_x_now = sd_for_avg[x_col].astype(float).mean()
                        except Exception:
                              avg_x_now = sd_for_avg[EFFECTIVE_MRR_COL].astype(float).mean()

                        if show_arrows_flag and (get_updated_y_col_if_any() is not None):
                              avg_y_now = sd_for_avg[get_updated_y_col_if_any()].astype(float).mean()
                        else:
                              avg_y_now = sd_for_avg['MRR Growth (%)'].astype(float).mean()
                        pax, pay = to_plot_coords(avg_x_now, avg_y_now)
                        avg_color = 'navy'
                        sc = ax.scatter(pax, pay, color=avg_color, s=300, marker='o',
                                                edgecolors='black', label=f"{selected_sector} Avg", zorder=3, clip_on=True)
                        scatter_points.append((sc, sd_for_avg))

                        if show_arrows_flag:
                              if base_col_for_arrow in sd_for_avg.columns:
                                    old_avg_x = sd_for_avg[base_col_for_arrow].astype(float).mean()
                              else:
                                    old_avg_x = avg_x_now
                              old_avg_y = sd_for_avg['MRR Growth (%)'].astype(float).mean()
                              p0x, p0y = to_plot_coords(old_avg_x, old_avg_y)
                              p1x, p1y = pax, pay
                              extra_points_for_fit.append((p0x, p0y))
                              extra_points_for_fit.append((p1x, p1y))

                              ax.scatter([p0x], [p0y], color=avg_color, s=300, alpha=0.35,
                                               edgecolors='none', zorder=5, label="_nolegend_", clip_on=True)
                              if (p0x != p1x) or (p0y != p1y):
                                    ann_avg = ax.annotate(
                                          "", xy=(p1x, p1y), xytext=(p0x, p0y),
                                          arrowprops=dict(arrowstyle="->", lw=1.0, alpha=0.5, clip_on=True)
                                    )
                                    try:
                                          ann_avg.set_clip_on(True)
                                          if hasattr(ann_avg, "arrow_patch") and ann_avg.arrow_patch is not None:
                                                ann_avg.arrow_patch.set_clip_on(True)
                                    except Exception:
                                          pass

      # --- Merkez çizgileri ---
      ax.axvline(plot_cx, color='dodgerblue', linewidth=2, zorder=2)
      ax.axhline(plot_cy, color='darkorange', linewidth=2, zorder=2)

      if settings_state.get("draw_growth_zero", True):
            if settings_state.get("swap_axes", False):
                  ax.axvline(0, color='red', linestyle=':', linewidth=1.5, zorder=1)
            else:
                  ax.axhline(0, color='red', linestyle=':', linewidth=1.5, zorder=1)

      # ===================== YENİ: REGRESYON ÇİZGİSİ ÇİZİMİ =====================
      if settings_state.get("show_regression_line", False) and current_regression_line['m'] is not None:
            try:
                  m = current_regression_line['m']
                  b = current_regression_line['b']

                  # Mevcut eksen limitlerini al
                  x0, x1 = ax.get_xlim()
                  span = x1 - x0 if x1 != x0 else 1.0

                  # Görünür aralığın çok daha ötesine uzat (sonsuzmuş gibi)
                  x_far0 = x0 - span * 1000
                  x_far1 = x1 + span * 1000

                  xs = np.array([x_far0, x_far1])
                  ys = m * xs + b

                  ax.plot(
                        xs,
                        ys,
                        color='purple',
                        linestyle='--',
                        linewidth=2.0,
                        zorder=3,
                        label='Regression Line'
                  )
            except Exception as e:
                  print(f"Regresyon çizimi hatası: {e}")
      # ===================== /REGRESYON ÇİZGİSİ =====================

      if settings_state.get("swap_axes", False):
            ax.set_xlabel("Growth (%)", fontsize=12)
            ax.set_ylabel("MRR Value", fontsize=12)
      else:
            ax.set_xlabel("MRR Value", fontsize=12)
            ax.set_ylabel("Growth (%)", fontsize=12)

      ax.grid(True, linestyle='--', alpha=0.6)

      # Legend
      if is_risk_view_active(sector_combobox.get()):
            # Risk görünümü için visible_df_base (filtresiz) kullanılmalı
            sd_vis = visible_df_base[visible_df_base['Company Sector'] == sector_combobox.get()]
            if RISK_COL in sd_vis.columns:
                  sd_vis = sd_vis[sd_vis[RISK_COL].astype(str).str.upper().apply(lambda v: v in RISK_VALUES or True)]
                  legend_items = []
                  for risk_name in ["HIGH RISK", "MEDIUM RISK", "LOW RISK", "NO RISK", "BOOKED CHURN"]:
                        count = 0
                        if RISK_COL in sd_vis.columns:
                              col = sd_vis[RISK_COL].astype(str).str.upper()
                              count = int((col == risk_name).sum())
                        legend_items.append(Patch(color=RISK_COLOR[risk_name], label=f"{risk_name} ({count})"))
                  legend_items.append(Patch(color="navy", label=f"{sector_combobox.get()} Avg"))
                  legend1 = ax.legend(
                        handles=legend_items, title="Risk / Avg",
                        bbox_to_anchor=(1.005, 1), loc='upper left',
                        fontsize=10, handlelength=1.4, labelspacing=1.2, borderpad=0.7, handletextpad=0.8
                  )
                  ax.add_artist(legend1); active_legends.append(legend1)
      else:
            handles, labels = ax.get_legend_handles_labels()
            uniq = {}
            for h, l in zip(handles, labels):
                  if l not in uniq:
                        uniq[l] = h
            handles = list(uniq.values()); labels = [lbl.replace(" Avg", "") for lbl in uniq.keys()]
            if len(handles) > 0:
                  if sector_combobox.get() == "Sector Avg":
                        legend1 = ax.legend(
                              handles=handles, labels=labels, title="Sectors (Avg Points)",
                              bbox_to_anchor=(1.005, 1), loc='upper left',
                              fontsize=10, handlelength=1.2, labelspacing=1.5, borderpad=0.7, handletextpad=0.8
                        )
                  else:
                        legend1 = ax.legend(
                              handles=handles, labels=labels, title="Company Sector",
                              bbox_to_anchor=(1.005, 1), loc='upper left',
                              fontsize=10, handlelength=1.2, labelspacing=1.5, borderpad=0.7, handletextpad=0.8
                        )
                  ax.add_artist(legend1); active_legends.append(legend1)
      # Axis legend
      if settings_state.get("swap_axes", False):
            axes_legend = ax.legend(
                  handles=[
                        Patch(color='dodgerblue', label=f'Growth (X={plot_cx:.2f})'),
                        Patch(color='darkorange', label=f'MRR Value (Y={plot_cy:.2f})')
                  ],
                  bbox_to_anchor=(1.005, 0.3), loc='upper left',
                  title="Axes", fontsize=10, labelspacing=1.5, borderpad=0.7, handletextpad=0.8
            )
      else:
            axes_legend = ax.legend(
                  handles=[
                        Patch(color='dodgerblue',   label=f'MRR Value (X={plot_cx:.2f})'),
                        Patch(color='darkorange', label=f'Growth (Y={plot_cy:.2f})')
                  ],
                  bbox_to_anchor=(1.005, 0.3), loc='upper left',
                  title="Axes", fontsize=10, labelspacing=1.5, borderpad=0.7, handletextpad=0.8
            )
      ax.add_artist(axes_legend); active_legends.append(axes_legend)

      # ====== LİMİTLERİ AYARLA ======
      if fit_to_data:
            # Fit_to_data yaparken *filtreli* visible_df kullanılır
            if show_arrows_flag and extra_points_for_fit:
                  limits = compute_fit_limits(
                        sector_combobox.get(), x_col, visible_df, pad_ratio=PAD_RATIO,
                        eff_center=(eff_center_x, eff_center_y), extra_points=extra_points_for_fit
                  )
            else:
                  limits = compute_fit_limits(
                        sector_combobox.get(), x_col, visible_df, pad_ratio=PAD_RATIO,
                        eff_center=(eff_center_x, eff_center_y), extra_points=None
                  )
            if limits is not None:
                  xmin, xmax, ymin, ymax = limits
                  ax.set_xlim(xmin, xmax)
                  ax.set_ylim(ymin, ymax)
            else:
                  ax.set_xlim(plot_cx - zoom_x_range, plot_cx + zoom_x_range)
                  ax.set_ylim(plot_cy - zoom_y_range, plot_cy + zoom_y_range)
      else:
            if preserve_zoom and cur_xlim is not None and cur_ylim is not None:
                  try:
                        ax.set_xlim(cur_xlim); ax.set_ylim(cur_ylim)
                  except Exception:
                        ax.set_xlim(plot_cx - zoom_x_range, plot_cx + zoom_x_range)
                        ax.set_ylim(plot_cy - zoom_y_range, plot_cy + zoom_y_range)
            else:
                  ax.set_xlim(plot_cx - zoom_x_range, plot_cx + zoom_x_range)
                  ax.set_ylim(plot_cy - zoom_y_range, plot_cy + zoom_y_range)

      # ========================= Quadrant Risk Color Map Overlay (distance-weighted) =========================
      try:
            if settings_state.get("activate_risk_colormap", False) \
                 and sector_combobox.get() not in ("Sector Avg", "All") \
                 and (RISK_COL in df.columns):
                  # Overlay, *filtreli* visible_df'e göre hesaplanmalı
                  sec_df = visible_df[visible_df['Company Sector'] == sector_combobox.get()].copy()
                  if len(sec_df) > 0:
                        cx, cy = plot_cx, plot_cy
                        x0, x1 = ax.get_xlim()
                        y0, y1 = ax.get_ylim()
                        sums = {"Q1": [0.0,0.0,0.0], "Q2":[0.0,0.0,0.0], "Q3":[0.0,0.0,0.0], "Q4":[0.0,0.0,0.0]}
                        weights = {"Q1":0.0, "Q2":0.0, "Q3":0.0, "Q4":0.0}
                        use_weight = settings_state.get("risk_cmap_weighted", True)
                        alpha_pow = float(settings_state.get("risk_cmap_weight_power", 1.0))

                        def norm_dist_x(px, side):
                              if side == 'R':
                                    span = max(x1 - cx, 1e-9)
                                    return max(0.0, min(1.0, (px - cx) / span))
                              else:
                                    span = max(cx - x0, 1e-9)
                                    return max(0.0, min(1.0, (cx - px) / span))

                        def norm_dist_y(py, side):
                              if side == 'U':
                                    span = max(y1 - cy, 1e-9)
                                    return max(0.0, min(1.0, (py - cy) / span))
                              else:
                                    span = max(cy - y0, 1e-9)
                                    return max(0.0, min(1.0, (cy - py) / span))

                        for _, r in sec_df.iterrows():
                              try:
                                    xv = float(r[get_plot_x_col()])
                              except Exception:
                                    xv = float(r.get(EFFECTIVE_MRR_COL, r.get(BASE_MRR_FALLBACK_COL)))
                              yv = float(r['MRR Growth (%)'])
                              px, py = to_plot_coords(xv, yv)
                              risk_name = str(r.get(RISK_COL, "")).strip().upper()
                              rgb = to_rgb(RISK_COLOR.get(risk_name, (0.8,0.8,0.8)))

                              if px >= cx and py >= cy:     # (+,+)
                                    key = "Q1"; rx = norm_dist_x(px, 'R'); ry = norm_dist_y(py, 'U')
                              elif px < cx and py >= cy:   # (-,+)
                                    key = "Q2"; rx = norm_dist_x(px, 'L'); ry = norm_dist_y(py, 'U')
                              elif px < cx and py < cy:     # (-,-)
                                    key = "Q3"; rx = norm_dist_x(px, 'L'); ry = norm_dist_y(py, 'D')
                              else:                                    # (+,-)
                                    key = "Q4"; rx = norm_dist_x(px, 'R'); ry = norm_dist_y(py, 'D')

                              base_w = rx * ry
                              w = (base_w ** alpha_pow) if use_weight else 1.0
                              sums[key][0] += rgb[0] * w
                              sums[key][1] += rgb[1] * w
                              sums[key][2] += rgb[2] * w
                              weights[key] += w

                        def _avg_color(key):
                              w = weights[key]
                              if w <= 0:
                                    return None
                              return (sums[key][0]/w, sums[key][1]/w, sums[key][2]/w)

                        alpha_bg = 0.18
                        c1 = _avg_color("Q1")
                        if c1 is not None:
                              ax.add_patch(Rectangle((cx, cy), x1-cx, y1-cy, facecolor=c1, alpha=alpha_bg, edgecolor='none', zorder=0.5))
                        c2 = _avg_color("Q2")
                        if c2 is not None:
                              ax.add_patch(Rectangle((x0, cy), cx-x0, y1-cy, facecolor=c2, alpha=alpha_bg, edgecolor='none', zorder=0.5))
                        c3 = _avg_color("Q3")
                        if c3 is not None:
                              ax.add_patch(Rectangle((x0, y0), cx-x0, cy-y0, facecolor=c3, alpha=alpha_bg, edgecolor='none', zorder=0.5))
                        c4 = _avg_color("Q4")
                        if c4 is not None:
                              ax.add_patch(Rectangle((cx, y0), x1-cx, cy-y0, facecolor=c4, alpha=alpha_bg, edgecolor='none', zorder=0.5))
      except Exception:
            pass
      # ======================= /overlay =======================

      # Total customers etiketi, *filtresiz* visible_df_base'e göre hesaplanmalı
       
      sector_churn_stats_cache.clear()
       
      if selected_sector == "Sector Avg":
            df_for_total = visible_df_base
      elif selected_sector == "All":
            df_for_total = visible_df_base
      else:
            temp_df_for_total = visible_df_base[visible_df_base['Company Sector'] == selected_sector]
            if risk_active and (RISK_COL in temp_df_for_total.columns):
                  df_for_total = temp_df_for_total[
                        temp_df_for_total[RISK_COL].astype(str).str.upper().apply(_risk_allowed)
                  ]
            else:
                  df_for_total = temp_df_for_total

      total_customers_label_count = len(df_for_total)

      # MRR toplamı (EFFECTIVE_MRR_COL üzerinden)
      if EFFECTIVE_MRR_COL in df_for_total.columns:
            total_mrr_val = df_for_total[EFFECTIVE_MRR_COL].astype(float).sum()
      else:
            total_mrr_val = 0.0

      total_label.config(text=f"Total Customers: {total_customers_label_count}")
      total_mrr_label.config(text=f"Total Customer MRR Value: ${total_mrr_val:,.0f}")

      # Total Customers altında: sektör bazlı adet + MRR payı
      sector_entries = []
      if selected_sector in ("Sector Avg", "All") and total_mrr_val > 0:
            for sec in sectors:
                  if sec not in sector_stats_for_counts:
                        continue
                  cnt, sec_mrr = sector_stats_for_counts[sec]
                  if cnt <= 0 or sec_mrr <= 0:
                        continue
                  share = (sec_mrr / total_mrr_val) * 100.0
                  sector_entries.append((share, sec, cnt))

      # pay’a göre büyükten küçüğe sırala
      sector_entries.sort(key=lambda t: t[0], reverse=True)
      sector_lines = [
            f"{sec}: {cnt} ({share:.1f}%)"
            for (share, sec, cnt) in sector_entries
      ]

      sector_count_label.config(text="\n".join(sector_lines))

      # --- Churn metni ---
      # Churn metinleri de *filtresiz* stats_df (veya visible_df_base) üzerinden hesaplanmalı
      def _calc_churn_mrr_ratio(df_sub):
            import pandas as _pd

            if df_sub is None or len(df_sub) == 0:
                  return 0.0, 0.0, 0.0, 0   # churn_mrr, total_mrr, ratio_pct, churn_count

            if CHURN_COL in df_sub.columns:
                  churn_col = df_sub[CHURN_COL].astype(str).str.upper()
                  churn_mask = churn_col.eq("CHURN")
            else:
                  churn_mask = _pd.Series(False, index=df_sub.index)

            active_mask = ~churn_mask

            # Aktif (churn olmayan) MRR
            active_mrr = 0.0
            if EFFECTIVE_MRR_COL in df_sub.columns:
                  active_mrr = df_sub.loc[active_mask, EFFECTIVE_MRR_COL].astype(float).sum()

            # Churn olmuş MRR
            churned_mrr = 0.0
            if CHURNED_MRR_COL in df_sub.columns:
                  churned_mrr = df_sub.loc[churn_mask, CHURNED_MRR_COL].astype(float).sum()
            elif EFFECTIVE_MRR_COL in df_sub.columns:
                  churned_mrr = df_sub.loc[churn_mask, EFFECTIVE_MRR_COL].astype(float).sum()

            total_mrr = active_mrr + churned_mrr
            ratio_pct = (churned_mrr / total_mrr * 100.0) if total_mrr > 0 else 0.0

            churn_count = int(churn_mask.sum())

            return float(churned_mrr), float(total_mrr), float(ratio_pct), churn_count
      if CHURN_COL in stats_df.columns:
          sel = sector_combobox.get()
          sdf = stats_df.copy()

          # Verileri tutacak değişkenler
          total_churn_mrr_all = 0.0
          total_mrr_all = 0.0
          total_churn_customers_all = 0
          global_ratio_pct = 0.0
          sector_entries = [] # Liste için satırlar

          # A) Hesaplama Mantığı
          if sel in ("Sector Avg", "All"):
                # Çoklu sektör görünümü: Tek tek sektörleri gez ve listeyi hazırla
                for sec in sectors:
                      sec_df = sdf[sdf['Company Sector'] == sec]
                      
                      # Helper fonksiyon ile hesapla
                      c_mrr, t_mrr, r_pct, c_cnt = _calc_churn_mrr_ratio(sec_df)
                    
                      # Global toplamlara ekle (Sadece Sector Avg modunda manuel topluyoruz, 
                      # All modunda zaten sdf full data ama listeyi oluşturmak için bu döngü şart)
                      if sel == "Sector Avg":
                            total_churn_mrr_all += c_mrr
                            total_mrr_all += t_mrr
                            total_churn_customers_all += c_cnt
                    
                      # Listeye ekleme şartı: Ya churn var ya da aktif MRR var
                      if t_mrr > 0 or c_cnt > 0:
                            sector_entries.append((r_pct, sec, c_cnt))
                
                # Eğer "All" modundaysak, global toplamları direkt ana veriden (sdf) alalım (Daha hassas olur)
                if sel == "All":
                      total_churn_mrr_all, total_mrr_all, global_ratio_pct, total_churn_customers_all = _calc_churn_mrr_ratio(sdf)
                else:
                      # Sector Avg için global oranı hesapla
                      if total_mrr_all > 0:
                            global_ratio_pct = (total_churn_mrr_all / total_mrr_all) * 100.0
          
          else: 
                # B) Tek Sektör Seçimi
                sec_df = sdf[sdf['Company Sector'] == sel]
                total_churn_mrr_all, total_mrr_all, global_ratio_pct, total_churn_customers_all = _calc_churn_mrr_ratio(sec_df)
                # Tek sektörde detay listesine gerek yok (veya tek satır ekleyebiliriz)
                sector_entries = [] 

          # C) Label Güncellemeleri (Herkes için ortak)
          churn_customer_label.config(
              text=f"Total Customer Churn: {total_churn_customers_all}", 
              font=("Arial", 12, "bold")
          )
          
          if total_mrr_all > 0 or total_churn_customers_all > 0:
                churn_total_label.config(
                    text=f"Total Churn MRR Value: ${total_churn_mrr_all:,.0f}",
                    font=("Arial", 10, "bold")
                )
          else:
                churn_total_label.config(text="Total Churn MRR: $0")

          # D) Liste Güncellemesi (Text widget'ına yazma)
          if sector_entries:
                # Orana göre sırala (Yüksek churn oranı en üstte)
                sector_entries.sort(key=lambda t: t[0], reverse=True)
                lines = [
                      f"{sec}: {c_cnt} ({ratio:.1f}%)"
                      for (ratio, sec, c_cnt) in sector_entries
                ]
                churn_sector_label.config(text="\n".join(lines))
          else:
                churn_sector_label.config(text="")

          # E) Oran Göstergesi
          if total_mrr_all > 0:
                churn_ratio_label.config(text=f"Total Churn Ratio: {global_ratio_pct:.1f}%")
                try: churn_ratio_label.pack(pady=(0, 10), after=frame_churn_stats)
                except: pass
          else:
                churn_ratio_label.pack_forget()

      else:
          # Churn kolonu yoksa temizle
          churn_customer_label.config(text="")
          churn_total_label.config(text="")
          churn_sector_label.config(text="")
          churn_ratio_label.pack_forget()

      _apply_churn_labels_visibility()
      # Sağ paneldeki sıralamayı mevcut seçime göre yeniden düzenle
      try:
           _reflow_right_panel_for_selection(sector_combobox.get())
      except Exception:
           pass
     
      if analytics_state["show_marginals"] and selected_sector != "Sector Avg":
            try:
                  divider = make_axes_locatable(ax)
                  # Üstte X Histogramı
                  ax_histx = divider.append_axes("top", 1.2, pad=0.1, sharex=ax)
                  # Sağda Y Histogramı
                  ax_histy = divider.append_axes("right", 1.2, pad=0.1, sharey=ax)
                   
                  # Eksen yazılarını temizle (Ana grafikle çakışmasın)
                  ax_histx.xaxis.set_tick_params(labelbottom=False)
                  ax_histy.yaxis.set_tick_params(labelleft=False)
                   
                  # Veriyi al
                  mrr_vals = visible_df_base[x_col].astype(float)
                  growth_vals = visible_df_base['MRR Growth (%)'].astype(float)
                   
                  # Histogramları çiz
                  ax_histx.hist(mrr_vals, bins=30, color='#1f77b4', alpha=0.6, edgecolor='white')
                  ax_histy.hist(growth_vals, bins=30, orientation='horizontal', color='#ff7f0e', alpha=0.6, edgecolor='white')
                   
                  # Referanslara ekle (silmek için)
                  analytics_state["marginal_artists"].extend([ax_histx, ax_histy])
            except Exception as e:
                  print(f"Marginal Plot Error: {e}")
      # -----------------------------------------------

      canvas.draw_idle()
      update_fixed_banner()

      # --- SEARCH highlight: search bar açıksa ve entry doluysa highlight uygula
      if settings_state.get("activate_search_box", False):
            if search_var.get().strip():
                  _highlight_matches(search_var.get())




# --- Mini auto-zoom butonu (grafiğin sağ üst köşesi) ---



def on_motion(event):
      """
      Mouse hareketlerini takip eder.
      - Sector Avg ise: Cache'den okur (HIZLI).
      - Müşteri ise: Detayları gösterir.
      - Tooltip'i 'set_tooltip' ile en üst katmanda çizer.
      """
       
      # 1. Seçim yapılıyorsa (kutu çizme) veya Sector Avg'da Pan yapılıyorsa gizle
      if selection_state.get("active", False) or (pan_active and sector_combobox.get() == "Sector Avg"):
            set_tooltip(None, 0, 0)
            return

      # 2. Grafik alanı dışındaysa gizle
      if event.inaxes != ax:
            set_tooltip(None, 0, 0)
            return

      found = False
       
      # Scatter noktalarını kontrol et
      for sc, sector_data in scatter_points:
            contains, ind = sc.contains(event)
            if not contains:
                  continue

            found = True
            label_now = sc.get_label() or ""
            is_avg_point = label_now.endswith(" Avg")
             
            # Koordinatları al
            offsets = sc.get_offsets()
            if len(offsets) > 1:
                    idx = ind["ind"][0]
                    px, py = offsets[idx]
            else:
                    px, py = offsets[0]
                    idx = 0 # Tek nokta varsa index 0

            # Eksen takası varsa değerleri düzelt
            if settings_state.get("swap_axes", False):
                    disp_x, disp_y = py, px
            else:
                    disp_x, disp_y = px, py

            sector_name = label_now.replace(' Avg', '')
            text = ""

            # --- SENARYO A: SECTOR AVG (CACHE KULLANIR - KASMA YAPMAZ) ---
            if is_avg_point:
                  text = f"{sector_name}\nMRR: ${disp_x:,.0f}\nGrowth: %{disp_y:.2f}"
                   
                  # update_plot içinde doldurduğumuz cache'den oku
                  if sector_name in sector_churn_stats_cache:
                        stats = sector_churn_stats_cache[sector_name]
                        # stats = {'churn_pct': ..., 'churn_count': ..., 'total_count': ...}
                         
                        if stats.get('churn_pct') is not None:
                              text += f"\nChurn: %{stats['churn_pct']:.1f}"
                               
            # --- SENARYO B: TEKİL MÜŞTERİ (DETAYLI) ---
            else:
                  row = sector_data.iloc[idx]
                  name = row.get('Customer', '')
                  text = f"{name}\nMRR: ${disp_x:,.0f}\nGrowth: %{disp_y:.2f}"
                   
                  # Lisans (Sadece Exc. modunda)
                  if license_var.get() == "Exc." and 'License Percent' in row:
                          try: text += f"\nLic: %{float(row['License Percent'])*100:.1f}"
                          except: pass
                   
                  # Risk
                  if RISK_COL in row:
                          rv = str(row[RISK_COL]).strip()
                          if rv and rv.lower() != "nan": text += f"\nRisk: {rv}"

                  # Yaş
                  if "Customer Age (Months)" in row:
                        try:
                              age = row["Customer Age (Months)"]
                              import pandas as _pd
                              if not _pd.isna(age): text += f"\nAge: {int(age)} Mo."
                        except: pass

                  # Churn
                  if CHURN_COL in row:
                          cv = str(row[CHURN_COL]).strip().upper()
                          if cv == "CHURN":
                                text += "\n[CHURNED]"
                                if CHURN_DATE_COL in row:
                                      cd = str(row[CHURN_DATE_COL]).split()[0] # Sadece tarihi al
                                      if cd != "NaT" and cd != "nan":
                                            text += f" ({cd})"
                   
                  # Eski MRR (Oklar açıksa)
                  base_col = get_base_mrr_col_for_age_mode()
                  show_arrows = (
                        license_var.get() == "Exc."
                        and settings_state.get("use_updated_exc_license_values", False)
                        and settings_state.get("show_difference_arrows", False)
                  )
                  if show_arrows and base_col in row:
                        try:
                              prev = float(row[base_col])
                              text += f"\nPrev: ${prev:,.0f}"
                        except: pass

            # --- ÇİZİM ---
            # event.guiEvent.x_root -> Ekranın sol üstüne göre mutlak X
            # event.guiEvent.y_root -> Ekranın sol üstüne göre mutlak Y
            if event.guiEvent:
                  set_tooltip(text, event.guiEvent.x_root, event.guiEvent.y_root)
             
            break # İlk noktayı bulunca döngüyü kır

      # Hiçbir nokta bulunamadıysa gizle
      if not found:
            set_tooltip(None, 0, 0)

canvas.mpl_connect("motion_notify_event", on_motion)
canvas.mpl_connect("motion_notify_event", on_motion)


def on_right_click(event):
      # Sadece sağ tık
      if getattr(event, "button", None) != 3:
            return

      if event.inaxes != ax:
            return

      # ========== YENİ: Sector Avg görünümünde AVG noktasına sağ tık → tüm sektörü kaldır ==========
      if sector_combobox.get() == "Sector Avg":
            for sc, sector_data in scatter_points:
                  label = sc.get_label() or ""
                  if not label.endswith(" Avg"):
                        continue

                  contains, ind = sc.contains(event)
                  if contains:
                        sector_name = label.replace(" Avg", "")
                        # Bu sektördeki TÜM müşterileri kaldır (global df üzerinden)
                        keys_for_sector = []
                        try:
                              sec_df = df[df['Company Sector'] == sector_name]
                              for _, row in sec_df.iterrows():
                                    key = get_point_key(row, settings_state)
                                    if key not in manual_removed:
                                          manual_removed.add(key)
                                          keys_for_sector.append(key)
                        except Exception:
                              keys_for_sector = []

                        if keys_for_sector:
                              # Undo için SECTOR kaydı tut
                              undo_stack.append(('SECTOR', keys_for_sector))
                              update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)
                        return
            # Sector Avg seçiliyken ama AVG noktasına değil, normal müşteri noktasına sağ tık ise
            # alttaki standart müşteri silme mantığına düşsün (break etmeden devam)
      # =============================================================================================

      # Eski davranış: Tekil müşteri/point kaldırma
      for sc, sector_data in scatter_points:
            contains, ind = sc.contains(event)
            if contains:
                  # Eğer bu tek bir AVG noktası ise (ve yukarıda Sector Avg özel case'i yakalamadıysa)
                  if hasattr(sc, "get_offsets") and len(sc.get_offsets()) == 1 and len(sc.get_offsets()[0]) == 2 and sc.get_label().endswith(" Avg"):
                        ox, oy = sc.get_offsets()[0]
                        if settings_state.get("swap_axes", False):
                              x_val, y_val = float(oy), float(ox)
                        else:
                              x_val, y_val = float(ox), float(oy)
                        key = (x_val, y_val)
                  else:
                        idx = ind["ind"][0]
                        row = sector_data.iloc[idx]
                        key = get_point_key(row, settings_state)

                  if key not in manual_removed:
                        manual_removed.add(key)
                        undo_stack.append(('POINT', key))
                        update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)
                  break

canvas.mpl_connect("button_press_event", on_right_click)


def on_undo(event=None):
      if not undo_stack:
            return
       
      # Stack'ten son işlemi al
      action = undo_stack.pop()
      tag = action[0]
      data = action[1]

      if tag == 'POINT':
            # Tekil nokta silme geri alımı
            key = data
            try:
                  manual_removed.remove(key)
            except KeyError:
                  pass

      elif tag == 'BATCH':
            # YENİ: Toplu silme geri alımı (Box Selection ile silinenler)
            keys_list = data
            for k in keys_list:
                  try:
                        manual_removed.remove(k)
                  except KeyError:
                        pass

      elif tag == 'LIMIT':
            # Ayar değişikliği geri alımı
            prev_snapshot = data
            for k, v in prev_snapshot.items():
                  settings_state[k] = v
            # Butonların görsel durumunu düzelt
            reg_filter_var.set(settings_state.get("regression_filter", "none"))
            try:
                  # Eğer buton fonksiyonları erişilebilir durumdaysa güncelle
                  if settings_state["regression_filter"] == "above":
                        reg_btn_up.state(["selected"]); reg_btn_down.state(["!selected"])
                  elif settings_state["regression_filter"] == "below":
                        reg_btn_up.state(["!selected"]); reg_btn_down.state(["selected"])
                  else:
                        reg_btn_up.state(["!selected"]); reg_btn_down.state(["!selected"])
            except:  
                  pass

      elif tag == 'SECTOR':
            # Sektör silme geri alımı
            keys = data
            for k in keys:
                  try:
                        manual_removed.remove(k)
                  except KeyError:
                        pass

      # Seçimleri temizle ve çiz
      selection_state["selected_keys"].clear()
      trigger_auto_zoom()

root.bind_all("<Control-z>", on_undo)
root.bind_all("<Control-p>", open_settings)


def on_scroll(event):
      global last_annotation
      if last_annotation:
            try:
                  last_annotation.remove()
            except Exception:
                  pass
            last_annotation = None

      factor = 0.9 if getattr(event, "button", "") == 'up' else 1.1
      if hasattr(event, "step"):
            factor = 0.9 if event.step > 0 else 1.1

      xdata = event.xdata if event.xdata is not None else (ax.get_xlim()[0] + ax.get_xlim()[1]) / 2.0
      ydata = event.ydata if event.ydata is not None else (ax.get_ylim()[0] + ax.get_ylim()[1]) / 2.0

      x_left     = xdata - (xdata - ax.get_xlim()[0]) * factor
      x_right   = xdata + (ax.get_xlim()[1] - xdata) * factor
      y_bottom = ydata - (ydata - ax.get_ylim()[0]) * factor
      y_top      = ydata + (ax.get_ylim()[1] - ydata) * factor

      ax.set_xlim(x_left, x_right)
      ax.set_ylim(y_bottom, y_top)
       
      # Grafiği yenile
      update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)
       
      # --- DÜZELTME: Zoom bittikten sonra seçili noktaları tekrar boya ---
      draw_selection_highlights()

canvas.mpl_connect("scroll_event", on_scroll)

pan_active = False
pan_last = None

def on_press(event):
      global pan_active, pan_last
       
      # Bizim manuel Ctrl takipçimize bakıyoruz
      is_ctrl = ctrl_state["pressed"]

      # --- SENARYO 1: CTRL BASILIYSA ---
      # Pan yapma, buradan çık (Meydan on_select_press'e kalsın)
      if is_ctrl:
            return

      # --- SENARYO 2: SADECE SOL TIK (PAN & TEMİZLİK) ---
      # 1. Eğer seçili müşteriler varsa hafızadan sil (AMA ÇİZME!)
      if selection_state["selected_keys"]:
            selection_state["selected_keys"].clear()
            clear_selection_visuals()
            # BURADA canvas.draw_idle() YAPMIYORUZ!  
            # Çünkü yaparsak pan hareketiyle çakışıp kasma yapar.
            # Bırakalım hareket başlayınca temiz haliyle çizilsin.

      # 2. Pan (Kaydırma) modunu başlat
      if event.button == 1 and event.inaxes == ax:
            pan_active = True
            pan_last = (event.x, event.y)
             
            # Performans için Legend'ları geçici gizle
            if sector_combobox.get() == "Sector Avg" and active_legends:
                  for lg in active_legends:
                        try:
                              lg.set_visible(False)
                        except Exception:
                              pass
                  # Pan başlangıcında tek bir update yeterli
                  # (Hemen hareket edecekseniz draw_idle'a gerek yok ama
                  # duran tıklamalar için koyuyoruz, hareket başlayınca override olur)
                  canvas.draw_idle()
def on_release(event):
      global pan_active
       
      if not pan_active:
            return

      if event.button == 1:
            pan_active = False
            # Pan bitti, grafiği en temiz haliyle tekrar çiz
            update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)
             
            # --- DÜZELTME: Pan bittikten sonra seçili noktaları tekrar boya ---
            draw_selection_highlights()

def on_motion_pan(event):
      global pan_last
       
      # Pan aktif değilse veya mouse eksen dışındaysa çık
      if not (pan_active and pan_last and event.inaxes == ax):
            return
       
      # Sürükleme esnasında sonradan CTRL'ye basılırsa durdur
      if ctrl_state["pressed"]:
            return

      dx_pixels = event.x - pan_last[0]
      dy_pixels = event.y - pan_last[1]
      pan_last = (event.x, event.y)

      x0_l, x1_l = ax.get_xlim()
      y0_l, y1_l = ax.get_ylim()
      x_range = (x1_l - x0_l)
      y_range = (y1_l - y0_l)

      w = max(1, canvas_widget.winfo_width())
      h = max(1, canvas_widget.winfo_height())
       
      dx = -dx_pixels / w * x_range
      dy = -dy_pixels / h * y_range

      ax.set_xlim(x0_l + dx, x1_l + dx)
      ax.set_ylim(y0_l + dy, y1_l + dy)

      canvas.draw_idle()

canvas.mpl_connect("button_press_event", on_press)
canvas.mpl_connect("button_release_event", on_release)
canvas.mpl_connect("motion_notify_event", on_motion_pan)


def refresh_show_arrows_enabled():
      sel = sector_combobox.get()
      enabled = (license_var.get() == "Exc." and exc_updated_var.get() and sel != "Sector Avg")
      if not enabled:
            exc_show_arrows_var.set(False)
            settings_state["show_difference_arrows"] = False
            exc_show_arrows_cb.configure(state=tk.DISABLED)
      else:
            exc_show_arrows_cb.configure(state=tk.NORMAL)


def on_sector_change(event):
      # ... (Mevcut logic devam ediyor) ...
      if sector_combobox.get() == "Sector Avg":
            if exc_show_arrows_var.get():
                  exc_show_arrows_var.set(False)
                  settings_state["show_difference_arrows"] = False
       
      refresh_show_arrows_enabled()
      toggle_regression_buttons_visibility() # Regresyon buton kontrolü

      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)
      _apply_churn_labels_visibility()
       
      if settings_state.get("activate_search_box", False):
            _update_search_list(search_var.get())

      # --- DÜZELTME: Focus Lag Çözümü ---
      # Seçimden hemen sonra odağı ana pencereye/canvas'a zorla ver.
      # Böylece Ctrl tuşu anında algılanır.
      canvas.get_tk_widget().focus_set()
      root.focus_set()

sector_combobox.bind("<<ComboboxSelected>>", on_sector_change)

# =====================================================
# License filter alanı
# =====================================================
license_var = tk.StringVar(value="Inc.")
license_frame = ttk.LabelFrame(sidebar, text="License Option", padding=8)
license_frame.grid(row=2, column=0, sticky="sew", padx=10, pady=(4, 10))
license_frame.grid_columnconfigure(0, weight=1)
license_frame.grid_columnconfigure(1, weight=1)

exc_opts_frame = ttk.Frame(license_frame)
exc_opts_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 2))

exc_updated_var = tk.BooleanVar(value=settings_state.get("use_updated_exc_license_values", False))
exc_show_arrows_var = tk.BooleanVar(value=settings_state.get("show_difference_arrows", False))


def on_exc_updated_toggle():
      settings_state["use_updated_exc_license_values"] = bool(exc_updated_var.get())
      refresh_show_arrows_enabled()
      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)


def on_exc_show_arrows_toggle():
      if sector_combobox.get() == "Sector Avg":
            exc_show_arrows_var.set(False)
            settings_state["show_difference_arrows"] = False
            refresh_show_arrows_enabled()
            return
      settings_state["show_difference_arrows"] = bool(exc_show_arrows_var.get())
      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)


exc_updated_cb = ttk.Checkbutton(exc_opts_frame, text="Updated Exc. License Values",
                                                  variable=exc_updated_var, command=on_exc_updated_toggle)
exc_show_arrows_cb = ttk.Checkbutton(exc_opts_frame, text="Show difference arrows",
                                                        variable=exc_show_arrows_var, command=on_exc_show_arrows_toggle)
exc_updated_cb.grid(row=0, column=0, sticky="w", padx=2, pady=2)
exc_show_arrows_cb.grid(row=1, column=0, sticky="w", padx=2, pady=2)

threshold_frame = ttk.Frame(license_frame)
threshold_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))

ttk.Label(threshold_frame, text="License threshold (%):").grid(row=0, column=0, sticky="w", padx=(0,6))
numeric_entry_var = tk.StringVar()
numeric_entry = ttk.Entry(threshold_frame, textvariable=numeric_entry_var, width=10, justify="center")
vcmd = (root.register(validate_float), "%P")
numeric_entry.config(validate="key", validatecommand=vcmd)
numeric_entry.grid(row=0, column=1, sticky="w")


def on_license_filter():
      license_removed.clear()
      try:
            value_str = numeric_entry.get()
            min_license = parse_number_entry(value_str) / 100.0
      except ValueError:
            min_license = 0.0

      # Sadece Exc. modunda filtre uygula
      if license_var.get() == "Exc.":     
            rev = settings_state.get("reverse_effect", False)

            for _, row in df.iterrows():

                  # 1) CHURN satırlarını tamamen atla
                  if CHURN_COL in df.columns:
                        try:
                              churn_flag = str(row.get(CHURN_COL, "")).strip().upper()
                              if churn_flag == "CHURN":
                                    continue
                        except Exception:
                              pass

                  # 2) License Percent değerini float'a çevir
                  raw_val = row.get("License Percent", 0)

                  try:
                        import pandas as _pd
                        # NaN ise atla
                        if _pd.isna(raw_val):
                              continue

                        if isinstance(raw_val, str):
                              cleaned = raw_val.strip()
                              # İçinde hiç rakam yoksa (ör: "CHURN") bu satırı da atla
                              if not any(ch.isdigit() for ch in cleaned):
                                    continue
                              license_value = parse_number_entry(cleaned)
                        else:
                              license_value = float(raw_val)
                  except Exception:
                        # Herhangi bir parse hatasında satırı atla
                        continue

                  key = get_point_key(row, settings_state)

                  if not rev:
                        if license_value > min_license:
                              license_removed.add(key)
                  else:
                        if license_value <= min_license:
                              license_removed.add(key)

      refresh_show_arrows_enabled()
      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)
      if settings_state.get("activate_search_box", False):
            _update_search_list(search_var.get())


def on_license_key_release(event):
      on_license_filter()

numeric_entry.bind("<KeyRelease>", on_license_key_release)


def update_exc_controls_visibility():
      if license_var.get() == "Exc.":
            exc_opts_frame.grid()
            threshold_frame.grid()
            refresh_show_arrows_enabled()
      else:
            try: exc_opts_frame.grid_remove()
            except Exception: pass
            try: threshold_frame.grid_remove()
            except Exception: pass


def on_license_select_v1():
      # Inc. seçildi → normal davran, churn checkbox'larına karışma
      license_var.set("Inc.")
      update_exc_controls_visibility()
      license_removed.clear()
      refresh_show_arrows_enabled()
      update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)
      if settings_state.get("activate_search_box", False):
            _update_search_list(search_var.get())


def on_license_select_v2():
      # Exc. seçildi → Churn seçenekleriyle ÇAKIŞMASIN
      license_var.set("Exc.")

      # Kullanıcı Exc'e geçtiyse: Include / Show Only churn tiklerini kaldır
      churn_enabled_var.set(False)
      churn_only_var.set(False)
      settings_state["churn_enabled"] = False
      settings_state["show_only_churn"] = False
      _apply_churn_labels_visibility()

      update_exc_controls_visibility()
      numeric_entry.delete(0, tk.END); numeric_entry.insert(0, "0")
      numeric_entry.update_idletasks()
      on_license_filter()


def on_left_click_select_sector(event):
      """ Sector Avg görünümündeyken, AVG noktasına sol tık → ilgili sektörü combobox'ta seç. """
       
      # --- DÜZELTME: CTRL BASILIYSA BU FONKSİYON ÇALIŞMASIN ---
      # Eğer Ctrl basılıysa, kullanıcı sektörü "Seçmek" (Select/Toggle) istiyordur,  
      # içine girmek (Drill-down) istemiyordur. Buradan çıkıyoruz.
      if ctrl_state["pressed"]:
            return
      # --------------------------------------------------------

      if event.inaxes != ax or getattr(event, "button", None) != 1:
            return
       
      if sector_combobox.get() != "Sector Avg":
            return

      for sc, sd in scatter_points:
            label = sc.get_label() or ""
            if not label.endswith(" Avg"):
                  continue
             
            contains, ind = sc.contains(event)
            if contains:
                  sector_name = label.replace(" Avg", "")
                  try:
                        sector_combobox.set(sector_name)
                        refresh_show_arrows_enabled()
                        toggle_regression_buttons_visibility()
                         
                        # Yeni sektöre girerken eski seçimleri temizlemek mantıklı olur
                        selection_state["selected_keys"].clear()
                        clear_selection_visuals()
                         
                        update_plot(sector_name, preserve_zoom=False, fit_to_data=True)
                        sector_combobox.event_generate("<<ComboboxSelected>>")
                         
                        # Sektör değişince Focus'u düzelt
                        canvas.get_tk_widget().focus_set()
                        root.focus_set()
                  except Exception:
                        pass
                  break

canvas.mpl_connect("button_press_event", on_left_click_select_sector)

radio_inc = ttk.Radiobutton(license_frame, text="Inc.", variable=license_var, value="Inc.", command=on_license_select_v1)
radio_exc = ttk.Radiobutton(license_frame, text="Exc.", variable=license_var, value="Exc.", command=on_license_select_v2)
radio_inc.grid(row=2, column=0, padx=12, pady=(6, 6), sticky="w")
radio_exc.grid(row=2, column=1, padx=12, pady=(6, 6), sticky="w")
license_var.set("Inc.")
radio_inc.invoke()
update_exc_controls_visibility()
# ========= Sidebar başlangıç genişliğini ölç ve hafif artır =========
root.update_idletasks()
BASE_SIDEBAR_WIDTH = max(sidebar.winfo_width(), sidebar.winfo_reqwidth())
sidebar.config(width=BASE_SIDEBAR_WIDTH + SIDEBAR_EXTRA_WIDTH)
sidebar.grid_propagate(False)
root.grid_columnconfigure(1, minsize=BASE_SIDEBAR_WIDTH + SIDEBAR_EXTRA_WIDTH)

# İlk çizim
splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=80, sub="Rendering first view…")
update_plot(sector_combobox.get(), preserve_zoom=False, fit_to_data=True)

# Başlangıçta arama barı görünürlüğünü uygula
def _place_excel_btn_and_search():
      _place_excel_btn_next_to_settings()
      toggle_search_bar_visibility()
      # YENİ: Başlangıçta regresyon butonlarının görünürlüğünü uygula
      toggle_regression_buttons_visibility()

root.after_idle(_place_excel_btn_and_search)

splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=90, sub="Loading handbook resources...")
try:
      preload_handbook_images()
except Exception as e:
      print(f"Preload warning: {e}")

def _hide_search_list_on_click(event):
      """Eğer tıklanan widget search_list, search_entry veya search_info değilse gizle"""
      def _do_hide():
            try:
                  widget = event.widget
                  if widget not in (search_entry, search_list, search_info):
                        search_list.grid_remove()
                        search_info.config(text="")   # gizlemeden önce text sıfırla
            except Exception:
                  pass
      root.after(50, _do_hide)

root.bind("<Button-1>", _hide_search_list_on_click, add="+")

def _show_search_on_click(event):
      """search_entry'ye tıklanınca liste ve label yeniden görünür"""
      try:
            term = (search_var.get() or "").strip()
            if term:
                  # liste ve label yeniden görünür olsun
                  search_list.grid()
                  # eşleşme sayısını yeniden hesapla ve label’a yaz
                  count = search_list.size()
                  search_info.config(text=f"{count} match")
                  search_info.grid()
      except Exception:
            pass

search_entry.bind("<Button-1>", _show_search_on_click, add="+")

def _toggle_search_box_hotkey(event=None):
      """Ctrl+F ile arama kutusunu aç/kapa (Fixlendi)"""
      try:
            # 1. Mevcut durumu ayarlar sözlüğünden al
            current_state = settings_state.get("activate_search_box", False)
             
            # 2. Durumu tersine çevir (True -> False / False -> True)
            new_state = not current_state
            settings_state["activate_search_box"] = new_state
             
            # 3. Merkezi görünürlük fonksiyonunu çağır
            # (Bu fonksiyon zaten _position_search_frame'i çağırıp doğru yere koyuyor)
            toggle_search_bar_visibility()

            # 4. Odaklanma Yönetimi
            if new_state:
                  # Arama açıldıysa, imleci kutunun içine koy
                  # after(50) kullanıyoruz ki UI çizildikten sonra odaklansın
                  search_entry.after(50, search_entry.focus_set)
            else:
                  # Kapandıysa odağı grafiğe geri ver (Klavye kısayolları çalışsın diye)
                  canvas.get_tk_widget().focus_set()
                   
                  # Listeyi ve highlightları temizle
                  try:
                        search_list.grid_remove()
                        search_info.config(text="")
                  except: pass
                  _clear_highlight_overlays()

      except Exception as e:
            print(f"Ctrl+F toggle hatası: {e}")
       
      return "break"   # Event'in başka yerlere (örn: Matplotlib) gitmesini engelle

# --- Bağlamaları Güncelle ---
# Hem küçük 'f' hem büyük 'F' (Caps Lock açıkken) için bağlama yapıyoruz
root.bind("<Control-f>", _toggle_search_box_hotkey)
root.bind("<Control-F>", _toggle_search_box_hotkey)

# YENİ: Regresyon çizgisi için kısayol (Ctrl+R+L)
def _toggle_regression_line_hotkey(event=None):
      """Ctrl+R+L ile regresyon çizgisini aç/kapa"""
      try:
            current_state = settings_state.get("show_regression_line", False)
            new_state = not current_state
            settings_state["show_regression_line"] = new_state
             
            # Eğer kapatılıyorsa, filtreyi de kapat
            if not new_state:
                  settings_state["regression_filter"] = "none"
                  reg_filter_var.set("none")
                  reg_btn_up.state(["!selected"])
                  reg_btn_down.state(["!selected"])
             
            # Butonların görünürlüğünü güncelle
            toggle_regression_buttons_visibility()
            # Grafiği yeniden çiz
            update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)
      except Exception as e:
            print(f"Ctrl+R+L toggle hata: {e}")

root.bind("<Control-f>", _toggle_search_box_hotkey)
# <Control-r> (küçük r) auto-zoom için kullanılıyor
root.bind("<Control-r>", lambda e: trigger_auto_zoom())  
# <Control-R> (büyük R) auto-zoom için kullanılıyor
root.bind("<Control-R>", lambda e: trigger_auto_zoom())  
# YENİ: Regresyon kısayolu (Ctrl+R+L - Control-Shift-R + L çalışmayabilir, Control-Alt-R deneyelim)
# Not: Tk'de Ctrl+R+L gibi üçlü kombinasyonlar standart değildir.
# Ctrl+Shift+R veya Ctrl+Alt+R daha stabildir. Ctrl+Alt+L kullanalım (L = Line).
root.bind("<Control-l>", _toggle_regression_line_hotkey)
root.bind("<Control-L>", _toggle_regression_line_hotkey)
root.bind("<Control-g>", lambda e: open_handbook())
root.bind("<Control-G>", lambda e: open_handbook()) # Büyük harf hassasiyeti için


# =====================================================
# FOCUS / TAB GÖRÜNTÜLERİNİ KALDIRMA
# =====================================================
def _strip_focus_from_widget(widget):
      """Widget ve çocuklarında focus highlight ve Tab ile gezinmeyi devre dışı bırak."""
      try:
            # Tk / Ttk çoğu widget'ta takefocus parametresi var
            widget.configure(takefocus=0)
      except Exception:
            pass
      # Bazı klasik Tk widget'larda highlight'ı sıfırlayabiliriz
      for opt in ("highlightthickness", "highlightcolor", "highlightbackground"):
            try:
                  if opt == "highlightthickness":
                        widget.configure(**{opt: 0})
                  else:
                        # Arka planla aynı yapmaya çalış
                        bg = widget.cget("background") if "background" in widget.keys() else None
                        if bg is not None:
                              widget.configure(**{opt: bg})
            except Exception:
                  pass

def _strip_focus_globally():
      try:
            _strip_focus_from_widget(root)
            for w in root.winfo_children():
                  _strip_focus_from_widget(w)
                  # Toplevel / Frame gibi ise alt çocukları da dolaş
                  try:
                        for c in w.winfo_children():
                              _strip_focus_from_widget(c)
                              try:
                                    for c2 in c.winfo_children():
                                         _strip_focus_from_widget(c2)
                              except Exception:
                                    pass
                  except Exception:
                        pass
      except Exception:
            pass
      # Yeni açılan pencereler (settings vs) için periyodik tekrar
      root.after(1000, _strip_focus_globally)

# Tab ve Shift+Tab ile focus taşımayı tamamen engelle
def _block_tab(event):
      return "break"

root.bind_all("<Tab>", _block_tab)
root.bind_all("<ISO_Left_Tab>", _block_tab)
root.bind_all("<Shift-Tab>", _block_tab)

# Başlangıçta focus temizleyiciyi devreye al
root.after(300, _strip_focus_globally)

# Splash kapat — ANA PENCEREYİ MAKSİMİZE ET ve göster
maximize_main_window(root, prefer_kiosk=False)
splash_set(splash, pbar, splash_title_lbl, splash_sub_lbl, pct=100, sub="Done")
try:
      splash.grab_release()
except Exception:
      pass
splash.destroy()
root.deiconify()

handbook_win_ref = None

def open_handbook():
      """
      Analitik Düzlem & Kullanım Kılavuzu (Scroll ve Zıplama Sorunları Giderildi)
      """
      global handbook_win_ref

      # 1. PENCERE KONTROLÜ
      if handbook_win_ref is not None and handbook_win_ref.winfo_exists():
            try:
                  handbook_win_ref.deiconify()       
                  handbook_win_ref.lift()              
                  handbook_win_ref.focus_force()    
                  return
            except Exception:
                  handbook_win_ref = None

      # 2. YENİ PENCERE OLUŞTUR
      hb_win = tk.Toplevel(root)
      handbook_win_ref = hb_win
       
      hb_win.title("Analitik Düzlem & Kullanım Kılavuzu")
      hb_win.transient(root)
       
      w, h = 1000, 800
      center_over_parent(hb_win, root, w, h)

      hb_win.bind("<Escape>", lambda e: hb_win.destroy())

      # --- Stiller ---
      style = ttk.Style()
      style.configure("Handbook.TNotebook", tabposition='nw', background="white")
       
      nb = ttk.Notebook(hb_win, style="Handbook.TNotebook")
      nb.pack(fill="both", expand=True, padx=0, pady=0)

      # --- İçerik Oluşturucu Yardımcı Fonksiyon ---
      def add_handbook_tab(title, content_segments):
            # Ana çerçeve
            frame = tk.Frame(nb, bg="white")  
            nb.add(frame, text=f" {title} ")
             
            # Grid Layout
            frame.grid_columnconfigure(1, weight=1)
            frame.grid_rowconfigure(0, weight=1)

            # Scrollbar
            scrollbar = ttk.Scrollbar(frame, orient="vertical")
            scrollbar.grid(row=0, column=3, sticky="ns")

            # Metin Kutusu
            txt = tk.Text(frame, wrap="word", padx=0, pady=0,  
                                 font=("Segoe UI", 10), bg="white", relief="flat",
                                 border=0, highlightthickness=0,
                                 yscrollcommand=scrollbar.set,
                                 cursor="arrow")  
             
            txt.grid(row=0, column=1, sticky="nsew", padx=0, pady=20)
             
            # Yan Boşluklar (Margin)
            tk.Frame(frame, bg="white", width=30).grid(row=0, column=0, sticky="ns")
            tk.Frame(frame, bg="white", width=20).grid(row=0, column=2, sticky="ns")

            scrollbar.config(command=txt.yview)
             
            # Taglar
            txt.tag_configure("h1", font=("Segoe UI", 18, "bold"), foreground="#2c3e50", spacing3=15, spacing1=10)
            txt.tag_configure("h2", font=("Segoe UI", 13, "bold"), foreground="#1f77b4", spacing3=10, spacing1=25)
            txt.tag_configure("bold", font=("Segoe UI", 10, "bold"))
            txt.tag_configure("bullet", lmargin1=25, lmargin2=35, spacing1=4)
            txt.tag_configure("normal", lmargin1=5, lmargin2=5, spacing1=3)

            txt.insert("end", "\n", "normal")  

            # --- DÜZELTİLMİŞ SCROLL PROPAGATOR (AKICI SCROLL) ---
            def _propagate_scroll(event):
                  """
                  Görsellerin üzerindeyken çalışır. Satır (units) bazlı değil,  
                  Pixel/Oran (moveto) bazlı kaydırma yaparak büyük görsellerin  
                  tek seferde atlanmasını engeller.
                  """
                  try:
                        delta = 0
                        if hasattr(event, "delta") and event.delta:
                              delta = event.delta
                        elif hasattr(event, "num"): # Linux uyumluluğu
                              if event.num == 4: delta = 120
                              elif event.num == 5: delta = -120
                         
                        if delta:
                              # Mevcut görünüm oranlarını al (0.0 - 1.0 arası)
                              cur_top, cur_bot = txt.yview()
                              view_height = cur_bot - cur_top
                               
                              # Ekran boyunun %5'i kadar kaydır (Yumuşak geçiş için ideal oran)
                              # Bu sayede görsel 1000px bile olsa satır olarak atlamaz, piksel piksel kayar.
                              scroll_step = 0.05 * view_height
                               
                              if delta > 0: # Yukarı
                                    new_top = max(0.0, cur_top - scroll_step)
                              else: # Aşağı
                                    new_top = min(1.0, cur_top + scroll_step)
                                     
                              txt.yview_moveto(new_top)
                               
                  except Exception:
                        pass
                  return "break" # Event'in başka yere gitmesini engelle

            img_counter = 0  

            for segment in content_segments:
                  # --- TEXT TİPİ İÇERİK ---
                  if segment["type"] == "text":
                        lines = segment["data"].split('\n')
                        for line in lines:
                              line = line.strip()
                              if not line:
                                    txt.insert("end", "\n")
                                    continue
                               
                              if line.startswith("# "):
                                    txt.insert("end", line[2:] + "\n", "h1")
                              elif line.startswith("## "):
                                    txt.insert("end", line[3:] + "\n", "h2")
                              elif line.startswith("- "):
                                    parts = line[2:].split("**")
                                    txt.insert("end", "• ", "bullet")
                                    for i, part in enumerate(parts):
                                          tag = "bold" if i % 2 == 1 else "bullet"
                                          txt.insert("end", part, tag)
                                    txt.insert("end", "\n")
                              else:
                                    parts = line.split("**")
                                    txt.insert("end", "", "normal")
                                    for i, part in enumerate(parts):
                                          tag = "bold" if i % 2 == 1 else "normal"
                                          txt.insert("end", part, tag)
                                    txt.insert("end", "\n")
                   
                  # --- IMAGE TİPİ İÇERİK ---
                  elif segment["type"] == "image":
                        img_file = segment.get("file")
                        caption_text = segment.get("caption", "Görsel")
                         
                        img_counter += 1
                         
                        # 1. Container
                        container = tk.Frame(txt, bg="white", bd=0)  

                        # 2. Header
                        header_frame = tk.Frame(container, bg="#f8f9fa", height=40, cursor="hand2")
                        header_frame.pack(fill="x", expand=True)
                         
                        stripe = tk.Frame(header_frame, bg="#1f77b4", width=4)
                        stripe.pack(side="left", fill="y")
                         
                        header_lbl = tk.Label(header_frame,  
                                                         text=f"▶   Görseli Göster: {caption_text}",  
                                                         font=("Segoe UI", 10, "bold"),
                                                         bg="#f8f9fa", fg="#495057",
                                                         anchor="w", padx=10, pady=10)
                        header_lbl.pack(side="left", fill="x", expand=True)

                        # 3. Content Frame
                        content_frame = tk.Frame(container, bg="white", pady=10)
                         
                        # Görsel Yükleme
                        tk_img = load_handbook_image(img_file, width=850)
                         
                        if tk_img:
                              img_lbl = tk.Label(content_frame, image=tk_img, bg="white", bd=0)
                              img_lbl.image = tk_img  
                              img_lbl.pack(anchor="center")
                               
                              # Yeni Scroll Bağlamaları
                              img_lbl.bind("<MouseWheel>", _propagate_scroll)
                              img_lbl.bind("<Button-4>", _propagate_scroll)
                              img_lbl.bind("<Button-5>", _propagate_scroll)
                        else:
                              missing_lbl = tk.Label(content_frame,  
                                                                 text=f"⚠️ Dosya bulunamadı: assets/{img_file}",
                                                                 fg="red", bg="white")
                              missing_lbl.pack(pady=10)
                              missing_lbl.bind("<MouseWheel>", _propagate_scroll)
                              missing_lbl.bind("<Button-4>", _propagate_scroll)
                              missing_lbl.bind("<Button-5>", _propagate_scroll)

                        if caption_text:
                              cap_lbl = tk.Label(content_frame, text=caption_text,  
                                                           font=("Segoe UI", 9, "italic"), fg="#6c757d", bg="white")
                              cap_lbl.pack(pady=(5,0))
                              cap_lbl.bind("<MouseWheel>", _propagate_scroll)
                              cap_lbl.bind("<Button-4>", _propagate_scroll)
                              cap_lbl.bind("<Button-5>", _propagate_scroll)

                        # --- DÜZELTME: ZIPLAMASIZ TOGGLE ---
                        def toggle_image(e=None,  
                                                  h_lbl=header_lbl,  
                                                  c_frame=content_frame,  
                                                  cont=container,  
                                                  txt_cap=caption_text):
                               
                              is_visible = c_frame.winfo_viewable()
                               
                              if is_visible:
                                    c_frame.pack_forget()
                                    h_lbl.config(text=f"▶   Görseli Göster: {txt_cap}", bg="#f8f9fa", fg="#495057")
                                    header_frame.config(bg="#f8f9fa")
                              else:
                                    c_frame.pack(fill="x", expand=True, padx=10)
                                    h_lbl.config(text=f"▼   Görseli Gizle: {txt_cap}", bg="#e7f5ff", fg="#1f77b4")
                                    header_frame.config(bg="#e7f5ff")
                               
                              # Sadece boyutları güncelle, ama txt.see() YAPMA!
                              # txt.see() ekranı zorla kaydırdığı için zıplama yapar.
                              # update_idletasks yeterlidir, içerik doğal olarak aşağı itilir.
                              c_frame.update_idletasks()  
                              cont.update_idletasks()
                               
                              # Düzeltme: Focus'u pencerede tut
                              txt.focus_set()

                        header_frame.bind("<Button-1>", toggle_image)
                        header_lbl.bind("<Button-1>", toggle_image)
                        stripe.bind("<Button-1>", toggle_image)

                        for widget in (container, header_frame, header_lbl, stripe, content_frame):
                              widget.bind("<MouseWheel>", _propagate_scroll)
                              widget.bind("<Button-4>", _propagate_scroll)
                              widget.bind("<Button-5>", _propagate_scroll)

                        txt.insert("end", "\n")  
                        txt.window_create("end", window=container, stretch=1)
                        txt.insert("end", "\n")  
             
            txt.configure(state="disabled")

      # ================= İÇERİK TANIMLARI =================
      # (Buradaki içerik tanımlarınız orijinal kodla aynı kalmalı,  
      # sadece yukarıdaki fonksiyon yapısı değişti)

      # TAB 1: GRAFİK OKUMA
      content_graph = [
            {"type": "text", "data": """# Grafik ve Eksenlerin Anlamı

Bu uygulama, müşteri portföyünü **MRR** ve **Growth** eksenlerinde görselleştirir. Her bir nokta bir müşteriyi veya bir sektör ortalamasını temsil eder.
"""},
            {"type": "text", "data": """## 1. Eksenlerin Mantığı
- **X Ekseni (Yatay):** Müşterinin MRR değerini gösterir. Sağa gidildikçe müşteri   MRR'ı artar.
- **Y Ekseni (Dikey):** Müşterinin büyüme hızını gösterir. Yukarı gidildikçe büyüme hızı artar.
- **Kesişim Noktası (Merkez):** Grafiğin ortasındaki çizgilerin kesiştiği nokta, tüm portföyün (veya filtrelenen verinin) ortalamasını gösterir.
"""},
            {"type": "image", "file": "hb_graph_reading.png",  
              "caption": "Şekil 1: Analitik düzlem. Yatay eksen MRR'ı, dikey eksen büyümeyi gösterir."},
             
            {"type": "text", "data": """## 2. Quadrant (Dört Bölge) Analizi
Merkez çizgileri grafiği 4 ana bölgeye ayırır:
- **Sağ Üst (+, +):** **"Yıldızlar"**. Hem MRR'ı hem de büyüme hızı ortalamanın üzerinde olan müşterileri temsil eder.
- **Sol Üst (-, +):** **"Potansiyeller"**. MRR'ı henüz ortalamanın altında ama çok hızlı büyüyenler.
- **Sağ Alt (+, -):** **"Nakit İnekleri"**. MRR'ı yüksek ama büyümesi ortalamadan yavaş olan müşteriler. Riskli olabilir.
- **Sol Alt (-, -):** **"Düşük Performans"**. Hem MRR'ı hem de büyüme hızı ortalamanın altında olan müşteriler.
"""},
            {"type": "image", "file": "hb_risk_map.png",  
              "caption": "Şekil 2: Dört Bölge Analizi."},
             
      ]

      # TAB 2: REGRESYON
      content_regression = [
            {"type": "text", "data": """# Regresyon Analizi (Trend Çizgisi)

Settings menüsünden veya **Ctrl+L** kısayolu ile açılan regresyon çizgisi, filtrelenen verilerin genel eğilimi matematiksel olarak hesaplar.

## Regresyon Çizgisi Nedir?
Bu çizgi, **MRR büyüklüğü ile Büyüme Oranı arasındaki ilişkiyi** (korelasyonu) gösterir.
- **Çizgi Aşağı Eğimliyse:** Müşteriler büyüdükçe (MRR arttıkça) büyüme hızları yavaşlıyor demektir (Doğal bir durumdur, "Büyümenin Bedeli").
- **Çizgi Yukarı Eğimliyse:** Büyük müşteriler, küçüklerden daha hızlı büyüyor demektir (Pozitif bir durum)

## Filtreleme Okları  
Regresyon açıldığında sağ alt köşede iki ok butonu belirir:
- **Yukarı Ok :** Sadece regresyon çizgisinin üzerinde kalan müşterileri gösterir.
- **Aşağı Ok :** Sadece regresyon çizgisinin altında kalan müşterileri gösterir.
- **Tekrar Tıklama:** Seçili oka tekrar basarsanız filtre kalkar ve tüm noktalar görünür.
"""},
            {"type": "image", "file": "hb_regression.png",  
              "caption": "Şekil 3: Regresyon çizgisi ve sağ alttaki filtre okları"}
      ]

      # TAB 3: AYARLAR
      content_settings = [
            {"type": "text", "data": """# Settings Menüsü Detayları

Ayarlar penceresindeki her bir sekmenin işlevi aşağıdadır:

## 1. Limit Options
Veri setini belirli kriterlere göre daraltmanızı sağlar.
- **Mode (Limit / No Limit):** Filtrelerin aktif olup olmayacağını seçer.
- **Ranges:** Sadece belirli bir MRR aralığındaki (ör. 1000$ - 5000$) veya Büyüme aralığındaki (ör. %10 üzeri) müşterileri görmek için kullanılır.
- **Filter by Age:**
   - **(0-Current):** Tüm müşterileri gösterir (Varsayılan).
   - **(0-1):** Sadece 1. yılını tamamlamış müşterileri baz alır. Veriler 1. yıl sonu verisine döner.
   - **(0-2):** Sadece 2. yılını tamamlamış müşterileri gösterir.
   - **(1-2):** Sadece 2. yılını tamamlamış müşterilerin 1. yıldan itibaren olan verilerini gösterir.
"""},
            {"type": "image", "file": "hb_settings_limit.png", "caption": "Şekil 4: Limit Options Ayarları"},

            {"type": "text", "data": """## 2. License Options (Exc. Modu)
**Not:** License options sekmesi, eğer license option exc. seçeneği seçili değilse erişilebilir olmaz.              
- **Reverse Effect:** Lisans filtre mantığını tersine çevirir ("X değerden büyük olanları gizle" yerine "küçük olanları gizle" yapar).
- **Sağ Paneldeki "Exc." Modu:** Lisans gelirlerini hariç tutarak saf hizmet gelirine odaklanmak içindir.
- **Show Difference Arrows:** "Exc." modundayken açılırsa, müşterinin Lisans Dahil (Inc.) halinden Lisans Hariç (Exc.) haline geçişini grafikte **oklarla** gösterir. Okun boyu, lisans gelirinin büyüklüğünü temsil eder.
"""},
            {"type": "image", "file": "hb_settings_reverse.png", "caption": "Şekil 5: License Options: Reverse Effect"},
            {"type": "image", "file": "hb_settings_exc_mode.png", "caption": "Şekil 6: Right Panel: Inc./Exc. Selection"},
            {"type": "image", "file": "hb_settings_arrows.png", "caption": "Şekil 7: Show Difference Arrows"},

            {"type": "text", "data": """## 3. Axis Settings
- **Fixed Axis:** Çeşitli filtreler uygulandığında bile merkez çizgilerinin (ortalama çizgilerinin) yerini sabitler.
- **Draw Growth=0 Line:** Büyümesi %0 olan noktaya kırmızı kesik bir çizgi çeker. Referans noktasıdır.
- **Swap Axes:** X ve Y eksenlerinin yerini değiştirir. (X=Büyüme, Y=MRR olur).
"""},
            {"type": "image", "file": "hb_settings_axis.png", "caption": "Şekil 8: Axis Settings Paneli"},

            {"type": "text", "data": """## 4. Customer Risk
- **Show Risk Statement:** Risk görünümünü genel olarak açar/kapatır.
- **Show NO/LOW/MED/HIGH:** Belirli risk gruplarını grafikten gizlemek için tikleri kaldırabilirsiniz. Örneğin sadece "HIGH RISK" müşterilere odaklanmak için diğerlerini kapatabilirsiniz.
"""},
            {"type": "image", "file": "hb_settings_risk.png", "caption": "Şekil 9: Customer Risk Paneli"},

            {"type": "text", "data": """## 5. Graph Settings
- **Show Sector Counts Above AVG Points:** "Sector Avg" modundayken, yuvarlakların üzerine o sektörde kaç müşteri olduğunu yazar (Örn: #45).
- **Activate Search Box:** Ana ekrandaki arama çubuğunu açar/kapatır.
- **Activate Customer Risk Color Map:** Aktif hale getirildiğinde dört farklı bölgenin arkaplanları o bölgedeki müşterilerin risk renklerinin ortalamasına bürünür:
- **Distance-weighted quadrant colors:** 0-3 arası değer alabilir. Girilen değere göre müşterinin ortalamaya(eksenlerin kesiştiği yer) olan uzaklığı kendi bölgesindeki renk ortalama belirleme katsayısının önemini arttırır.
- **Show Regression Line:** Grafikteki regresyon çizgisini açar/kapatır.
- **Fix Regression Line:** Regresyon çizgisini sabitler. Filtre uygulanıldığında konumunu korumaya devam eder.
"""},
            {"type": "image", "file": "hb_settings_graph.png", "caption": "Şekil 10: Graph Settings Paneli"},

      ]

      # TAB 4: KONTROLLER
      content_controls = [
            {"type": "text", "data": """# Kontroller ve Kısayollar

Uygulamayı klavye ve fare ile hızlı yönetmek için aşağıdaki yöntemleri kullanabilirsiniz.

## Fare Kullanımı
- **Sol Tık (Basılı Tutup Sürükle):** Grafiği kaydırır (Pan).
- **Ctrl + Sol Tık (Sürükle):** Kutu çizerek çoklu seçim yapar (Box Selection).
- **Sağ Tık:** Üzerine gelinen müşteriyi veya (Sector Avg modundaysanız) o sektörü analizden siler.
- **Tekerlek:** İmlecin olduğu yere yakınlaşır/uzaklaşır (Zoom).

## Klavye Kısayolları (Genel)
- **Ctrl + F (Find):** Arama çubuğunu açar/kapatır.
- **Ctrl + L (Line):** Regresyon (Trend) çizgisini açar/kapatır.
- **Ctrl + R (Reset):** Grafiği verilere otomatik sığdırır (Auto-Zoom).
- **Ctrl + Z (Undo):** Silinen noktaları geri alır.
- **Ctrl + P (Preferences):** Ayarlar penceresini açar.
- **Ctrl + G (Guide):** Bu kılavuzu açar.

## Seçim ve Odaklanma Kısayolları
- **Shift (Basılı Tut):** Sadece arama kutusu açıkken çalışır. Single Mode işlevinin kısayoludur. Tuşu bırakınca eski görünüm geri gelir.
- **Delete:** Seçili olan (etrafı yanan) noktaları grafikten siler.
- **Ctrl + E:** Seçimi tersine çevirir (Seçili olanları bırakır, seçili olmayanları seçer).

## Arama Kutusu (Search Bar) Davranışları
- **Normal Mod:** Müşteri isimlerini arar. Eşleşen müşterileri aşağıda listede gösterir. Listeden müşteri seçilirse müşterinin noktası yanar.
- **Single Mod:** Basılı tutulduğunda arama kutusunda seçili olan müşteriye odaklanıp diğer müşterileri saklar.
"""}
      ]

      # TAB 5: CHURN
      content_churn = [
            {"type": "text", "data": """# Churn (Kayıp) Analizi ve Seçenekleri

Sağ panelde bulunan **Churn Options** kutusu, kaybedilen müşterileri (Churn) analiz etmenizi sağlar.

## 1. Görünüm Seçenekleri
- **Include Churned Customers:** - Normalde grafik sadece aktif müşterileri gösterir. Bu kutucuğu işaretlerseniz, analiz havuzuna Churn olmuş müşteriler de dahil edilir.
   - Churn müşteriler grafikte **Kırmızı 'X'** işareti ile ayırt edilir.
- **Show Only Churned Customers:** - Aktif müşterileri tamamen gizler ve **sadece** kaybedilen müşterileri gösterir.
   - Kayıpların hangi bölgelerde (Quadrant) veya hangi MRR seviyelerinde yoğunlaştığını görmek için kullanılır.
"""},
            {"type": "image", "file": "hb_churn_view.png", "caption": "Şekil 11: Churn Options Paneli"},

            {"type": "text", "data": """## 2. Churn Ratio (Kayıp Oranı) Nasıl Hesaplanır?
Panelde gördüğünüz "Churn Ratio" veya "Total Churn Ratio", müşteri adedine göre değil, **Parasal Değere (MRR)** göre hesaplanır.

**Formül:**
`Churn Oranı = (Churned MRR) / (Aktif MRR + Churned MRR)`
"""}
      ]

      # Sekmeleri oluştur
      add_handbook_tab("Grafik Okuma", content_graph)
      add_handbook_tab("Regresyon Analizi", content_regression)
      add_handbook_tab("Ayarlar Detayı", content_settings)
      add_handbook_tab("Churn Seçenekleri", content_churn)
      add_handbook_tab("Kontroller & Kısayollar", content_controls)

      # Alt kısma kapat butonu
      btn_f = tk.Frame(hb_win, bg="white", padx=10, pady=10)
      btn_f.pack(fill="x", side="bottom")
      ttk.Button(btn_f, text="Kapat", style="Export.TButton", command=hb_win.destroy).pack(side="right")

# --- 1. Handbook Butonunu Oluştur ---
# Export butonuyla aynı stili kullansın
handbook_btn = ttk.Button(root, text="📘 Handbook", command=open_handbook, style="Export.TButton")

# --- 2. Üst Bar Yerleşimini Düzenle ---
# Settings -> Excel -> Handbook -> SearchBar sıralamasını garanti altına alan fonksiyon
def _update_top_bar_layout():
    """Üst bar yerleşimini soldan sağa zincirleme şekilde yapar."""
    try:
        root.update_idletasks()
        
        # 1. Settings Butonu (Zaten Yeri Sabit: SETTINGS_BTN_X)
        s_w = settings_btn.winfo_width()
        if s_w < 10: s_w = 90 
        
        # 2. Excel Butonu (Settings'in Sağına)
        excel_x = SETTINGS_BTN_X + s_w + 4
        excel_btn.place(x=excel_x, y=SETTINGS_BTN_Y)
        
        # 3. Handbook Butonu (Excel'in Sağına)
        e_w = excel_btn.winfo_width()
        if e_w < 10: e_w = 90
            
        hb_x = excel_x + e_w + 4
        handbook_btn.place(x=hb_x, y=SETTINGS_BTN_Y)
        
        # 4. Arama Çubuğu (Eğer açıksa Handbook'un sağına)
        if settings_state.get("activate_search_box", False):
            _position_search_frame()
            
    except Exception:
        pass

# Mevcut _position_search_frame fonksiyonunu GÜNCELLİYORUZ (Override)
# Bu fonksiyon orijinal kodda vardı, şimdi handbook'a göre hizalayacak şekilde değiştiriyoruz.

# Uygulama başlarken yerleşimi tetikle
root.after_idle(_update_top_bar_layout)
# Arama çubuğu güncellemesini de tetikle (eğer açıksa)
root.after_idle(lambda: _position_search_frame() if settings_state.get("activate_search_box") else None)

# ==============================================================================
#SOL TIK BASILI TUTMA SEÇME OLAYI
# =============================================================================
# BOX SELECTION (KUTU SEÇİMİ) & MULTI-SELECT SİSTEMİ
# =============================================================================

# Seçim durumu ve değişkenleri
selection_state = {
      "active": False,
      "start_pos": None,
      "rect": None,
      "selected_keys": set(),
      "highlight_artists": [],
      "background": None   # <--- YENİ: Arka planı hafızada tutmak için
}

def clear_selection_visuals():
      """Seçim efektlerini temizler."""
      for art in selection_state["highlight_artists"]:
            try:
                  art.remove()
            except:
                  pass
      selection_state["highlight_artists"].clear()

def draw_selection_highlights():
      """Seçili noktaların/sektörlerin etrafına glow efekti çizer."""
      clear_selection_visuals()
       
      if not selection_state["selected_keys"]:
            canvas.draw_idle()
            return

      xs, ys = [], []
       
      is_sector_avg_mode = (sector_combobox.get() == "Sector Avg")

      if is_sector_avg_mode:
            # Sector Avg modundaysak, seçili KEY'ler "SEC_AVG|..." formatındadır.
            for sc, _ in scatter_points:
                  lbl = sc.get_label()
                  if lbl.endswith(" Avg"):
                        sec_name = lbl.replace(" Avg", "")
                        key = f"SEC_AVG|{sec_name}"
                         
                        if key in selection_state["selected_keys"]:
                              # Koordinatı al
                              off = sc.get_offsets()[0]
                              xs.append(off[0])
                              ys.append(off[1])
      else:
            # Normal Mod
            for item in selection_state["selected_keys"]:
                  # Güvenlik: Yanlış moddan kalan key varsa atla
                  if isinstance(item, str) and item.startswith("SEC_AVG|"):
                        continue
                   
                  # ID'yi yut, X ve Y'yi al
                  if len(item) == 3:
                        _, raw_x, raw_y = item
                  else:
                        raw_x, raw_y = item

                  px, py = to_plot_coords(raw_x, raw_y)
                  xs.append(px)
                  ys.append(py)

      if not xs:
            canvas.draw_idle()
            return

      # Glow boyutu: Sektör avg ise daha büyük olsun
      s_size = 600 if is_sector_avg_mode else 300

      # ================= ESTETİK GÜNCELLEME =================
      # Sarı/Turuncu yerine modern MAVİ tonları
       
      # 1. Glow (Arkada hafif mavi parıltı - alpha 0.3)
      glow = ax.scatter(
            xs, ys,  
            s=s_size,  
            c='#1f77b4',           # Altın sarısı yerine Mavi
            alpha=0.3,              # Biraz daha şeffaf
            edgecolors='none',  
            zorder=2.5
      )
       
      # 2. Ring (Önde net mavi çerçeve)
      ring = ax.scatter(
            xs, ys,  
            s=s_size,  
            facecolors='none',  
            edgecolors='#1f77b4', # Turuncu yerine Mavi
            linewidths=2.0,  
            zorder=2.6
      )
      # ======================================================

      selection_state["highlight_artists"].extend([glow, ring])
      canvas.draw_idle()

# --- OPTİMİZE EDİLMİŞ EVENTLER ---

def on_select_press(event):
      """
      Ctrl + Sol Tık: Seçimi başlatır.
      ESTETİK GÜNCELLEME: Soluk sarı yerine modern mavi, yarı saydam kutu.
      """
       
      is_ctrl = ctrl_state["pressed"]

      if event.button != 1 or not is_ctrl:
            return

      if event.inaxes != ax or pan_active:
            return

      selection_state["active"] = True
      selection_state["start_pos"] = (event.xdata, event.ydata)
       
      selection_state["background"] = None  

      # Dikdörtgeni oluştur
      if selection_state["rect"] is None:
            rect = Rectangle(
                  (event.xdata, event.ydata), 0, 0,  
                  # --- ESTETİK AYARLAR ---
                  linewidth=1.5,                     # Çerçeve kalınlığı (biraz daha belirgin)
                  edgecolor='#1f77b4',            # Matplotlib'in modern mavisi (veya 'dodgerblue')
                  facecolor=(0.12, 0.46, 0.7, 0.2), # İç dolgu rengi (RGB) + 0.2 Şeffaflık (Alpha)
                  linestyle='-',                     # Kesik çizgi yerine düz çizgi (daha temiz durur)
                  # -----------------------
                  zorder=2000,  
                  animated=True  
            )
            ax.add_patch(rect)
            selection_state["rect"] = rect
      else:
            # Var olanı sıfırla
            selection_state["rect"].set_xy((event.xdata, event.ydata))
            selection_state["rect"].set_width(0)
            selection_state["rect"].set_height(0)
             
            # Renk ayarlarını burada da güncelle (eski ayar kalmasın diye)
            selection_state["rect"].set_linewidth(1.5)
            selection_state["rect"].set_edgecolor('#1f77b4')
            selection_state["rect"].set_facecolor((0.12, 0.46, 0.7, 0.2))
            selection_state["rect"].set_linestyle('-')
             
            selection_state["rect"].set_visible(True)
            selection_state["rect"].set_animated(True)

def on_select_motion(event):
      """
      Sürükleme: Fare dışarı taşsa bile dikdörtgeni kenara yapıştırır (Clamping).
      """
      if not selection_state["active"] or selection_state["rect"] is None:
            return

      # --- DÜZELTME BAŞLANGIÇ ---
      # Orijinal kodda "if event.inaxes != ax: return" vardı.  
      # Bu, hızlı hareketlerde takılmaya neden oluyordu. Bunu sildik.

      # 1. Farenin anlık koordinatlarını al
      x_curr, y_curr = event.xdata, event.ydata

      # 2. Eğer fare grafiğin tamamen dışındaysa (xdata None döner),
      #      Piksel koordinatlarından (event.x, event.y) veriyi geri hesapla.
      if x_curr is None or y_curr is None:
            try:
                  # Pixel -> Data dönüşümü
                  inv = ax.transData.inverted()
                  x_curr, y_curr = inv.transform((event.x, event.y))
            except Exception:
                  # Çok ekstrem bir hata olursa çık
                  return

      # 3. Koordinatları Grafik Sınırlarına Hapset (Clamping)
      # Böylece fare monitörün diğer ucuna gitse bile kutu grafiğin kenarında biter.
      x0_lim, x1_lim = ax.get_xlim()
      y0_lim, y1_lim = ax.get_ylim()

      # Sınırların hangisi küçük hangisi büyük emin olalım (ters eksen ihtimaline karşı)
      x_min_lim, x_max_lim = sorted([x0_lim, x1_lim])
      y_min_lim, y_max_lim = sorted([y0_lim, y1_lim])

      # Değeri sınırlar içinde tut
      x_curr = max(x_min_lim, min(x_curr, x_max_lim))
      y_curr = max(y_min_lim, min(y_curr, y_max_lim))
      # --- DÜZELTME BİTİŞ ---

      # --- Lazy Copy Mantığı (Aynen kalıyor) ---
      if selection_state["background"] is None:
            canvas.draw()
            selection_state["background"] = canvas.copy_from_bbox(ax.bbox)
            ax.draw_artist(selection_state["rect"])

      canvas.restore_region(selection_state["background"])

      # 4. Dikdörtgeni güncelle
      x0, y0 = selection_state["start_pos"]
       
      width = x_curr - x0
      height = y_curr - y0

      selection_state["rect"].set_width(width)
      selection_state["rect"].set_height(height)
      selection_state["rect"].set_xy((x0, y0))

      ax.draw_artist(selection_state["rect"])
      canvas.blit(ax.bbox)

def on_select_release(event):
      """Tık bırakma: Seçimi tamamla (Dışarıda bırakılsa bile hata vermez)."""
       
      if not selection_state["active"]:
            return

      # 1. Görsel Temizlik
      if selection_state["rect"]:
            selection_state["rect"].set_visible(False)
            selection_state["rect"].set_animated(False)
       
      selection_state["active"] = False

      if selection_state["background"] is not None:
            canvas.restore_region(selection_state["background"])
            canvas.blit(ax.bbox)
            selection_state["background"] = None

      # --- DÜZELTİLMİŞ KOORDİNAT HESABI ---
       
      # 2. Ham veriyi al
      x_end = event.xdata
      y_end = event.ydata

      # 3. Eğer fare dışarıdaysa (None ise) pikselden hesapla
      if x_end is None or y_end is None:
            try:
                  inv = ax.transData.inverted()
                  x_end, y_end = inv.transform((event.x, event.y))
            except Exception:
                  # Hesaplama hatası olursa None kalabilir, aşağıda düzelteceğiz
                  pass

      # 4. GÜVENLİK KİLİDİ (Hala None ise başlangıç noktasını kullan)
      # Bu blok sayesinde "TypeError: float - NoneType" hatası imkansız hale gelir.
      if x_end is None or y_end is None:
            x_end, y_end = selection_state["start_pos"]

      # 5. Sınırlandırma (Clamping) - Grafiğin dışına taşmaması için
      try:
            x0_lim, x1_lim = ax.get_xlim()
            y0_lim, y1_lim = ax.get_ylim()
             
            # Eksenler ters çevrilmiş olabilir, min/max garantileyelim
            x_min_lim, x_max_lim = sorted([x0_lim, x1_lim])
            y_min_lim, y_max_lim = sorted([y0_lim, y1_lim])

            # Değeri sınırlar içine hapset
            x_end = max(x_min_lim, min(x_end, x_max_lim))
            y_end = max(y_min_lim, min(y_end, y_max_lim))
      except Exception:
            # Eksen limitleri alınamazsa (çok nadir), yine başlangıç noktasına dön
            x_end, y_end = selection_state["start_pos"]

      # --- SEÇİM MANTIĞI (Hesaplamalar) ---

      x_start, y_start = selection_state["start_pos"]
       
      # Tekil Tık mı? (Mesafe hesabı artık güvenli çünkü None olma şansı yok)
      xlims = ax.get_xlim(); ylims = ax.get_ylim()
      diag = ((xlims[1]-xlims[0])**2 + (ylims[1]-ylims[0])**2)**0.5
       
      # Pisagor (Distance)
      dist = ((x_start - x_end)**2 + (y_start - y_end)**2)**0.5
       
      is_single_click = (dist < diag * 0.01)

      # Kutu sınırlarını belirle
      x_min, x_max = sorted([x_start, x_end])
      y_min, y_max = sorted([y_start, y_end])
       
      is_sector_avg_mode = (sector_combobox.get() == "Sector Avg")

      # SENARYO A: TEKİL TIKLAMA
      if is_single_click:
            # Tıklama işlemi için 'event' nesnesini kullanıyoruz.
            # event.inaxes kontrolünü burada manuel yapabiliriz veya contains'e bırakabiliriz.
            # Eğer fare dışarıdaysa contains zaten False döner.
            for sc, sub_df in scatter_points:
                  contains, ind = sc.contains(event)
                  if contains:
                        if is_sector_avg_mode:
                              lbl = sc.get_label()
                              if lbl.endswith(" Avg"):
                                    sec_name = lbl.replace(" Avg", "")
                                    key = f"SEC_AVG|{sec_name}"
                              else:
                                    continue
                        else:
                              idx = ind["ind"][0]  
                              row = sub_df.iloc[idx]
                              key = get_point_key(row, settings_state)
                         
                        if key in selection_state["selected_keys"]:
                              selection_state["selected_keys"].remove(key)
                        else:
                              selection_state["selected_keys"].add(key)
                        break  

      # SENARYO B: KUTU SEÇİMİ (BOX DRAG)
      else:
            if is_sector_avg_mode:
                  for sc, _ in scatter_points:
                        offsets = sc.get_offsets()
                        if len(offsets) > 0:
                              px, py = offsets[0]
                              if (x_min <= px <= x_max) and (y_min <= py <= y_max):
                                    lbl = sc.get_label()
                                    if lbl.endswith(" Avg"):
                                          sec_name = lbl.replace(" Avg", "")
                                          key = f"SEC_AVG|{sec_name}"
                                          selection_state["selected_keys"].add(key)
            else:
                  x_col_name = get_plot_x_col()
                  for sc, sub_df in scatter_points:
                        for _, row in sub_df.iterrows():
                              try: val_x = float(row[x_col_name])
                              except: val_x = float(row.get(EFFECTIVE_MRR_COL, row.get(BASE_MRR_FALLBACK_COL)))
                              val_y = float(row['MRR Growth (%)'])
                               
                              px, py = to_plot_coords(val_x, val_y)
                              key = get_point_key(row, settings_state)
                               
                              if (x_min <= px <= x_max) and (y_min <= py <= y_max):
                                    selection_state["selected_keys"].add(key)

      draw_selection_highlights()

      # Focus Lag Çözümü
      try:
            canvas.get_tk_widget().focus_set()
            root.focus_set()
      except:
            pass

def on_delete_selected(event):
      """Delete tuşu ile silme."""
      if not selection_state["selected_keys"]:
            return
       
      keys_to_remove_from_view = list(selection_state["selected_keys"])
      keys_to_add_to_manual = []

      # Eğer Sector Avg modundaysak, seçili olanlar "SEC_AVG|Teknoloji" gibi stringlerdir.
      # Bunları gerçek müşteri key'lerine çevirmemiz lazım.
      is_sector_avg_mode = (sector_combobox.get() == "Sector Avg")

      if is_sector_avg_mode:
            for sec_key in keys_to_remove_from_view:
                  if isinstance(sec_key, str) and sec_key.startswith("SEC_AVG|"):
                        sec_name = sec_key.split("|")[1]
                         
                        # O sektördeki tüm müşterileri bul
                        sec_df = df[df['Company Sector'] == sec_name]
                        for _, row in sec_df.iterrows():
                              pt_key = get_point_key(row, settings_state)
                              if pt_key not in manual_removed:
                                    keys_to_add_to_manual.append(pt_key)
                                    manual_removed.add(pt_key)
             
            if keys_to_add_to_manual:
                  undo_stack.append(('SECTOR', keys_to_add_to_manual))

      else:
            # Normal mod: Doğrudan ekle
            for key in keys_to_remove_from_view:
                  manual_removed.add(key)
                  keys_to_add_to_manual.append(key)
             
            if keys_to_add_to_manual:
                  undo_stack.append(('BATCH', keys_to_add_to_manual))
       
      selection_state["selected_keys"].clear()
      clear_selection_visuals()
       
      update_plot(sector_combobox.get(), preserve_zoom=True, fit_to_data=False)

# --- EVENT BAĞLAMALARI (BINDINGS) ---
canvas.mpl_connect("button_press_event", on_press)              # Pan Press (Güncelledik)
canvas.mpl_connect("motion_notify_event", on_motion_pan)     # Pan Motion (Güncelledik)
canvas.mpl_connect("button_release_event", on_release)        # Pan Release (Güncelledik)

canvas.mpl_connect("button_press_event", on_select_press)      # Box Press (Yeni)
canvas.mpl_connect("motion_notify_event", on_select_motion)   # Box Motion (Yeni)
canvas.mpl_connect("button_release_event", on_select_release)# Box Release (Yeni)

def invert_selection(event=None):
      """Ctrl+E: Seçimi Tersine Çevir."""
      if not scatter_points:
            return

      all_visible_keys = set()
      is_sector_avg_mode = (sector_combobox.get() == "Sector Avg")

      if is_sector_avg_mode:
            # Sektör anahtarlarını topla
            for sc, _ in scatter_points:
                  lbl = sc.get_label()
                  if lbl.endswith(" Avg"):
                        sec_name = lbl.replace(" Avg", "")
                        key = f"SEC_AVG|{sec_name}"
                        all_visible_keys.add(key)
      else:
            # Müşteri anahtarlarını topla
            for sc, sub_df in scatter_points:
                  for _, row in sub_df.iterrows():
                        key = get_point_key(row, settings_state)
                        all_visible_keys.add(key)

      current_selection = selection_state["selected_keys"]
      new_selection = all_visible_keys - current_selection
      selection_state["selected_keys"] = new_selection

      draw_selection_highlights()

# --- Kısayol Bağlamaları ---
root.bind("<Control-e>", invert_selection)
root.bind("<Control-E>", invert_selection) # Büyük harf hassasiyeti için

root.bind("<Delete>", on_delete_selected)

# Küçük bir düzeltme: Grafiğin her yenilenmesinde seçim görseli silinebilir,  
# update_plot fonksiyonunun sonuna şunu eklememiz lazım:
# Ancak mevcut update_plot içine girmeden, onu wrap eden bir yapı kullanabiliriz
# ya da manuel olarak her update_plot çağrısından sonra seçimleri sıfırlayabiliriz.
# Şimdilik kullanıcı deneyimi açısından: Grafik değişirse (filtre vs.) seçim kalsın mı?  
# Genelde veri değişirse seçim bozulabilir. En güvenlisi temizlemek.

# update_plot fonksiyonunun orijinaline dokunmadan, global bir hook gibi
# seçimleri temizleyen bir mekanizma ekleyemiyoruz kolayca.
# Bu yüzden `update_plot` çağrıldığında `selection_state["selected_keys"].clear()`  
# yapılması mantıklı olurdu ama senin koduna çok müdahale etmemek için  
# Sadece highlightları siliyorum (zaten pointler yeniden çizilince arkada kalırlar).

def _auto_clear_selection_on_change(*args):
      # Sektör değişince seçimi temizle
      selection_state["selected_keys"].clear()
      clear_selection_visuals()

ctrl_state = {"pressed": False}

def _set_ctrl_on(event):
      ctrl_state["pressed"] = True

def _set_ctrl_off(event):
      ctrl_state["pressed"] = False

# Klavye olaylarını ana pencereye bağla
root.bind("<KeyPress-Control_L>", _set_ctrl_on, add="+")
root.bind("<KeyPress-Control_R>", _set_ctrl_on, add="+")
root.bind("<KeyRelease-Control_L>", _set_ctrl_off, add="+")
root.bind("<KeyRelease-Control_R>", _set_ctrl_off, add="+")

# Pencere odağı kaybedip kazanırsa takılmayı önlemek için resetle
def _reset_ctrl_on_focus(event):
      ctrl_state["pressed"] = False

root.bind("<FocusOut>", _reset_ctrl_on_focus, add="+")
sector_combobox.bind("<<ComboboxSelected>>", _auto_clear_selection_on_change, add="+")

# =============================================================================
# SINGLE MODE KLAVYE KISAYOLU (CTRL + SHIFT)
# =============================================================================

# Tuşların durumunu takip etmek için state sözlüğü
keyboard_focus_state = {
      "active": False   # Şu an Single Mode aktif mi?
}

def _on_key_press_focus_shortcut(event):
      """Tuşa basıldığında: Sadece Shift ise Single Mode'u aç."""
       
      # 1. Arama kutusu kapalıysa çalışma
      if not settings_state.get("activate_search_box", False):
            return

      # 2. Arama kutusu boşsa çalışma (Boşken odaklanacak bir şey yok)
      if not search_var.get().strip():
            return

      # 3. Basılan tuş Shift mi? (Sol veya Sağ)
      if "shift" in event.keysym.lower():
            # Eğer zaten aktif değilse aktifleştir (Tekrar tekrar tetiklenmesin)
            if not keyboard_focus_state["active"]:
                  keyboard_focus_state["active"] = True
                   
                  # Butonu görsel olarak basılı yap
                  try: btn_focus.state(["pressed"])
                  except: pass
                   
                  # Single Mode fonksiyonunu çağır
                  _on_focus_press(None)

def _on_key_release_focus_shortcut(event):
      """Tuş bırakıldığında: Shift bırakılırsa Single Mode'u kapat."""
       
      if "shift" in event.keysym.lower():
            # Eğer aktifse kapat
            if keyboard_focus_state["active"]:
                  keyboard_focus_state["active"] = False
                   
                  # Buton görselini düzelt
                  try: btn_focus.state(["!pressed"])
                  except: pass
                   
                  # Single Mode'dan çık
                  _on_focus_release(None)

# --- Tuşları Bağla (Sadece Shift) ---
# Önceki Ctrl bağlamalarını temizlemeye gerek yok, üstüne yazmaz ama
# temiz bir başlangıç için sadece bunları eklemeniz yeterli.

root.bind("<KeyPress-Shift_L>",     _on_key_press_focus_shortcut, add="+")
root.bind("<KeyPress-Shift_R>",     _on_key_press_focus_shortcut, add="+")

root.bind("<KeyRelease-Shift_L>", _on_key_release_focus_shortcut, add="+")
root.bind("<KeyRelease-Shift_R>", _on_key_release_focus_shortcut, add="+")
# Main loop
root.mainloop()