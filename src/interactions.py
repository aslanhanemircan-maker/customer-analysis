def handle_scroll_event(event, ax, update_plot_callback):
    """
    Mouse tekerleği ile zoom yapma mantığı.
    """
    # Zoom faktörü (Hız)
    base_scale = 1.1
    if getattr(event, "button", "") == 'up':
        factor = 1 / base_scale
    elif getattr(event, "step", 0) > 0:
        factor = 1 / base_scale
    else:
        factor = base_scale

    # Mouse'un olduğu yer (Merkez)
    xdata = event.xdata
    ydata = event.ydata

    # Eğer mouse grafik dışındaysa, merkeze zoom yap
    if xdata is None or ydata is None:
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        xdata = (x0 + x1) / 2
        ydata = (y0 + y1) / 2

    # Mevcut limitler
    cur_xlim = ax.get_xlim()
    cur_ylim = ax.get_ylim()

    # Yeni limitleri hesapla (Mouse merkezli zoom)
    new_width = (cur_xlim[1] - cur_xlim[0]) * factor
    new_height = (cur_ylim[1] - cur_ylim[0]) * factor

    rel_x = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
    rel_y = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])

    ax.set_xlim([xdata - new_width * (1 - rel_x), xdata + new_width * rel_x])
    ax.set_ylim([ydata - new_height * (1 - rel_y), ydata + new_height * rel_y])

    # Callback fonksiyonunu çağırarak grafiği çizdir
    if update_plot_callback:
        update_plot_callback()

def handle_pan_press(event, pan_state, ctrl_pressed, selection_active, ax):
    """
    Sol tık ile sürükleme işlemini başlatır.
    Eğer Ctrl basılıysa veya seçim yapılıyorsa çalışmaz.
    """
    # Ctrl basılıysa Pan yapma (Seçim modudur)
    if ctrl_pressed:
        return False

    # Sadece sol tık ve grafik içi
    if event.button == 1 and event.inaxes == ax:
        pan_state["active"] = True
        pan_state["last"] = (event.x, event.y)
        return True # Pan başladı sinyali
    return False

def handle_pan_release(event, pan_state, update_plot_callback):
    """
    Sürükleme işlemini bitirir ve grafiği günceller.
    """
    if not pan_state["active"]:
        return

    if event.button == 1:
        pan_state["active"] = False
        pan_state["last"] = None
        
        # Pan bitti, grafiği en temiz haliyle tekrar çiz (Callback)
        if update_plot_callback:
            update_plot_callback()

def handle_pan_motion(event, pan_state, ax, canvas, ctrl_pressed):
    """
    Mouse hareket ettikçe grafiği kaydırır.
    """
    # Pan aktif değilse veya mouse eksen dışındaysa çık
    if not (pan_state["active"] and pan_state["last"] and event.inaxes == ax):
        return

    # Sürükleme esnasında sonradan CTRL'ye basılırsa durdur
    if ctrl_pressed:
        return

    # Piksel farkını hesapla
    dx_pixels = event.x - pan_state["last"][0]
    dy_pixels = event.y - pan_state["last"][1]
    pan_state["last"] = (event.x, event.y)

    # Mevcut limitleri al
    x0_l, x1_l = ax.get_xlim()
    y0_l, y1_l = ax.get_ylim()
    x_range = (x1_l - x0_l)
    y_range = (y1_l - y0_l)

    # Canvas boyutlarını al (Tkinter widget üzerinden)
    w = max(1, canvas.get_tk_widget().winfo_width())
    h = max(1, canvas.get_tk_widget().winfo_height())
    
    # Yeni limitleri hesapla (Ters orantılı kaydırma)
    dx = -dx_pixels / w * x_range
    dy = -dy_pixels / h * y_range

    ax.set_xlim(x0_l + dx, x1_l + dx)
    ax.set_ylim(y0_l + dy, y1_l + dy)

    # Hızlı çizim (sadece artistleri güncelle)
    canvas.draw_idle()
# src/interactions.py en altına:

from matplotlib.patches import Rectangle

