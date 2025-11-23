import pandas as pd
import numpy as np
from utils import to_plot_coords

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

def get_visible_customer_names(df, settings_state, current_sector, hidden_keys, prefix):
    """
    Arama kutusu için aday listesi oluşturur.
    - Sector Avg modu: Sektör isimlerini döndürür.
    - Diğer modlar: Görünür müşteri isimlerini döndürür.
    """
    prefix_cf = tr_lower(prefix)
    
    # --- SENARYO 1: SECTOR AVG MODU ---
    if current_sector == "Sector Avg":
        candidates = []
        if 'Company Sector' in df.columns:
            sectors = df['Company Sector'].unique()
            for sec in sectors:
                if not df[df['Company Sector'] == sec].empty:
                    candidates.append(f"{sec} Avg")
        
        return [c for c in candidates if tr_lower(c).startswith(prefix_cf)]

    # --- SENARYO 2: MÜŞTERİ ARAMA MODU ---
    # visible_df oluştur (filtrelenmiş veri)
    vis_df = df[~df.apply(lambda r: get_point_key(r, settings_state) in hidden_keys, axis=1)].copy()

    vis_df = apply_churn_filters(vis_df, settings_state)
    vis_df = apply_age_filters(vis_df, settings_state)

    if current_sector not in ("All", "Sector Avg"):
        if 'Company Sector' in vis_df.columns:
            vis_df = vis_df[vis_df['Company Sector'] == current_sector]
        
        if is_risk_view_active(current_sector, df.columns, settings_state) and (RISK_COL in vis_df.columns):
            vis_df = vis_df[vis_df[RISK_COL].astype(str).str.upper().apply(lambda val: is_risk_allowed(val, settings_state))]

    if 'Customer' not in vis_df.columns:
        return []
    
    names = vis_df['Customer'].dropna().astype(str)
    return [n for n in names if tr_lower(n).startswith(prefix_cf)]

