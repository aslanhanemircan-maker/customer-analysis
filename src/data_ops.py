import pandas as pd
import numpy as np

# --- SABİTLER (Senin kodundan aldım) ---
CHURN_COL = 'Churn'
CHURNED_MRR_COL = 'Churned MRR'
EFFECTIVE_MRR_COL = 'Effective MRR'
CURRENT_MRR_COL = 'Current MRR'
BASE_MRR_FALLBACK_COL = 'First Year Ending MRR'
RISK_COL = 'Customer Risk'

def tr_lower(text):
    """Türkçe karakter uyumlu küçük harfe çevirme."""
    if not text:
        return ""
    text = text.replace("İ", "i").replace("I", "ı")
    return text.lower()

def load_and_clean_data(file_path):
    """
    Excel dosyasını okur, gerekli kolonları oluşturur ve temizler.
    Geriye kullanıma hazır 'df' (DataFrame) döndürür.
    """
    # 1. Dosyayı Oku
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        raise RuntimeError(f"Excel dosyası okunamadı: {e}")

    # 2. Growth Kolonunu Ayarla
    # "MRR Growth (0-today)" varsa onu al, yoksa eskisini al
    if 'MRR Growth (0-today)' in df.columns:
        df['MRR Growth (%)'] = df['MRR Growth (0-today)'] * 100
    else:
        df['MRR Growth (%)'] = df['MRR Growth'] * 100

    # 3. MRR Kaynağını Belirle (Current vs First Year)
    if CURRENT_MRR_COL in df.columns:
        base_mrr_series = df[CURRENT_MRR_COL]
    else:
        base_mrr_series = df[BASE_MRR_FALLBACK_COL]

    df[EFFECTIVE_MRR_COL] = base_mrr_series.astype(float)

    # 4. Churn Olanların MRR'ını Güncelle
    # Eğer müşteri Churn ise, 'Effective MRR' değeri 'Churned MRR' olmalı
    if (CHURN_COL in df.columns) and (CHURNED_MRR_COL in df.columns):
        churn_mask = df[CHURN_COL].astype(str).str.upper().eq("CHURN")
        df.loc[churn_mask, EFFECTIVE_MRR_COL] = df.loc[churn_mask, CHURNED_MRR_COL].astype(float)

    return df

def get_point_key(row, settings_state):
    """
    Nokta kimliği: (Index, Effective MRR, MRR Growth (%))
    """
    age_mode = settings_state.get("age_filter_mode", "0-Current")
    
    target_x = None
    target_y = None
    
    if age_mode == "0-1":
        target_x = "First Year Ending MRR"
        target_y = "MRR Growth (0-1)"
    elif age_mode == "0-2":
        target_x = "Second Year Ending MRR"
        target_y = "MRR Growth (0-2)"
    elif age_mode == "1-2":
        target_x = "Second Year Ending MRR"
        target_y = "MRR Growth(1-2)"  
        
    try:
        if target_x and target_y and target_x in row and target_y in row:
            x_val = float(row[target_x])
            y_val = float(row[target_y]) * 100.0
            return (row.name, x_val, y_val)

        # Varsayılan (0-Current)
        # data_ops içinde EFFECTIVE_MRR_COL gibi sabitler zaten tanımlı olmalı
        x = float(row.get(EFFECTIVE_MRR_COL, row.get(BASE_MRR_FALLBACK_COL)))
        y = float(row['MRR Growth (%)'])
        return (row.name, x, y)
        
    except Exception:
        return (row.name, 0.0, 0.0)