def handle_select_press(event, selection_state, pan_active, ctrl_pressed, ax):
    """
    Kutu seçimini başlatır.
    """
    # Eğer Ctrl basılı DEĞİLSE seçim yapma
    if not ctrl_pressed:
        return False

    # Eğer Pan yapılıyorsa veya grafik dışındaysa çalışma
    if event.inaxes != ax or pan_active:
        return False

    selection_state["active"] = True
    selection_state["start_pos"] = (event.xdata, event.ydata)
    selection_state["background"] = None  

    # Dikdörtgeni oluştur (veya güncelle)
    if selection_state["rect"] is None:
        rect = Rectangle(
            (event.xdata, event.ydata), 0, 0,  
            linewidth=1.5,                      
            edgecolor='#1f77b4',             
            facecolor=(0.12, 0.46, 0.7, 0.2), 
            linestyle='-',                      
            zorder=2000,  
            animated=True  
        )
        ax.add_patch(rect)
        selection_state["rect"] = rect
    else:
        selection_state["rect"].set_xy((event.xdata, event.ydata))
        selection_state["rect"].set_width(0)
        selection_state["rect"].set_height(0)
        selection_state["rect"].set_visible(True)
        selection_state["rect"].set_animated(True)

    return True

def handle_select_motion(event, selection_state, ax, canvas):
    """
    Kutu çizimini sürükleyerek günceller. 
    Mouse grafik dışına çıksa bile sınırları korur (Clamping).
    """
    if not selection_state["active"] or selection_state["rect"] is None:
        return

    # 1. Koordinatları Al
    x_curr, y_curr = event.xdata, event.ydata

    # 2. Eğer mouse grafik dışındaysa (None ise), Pikselden hesapla
    if x_curr is None or y_curr is None:
        try:
            # Ekran piksellerini (event.x, event.y) Veri koordinatına çevir
            inv = ax.transData.inverted()
            x_curr, y_curr = inv.transform((event.x, event.y))
        except Exception:
            pass

    # 3. Eğer hala None ise (çok nadir), işlem yapma
    if x_curr is None or y_curr is None:
        return

    # 4. Sınırlandırma (Clamping)
    # Grafiğin şu anki X ve Y sınırlarını al
    x0_lim, x1_lim = ax.get_xlim()
    y0_lim, y1_lim = ax.get_ylim()

    # Eksenler ters olabilir, o yüzden min/max ile sırala
    x_min_bound, x_max_bound = sorted([x0_lim, x1_lim])
    y_min_bound, y_max_bound = sorted([y0_lim, y1_lim])

    # Değeri sınırlar içine hapset
    x_curr = max(x_min_bound, min(x_curr, x_max_bound))
    y_curr = max(y_min_bound, min(y_curr, y_max_bound))

    # 5. Çizim (Lazy Copy)
    if selection_state["background"] is None:
        canvas.draw()
        selection_state["background"] = canvas.copy_from_bbox(ax.bbox)
        ax.draw_artist(selection_state["rect"])

    canvas.restore_region(selection_state["background"])

    # Dikdörtgeni güncelle
    x0, y0 = selection_state["start_pos"]
    width = x_curr - x0
    height = y_curr - y0

    selection_state["rect"].set_width(width)
    selection_state["rect"].set_height(height)
    selection_state["rect"].set_xy((x0, y0))

    ax.draw_artist(selection_state["rect"])
    canvas.blit(ax.bbox)

