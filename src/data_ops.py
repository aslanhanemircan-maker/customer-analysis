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
    
def get_limit_removed_keys(df, settings_state):
    """
    Limit modunda (Min/Max filtreleri) gizlenmesi gereken noktaların
    key'lerini (set olarak) döndürür.
    """
    if settings_state.get("mode") != "limit":
        return set()
    
    mrr_min = settings_state.get("mrr_min", None)
    mrr_max = settings_state.get("mrr_max", None)
    gy_min = settings_state.get("growth_min", None)
    gy_max = settings_state.get("growth_max", None)
    
    s = set()
    for _, row in df.iterrows():
        # get_point_key bu dosyanın içinde olduğu için direkt çağırabiliriz
        key = get_point_key(row, settings_state)
        
        # key yapısı: (index, x_val, y_val)
        # Eğer tuple 3 elemanlıysa parçala, değilse (nadiren) atla
        if isinstance(key, tuple) and len(key) == 3:
            idx, x, y = key
            
            out = False
            if mrr_min is not None and x < mrr_min: out = True
            if mrr_max is not None and x > mrr_max: out = True
            if gy_min is not None and y < gy_min:   out = True
            if gy_max is not None and y > gy_max:   out = True
            
            if out:
                s.add(key)
                
    return s  

def is_risk_allowed(risk_val, settings_state):
    """
    Bir müşterinin risk durumuna göre gösterilip gösterilmeyeceğine karar verir.
    """
    # Gelen değer boşsa veya tanımsızsa string'e çevirip temizle
    val = (str(risk_val or "")).strip().upper()
    
    if val == "NO RISK":        return settings_state.get("risk_show_no", True)
    if val == "LOW RISK":       return settings_state.get("risk_show_low", True)
    if val == "MEDIUM RISK":    return settings_state.get("risk_show_med", True)
    if val == "HIGH RISK":      return settings_state.get("risk_show_high", True)
    if val == "BOOKED CHURN":   return settings_state.get("risk_show_booked", True)
    
    # Tanımsız bir risk durumu varsa varsayılan olarak göster
    return True

def apply_churn_filters(df_in, settings_state):
    """
    Include / Show Only durumuna göre churn satırlarını filtreler.
    """
    # CHURN_COL sabitine bu dosya içinden erişilebilir
    if CHURN_COL not in df_in.columns:
        return df_in

    churn_enabled = settings_state.get("churn_enabled", True)
    show_only = settings_state.get("show_only_churn", False)

    # Büyük/küçük harf duyarlılığı olmasın diye upper() kullanıyoruz
    col = df_in[CHURN_COL].astype(str).str.upper()

    if show_only:
        # Sadece Churn olanları göster
        return df_in[col.eq("CHURN")]
    elif not churn_enabled:
        # Churn olanları gizle (Sadece aktifler)
        return df_in[~col.eq("CHURN")]
    else:
        # Hepsini göster
        return df_in

# --- Age Constants ---
AGE_MODE_0_CURRENT = "0-Current"
AGE_MODE_0_1       = "0-1"
AGE_MODE_0_2       = "0-2"
AGE_MODE_1_2       = "1-2"

def get_age_filter_mode(settings_state):
    """Settings içindeki aktif yaş filtresi modu."""
    return settings_state.get("age_filter_mode", AGE_MODE_0_CURRENT)

def apply_age_filters(df_in, settings_state):
    """
    Yaş filtresine göre satırları filtreler:
    - 0-Current: hiç filtre yok (herkes görünür)
    - 0-1: DoesCustomerCompleteItsFirstYear = Yes olmalı
    - 0-2 / 1-2: DoesCustomersCompleteItsSecondYear = Yes olmalı
    """
    mode = get_age_filter_mode(settings_state)
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

def get_growth_source_col_for_age_mode(settings_state, df_columns):
    """
    Aktif yaş filtresine göre hangi growth kolonunu kullanacağımızı döndürür.
    """
    mode = get_age_filter_mode(settings_state)

    if mode == AGE_MODE_0_1:
        return "MRR Growth (0-1)"
    elif mode == AGE_MODE_0_2:
        return "MRR Growth (0-2)"
    elif mode == AGE_MODE_1_2:
        return "MRR Growth(1-2)"
    else:
        # 0-Current
        if "MRR Growth (0-today)" in df_columns:
            return "MRR Growth (0-today)"
        return "MRR Growth"

def get_base_mrr_col_for_age_mode(settings_state, df_columns):
    """
    X eksenindeki baz MRR kolonunu yaş moduna göre seç.
    """
    mode = get_age_filter_mode(settings_state)

    if mode == AGE_MODE_0_1:
        return "First Year Ending MRR"
    elif mode in (AGE_MODE_0_2, AGE_MODE_1_2):
        return "Second Year Ending MRR"
    else:
        # 0-Current
        return CURRENT_MRR_COL if CURRENT_MRR_COL in df_columns else BASE_MRR_FALLBACK_COL

def get_exc_mrr_col_for_age_mode(settings_state):
    """
    Exc. License MRR için yaş moduna göre kaynak sütun.
    """
    mode = get_age_filter_mode(settings_state)

    if mode == AGE_MODE_0_1:
        return "First Year Ending Exc. License MRR"
    elif mode in (AGE_MODE_0_2, AGE_MODE_1_2):
        return "Second Year Ending Exc. License MRR"
    else:
        return "Exc. License MRR"    

def is_risk_view_active(selected_sector, df_columns, settings_state):
    """
    Risk görünümü aktif mi kontrol eder.
    Sadece belirli bir sektör seçiliyken ve checkbox açıksa True döner.
    """
    if RISK_COL not in df_columns:
        return False
    # "Sector Avg" veya "All" dışındaki bir sektör seçiliyse ve ayar açıksa
    return (settings_state.get("risk_view_enabled", False) and selected_sector not in ("Sector Avg", "All"))

def calculate_churn_stats(df_sub):
    """
    Verilen DataFrame alt kümesi için Churn istatistiklerini hesaplar.
    Dönüş: (churned_mrr, total_mrr, ratio_pct, churn_count)
    """
    if df_sub is None or len(df_sub) == 0:
        return 0.0, 0.0, 0.0, 0

    # Churn Maskesi Oluştur
    if CHURN_COL in df_sub.columns:
        churn_col = df_sub[CHURN_COL].astype(str).str.upper()
        churn_mask = churn_col.eq("CHURN")
    else:
        churn_mask = pd.Series(False, index=df_sub.index)

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