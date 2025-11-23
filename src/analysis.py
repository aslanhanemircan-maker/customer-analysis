import numpy as np
import pandas as pd

# Sklearn (K-Means için) varsa import et, yoksa hata vermesin
try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

def calculate_kmeans_labels(df_in, x_col, k=3):
    """
    Verilen DataFrame için K-Means kümeleme yapar.
    Geriye etiketleri (0, 1, 2...) döndürür.
    """
    if not _HAS_SKLEARN or len(df_in) < k:
        return None
    
    try:
        # Sadece sayısal verileri al
        # x_col: Grafikte X ekseninde hangi veri varsa (MRR veya License MRR)
        X = df_in[[x_col, 'MRR Growth (%)']].copy().fillna(0)
        
        # Ölçekleme (Normalization) şart
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        return labels
    except Exception as e:
        print(f"KMeans Error: {e}")
        return None

def calculate_pareto_mask(df_in, x_col):
    """
    MRR'ın %80'ini oluşturan müşterileri (True/False) işaretler.
    (Pareto Prensibi: Gelirin %80'i müşterilerin %20'sinden gelir)
    """
    try:
        # Büyükten küçüğe sırala
        df_sorted = df_in.sort_values(by=x_col, ascending=False)
        total_revenue = df_sorted[x_col].sum()
        
        # Kümülatif toplam
        cumsum = df_sorted[x_col].cumsum()
        
        # %80 sınırını belirle
        cutoff = total_revenue * 0.80
        
        # Maskeyi oluştur
        pareto_mask_sorted = cumsum <= cutoff
        
        # Maskeyi orijinal sıraya göre geri döndür
        return pareto_mask_sorted.reindex(df_in.index, fill_value=False)
    except Exception:
        return None

def calculate_regression_line(df_in, x_col, swap_axes=False):
    """
    Verilen veri için Lineer Regresyon (Eğim ve Kesişim) hesaplar.
    Geriye {'m': eğim, 'b': kesişim} sözlüğü döndürür.
    """
    result = {'m': None, 'b': None}
    
    if len(df_in) < 2:
        return result

    try:
        # Eksenlerin durumuna göre X ve Y verisini ayarla
        if swap_axes:
            # Y = MRR, X = Growth
            x_data = df_in['MRR Growth (%)'].astype(float).values
            y_data = df_in[x_col].astype(float).values
        else:
            # Y = Growth, X = MRR (Standart)
            x_data = df_in[x_col].astype(float).values
            y_data = df_in['MRR Growth (%)'].astype(float).values
        
        # NaN ve Sonsuz değerleri temizle
        valid_mask = ~np.isnan(x_data) & ~np.isnan(y_data) & ~np.isinf(x_data) & ~np.isinf(y_data)
        x_clean = x_data[valid_mask]
        y_clean = y_data[valid_mask]

        if len(x_clean) >= 2:
            # Polyfit (1. derece polinom = Doğru denklemi)
            m, b = np.polyfit(x_clean, y_clean, 1)
            result['m'] = m
            result['b'] = b
            
    except Exception as e:
        print(f"Regresyon Hatası: {e}")
        
    return result

def apply_regression_filter(df_in, x_col, settings_state, regression_line, regression_removed_set, swap_axes=False):
    """
    Hesaplanmış regresyon çizgisine göre dataframe'i filtreler.
    Gizlenen noktaları 'regression_removed_set' kümesine ekler.
    """
    # Circular import olmaması için get_point_key'i burada import ediyoruz
    from data_ops import get_point_key

    filter_mode = settings_state.get("regression_filter", "none")
    m = regression_line.get('m')
    b = regression_line.get('b')

    # 1. Filtre kapalıysa veya çizgi yoksa temizle ve çık
    if filter_mode == "none" or m is None or b is None:
        regression_removed_set.clear()
        return df_in

    # 2. Eksen durumuna göre X ve Y verilerini ayarla
    if swap_axes:
        # Eksenler ters (Y=MRR, X=Growth)
        x_data = df_in['MRR Growth (%)'].astype(float)
        y_data = df_in[x_col].astype(float)
    else:
        # Normal (Y=Growth, X=MRR)
        x_data = df_in[x_col].astype(float)
        y_data = df_in['MRR Growth (%)'].astype(float)
    
    # 3. Tahmini Y'yi hesapla: y_pred = m*x + b
    y_pred = m * x_data + b
    
    # 4. Maskeleme
    if filter_mode == "above":
        mask = (y_data >= y_pred)
    elif filter_mode == "below":
        mask = (y_data <= y_pred)
    else:
        mask = True 
    
    # 5. Gizlenenleri kaydet
    regression_removed_set.clear()
    
    if mask is not True:
        removed_df = df_in[~mask]
        for _, row in removed_df.iterrows():
            regression_removed_set.add(get_point_key(row, settings_state))
    
    return df_in[mask]