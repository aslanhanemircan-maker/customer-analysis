import os
import tkinter as tk
from tkinter import ttk
from utils import external_resource_path, center_on_screen

# --- GLOBAL CACHE ---
HANDBOOK_IMAGES = {}
handbook_win_ref = None

def load_handbook_image(filename, width=None):
    """
    Assets klasöründen görsel yükler, yeniden boyutlandırır (opsiyonel) ve önbelleğe alır.
    Modern görünüm için görsellerin yüksek kaliteli olması önemlidir.
    """
    if filename in HANDBOOK_IMAGES:
        return HANDBOOK_IMAGES[filename]

    path = external_resource_path("assets", filename)
    if not os.path.exists(path):
        return None

    try:
        # PIL (Pillow) kullanarak modern yeniden boyutlandırma
        # Eğer PIL yüklü değilse standart PhotoImage denenir (kalite düşebilir)
        try:
            from PIL import Image, ImageTk
            pil_img = Image.open(path)
            if width:
                # En boy oranını koruyarak yeniden boyutlandır
                aspect = pil_img.height / pil_img.width
                height = int(width * aspect)
                pil_img = pil_img.resize((width, height), Image.LANCZOS) # Yüksek kalite filtre
            
            tk_img = ImageTk.PhotoImage(pil_img)
            HANDBOOK_IMAGES[filename] = tk_img
            return tk_img
        except ImportError:
            # Fallback: Standart Tkinter (boyutlandırma yapamaz)
            tk_img = tk.PhotoImage(file=path)
            HANDBOOK_IMAGES[filename] = tk_img
            return tk_img
    except Exception:
        return None

def preload_handbook_images():
    """
    Handbook görsellerini uygulama açılırken hafızaya yükler.
    Böylece butona basıldığında bekleme yapmaz.
    """
    # Handbook içinde kullandığınız tüm dosya isimleri
    files_to_preload = [
        "hb_graph_reading.png",  
        "hb_risk_map.png",  
        "hb_regression.png",
        "hb_settings_limit.png",  
        "hb_settings_reverse.png",  
        "hb_settings_exc_mode.png",
        "hb_settings_arrows.png",  
        "hb_settings_axis.png",  
        "hb_settings_risk.png",
        "hb_settings_graph.png",  
        "hb_churn_view.png"
    ]
    
    for f in files_to_preload:
        # Genişlik (width) handbook içindekiyle aynı olmalı (850)
        # Böylece cache tam eşleşir.
        load_handbook_image(f, width=850)

