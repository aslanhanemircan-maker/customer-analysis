# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from ui_components import create_collapsible_stat_card

def build_sidebar_ui(parent, sectors_list, vars_dict, callbacks, has_sklearn):
    """
    Sağ yan paneli (Sidebar) inşa eder ve dinamik widget referanslarını döndürür.
    
    Parametreler:
      parent: Sidebar'ın içine yerleşeceği ana frame (sidebar frame)
      sectors_list: Sektör listesi (combobox için)
      vars_dict: BooleanVar ve StringVar'ları içeren sözlük
      callbacks: Butonlara/Checkboxlara atanacak fonksiyonlar
      has_sklearn: Scikit-learn yüklü mü? (Analytics paneli için)
      
    Dönüş:
      widgets: { 'total_label': ..., 'sector_combobox': ..., vb. }
    """
    widgets = {}

    # --- ÜST KISIM: KONTROLLER ---
    controls_frame = ttk.Frame(parent)
    controls_frame.grid(row=0, column=0, sticky="nsew")
    
    # 1. Sektör Seçimi
    lbl_select = tk.Label(controls_frame, text="Select Sector:")
    lbl_select.pack(anchor="w", padx=10, pady=(0, 5))

    sector_options = ["Sector Avg"] + list(sectors_list) + ["All"]
    sector_combobox = ttk.Combobox(controls_frame, values=sector_options, state="readonly")
    sector_combobox.current(0)
    sector_combobox.pack(fill="x", padx=10, pady=(0, 15))
    
    # Callback bağlama
    if "on_sector_change" in callbacks:
        sector_combobox.bind("<<ComboboxSelected>>", callbacks["on_sector_change"])
    
    widgets["sector_combobox"] = sector_combobox

    # 2. ACTIVE CUSTOMERS KARTI
    frame_active, lbl_total, lbl_mrr, lbl_sec_list = create_collapsible_stat_card(
        controls_frame, title_bg="#e6f3ff"
    )
    frame_active.pack(fill="x", padx=10, pady=(0, 10))
    
    widgets["frame_active_stats"] = frame_active
    widgets["total_label"] = lbl_total
    widgets["total_mrr_label"] = lbl_mrr
    widgets["sector_count_label"] = lbl_sec_list

    # 3. CHURN STATISTICS KARTI
    frame_churn, lbl_churn_cust, lbl_churn_total, lbl_churn_list = create_collapsible_stat_card(
        controls_frame, title_bg="#ffe6e6"
    )
    frame_churn.pack(fill="x", padx=10, pady=(0, 10))
    
    widgets["frame_churn_stats"] = frame_churn
    widgets["churn_customer_label"] = lbl_churn_cust
    widgets["churn_total_label"] = lbl_churn_total
    widgets["churn_sector_label"] = lbl_churn_list

    # Spacer
    bottom_spacer = ttk.Frame(controls_frame)
    bottom_spacer.pack(fill="both", expand=True)

    # --- ORTA KISIM: CHURN OPTIONS ---
    churn_frame = ttk.LabelFrame(parent, text="Churn Options", padding=8)
    churn_frame.grid(row=1, column=0, sticky="sew", padx=10, pady=(0, 6))
    churn_frame.grid_columnconfigure(0, weight=1)
    
    churn_ratio_label = ttk.Label(
        churn_frame, 
        text="", 
        font=("Arial", 11, "bold"), 
        justify="left"
    )
    churn_ratio_label.grid(row=0, column=0, sticky="w", padx=4, pady=(0, 4))
    
    # Main.py'nin erişebilmesi için widget sözlüğüne ekle
    widgets["churn_ratio_label"] = churn_ratio_label

    # Churn Ratio (Mini label in frame)
    mini_ratio_lbl = ttk.Label(churn_frame, text="", font=("Arial", 11, "bold"), justify="left")
    mini_ratio_lbl.grid(row=0, column=0, sticky="w", padx=4, pady=(0, 4))
    widgets["mini_churn_ratio_label"] = mini_ratio_lbl # İsim çakışmasın diye mini dedik

    # Checkboxlar
    churn_cb = ttk.Checkbutton(
        churn_frame, text="Include Churned Customers", 
        variable=vars_dict["churn_enabled"], command=callbacks.get("on_churn_toggle")
    )
    churn_cb.grid(row=1, column=0, sticky="w", padx=4, pady=(0, 2))

    churn_only_cb = ttk.Checkbutton(
        churn_frame, text="Show Only Churned Customers", 
        variable=vars_dict["churn_only"], command=callbacks.get("on_only_churn_toggle")
    )
    churn_only_cb.grid(row=2, column=0, sticky="w", padx=4, pady=(0, 2))

    # --- ALT KISIM: ANALYTICS PANEL ---
    analytics_frame = ttk.LabelFrame(parent, text="Advanced Analytics (Beta)", padding=8)
    analytics_frame.grid(row=3, column=0, sticky="sew", padx=10, pady=(10, 6))

    chk_marg = ttk.Checkbutton(
        analytics_frame, text="Show Marginal Histograms", 
        variable=vars_dict["an_marginal"], command=callbacks.get("apply_analytics")
    )
    chk_marg.grid(row=0, column=0, sticky="w", padx=2, pady=2)

    lbl_modes = ttk.Label(analytics_frame, text="AI Analysis Mode:", font=("Segoe UI", 9, "bold"))
    lbl_modes.grid(row=1, column=0, sticky="w", padx=2, pady=(6,2))

    rb_none = ttk.Radiobutton(analytics_frame, text="None (Standard View)", value="none", 
                              variable=vars_dict["an_mode"], command=callbacks.get("apply_analytics"))
    rb_kmeans = ttk.Radiobutton(analytics_frame, text="K-Means Clustering (3 Groups)", value="kmeans", 
                                variable=vars_dict["an_mode"], command=callbacks.get("apply_analytics"))
    rb_pareto = ttk.Radiobutton(analytics_frame, text="Pareto Analysis (Top %20)", value="pareto", 
                                variable=vars_dict["an_mode"], command=callbacks.get("apply_analytics"))

    rb_none.grid(row=2, column=0, sticky="w", padx=10)
    rb_kmeans.grid(row=3, column=0, sticky="w", padx=10)
    rb_pareto.grid(row=4, column=0, sticky="w", padx=10)

    if not has_sklearn:
        rb_kmeans.configure(state="disabled", text="K-Means (sklearn not found)")

    # Layout ayarları
    controls_frame.grid_rowconfigure(8, weight=1)
    controls_frame.grid_columnconfigure(0, weight=1)

    # EKSİK OLAN PARÇA: controls_frame'i sözlüğe ekle
    widgets["controls_frame"] = controls_frame 

    return widgets