def handle_select_release(event, selection_state, ax, canvas, get_point_key_func, to_plot_coords_func, scatter_points, sector_mode, settings_state):
    """
    Seçimi tamamlar. Mouse dışarıda bırakılsa bile en son kenarı kabul eder.
    """
    if not selection_state["active"]:
        return False

    # Görsel Temizlik
    if selection_state["rect"]:
        selection_state["rect"].set_visible(False)
        selection_state["rect"].set_animated(False)
    
    selection_state["active"] = False

    if selection_state["background"] is not None:
        canvas.restore_region(selection_state["background"])
        canvas.blit(ax.bbox)
        selection_state["background"] = None

    # --- BİTİŞ KOORDİNATINI HESAPLA ---
    x_end, y_end = event.xdata, event.ydata

    # Eğer mouse dışarıdaysa pikselden hesapla
    if x_end is None or y_end is None:
        try:
            inv = ax.transData.inverted()
            x_end, y_end = inv.transform((event.x, event.y))
        except:
            # Hesaplayamazsa başlangıç noktasına dön (Seçim iptal gibi olur)
            x_end, y_end = selection_state["start_pos"]

    # Sınırlandırma (Clamping) - Grafiğin dışına taşmasın
    x0_lim, x1_lim = ax.get_xlim()
    y0_lim, y1_lim = ax.get_ylim()
    x_min_bound, x_max_bound = sorted([x0_lim, x1_lim])
    y_min_bound, y_max_bound = sorted([y0_lim, y1_lim])
    
    x_end = max(x_min_bound, min(x_end, x_max_bound))
    y_end = max(y_min_bound, min(y_end, y_max_bound))

    # --- KUTU SINIRLARI ---
    x_start, y_start = selection_state["start_pos"]
    x_min, x_max = sorted([x_start, x_end])
    y_min, y_max = sorted([y_start, y_end])

    # Tekil Tık Kontrolü (Çok küçük hareketse tek tık say)
    # (Piksel bazlı değil veri bazlı mesafe, zoom seviyesine göre değişir ama yeterlidir)
    diag = ((x0_lim-x1_lim)**2 + (y0_lim-y1_lim)**2)**0.5
    dist = ((x_start - x_end)**2 + (y_start - y_end)**2)**0.5
    is_single_click = (dist < diag * 0.01) 

    swap_axes = settings_state.get("swap_axes", False)
    is_sector_avg_mode = (sector_mode == "Sector Avg")
    
    changed = False
    
    if is_single_click:
        # --- TEK TIK MANTIĞI ---
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
                    key = get_point_key_func(row, settings_state)
                
                if key in selection_state["selected_keys"]:
                    selection_state["selected_keys"].remove(key)
                else:
                    selection_state["selected_keys"].add(key)
                changed = True
                break
    else:
        # --- KUTU SEÇİMİ MANTIĞI ---
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
                            changed = True
        else:
            # Normal Müşteri Modu
            # scatter_points içindeki her dataframe'i geziyoruz
            for sc, sub_df in scatter_points:
                 for _, row in sub_df.iterrows():
                     # Noktanın key'ini ve koordinatını bul
                     key = get_point_key_func(row, settings_state)
                     
                     # get_point_key (id, x, y) döndürür
                     if isinstance(key, tuple) and len(key) == 3:
                         _, val_x, val_y = key
                         # Grafik koordinatına çevir (Swap axis varsa diye)
                         px, py = to_plot_coords_func(val_x, val_y, swap_axes)
                         
                         if (x_min <= px <= x_max) and (y_min <= py <= y_max):
                             selection_state["selected_keys"].add(key)
                             changed = True

    return changed

def handle_focus_shortcut_press(event, settings_state, search_var, keyboard_focus_state, btn_focus_widget, on_focus_press_callback):
    """
    Shift tuşuna basıldığında Single Mode'u aktif eder.
    """
    # 1. Arama kutusu kapalıysa çalışma
    if not settings_state.get("activate_search_box", False):
        return
    
    # 2. Arama kutusu boşsa çalışma (Boşken odaklanacak bir şey yok)
    # search_var bir Tkinter StringVar nesnesi mi yoksa düz string mi kontrol et
    try:
        term = search_var.get().strip()
    except AttributeError:
        term = str(search_var).strip()

    if not term:
        return

    # 3. Basılan tuş Shift mi? (Sol veya Sağ)
    if "shift" in event.keysym.lower():
        # Eğer zaten aktif değilse aktifleştir (Tekrar tekrar tetiklenmesin)
        if not keyboard_focus_state["active"]:
            keyboard_focus_state["active"] = True
            
            # Butonu görsel olarak basılı yap
            try: 
                btn_focus_widget.state(["pressed"])
            except: 
                pass
            
            # İşlemi başlat
            if on_focus_press_callback:
                on_focus_press_callback(None)

def handle_focus_shortcut_release(event, keyboard_focus_state, btn_focus_widget, on_focus_release_callback):
    """
    Shift bırakıldığında Single Mode'u kapatır.
    """
    if "shift" in event.keysym.lower():
        # Eğer aktifse kapat
        if keyboard_focus_state["active"]:
            keyboard_focus_state["active"] = False
            
            # Buton görselini düzelt
            try: 
                btn_focus_widget.state(["!pressed"])
            except: 
                pass
            
            # Single Mode'dan çık
            if on_focus_release_callback:
                on_focus_release_callback(None)
                
def update_ctrl_state(ctrl_state, is_pressed):
    """
    Ctrl tuşunun basılı olup olmadığını günceller.
    """
    ctrl_state["pressed"] = is_pressed                