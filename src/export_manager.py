# -*- coding: utf-8 -*-
import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox

# Diğer modüllerden gerekli fonksiyonlar
from ui_components import ask_export_scope
from data_ops import prepare_export_dataframe, get_limit_removed_keys

def run_export_workflow(parent, df, file_path_ref, settings_state, selection_state, 
                       manual_removed, license_removed, regression_removed, 
                       current_sector):
    """
    Excel dışa aktarma sürecini yönetir.
    """
    
    # 1. Seçim var mı kontrol et
    selected_keys = selection_state.get("selected_keys", set())
    selected_count = len(selected_keys)
    export_mode = "all" # Varsayılan davranış

    if selected_count > 0:
        # Seçim varsa kullanıcıya sor (Tümü mü, Sadece seçililer mi?)
        user_choice = ask_export_scope(parent, selected_count)
        if user_choice is None:
            return # İptal etti veya pencereyi kapattı
        export_mode = user_choice

    # 2. Dosya konumu seç
    try:
        initial_dir = os.path.dirname(file_path_ref) if file_path_ref else os.getcwd()
    except Exception:
        initial_dir = os.getcwd()

    default_name = "Selected_Data.xlsx" if export_mode == "selected" else "Chart_Data.xlsx"

    save_path = filedialog.asksaveasfilename(
        parent=parent,
        title="Dışa aktarılacak Excel konumunu seçin",
        defaultextension=".xlsx",
        filetypes=[("Excel Workbook", "*.xlsx")],
        initialdir=initial_dir,
        initialfile=default_name
    )
    
    if not save_path:
        return  

    try:
        # 3. Veriyi topla (prepare_export_dataframe data_ops içindedir)
        is_selected_only = (export_mode == "selected")
        
        # Gizli anahtarları topla
        current_hidden = set().union(
            manual_removed, 
            license_removed, 
            get_limit_removed_keys(df, settings_state)
        )
        current_hidden = current_hidden.union(regression_removed)
        
        data = prepare_export_dataframe(
            df, 
            settings_state, 
            current_hidden, 
            current_sector, 
            selected_keys, 
            only_selected=is_selected_only
        )

        if data.empty:
            messagebox.showwarning("Uyarı", "Dışa aktarılacak veri bulunamadı.", parent=parent)
            return

        # 4. Yaz
        try:
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                data.to_excel(writer, index=False, sheet_name="Chart Data")
        except Exception:
            # Fallback
            with pd.ExcelWriter(save_path) as writer:
                data.to_excel(writer, index=False, sheet_name="Chart Data")

    except Exception as e:
        err = tk.Toplevel(parent)
        err.title("Export error")
        # Basit ortalama (utils import etmemek için manuel yapıyoruz ya da parent'a göre)
        tk.Label(err, text="Export failed:\n"+str(e), fg="red", wraplength=350).pack(expand=True, padx=20, pady=20)
        tk.Button(err, text="Close", command=err.destroy).pack(pady=(0,10))