# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

# Takvim bileşeni kontrolü
try:
    from tkcalendar import DateEntry
    _HAS_TKCALENDAR = True
except ImportError:
    DateEntry = None
    _HAS_TKCALENDAR = False

# Utils'den gerekli fonksiyonları alıyoruz
from utils import parse_number_entry, parse_optional_number, validate_float
from ui_components import center_over_parent

def show_settings_window(parent, settings_state, undo_stack, current_regression_line, license_mode_str, callbacks):
    """
    Ayarlar penceresini açar.
    
    Parametreler:
      parent: Ana pencere (root) referansı.
      settings_state: Global ayar sözlüğü.
      undo_stack: Geri alma listesi.
      current_regression_line: {'m': ..., 'b': ...} sözlüğü.
      license_mode_str: 'Inc.' veya 'Exc.' string değeri (tab kontrolü için).
      callbacks: {'on_license_filter': func, 'toggle_search': func, 'toggle_reg_btns': func, 'redraw': func}
    """

    settings_win = tk.Toplevel(parent)
    settings_win.title("Settings")
    settings_win.transient(parent)
    settings_win.grab_set()
    settings_win.focus_force()
    center_over_parent(settings_win, parent, 760, 640)

    # ========================================================================
    # 1. DEĞİŞKENLER (Variables)
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
    draw_zero_var = tk.BooleanVar(value=True)
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
    
    # Fix Regression Değişkeni
    fix_reg_var = tk.BooleanVar(value=settings_state.get("fix_regression_line", False))

    # Hata mesajı hedefi (Graph sekmesi için)
    nonlocal_error_target = {"label": None, "var": None}

    # --- Helper Functions ---

    def on_close_btn():
        try:
            settings_win.grab_release()
        except Exception:
            pass
        settings_win.destroy()

    def on_save():
        # Validasyon (Risk Cmap)
        if nonlocal_error_target["var"] is not None:
            nonlocal_error_target["var"].set("")
        
        val = 1.0
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
                if nonlocal_error_target["var"] is not None:
                    nonlocal_error_target["var"].set("Enter a valid value (0–3)")
                # Hata durumunda focus'u oraya ver (power_entry referansı aşağıda oluşacak, burada try-except ile)
                try:
                    # power_entry'ye erişim için local scope dışına bakmamız gerekebilir
                    # UI oluştururken değişkene atayacağız.
                    pass 
                except Exception:
                    pass
                return
        else:
            val = settings_state.get("risk_cmap_weight_power", 1.0)

        # Undo Stack
        undo_stack.append(('LIMIT', settings_state.copy()))

        # --- STATE GÜNCELLEME ---
        settings_state["mode"] = limit_mode.get()
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

        settings_state["reverse_effect"] = bool(reverse_var.get())
        settings_state["fixed_axis"] = bool(fixed_axis_var.get())
        
        # Fixed Center Mantığı
        if settings_state["fixed_axis"]:
            # Eğer center main.py'den gelmesi gerekiyorsa ve burada yoksa
            # Main.py tarafında halledilecek veya buraya parametre olarak center gönderilmeliydi.
            # Mevcut kodda settings_state["fixed_center"] korunuyor.
            pass 
        else:
            settings_state["fixed_center"] = None
            
        settings_state["draw_growth_zero"] = bool(draw_zero_var.get())
        settings_state["swap_axes"] = bool(swap_axes_var.get())

        # Risk Settings
        settings_state["risk_view_enabled"] = bool(risk_enabled_var.get())
        settings_state["risk_show_no"] = bool(risk_show_no_var.get())
        settings_state["risk_show_low"] = bool(risk_show_low_var.get())
        settings_state["risk_show_med"] = bool(risk_show_med_var.get())
        settings_state["risk_show_high"] = bool(risk_show_high_var.get())
        settings_state["risk_show_booked"] = bool(risk_show_booked_var.get())

        # Graph Settings
        settings_state["show_avg_labels"] = bool(show_avg_labels_var.get())
        settings_state["show_sector_counts_above_avg"] = bool(show_sector_counts_var.get())
        settings_state["activate_risk_colormap"] = bool(risk_cmap_var.get())
        settings_state["risk_cmap_weighted"] = bool(risk_cmap_weighted_var.get())
        settings_state["risk_cmap_weight_power"] = float(val)
        settings_state["activate_search_box"] = bool(search_box_var.get())
        
        # Regresyon Settings
        settings_state["show_regression_line"] = bool(regression_var.get())
        is_fixed_now = bool(fix_reg_var.get())
        settings_state["fix_regression_line"] = is_fixed_now

        if is_fixed_now:
            # Eğer sabitleme açıksa ve parametre varsa koru
            if current_regression_line.get('m') is not None:
                settings_state["fixed_regression_params"] = current_regression_line.copy()
        else:
            settings_state["fixed_regression_params"] = None
            
        if not settings_state["show_regression_line"]:
            settings_state["regression_filter"] = "none"
            # Reg filter var main.py tarafında güncellenmeli (callback ile)

        # --- Callbackleri Tetikle ---
        # 1. License Filter (Redraw yapar)
        if "on_license_filter" in callbacks:
            callbacks["on_license_filter"]()
        
        # 2. Search Bar Visibility
        if "toggle_search" in callbacks:
            callbacks["toggle_search"]()
            
        # 3. Regression Buttons Visibility
        if "toggle_reg_btns" in callbacks:
            callbacks["toggle_reg_btns"]()

        try:
            settings_win.grab_release()
        except Exception:
            pass
        settings_win.destroy()

    # ========================================================================
    # 2. ARAYÜZ OLUŞTURMA (UI Construction)
    # ========================================================================
    nb = ttk.Notebook(settings_win)

    # --- Tab 1: Limit Options ---
    tab_limit = ttk.Frame(nb); nb.add(tab_limit, text="Limit Options")
    tab_limit.columnconfigure(0, weight=1)
    tab_limit.rowconfigure(0, weight=0) # No Limit / Limit radio
    tab_limit.rowconfigure(1, weight=0) # Ranges
    tab_limit.rowconfigure(2, weight=0) # Filter by Age
    tab_limit.rowconfigure(3, weight=1) # spacer
    tab_limit.rowconfigure(4, weight=0) # Save / Close buttons

    # Radios
    radios_frame = ttk.Frame(tab_limit)
    radios_frame.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
    rb_no = ttk.Radiobutton(radios_frame, text="No Limit", value="no_limit", variable=limit_mode)
    rb_yes = ttk.Radiobutton(radios_frame, text="Limit", value="limit", variable=limit_mode)
    rb_no.grid(row=0, column=0, padx=(0, 16), pady=4, sticky="w")
    rb_yes.grid(row=0, column=1, padx=(0, 16), pady=4, sticky="w")

    # Ranges
    entries_frame = ttk.LabelFrame(tab_limit, text="Ranges", padding=8)
    vcmd = (parent.register(validate_float), "%P") # validate_float utils'den geldi
    
    entries_controls = {"e1": None, "e2": None, "e3": None, "e4": None}

    def build_entries_grid():
        for w in entries_frame.winfo_children():
            w.destroy()
        
        entries_frame.grid(row=1, column=0, sticky="we", padx=10, pady=(4, 8))

        # MRR Min
        ttk.Label(entries_frame, text="MRR Min Value:").grid(row=0, column=0, sticky="w", padx=(4,6), pady=4)
        entries_controls["e1"] = ttk.Entry(entries_frame, textvariable=mrr_min_var, width=14, justify="center", validate="key", validatecommand=vcmd)
        entries_controls["e1"].grid(row=0, column=1, sticky="w", padx=(0,10), pady=4)

        # MRR Max
        ttk.Label(entries_frame, text="MRR Max Value:").grid(row=0, column=2, sticky="w", padx=(16,6), pady=4)
        entries_controls["e2"] = ttk.Entry(entries_frame, textvariable=mrr_max_var, width=14, justify="center", validate="key", validatecommand=vcmd)
        entries_controls["e2"].grid(row=0, column=3, sticky="w", padx=(0,10), pady=4)

        # Growth Min
        ttk.Label(entries_frame, text="Growth Min (%):").grid(row=1, column=0, sticky="w", padx=(4,6), pady=4)
        entries_controls["e3"] = ttk.Entry(entries_frame, textvariable=growth_min_var, width=14, justify="center", validate="key", validatecommand=vcmd)
        entries_controls["e3"].grid(row=1, column=1, sticky="w", padx=(0,10), pady=4)

        # Growth Max
        ttk.Label(entries_frame, text="Growth Max (%):").grid(row=1, column=2, sticky="w", padx=(16,6), pady=4)
        entries_controls["e4"] = ttk.Entry(entries_frame, textvariable=growth_max_var, width=14, justify="center", validate="key", validatecommand=vcmd)
        entries_controls["e4"].grid(row=1, column=3, sticky="w", padx=(0,10), pady=4)

        for c in range(4): entries_frame.grid_columnconfigure(c, weight=0)

    def set_entries_enabled_state(enabled: bool):
        state = "normal" if enabled else "disabled"
        for key in ("e1","e2","e3","e4"):
            w = entries_controls.get(key)
            if w is not None:
                try: w.configure(state=state)
                except: pass

    def update_entries_visibility(*_):
        if not entries_controls["e1"]:
            build_entries_grid()
        set_entries_enabled_state(limit_mode.get() == "limit")

    update_entries_visibility()
    limit_mode.trace_add("write", lambda *args: update_entries_visibility())

    # Filter by Age
    age_frame = ttk.LabelFrame(tab_limit, text="Filter by Age", padding=8)
    age_frame.grid(row=2, column=0, sticky="w", padx=10, pady=(4, 8))

    rb_age_01 = ttk.Radiobutton(age_frame, text="(0-1)", value="0-1", variable=age_filter_var)
    rb_age_02 = ttk.Radiobutton(age_frame, text="(0-2)", value="0-2", variable=age_filter_var)
    rb_age_12 = ttk.Radiobutton(age_frame, text="(1-2)", value="1-2", variable=age_filter_var)
    rb_age_cur = ttk.Radiobutton(age_frame, text="(0-Current)", value="0-Current", variable=age_filter_var)

    rb_age_01.grid (row=0, column=0, padx=(4, 10), pady=2, sticky="w")
    rb_age_02.grid (row=0, column=1, padx=(0, 10), pady=2, sticky="w")
    rb_age_12.grid (row=0, column=2, padx=(0, 10), pady=2, sticky="w")
    rb_age_cur.grid(row=0, column=3, padx=(0, 4), pady=2, sticky="w")

    chk_divide_age = ttk.Checkbutton(age_frame, text="Divide by Age", variable=divide_by_age_var)
    chk_divide_age.grid(row=1, column=0, columnspan=4, sticky="w", padx=(4, 0), pady=(6, 2))

    # Buttons Tab 1
    btns1 = ttk.Frame(tab_limit)
    btns1.grid(row=4, column=0, sticky="ew", padx=10, pady=10)
    btns1.columnconfigure(0, weight=1); btns1.columnconfigure(1, weight=1)
    ttk.Button(btns1, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
    ttk.Button(btns1, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

    # --- Tab 2: License Options ---
    tab_license = ttk.Frame(nb); nb.add(tab_license, text="License Options")
    tab_license.columnconfigure(0, weight=1); tab_license.rowconfigure(0, weight=1); tab_license.rowconfigure(1, weight=0)
    lic_inner = ttk.Frame(tab_license, padding=10); lic_inner.grid(row=0, column=0, sticky="nsew")
    reverse_cb = ttk.Checkbutton(lic_inner, text="Reverse effect", variable=reverse_var)
    reverse_cb.grid(row=0, column=0, sticky="w", padx=2, pady=2)
    
    btns2 = ttk.Frame(tab_license); btns2.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
    btns2.columnconfigure(0, weight=1); btns2.columnconfigure(1, weight=1)
    ttk.Button(btns2, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
    ttk.Button(btns2, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

    # --- Tab 3: Axis Settings ---
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

    # --- Tab 4: Customer Risk ---
    tab_risk = ttk.Frame(nb); nb.add(tab_risk, text="Customer Risk")
    tab_risk.columnconfigure(0, weight=1); tab_risk.rowconfigure(0, weight=1); tab_risk.rowconfigure(1, weight=0)
    risk_inner = ttk.Frame(tab_risk, padding=10); risk_inner.grid(row=0, column=0, sticky="nsew")
    
    cb_pad_y = 6
    risk_master_cb = ttk.Checkbutton(risk_inner, text="Show Risk Statement", variable=risk_enabled_var)
    risk_master_cb.grid(row=0, column=0, sticky="w", padx=2, pady=cb_pad_y)
    
    risk_opts = ttk.LabelFrame(risk_inner, text="Show / Hide by Risk", padding=8)
    risk_opts.grid(row=1, column=0, sticky="nw", padx=2, pady=cb_pad_y)
    
    cb_no = ttk.Checkbutton(risk_opts, text="Show NO RISK", variable=risk_show_no_var)
    cb_low = ttk.Checkbutton(risk_opts, text="Show LOW RISK", variable=risk_show_low_var)
    cb_med = ttk.Checkbutton(risk_opts, text="Show MEDIUM RISK", variable=risk_show_med_var)
    cb_hi = ttk.Checkbutton(risk_opts, text="Show HIGH RISK", variable=risk_show_high_var)
    cb_booked = ttk.Checkbutton(risk_opts, text="Show BOOKED CHURN", variable=risk_show_booked_var)
    
    cb_no.grid(row=0, column=0, sticky="w", padx=4, pady=cb_pad_y)
    cb_low.grid(row=1, column=0, sticky="w", padx=4, pady=cb_pad_y)
    cb_med.grid(row=2, column=0, sticky="w", padx=4, pady=cb_pad_y)
    cb_hi.grid(row=3, column=0, sticky="w", padx=4, pady=cb_pad_y)
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

    # --- Tab 5: Graph Settings ---
    tab_graph = ttk.Frame(nb); nb.add(tab_graph, text="Graph Settings")
    tab_graph.columnconfigure(0, weight=1)
    tab_graph.rowconfigure(0, weight=1)
    tab_graph.rowconfigure(1, weight=0)
    graph_inner = ttk.Frame(tab_graph, padding=10); graph_inner.grid(row=0, column=0, sticky="nsew")
    cb_pad_y = 6

    chk_avg_labels = ttk.Checkbutton(graph_inner, text="Show sector name under AVG points", variable=show_avg_labels_var)
    chk_avg_labels.grid(row=0, column=0, sticky="w", padx=2, pady=cb_pad_y)

    chk_sector_counts = ttk.Checkbutton(graph_inner, text="Show sector customer counts above AVG points", variable=show_sector_counts_var)
    chk_sector_counts.grid(row=1, column=0, sticky="w", padx=2, pady=cb_pad_y)

    chk_risk_cmap = ttk.Checkbutton(graph_inner, text="Activate customer risk color map", variable=risk_cmap_var)
    chk_risk_cmap.grid(row=2, column=0, sticky="w", padx=2, pady=cb_pad_y)

    chk_risk_weighted = ttk.Checkbutton(graph_inner, text="Distance-weighted quadrant colors", variable=risk_cmap_weighted_var)
    chk_risk_weighted.grid(row=3, column=0, sticky="w", padx=2, pady=cb_pad_y)

    weight_power_label = ttk.Label(graph_inner, text="Weight power (0–3):")
    weight_power_label.grid(row=4, column=0, sticky="w", padx=2, pady=cb_pad_y)
    power_entry = ttk.Entry(graph_inner, width=8, textvariable=risk_cmap_power_var, justify="center", validate="key", validatecommand=vcmd)
    power_entry.grid(row=4, column=0, sticky="e", padx=8, pady=cb_pad_y)

    chk_search_box = ttk.Checkbutton(graph_inner, text="Activate search box", variable=search_box_var)
    chk_search_box.grid(row=5, column=0, sticky="w", padx=2, pady=cb_pad_y)

    chk_regression = ttk.Checkbutton(graph_inner, text="Show regression line", variable=regression_var)
    chk_regression.grid(row=6, column=0, sticky="w", padx=2, pady=cb_pad_y)

    chk_fix_reg = ttk.Checkbutton(graph_inner, text="Fix Regression Line", variable=fix_reg_var)
    chk_fix_reg.grid(row=7, column=0, sticky="w", padx=2, pady=6)

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
        except Exception: pass
    apply_risk_cmap_controls_state()
    risk_cmap_var.trace_add("write", apply_risk_cmap_controls_state)

    btns5 = ttk.Frame(tab_graph); btns5.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
    btns5.columnconfigure(0, weight=1); btns5.columnconfigure(1, weight=1)
    ttk.Button(btns5, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
    ttk.Button(btns5, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

    # --- Tab 6: Churn Settings ---
    tab_churn = ttk.Frame(nb); nb.add(tab_churn, text="Churn Settings")
    tab_churn.columnconfigure(0, weight=1)
    tab_churn.rowconfigure(0, weight=1)
    tab_churn.rowconfigure(1, weight=0)
    churn_inner = ttk.Frame(tab_churn, padding=10); churn_inner.grid(row=0, column=0, sticky="nsew")

    ttk.Label(churn_inner, text="Start Date:").grid(row=0, column=0, sticky="w", padx=2, pady=(4, 6))
    if _HAS_TKCALENDAR:
        churn_start_entry = DateEntry(churn_inner, width=16, date_pattern="yyyy-mm-dd", state="readonly", showweeknumbers=False, firstweekday="monday", locale="tr_TR")
    else:
        churn_start_var = tk.StringVar(value="")
        churn_start_entry = ttk.Entry(churn_inner, textvariable=churn_start_var, width=18, justify="center")
    churn_start_entry.grid(row=0, column=1, sticky="w", padx=(6, 12), pady=(4, 6))

    ttk.Label(churn_inner, text="End Date:").grid(row=1, column=0, sticky="w", padx=2, pady=(0, 8))
    if _HAS_TKCALENDAR:
        churn_end_entry = DateEntry(churn_inner, width=16, date_pattern="yyyy-mm-dd", state="readonly", showweeknumbers=False, firstweekday="monday", locale="tr_TR")
    else:
        churn_end_var = tk.StringVar(value="")
        churn_end_entry = ttk.Entry(churn_inner, textvariable=churn_end_var, width=18, justify="center")
    churn_end_entry.grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(0, 8))

    try:
        tab_index = nb.index(tab_churn)
        nb.tab(tab_index, state=("normal" if settings_state.get("churn_enabled", True) else "disabled"))
    except: pass

    btns6 = ttk.Frame(tab_churn); btns6.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
    btns6.columnconfigure(0, weight=1); btns6.columnconfigure(1, weight=1)
    ttk.Button(btns6, text="Close", command=on_close_btn).grid(row=0, column=0, sticky="w")
    ttk.Button(btns6, text="Save", command=on_save).grid(row=0, column=1, sticky="e")

    # --- License Tab State Check ---
    def update_tab_state_check(*_):
        try:
            nb.tab(1, state="normal" if license_mode_str == "Exc." else "disabled")
        except: pass
    update_tab_state_check()

    nb.pack(fill="both", expand=True, padx=12, pady=12)

    # --- Focus Sentinel ---
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