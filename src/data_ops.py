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