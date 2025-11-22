import tkinter as tk
from tkinter import ttk

# --- GLOBAL TOOLTIP YÖNETİCİSİ ---
_tt_win = None
_tt_lbl = None

def set_tooltip(text, x_root, y_root):
    global _tt_win, _tt_lbl
    # Metin yoksa gizle
    if not text:
        if _tt_win: _tt_win.withdraw()
        return

    # Pencere yoksa oluştur (Sadece 1 kere çalışır)
    if _tt_win is None:
        _tt_win = tk.Toplevel()
        _tt_win.overrideredirect(True)            # Çerçeveyi kaldır
        _tt_win.attributes("-topmost", True) 
        _tt_win.config(bg="#ffffe0")
        _tt_lbl = tk.Label(_tt_win, bg="#ffffe0", justify="left", relief="solid", bd=1, font=("Segoe UI", 9))
        _tt_lbl.pack()

    # Metni güncelle ve farenin yanına taşı
    _tt_lbl.config(text=text)
    _tt_win.geometry(f"+{x_root + 20}+{y_root + 20}")
    _tt_win.deiconify()
    _tt_win.lift()

def center_over_parent(win, parent, w=560, h=420):
    try:
        parent.update_idletasks()
        win.update_idletasks()
        px = parent.winfo_rootx(); py = parent.winfo_rooty()
        pw = parent.winfo_width();   ph = parent.winfo_height()
        if pw <= 1 or ph <= 1:
            mx = parent.winfo_pointerx(); my = parent.winfo_pointery()
            x = int(mx - w // 2); y = int(my - h // 2)
        else:
            x = int(px + (pw - w) / 2); y = int(py + (ph - h) / 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        try:
            sw = parent.winfo_screenwidth(); sh = parent.winfo_screenheight()
            x = int((sw - w) / 2); y = int((sh - h) / 2)
            win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

def create_collapsible_stat_card(parent, title_bg="#f0f0f0"):
    """
    Başlıklar (Count/MRR) sabit, alt liste (Sektörler) açılır/kapanır bir kart oluşturur.
    Geriye (container, lbl_count, lbl_mrr, lbl_list_adapter, btn_toggle) döndürür.
    """
    # 1. Ana Kart Çerçevesi
    card_frame = tk.Frame(parent, bg="white", bd=1, relief="solid")
    
    # 2. Üst Başlık Alanı
    header_frame = tk.Frame(card_frame, bg=title_bg, padx=5, pady=5)
    header_frame.pack(fill="x")
    
    # İstatistik Label'ları
    lbl_count = tk.Label(header_frame, text="0", font=("Arial", 12, "bold"), bg=title_bg, anchor="w")
    lbl_count.pack(fill="x")
    
    lbl_mrr = tk.Label(header_frame, text="$0", font=("Arial", 10, "bold"), fg="black", bg=title_bg, anchor="w")
    lbl_mrr.pack(fill="x")
    
    # Aç/Kapa Butonu
    btn_toggle = tk.Label(header_frame, text="▼ Show Breakdown", font=("Segoe UI", 8),  
                          fg="blue", cursor="hand2", bg=title_bg, anchor="w")
    btn_toggle.pack(fill="x", pady=(4, 0))
    
    # 3. İçerik Alanı (Scrollbar ve Text barındıracak)
    content_frame = tk.Frame(card_frame, bg="white", padx=5, pady=5)
    
    # --- SCROLLBAR VE TEXT WIDGET ---
    # Scrollbar sağa yaslanacak
    scrollbar = ttk.Scrollbar(content_frame, orient="vertical")
    scrollbar.pack(side="right", fill="y")
    
    # Text widget (Label yerine bunu kullanıyoruz)
    # height=5 -> Sadece 5 satır göster
    txt_list = tk.Text(content_frame, height=5, width=30, 
                       font=("Arial", 9), bg="white", bd=0, 
                       yscrollcommand=scrollbar.set, cursor="arrow")
    txt_list.pack(side="left", fill="both", expand=True)
    
    # Scrollbar'ı Text'e bağla
    scrollbar.config(command=txt_list.yview)
    
    # Başlangıçta sadece okunabilir olsun (State disabled)
    txt_list.configure(state="disabled")

    # --- ADAPTASYON (ÖNEMLİ) ---
    # Text widget'ı normalde 'text' parametresi almaz. 
    # Bu yüzden Text widget'ına sahte bir config metodu ekliyoruz.
    
    # Orijinal configure metodunu saklayalım
    _orig_config = txt_list.config

    def custom_config(text=None, **kwargs):
        # Eğer 'text' parametresi gelirse içeriği güncelle
        if text is not None:
            txt_list.configure(state="normal") # Yazmak için kilidi aç
            txt_list.delete("1.0", "end")      # Eskiyi sil
            txt_list.insert("1.0", text)       # Yeniyi yaz
            txt_list.configure(state="disabled") # Tekrar kilitle (Read-only)
        
        # Diğer parametreleri (örn: bg, fg) orijinal metoda pasla
        if kwargs:
            _orig_config(**kwargs)

    # Metodu override et (Python'un dinamikliği sağ olsun)
    txt_list.config = custom_config
    txt_list.configure = custom_config 
    
    # --- Toggle Mantığı ---
    is_expanded = [False] 
    
    def toggle(event=None):
        if is_expanded[0]:
            content_frame.pack_forget()
            btn_toggle.config(text="▼ Show Breakdown")
            is_expanded[0] = False
        else:
            content_frame.pack(fill="both", expand=True)
            btn_toggle.config(text="▲ Hide Breakdown")
            is_expanded[0] = True
            
    btn_toggle.bind("<Button-1>", toggle)
    
    return card_frame, lbl_count, lbl_mrr, txt_list