def prepare_export_dataframe(df, settings_state, hidden_keys, selected_sector, selected_keys_set, only_selected=False):
    """
    Mevcut grafikte görünen veriyi Export için DataFrame olarak hazırlar.
    main.py içindeki _gather_current_view_dataframe fonksiyonunun mantığıdır.
    """
    x_col = EFFECTIVE_MRR_COL
    if settings_state.get("use_updated_exc_license_values", False):
        # Bu ayar sadece Exc. modunda anlamlıdır.
        # Ancak biz export alırken genellikle ne görüyorsak onu almak isteriz.
        # O yüzden güvenli liman: 'Effective MRR' veya 'Exc. License MRR' 
        # Eğer 'Exc. License MRR' veride varsa ve ayar açıksa onu seçelim.
        if 'Exc. License MRR' in df.columns:
             x_col = 'Exc. License MRR'
             
    # 2. Gizli Noktaları Filtrele
    # hidden_keys parametresi (manual_removed + license_removed + limit_removed) içermeli
    base_df = df[~df.apply(lambda r: get_point_key(r, settings_state) in hidden_keys, axis=1)].copy()

    # 3. Temel Filtreler (Churn, Age)
    base_df = apply_churn_filters(base_df, settings_state)
    base_df = apply_age_filters(base_df, settings_state)

    # 4. Kolon Ayarlamaları (Growth ve Base MRR)
    age_growth_col = get_growth_source_col_for_age_mode(settings_state, df.columns)
    if age_growth_col in base_df.columns:
        base_df['MRR Growth (%)'] = base_df[age_growth_col].astype(float) * 100.0

    age_base_mrr_col = get_base_mrr_col_for_age_mode(settings_state, df.columns)
    if age_base_mrr_col in base_df.columns:
        base_df[EFFECTIVE_MRR_COL] = base_df[age_base_mrr_col].astype(float)

    # Churn ise MRR'ı güncelle
    if (CHURN_COL in base_df.columns) and (CHURNED_MRR_COL in base_df.columns):
        churn_mask_loc = base_df[CHURN_COL].astype(str).str.upper().eq("CHURN")
        base_df.loc[churn_mask_loc, EFFECTIVE_MRR_COL] = base_df.loc[churn_mask_loc, CHURNED_MRR_COL].astype(float)

    # Exc. License MRR doldur
    exc_src = get_exc_mrr_col_for_age_mode(settings_state)
    if exc_src in base_df.columns:
        base_df['Exc. License MRR'] = base_df[exc_src].astype(float)

    # 5. Regresyon Filtresi
    # apply_regression_filter fonksiyonunu kullan (data_ops içinde mevcut)
    # Not: current_regression_line parametresini dışarıdan almadığımız için
    # basitçe "Effective MRR" üzerinden (veya seçilen x_col üzerinden) filtreleme yapar.
    # Ancak regresyonun eğimi (m, b) main.py'de olduğu için burada tam çalışmayabilir.
    # Export için regresyon filtresi "nice to have"dir. Eğer çok kritikse
    # bu fonksiyonun argümanlarına (m, b) eklenmeli. Şimdilik pas geçiyoruz (Hata vermemesi için).
    # base_df = _apply_regression_filter(base_df, x_col) # <-- Şimdilik kapalı

    # 6. Seçim Filtresi (Only Selected)
    if only_selected and selected_sector != "Sector Avg":
        if not selected_keys_set:
            return pd.DataFrame()
        
        # get_point_key data_ops içinde mevcut
        base_df = base_df[base_df.apply(lambda r: get_point_key(r, settings_state) in selected_keys_set, axis=1)]

    # 7. Merkez Hesaplama (Quadrant için)
    # fixed_axis ayarı varsa
    if settings_state.get("fixed_axis", False) and settings_state.get("fixed_center") is not None:
        eff_center_x, eff_center_y = settings_state["fixed_center"]
    else:
        if len(base_df) > 0:
            eff_center_x = base_df[x_col].astype(float).mean()
            eff_center_y = base_df['MRR Growth (%)'].astype(float).mean()
        else:
            eff_center_x = 0
            eff_center_y = 0

    # Koordinatları al (swap_axes dikkate alınarak)
    plot_cx, plot_cy = to_plot_coords(eff_center_x, eff_center_y, settings_state.get("swap_axes", False))

    # --- SENARYO A: SECTOR AVG SEÇİLİYSE ---
    if selected_sector == "Sector Avg":
        summary_rows = []
        
        # Sektörleri bul
        if 'Company Sector' in df.columns:
            sectors = df['Company Sector'].unique()
        else:
            sectors = []

        for sector in sectors:
            if only_selected:
                sec_key = f"SEC_AVG|{sector}"
                if sec_key not in selected_keys_set:
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
            
            px, py = to_plot_coords(avg_mrr, avg_growth, settings_state.get("swap_axes", False))
            
            if px >= plot_cx and py >= plot_cy:     q_str = "(+,+)"
            elif px < plot_cx and py >= plot_cy:    q_str = "(-,+)"
            elif px < plot_cx and py < plot_cy:     q_str = "(-,-)"
            else:                                   q_str = "(+,-)"

            summary_rows.append({
                "Company Sector": sector,
                "Customer Count": count,
                "Average MRR": avg_mrr,
                "Average Growth (%)": avg_growth,
                "Total MRR": total_mrr,
                "Quadrant": q_str
            })
            
        return pd.DataFrame(summary_rows)

    # --- SENARYO B: NORMAL MÜŞTERİ LİSTESİ ---
    if selected_sector != "All":
        base_df = base_df[base_df['Company Sector'] == selected_sector]
    
    # Risk Filtresi
    # is_risk_view_active ve is_risk_allowed data_ops içinde mevcut
    if is_risk_view_active(selected_sector, df.columns, settings_state) and (RISK_COL in base_df.columns):
        base_df = base_df[base_df[RISK_COL].astype(str).str.upper().apply(lambda val: is_risk_allowed(val, settings_state))]

    # Çıktı Oluştur
    out = pd.DataFrame()
    if 'Customer' in base_df.columns:
        out['Customer'] = base_df['Customer']
    if 'Company Sector' in base_df.columns:
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

    # Quadrant Hesapla (Teker teker)
    qs = []
    for xv, yv in zip(out['MRR Value'].values, out['MRR Growth (%)'].values):
        px, py = to_plot_coords(float(xv), float(yv), settings_state.get("swap_axes", False))
        if px >= plot_cx and py >= plot_cy:     qs.append("(+,+)")
        elif px < plot_cx and py >= plot_cy:    qs.append("(-,+)")
        elif px < plot_cx and py < plot_cy:     qs.append("(-,-)")
        else:                                   qs.append("(+,-)")
    out['Quadrant'] = qs
    
    return out

def get_plot_x_col(df, settings_state, license_mode_string):
    """
    X ekseninde kullanılacak kolonu belirler.
    license_mode_string: 'Exc.' veya 'Inc.' (string olarak gelir)
    """
    # Ayarlardan kontrol et: Exc. modu mu ve updated values açık mı?
    use_updated = (
        settings_state.get("use_updated_exc_license_values", False)
        and license_mode_string == "Exc."
    )
    
    updated_col = 'Exc. License MRR'
    
    # Eğer şartlar sağlanıyorsa ve kolon df'de varsa onu dön
    if use_updated and (updated_col in df.columns):
        return updated_col
    
    # Yoksa varsayılan EFFECTIVE_MRR_COL dön
    # (Not: EFFECTIVE_MRR_COL bu dosyanın yukarısında zaten tanımlıdır)
    return EFFECTIVE_MRR_COL

def get_updated_y_col_if_any(df):
    """
    Veri setinde güncellenmiş Growth kolonlarından biri varsa adını döner.
    """
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