def open_handbook(root_window):
    """
    Analitik Düzlem & Kullanım Kılavuzu (Scroll ve Zıplama Sorunları Giderildi)
    """
    global handbook_win_ref

    # 1. PENCERE KONTROLÜ
    if handbook_win_ref is not None and handbook_win_ref.winfo_exists():
        try:
            handbook_win_ref.deiconify()        
            handbook_win_ref.lift()              
            handbook_win_ref.focus_force()     
            return
        except Exception:
            handbook_win_ref = None

    # 2. YENİ PENCERE OLUŞTUR
    hb_win = tk.Toplevel(root_window)
    handbook_win_ref = hb_win
    
    hb_win.title("Analitik Düzlem & Kullanım Kılavuzu")
    hb_win.transient(root_window)
    
    # Pencereyi ortala
    center_on_screen(hb_win, 1000, 800)

    hb_win.bind("<Escape>", lambda e: hb_win.destroy())

    # --- Stiller ---
    style = ttk.Style()
    style.configure("Handbook.TNotebook", tabposition='nw', background="white")
    
    nb = ttk.Notebook(hb_win, style="Handbook.TNotebook")
    nb.pack(fill="both", expand=True, padx=0, pady=0)

    # --- İçerik Oluşturucu Yardımcı Fonksiyon ---
    def add_handbook_tab(title, content_segments):
        # Ana çerçeve
        frame = tk.Frame(nb, bg="white")  
        nb.add(frame, text=f" {title} ")
        
        # Grid Layout
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical")
        scrollbar.grid(row=0, column=3, sticky="ns")

        # Metin Kutusu
        txt = tk.Text(frame, wrap="word", padx=0, pady=0,  
                      font=("Segoe UI", 10), bg="white", relief="flat",
                      border=0, highlightthickness=0,
                      yscrollcommand=scrollbar.set,
                      cursor="arrow")  
        
        txt.grid(row=0, column=1, sticky="nsew", padx=0, pady=20)
        
        # Yan Boşluklar (Margin)
        tk.Frame(frame, bg="white", width=30).grid(row=0, column=0, sticky="ns")
        tk.Frame(frame, bg="white", width=20).grid(row=0, column=2, sticky="ns")

        scrollbar.config(command=txt.yview)
        
        # Taglar
        txt.tag_configure("h1", font=("Segoe UI", 18, "bold"), foreground="#2c3e50", spacing3=15, spacing1=10)
        txt.tag_configure("h2", font=("Segoe UI", 13, "bold"), foreground="#1f77b4", spacing3=10, spacing1=25)
        txt.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        txt.tag_configure("bullet", lmargin1=25, lmargin2=35, spacing1=4)
        txt.tag_configure("normal", lmargin1=5, lmargin2=5, spacing1=3)

        txt.insert("end", "\n", "normal")  

        # --- DÜZELTİLMİŞ SCROLL PROPAGATOR (AKICI SCROLL) ---
        def _propagate_scroll(event):
            """
            Görsellerin üzerindeyken çalışır. Satır (units) bazlı değil,  
            Pixel/Oran (moveto) bazlı kaydırma yaparak büyük görsellerin  
            tek seferde atlanmasını engeller.
            """
            try:
                delta = 0
                if hasattr(event, "delta") and event.delta:
                    delta = event.delta
                elif hasattr(event, "num"): # Linux uyumluluğu
                    if event.num == 4: delta = 120
                    elif event.num == 5: delta = -120
            
                if delta:
                    # Mevcut görünüm oranlarını al (0.0 - 1.0 arası)
                    cur_top, cur_bot = txt.yview()
                    view_height = cur_bot - cur_top
                    
                    # Ekran boyunun %5'i kadar kaydır (Yumuşak geçiş için ideal oran)
                    # Bu sayede görsel 1000px bile olsa satır olarak atlamaz, piksel piksel kayar.
                    scroll_step = 0.05 * view_height
                    
                    if delta > 0: # Yukarı
                        new_top = max(0.0, cur_top - scroll_step)
                    else: # Aşağı
                        new_top = min(1.0, cur_top + scroll_step)
                    
                    txt.yview_moveto(new_top)
                    
            except Exception:
                pass
            return "break" # Event'in başka yere gitmesini engelle

        img_counter = 0  

        for segment in content_segments:
            # --- TEXT TİPİ İÇERİK ---
            if segment["type"] == "text":
                lines = segment["data"].split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        txt.insert("end", "\n")
                        continue
                    
                    if line.startswith("# "):
                        txt.insert("end", line[2:] + "\n", "h1")
                    elif line.startswith("## "):
                        txt.insert("end", line[3:] + "\n", "h2")
                    elif line.startswith("- "):
                        parts = line[2:].split("**")
                        txt.insert("end", "• ", "bullet")
                        for i, part in enumerate(parts):
                            tag = "bold" if i % 2 == 1 else "bullet"
                            txt.insert("end", part, tag)
                        txt.insert("end", "\n")
                    else:
                        parts = line.split("**")
                        txt.insert("end", "", "normal")
                        for i, part in enumerate(parts):
                            tag = "bold" if i % 2 == 1 else "normal"
                            txt.insert("end", part, tag)
                        txt.insert("end", "\n")
            
            # --- IMAGE TİPİ İÇERİK ---
            elif segment["type"] == "image":
                img_file = segment.get("file")
                caption_text = segment.get("caption", "Görsel")
                
                img_counter += 1
                
                # 1. Container
                container = tk.Frame(txt, bg="white", bd=0)  

                # 2. Header
                header_frame = tk.Frame(container, bg="#f8f9fa", height=40, cursor="hand2")
                header_frame.pack(fill="x", expand=True)
                
                stripe = tk.Frame(header_frame, bg="#1f77b4", width=4)
                stripe.pack(side="left", fill="y")
                
                header_lbl = tk.Label(header_frame,  
                                      text=f"▶   Görseli Göster: {caption_text}",  
                                      font=("Segoe UI", 10, "bold"),
                                      bg="#f8f9fa", fg="#495057",
                                      anchor="w", padx=10, pady=10)
                header_lbl.pack(side="left", fill="x", expand=True)

                # 3. Content Frame
                content_frame = tk.Frame(container, bg="white", pady=10)
                
                # Görsel Yükleme
                tk_img = load_handbook_image(img_file, width=850)
                
                if tk_img:
                    img_lbl = tk.Label(content_frame, image=tk_img, bg="white", bd=0)
                    img_lbl.image = tk_img  
                    img_lbl.pack(anchor="center")
                    
                    # Yeni Scroll Bağlamaları
                    img_lbl.bind("<MouseWheel>", _propagate_scroll)
                    img_lbl.bind("<Button-4>", _propagate_scroll)
                    img_lbl.bind("<Button-5>", _propagate_scroll)
                else:
                    missing_lbl = tk.Label(content_frame,  
                                           text=f"⚠️ Dosya bulunamadı: assets/{img_file}",
                                           fg="red", bg="white")
                    missing_lbl.pack(pady=10)
                    missing_lbl.bind("<MouseWheel>", _propagate_scroll)
                    missing_lbl.bind("<Button-4>", _propagate_scroll)
                    missing_lbl.bind("<Button-5>", _propagate_scroll)

                if caption_text:
                    cap_lbl = tk.Label(content_frame, text=caption_text,  
                                       font=("Segoe UI", 9, "italic"), fg="#6c757d", bg="white")
                    cap_lbl.pack(pady=(5,0))
                    cap_lbl.bind("<MouseWheel>", _propagate_scroll)
                    cap_lbl.bind("<Button-4>", _propagate_scroll)
                    cap_lbl.bind("<Button-5>", _propagate_scroll)

                # --- DÜZELTME: ZIPLAMASIZ TOGGLE ---
                def toggle_image(e=None,  
                                 h_lbl=header_lbl,  
                                 c_frame=content_frame,  
                                 cont=container,  
                                 txt_cap=caption_text):
                    
                    is_visible = c_frame.winfo_viewable()
                    
                    if is_visible:
                        c_frame.pack_forget()
                        h_lbl.config(text=f"▶   Görseli Göster: {txt_cap}", bg="#f8f9fa", fg="#495057")
                        header_frame.config(bg="#f8f9fa")
                    else:
                        c_frame.pack(fill="x", expand=True, padx=10)
                        h_lbl.config(text=f"▼   Görseli Gizle: {txt_cap}", bg="#e7f5ff", fg="#1f77b4")
                        header_frame.config(bg="#e7f5ff")
                    
                    # Sadece boyutları güncelle, ama txt.see() YAPMA!
                    # txt.see() ekranı zorla kaydırdığı için zıplama yapar.
                    # update_idletasks yeterlidir, içerik doğal olarak aşağı itilir.
                    c_frame.update_idletasks()  
                    cont.update_idletasks()
                    
                    # Düzeltme: Focus'u pencerede tut
                    txt.focus_set()

                header_frame.bind("<Button-1>", toggle_image)
                header_lbl.bind("<Button-1>", toggle_image)
                stripe.bind("<Button-1>", toggle_image)

                for widget in (container, header_frame, header_lbl, stripe, content_frame):
                    widget.bind("<MouseWheel>", _propagate_scroll)
                    widget.bind("<Button-4>", _propagate_scroll)
                    widget.bind("<Button-5>", _propagate_scroll)

                txt.insert("end", "\n")  
                txt.window_create("end", window=container, stretch=1)
                txt.insert("end", "\n")  
        
        txt.configure(state="disabled")

    # ================= İÇERİK TANIMLARI (ORİJİNAL METİNLER) =================

    # TAB 1: GRAFİK OKUMA
    content_graph = [
        {"type": "text", "data": """# Grafik ve Eksenlerin Anlamı

Bu uygulama, müşteri portföyünü **MRR** ve **Growth** eksenlerinde görselleştirir. Her bir nokta bir müşteriyi veya bir sektör ortalamasını temsil eder.
"""},
        {"type": "text", "data": """## 1. Eksenlerin Mantığı
- **X Ekseni (Yatay):** Müşterinin MRR değerini gösterir. Sağa gidildikçe müşteri   MRR'ı artar.
- **Y Ekseni (Dikey):** Müşterinin büyüme hızını gösterir. Yukarı gidildikçe büyüme hızı artar.
- **Kesişim Noktası (Merkez):** Grafiğin ortasındaki çizgilerin kesiştiği nokta, tüm portföyün (veya filtrelenen verinin) ortalamasını gösterir.
"""},
        {"type": "image", "file": "hb_graph_reading.png",  
         "caption": "Şekil 1: Analitik düzlem. Yatay eksen MRR'ı, dikey eksen büyümeyi gösterir."},
         
        {"type": "text", "data": """## 2. Quadrant (Dört Bölge) Analizi
Merkez çizgileri grafiği 4 ana bölgeye ayırır:
- **Sağ Üst (+, +):** **"Yıldızlar"**. Hem MRR'ı hem de büyüme hızı ortalamanın üzerinde olan müşterileri temsil eder.
- **Sol Üst (-, +):** **"Potansiyeller"**. MRR'ı henüz ortalamanın altında ama çok hızlı büyüyenler.
- **Sağ Alt (+, -):** **"Nakit İnekleri"**. MRR'ı yüksek ama büyümesi ortalamadan yavaş olan müşteriler. Riskli olabilir.
- **Sol Alt (-, -):** **"Düşük Performans"**. Hem MRR'ı hem de büyüme hızı ortalamanın altında olan müşteriler.
"""},
        {"type": "image", "file": "hb_risk_map.png",  
         "caption": "Şekil 2: Dört Bölge Analizi."},
         
    ]

    # TAB 2: REGRESYON
    content_regression = [
        {"type": "text", "data": """# Regresyon Analizi (Trend Çizgisi)

Settings menüsünden veya **Ctrl+L** kısayolu ile açılan regresyon çizgisi, filtrelenen verilerin genel eğilimi matematiksel olarak hesaplar.

## Regresyon Çizgisi Nedir?
Bu çizgi, **MRR büyüklüğü ile Büyüme Oranı arasındaki ilişkiyi** (korelasyonu) gösterir.
- **Çizgi Aşağı Eğimliyse:** Müşteriler büyüdükçe (MRR arttıkça) büyüme hızları yavaşlıyor demektir (Doğal bir durumdur, "Büyümenin Bedeli").
- **Çizgi Yukarı Eğimliyse:** Büyük müşteriler, küçüklerden daha hızlı büyüyor demektir (Pozitif bir durum)

## Filtreleme Okları  
Regresyon açıldığında sağ alt köşede iki ok butonu belirir:
- **Yukarı Ok :** Sadece regresyon çizgisinin üzerinde kalan müşterileri gösterir.
- **Aşağı Ok :** Sadece regresyon çizgisinin altında kalan müşterileri gösterir.
- **Tekrar Tıklama:** Seçili oka tekrar basarsanız filtre kalkar ve tüm noktalar görünür.
"""},
        {"type": "image", "file": "hb_regression.png",  
         "caption": "Şekil 3: Regresyon çizgisi ve sağ alttaki filtre okları"}
    ]

    # TAB 3: AYARLAR
    content_settings = [
        {"type": "text", "data": """# Settings Menüsü Detayları

Ayarlar penceresindeki her bir sekmenin işlevi aşağıdadır:

## 1. Limit Options
Veri setini belirli kriterlere göre daraltmanızı sağlar.
- **Mode (Limit / No Limit):** Filtrelerin aktif olup olmayacağını seçer.
- **Ranges:** Sadece belirli bir MRR aralığındaki (ör. 1000$ - 5000$) veya Büyüme aralığındaki (ör. %10 üzeri) müşterileri görmek için kullanılır.
- **Filter by Age:**
   - **(0-Current):** Tüm müşterileri gösterir (Varsayılan).
   - **(0-1):** Sadece 1. yılını tamamlamış müşterileri baz alır. Veriler 1. yıl sonu verisine döner.
   - **(0-2):** Sadece 2. yılını tamamlamış müşterileri gösterir.
   - **(1-2):** Sadece 2. yılını tamamlamış müşterilerin 1. yıldan itibaren olan verilerini gösterir.
"""},
        {"type": "image", "file": "hb_settings_limit.png", "caption": "Şekil 4: Limit Options Ayarları"},

        {"type": "text", "data": """## 2. License Options (Exc. Modu)
**Not:** License options sekmesi, eğer license option exc. seçeneği seçili değilse erişilebilir olmaz.              
- **Reverse Effect:** Lisans filtre mantığını tersine çevirir ("X değerden büyük olanları gizle" yerine "küçük olanları gizle" yapar).
- **Sağ Paneldeki "Exc." Modu:** Lisans gelirlerini hariç tutarak saf hizmet gelirine odaklanmak içindir.
- **Show Difference Arrows:** "Exc." modundayken açılırsa, müşterinin Lisans Dahil (Inc.) halinden Lisans Hariç (Exc.) haline geçişini grafikte **oklarla** gösterir. Okun boyu, lisans gelirinin büyüklüğünü temsil eder.
"""},
        {"type": "image", "file": "hb_settings_reverse.png", "caption": "Şekil 5: License Options: Reverse Effect"},
        {"type": "image", "file": "hb_settings_exc_mode.png", "caption": "Şekil 6: Right Panel: Inc./Exc. Selection"},
        {"type": "image", "file": "hb_settings_arrows.png", "caption": "Şekil 7: Show Difference Arrows"},

        {"type": "text", "data": """## 3. Axis Settings
- **Fixed Axis:** Çeşitli filtreler uygulandığında bile merkez çizgilerinin (ortalama çizgilerinin) yerini sabitler.
- **Draw Growth=0 Line:** Büyümesi %0 olan noktaya kırmızı kesik bir çizgi çeker. Referans noktasıdır.
- **Swap Axes:** X ve Y eksenlerinin yerini değiştirir. (X=Büyüme, Y=MRR olur).
"""},
        {"type": "image", "file": "hb_settings_axis.png", "caption": "Şekil 8: Axis Settings Paneli"},

        {"type": "text", "data": """## 4. Customer Risk
- **Show Risk Statement:** Risk görünümünü genel olarak açar/kapatır.
- **Show NO/LOW/MED/HIGH:** Belirli risk gruplarını grafikten gizlemek için tikleri kaldırabilirsiniz. Örneğin sadece "HIGH RISK" müşterilere odaklanmak için diğerlerini kapatabilirsiniz.
"""},
        {"type": "image", "file": "hb_settings_risk.png", "caption": "Şekil 9: Customer Risk Paneli"},

        {"type": "text", "data": """## 5. Graph Settings
- **Show Sector Counts Above AVG Points:** "Sector Avg" modundayken, yuvarlakların üzerine o sektörde kaç müşteri olduğunu yazar (Örn: #45).
- **Activate Search Box:** Ana ekrandaki arama çubuğunu açar/kapatır.
- **Activate Customer Risk Color Map:** Aktif hale getirildiğinde dört farklı bölgenin arkaplanları o bölgedeki müşterilerin risk renklerinin ortalamasına bürünür:
- **Distance-weighted quadrant colors:** 0-3 arası değer alabilir. Girilen değere göre müşterinin ortalamaya(eksenlerin kesiştiği yer) olan uzaklığı kendi bölgesindeki renk ortalama belirleme katsayısının önemini arttırır.
- **Show Regression Line:** Grafikteki regresyon çizgisini açar/kapatır.
- **Fix Regression Line:** Regresyon çizgisini sabitler. Filtre uygulanıldığında konumunu korumaya devam eder.
"""},
        {"type": "image", "file": "hb_settings_graph.png", "caption": "Şekil 10: Graph Settings Paneli"},

    ]

    # TAB 4: KONTROLLER
    content_controls = [
        {"type": "text", "data": """# Kontroller ve Kısayollar

Uygulamayı klavye ve fare ile hızlı yönetmek için aşağıdaki yöntemleri kullanabilirsiniz.

## Fare Kullanımı
- **Sol Tık (Basılı Tutup Sürükle):** Grafiği kaydırır (Pan).
- **Ctrl + Sol Tık (Sürükle):** Kutu çizerek çoklu seçim yapar (Box Selection).
- **Sağ Tık:** Üzerine gelinen müşteriyi veya (Sector Avg modundaysanız) o sektörü analizden siler.
- **Tekerlek:** İmlecin olduğu yere yakınlaşır/uzaklaşır (Zoom).

## Klavye Kısayolları (Genel)
- **Ctrl + F (Find):** Arama çubuğunu açar/kapatır.
- **Ctrl + L (Line):** Regresyon (Trend) çizgisini açar/kapatır.
- **Ctrl + R (Reset):** Grafiği verilere otomatik sığdırır (Auto-Zoom).
- **Ctrl + Z (Undo):** Silinen noktaları geri alır.
- **Ctrl + P (Preferences):** Ayarlar penceresini açar.
- **Ctrl + G (Guide):** Bu kılavuzu açar.

## Seçim ve Odaklanma Kısayolları
- **Shift (Basılı Tut):** Sadece arama kutusu açıkken çalışır. Single Mode işlevinin kısayoludur. Tuşu bırakınca eski görünüm geri gelir.
- **Delete:** Seçili olan (etrafı yanan) noktaları grafikten siler.
- **Ctrl + E:** Seçimi tersine çevirir (Seçili olanları bırakır, seçili olmayanları seçer).

## Arama Kutusu (Search Bar) Davranışları
- **Normal Mod:** Müşteri isimlerini arar. Eşleşen müşterileri aşağıda listede gösterir. Listeden müşteri seçilirse müşterinin noktası yanar.
- **Single Mod:** Basılı tutulduğunda arama kutusunda seçili olan müşteriye odaklanıp diğer müşterileri saklar.
"""}
    ]

    # TAB 5: CHURN
    content_churn = [
        {"type": "text", "data": """# Churn (Kayıp) Analizi ve Seçenekleri

Sağ panelde bulunan **Churn Options** kutusu, kaybedilen müşterileri (Churn) analiz etmenizi sağlar.

## 1. Görünüm Seçenekleri
- **Include Churned Customers:** - Normalde grafik sadece aktif müşterileri gösterir. Bu kutucuğu işaretlerseniz, analiz havuzuna Churn olmuş müşteriler de dahil edilir.
   - Churn müşteriler grafikte **Kırmızı 'X'** işareti ile ayırt edilir.
- **Show Only Churned Customers:** - Aktif müşterileri tamamen gizler ve **sadece** kaybedilen müşterileri gösterir.
   - Kayıpların hangi bölgelerde (Quadrant) veya hangi MRR seviyelerinde yoğunlaştığını görmek için kullanılır.
"""},
        {"type": "image", "file": "hb_churn_view.png", "caption": "Şekil 11: Churn Options Paneli"},

        {"type": "text", "data": """## 2. Churn Ratio (Kayıp Oranı) Nasıl Hesaplanır?
Panelde gördüğünüz "Churn Ratio" veya "Total Churn Ratio", müşteri adedine göre değil, **Parasal Değere (MRR)** göre hesaplanır.

**Formül:**
`Churn Oranı = (Churned MRR) / (Aktif MRR + Churned MRR)`
"""}
    ]

    # Sekmeleri oluştur
    add_handbook_tab("Grafik Okuma", content_graph)
    add_handbook_tab("Regresyon Analizi", content_regression)
    add_handbook_tab("Ayarlar Detayı", content_settings)
    add_handbook_tab("Churn Seçenekleri", content_churn)
    add_handbook_tab("Kontroller & Kısayollar", content_controls)

    # Alt kısma kapat butonu
    btn_f = tk.Frame(hb_win, bg="white", padx=10, pady=10)
    btn_f.pack(fill="x", side="bottom")
    ttk.Button(btn_f, text="Kapat", style="Export.TButton", command=hb_win.destroy).pack(side="right")