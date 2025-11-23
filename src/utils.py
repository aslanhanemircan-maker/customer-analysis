import os
import sys
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk

# ========================== Windows DPI / Ölçekleme ==========================
_IS_WINDOWS = sys.platform.startswith("win")

def enable_per_monitor_dpi_awareness():
    """
    OS tarafındaki bulanık bitmap ölçeklemeyi kapatmak için uygulamayı DPI-aware yap.
    """
    if not _IS_WINDOWS:
        return
    try:
        user32 = ctypes.windll.user32
        # Windows 10+: PER_MONITOR_AWARE_V2
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
            user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
            # -4: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()   # fallback
        except Exception:
            pass

def force_baseline_scaling(root, baseline_dpi=96):
    """
    Tk'nin ölçek değerini sabit 96 DPI referansına kilitle.
    """
    try:
        root.tk.call('tk', 'scaling', float(baseline_dpi) / 72.0)   # 96/72 = 1.333...
    except Exception:
        pass

# ========================== Kaynak Yolu ==========================
def external_resource_path(*parts):
    """
    GÜNCELLENDİ: Kod 'src' klasöründe olduğu için, kaynakları bulmak adına
    bir üst klasöre (project root) çıkar.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        base = os.path.dirname(current_dir) # Bir üst klasöre çık
        
    return os.path.join(base, *parts)

# ========================== Pencere Ortalama ==========================
def center_on_screen(win, w, h, y_offset=0):
    """Splash/Toplevel her zaman ekranın tam ortasında; y_offset ile kaydırılabilir."""
    try:
        # --- Windows: bulunduğu monitörün çalışma alanına göre tam ortala ---
        if _IS_WINDOWS:
            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                            ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                            ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

            hwnd = wintypes.HWND(int(win.winfo_id()))
            MONITOR_DEFAULTTONEAREST = 2
            hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                # Çalışma alanı (taskbar hariç)
                work = mi.rcWork
                work_w = work.right - work.left
                work_h = work.bottom - work.top
                x = work.left + int((work_w - w) / 2)
                y = work.top + int((work_h - h) / 2) + int(y_offset)
                if y < 0:
                    y = 0
                win.geometry(f"{w}x{h}+{x}+{y}")
                return

        # --- Diğer platformlar: klasik merkezleme ---
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 2) + int(y_offset)
        if y < 0:
            y = 0
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass

# ========================== Splash Ekranı ==========================
def show_splash(parent_root, title_text="Loading data…", subtitle_text="Please wait a moment"):
    splash = tk.Toplevel(parent_root)
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    splash.configure(bg="#222222")

    container = tk.Frame(splash, bg="#2b2b2b", bd=0, highlightthickness=0)
    container.pack(fill="both", expand=True, padx=2, pady=2)

    panel = tk.Frame(container, bg="#2f2f2f")
    panel.pack(fill="both", expand=True, padx=18, pady=18)

    # --- OPSİYONEL LOGO ---
    logo_loaded = False
    logo_label = None
    try:
        logo_path = external_resource_path("assets", "starting_screen.png")
        if os.path.exists(logo_path):
            logo_img = tk.PhotoImage(file=logo_path)
            logo_label = tk.Label(panel, image=logo_img, bg="#2f2f2f", bd=0, highlightthickness=0)
            logo_label.image = logo_img
            logo_label.pack(anchor="center", pady=(4, 12))
            logo_loaded = True
    except Exception:
        logo_loaded = False

    lbl_title = tk.Label(panel, text=title_text, fg="#FFFFFF", bg="#2f2f2f", font=("Segoe UI", 14, "bold"))
    lbl_title.pack(anchor="center", pady=(4, 6))
    lbl_sub = tk.Label(panel, text=subtitle_text, fg="#CCCCCC", bg="#2f2f2f", font=("Segoe UI", 10))
    lbl_sub.pack(anchor="center", pady=(0, 16))

    pbar = ttk.Progressbar(panel, mode="determinate", length=320, maximum=100)
    pbar.pack(anchor="center", pady=(6, 4))
    pbar["value"] = 0

    lbl_note = tk.Label(panel, text="Preparing the canvas & analytics…", fg="#AAAAAA", bg="#2f2f2f", font=("Segoe UI", 9))
    lbl_note.pack(anchor="center", pady=(6, 6))

    # Extra yükseklik ayarı
    tk.Frame(panel, height=0, bg="#2f2f2f").pack(fill="x")

    splash.update_idletasks()
    req_w = splash.winfo_reqwidth()
    req_h = splash.winfo_reqheight()
    if logo_loaded and logo_label is not None and hasattr(logo_label, "image"):
        try:
            img_w = logo_label.image.width()
            req_w = max(req_w, img_w + 36)
        except Exception:
            pass

    center_on_screen(splash, req_w, req_h, y_offset=0)
    try:
        splash.grab_set()
    except Exception:
        pass
    splash.update_idletasks()
    splash.update()
    return splash, pbar, lbl_title, lbl_sub

def splash_set(splash, pbar, lbl_title, lbl_sub, pct=None, title=None, sub=None):
    try:
        if title is not None:
            lbl_title.config(text=title)
        if sub is not None:
            lbl_sub.config(text=sub)
        if pct is not None:
            pbar["value"] = max(0, min(100, pct))
        splash.update_idletasks()
        splash.update()
    except Exception:
        pass

def parse_number_entry(val: str) -> float:
    """
    Kullanıcı girişini (örn: '1.000,50' veya '1000.5') float'a çevirir.
    """
    s = str(val or "").strip().replace(" ", "")
    if not s:
        return 0.0
    
    neg = False
    if s.startswith(("+", "-")):
        neg = s[0] == "-"
        s = s[1:]
    
    # Hem nokta hem virgül varsa (örn: 1.000,50 -> 1000.50 yap)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    else:
        # Sadece nokta varsa ve birden fazla nokta veya garip durum yoksa
        parts = s.split(".")
        # Eğer 1.000 gibi binlik ayracı ise (son parça 3 haneli değilse ondalıktır)
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) and 1 <= len(parts[0]) <= 3:
            s = "".join(parts)
            
    try:
        val = float(s)
        return -val if neg else val
    except Exception:
        return 0.0

def parse_optional_number(val: str):
    """
    Boş string gelirse None, yoksa float döndürür.
    """
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    return parse_number_entry(s)    

def validate_float(P: str) -> bool:
    """
    Tkinter Entry widget'ı için doğrulama fonksiyonu.
    Sadece rakam, nokta, virgül, eksi ve artıya izin verir.
    """
    if P == "":
        return True
    # İzin verilen karakterler: Rakamlar ve ., -+
    return all(ch.isdigit() or ch in "., -+" for ch in P)

def maximize_main_window(win, prefer_kiosk=False):
    """Pencereyi işletim sistemine uygun şekilde tam ekran yapar."""
    try:
        if prefer_kiosk:
            win.attributes("-fullscreen", True)
            win.bind("<Escape>", lambda e: win.attributes("-fullscreen", False))
            return
        win.state("zoomed")   # Windows
        return
    except Exception:
        pass
    try:
        win.attributes("-zoomed", True)   # Linux
        return
    except Exception:
        pass
    try:
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{sw}x{sh}+0+0")
    except Exception:
        pass