import dash
from dash import dcc, html, Input, Output, State, ctx, ALL, MATCH
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import os
import numpy as np
import math

# --- IMPORTS ---
from data_ops import load_and_clean_data
from analysis import calculate_regression_line

# --- SETUP ---
base_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_dir, "assets", "data.xlsx")

if os.path.exists(file_path):
    global_df = load_and_clean_data(file_path)
else:
    global_df = pd.DataFrame(columns=['Customer', 'Effective MRR', 'MRR Growth (%)', 'Company Sector', 'Churn'])

# --- MATPLOTLIB STYLE PALETTE (Matte) ---
MATTE_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', 
    '#bcbd22', '#17becf', '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', 
    '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'
]

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# --- HELPER: FILTER DATA ---
def filter_data(df, age_mode, min_mrr, max_mrr, min_growth, max_growth, show_churn, swap_axes, removed_list):
    dff = df.copy()
    
    # 0. Remove Deleted Points
    if removed_list:
        mask = ~dff['Customer'].isin(removed_list) & ~dff['Company Sector'].isin(removed_list)
        dff = dff[mask]

    # 1. Age Filter
    x_col = 'Effective MRR'
    y_col = 'MRR Growth (%)'
    
    if age_mode == '0-1':
        if 'DoesCustomerCompleteItsFirstYear' in dff.columns:
            dff = dff[dff['DoesCustomerCompleteItsFirstYear'].astype(str).str.upper() == 'YES']
        x_col = 'First Year Ending MRR'
        y_col = 'MRR Growth (0-1)'
    elif age_mode == '0-2':
        if 'DoesCustomersCompleteItsSecondYear' in dff.columns:
            dff = dff[dff['DoesCustomersCompleteItsSecondYear'].astype(str).str.upper() == 'YES']
        x_col = 'Second Year Ending MRR'
        y_col = 'MRR Growth (0-2)'
    elif age_mode == '1-2':
        if 'DoesCustomersCompleteItsSecondYear' in dff.columns:
            dff = dff[dff['DoesCustomersCompleteItsSecondYear'].astype(str).str.upper() == 'YES']
        x_col = 'Second Year Ending MRR'
        y_col = 'MRR Growth(1-2)'

    if x_col not in dff.columns: x_col = 'Effective MRR'
    if y_col not in dff.columns: y_col = 'MRR Growth (%)'

    if age_mode != '0-Current': 
        dff[y_col] = dff[y_col].astype(float) * 100
    
    dff['Plot_X'] = dff[x_col].astype(float)
    dff['Plot_Y'] = dff[y_col].astype(float)

    # 2. Limits
    if min_mrr is not None: dff = dff[dff['Plot_X'] >= min_mrr]
    if max_mrr is not None: dff = dff[dff['Plot_X'] <= max_mrr]
    if min_growth is not None: dff = dff[dff['Plot_Y'] >= min_growth]
    if max_growth is not None: dff = dff[dff['Plot_Y'] <= max_growth]

    # 3. Churn
    if not show_churn and 'Churn' in dff.columns: 
        dff = dff[dff['Churn'] != 'Churn']

    # 4. Axis Swap
    if swap_axes:
        dff['Plot_X'], dff['Plot_Y'] = dff['Plot_Y'], dff['Plot_X']
        x_title, y_title = "Growth (%)", "Effective MRR ($)"
    else:
        x_title, y_title = "Effective MRR ($)", "Growth (%)"
        
    return dff, x_title, y_title

# --- HELPER: SMART POSITIONS ---
def calculate_smart_positions(df, x_col, y_col, threshold=0.15):
    if len(df) < 2: return ['top center'] * len(df)
    x = df[x_col].values
    y = df[y_col].values
    x_norm = (x - x.min()) / (x.max() - x.min() + 1e-9)
    y_norm = (y - y.min()) / (y.max() - y.min() + 1e-9)
    positions = []
    for i in range(len(df)):
        dx = x_norm - x_norm[i]
        dy = y_norm - y_norm[i]
        dists = np.sqrt(dx**2 + dy**2)
        neighbor_indices = np.where((dists > 0) & (dists < threshold))[0]
        if len(neighbor_indices) == 0:
            positions.append('top center')
            continue
        avg_dx = np.mean(dx[neighbor_indices])
        avg_dy = np.mean(dy[neighbor_indices])
        angle = math.atan2(-avg_dy, -avg_dx)
        deg = math.degrees(angle)
        if -45 <= deg <= 45: pos = 'middle right'
        elif 45 < deg <= 135: pos = 'top center'
        elif -135 <= deg < -45: pos = 'bottom center'
        else: pos = 'middle left'
        positions.append(pos)
    return positions

# ==================== HANDBOOK MODAL (TURKISH CONTENT, TOGGLE IMAGES) ====================
handbook_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("📘 Kullanım Kılavuzu & Rehber")),
    dbc.ModalBody([
        dbc.Tabs([
            # TAB 1: GRAFİK OKUMA
            dbc.Tab(label="Grafik & Eksenler", children=[
                html.Div(className="p-3", children=[
                    html.H4("Analitik Düzlemi Anlamak", className="text-primary"),
                    html.P("Bu panel, müşteri portföyünü MRR (Gelir) ve Büyüme Hızı eksenlerinde görselleştirir."),
                    html.Ul([
                        html.Li([html.B("X Ekseni (Yatay):"), " Müşterinin MRR değerini gösterir. Sağa gidildikçe müşteri büyür."]),
                        html.Li([html.B("Y Ekseni (Dikey):"), " Müşterinin büyüme hızını (%) gösterir. Yukarı gidildikçe büyüme hızı artar."]),
                        html.Li([html.B("Merkez Çizgileri:"), " Mavi ve Turuncu çizgiler, o an ekranda görünen müşterilerin ortalamasını temsil eder."])
                    ]),
                    
                    # Görsel Toggle Butonu 1
                    dbc.Button("📸 Görseli Göster / Gizle", id={'type': 'hb-btn', 'index': 1}, color="info", outline=True, size="sm", className="mb-2"),
                    dbc.Collapse(
                        html.Img(src=app.get_asset_url('hb_graph_reading.png'), style={'width': '100%', 'border': '1px solid #ddd', 'borderRadius': '5px'}),
                        id={'type': 'hb-img', 'index': 1}, is_open=False
                    ),

                    html.Hr(),
                    html.H5("Dört Bölge (Quadrant) Analizi"),
                    html.P("Merkez çizgileri grafiği 4 ana bölgeye ayırır:"),
                    html.Ul([
                        html.Li("Sağ Üst (+,+): Yıldız Müşteriler (Yüksek MRR, Yüksek Büyüme)"),
                        html.Li("Sol Üst (-,+): Potansiyeller (Düşük MRR, Yüksek Büyüme)"),
                        html.Li("Sağ Alt (+,-): Nakit İnekleri (Yüksek MRR, Düşük Büyüme - Riskli Olabilir)"),
                        html.Li("Sol Alt (-,-): Düşük Performans")
                    ])
                ])
            ]),
            
            # TAB 2: REGRESYON
            dbc.Tab(label="Regresyon", children=[
                html.Div(className="p-3", children=[
                    html.H4("Regresyon Analizi (Trend Çizgisi)", className="text-primary"),
                    html.P("Kırmızı kesik çizgi, verilerinizin genel eğilimini matematiksel olarak gösterir."),
                    
                    # Görsel Toggle Butonu 2
                    dbc.Button("📸 Görseli Göster / Gizle", id={'type': 'hb-btn', 'index': 2}, color="info", outline=True, size="sm", className="mb-2"),
                    dbc.Collapse(
                        html.Img(src=app.get_asset_url('hb_regression.png'), style={'width': '100%'}),
                        id={'type': 'hb-img', 'index': 2}, is_open=False
                    ),

                    html.Br(), html.Br(),
                    html.P("Bu çizgi, müşteri büyüklüğü ile büyüme hızı arasındaki ilişkiyi (korelasyonu) anlamanızı sağlar:"),
                    html.Ul([
                        html.Li("Aşağı Eğimli Çizgi: Müşteriler büyüdükçe (MRR arttıkça) büyüme hızları yavaşlıyor demektir (Doğal Büyüme)."),
                        html.Li("Yukarı Eğimli Çizgi: Büyük müşteriler, küçüklerden daha hızlı büyüyor demektir (Pozitif İvme).")
                    ])
                ])
            ]),

            # TAB 3: AYARLAR
            dbc.Tab(label="Ayarlar & Filtreler", children=[
                html.Div(className="p-3", children=[
                    html.H4("Dashboard Ayarları", className="text-primary"),
                    html.P("Gelişmiş filtrelere sol paneldeki 'Settings' butonu ile ulaşabilirsiniz."),
                    
                    html.H6("1. Yaşa Göre Filtreleme (Cohort)"),
                    html.P("Müşterinin yaşam döngüsündeki belirli bir zaman dilimine odaklanmanızı sağlar (Örn: Sadece ilk yıl performansı)."),
                    
                    # Görsel Toggle Butonu 3
                    dbc.Button("📸 Görseli Göster / Gizle", id={'type': 'hb-btn', 'index': 3}, color="info", outline=True, size="sm", className="mb-2"),
                    dbc.Collapse(
                        html.Img(src=app.get_asset_url('hb_settings_limit.png'), style={'width': '80%', 'display': 'block', 'margin': 'auto'}),
                        id={'type': 'hb-img', 'index': 3}, is_open=False
                    ),

                    html.Br(),
                    html.H6("2. Limitler (Ranges)"),
                    html.P("Belirli bir aralığa odaklanmak için Min/Max değerleri girebilirsiniz (Örn: Sadece %10 üzeri büyüyenler).")
                ])
            ]),

            # TAB 4: CHURN
            dbc.Tab(label="Churn Analizi", children=[
                html.Div(className="p-3", children=[
                    html.H4("Churn (Kayıp) Görselleştirmesi", className="text-danger"),
                    html.P("Normalde grafik sadece aktif müşterileri gösterir."),
                    html.Ul([
                        html.Li("Kaybedilen müşterileri görmek için 'Include Churned Customers' kutucuğunu işaretleyin."),
                        html.Li("Veri setinizde 'Churn' sütunu varsa bu müşteriler analizde görünür."),
                        html.Li("Excel çıktısı aldığınızda da bu filtreler geçerli olur.")
                    ]),
                    
                    # Görsel Toggle Butonu 4
                    dbc.Button("📸 Görseli Göster / Gizle", id={'type': 'hb-btn', 'index': 4}, color="info", outline=True, size="sm", className="mb-2"),
                    dbc.Collapse(
                        html.Img(src=app.get_asset_url('hb_churn_view.png'), style={'width': '100%'}),
                        id={'type': 'hb-img', 'index': 4}, is_open=False
                    ),
                ])
            ]),
            
            # TAB 5: KONTROLLER (SİLME & GERİ ALMA ANLATIMI)
            dbc.Tab(label="Kontroller", children=[
                html.Div(className="p-3", children=[
                    html.H4("Fare & Etkileşim", className="text-primary"),
                    html.Ul([
                        html.Li([html.B("Sol Tık + Sürükle:"), " Grafiği kaydırır (Pan)."]),
                        html.Li([html.B("Fare Tekerleği:"), " Yakınlaşır / Uzaklaşır (Zoom)."]),
                        html.Li([html.B("Üzerine Gelme (Hover):"), " Detayları gösterir."]),
                    ]),
                    html.Hr(),
                    html.H4("Nokta Silme İşlemi (Delete Mode)", className="text-danger"),
                    html.P("Grafikten bir müşteri veya sektörü çıkarmak için:"),
                    html.Ul([
                        html.Li("Sol paneldeki 'Delete Mode' anahtarını açın."),
                        html.Li("Grafik üzerindeki herhangi bir noktaya tıklayın."),
                        html.Li("Nokta anında kaybolacaktır."),
                        html.Li("Hata yaparsanız 'Undo Last' butonuna basarak geri alabilirsiniz.")
                    ]),
                    html.P("Not: Delete Mode açıkken grafik üzerinde Pan (Sürükleme) yapamazsınız, sadece tıklama çalışır.", className="text-muted font-italic")
                ])
            ])
        ])
    ]),
    dbc.ModalFooter(
        dbc.Button("Kapat", id="close-handbook", className="ms-auto", n_clicks=0)
    ),
], id="handbook-modal", is_open=False, size="xl")

# --- SETTINGS MODAL ---
settings_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("Dashboard Settings")),
    dbc.ModalBody([
        html.H6("Filter by Age (Cohort Analysis)", className="text-primary"),
        dcc.RadioItems(
            id='age-filter-mode',
            options=[
                {'label': ' All Time (0-Current)', 'value': '0-Current'},
                {'label': ' First Year (0-1)', 'value': '0-1'},
                {'label': ' Second Year (0-2)', 'value': '0-2'},
                {'label': ' Year 1 to 2 (1-2)', 'value': '1-2'}
            ],
            value='0-Current',
            labelStyle={'display': 'block', 'marginBottom': '5px'}
        ),
        html.Hr(),
        html.H6("Value Limits (Range)", className="text-primary"),
        dbc.Row([
            dbc.Col([html.Label("Min MRR:"), dbc.Input(id='limit-mrr-min', type='number', placeholder="0")], width=6),
            dbc.Col([html.Label("Max MRR:"), dbc.Input(id='limit-mrr-max', type='number', placeholder="Max")], width=6)
        ], className="mb-2"),
        dbc.Row([
            dbc.Col([html.Label("Min Growth (%):"), dbc.Input(id='limit-growth-min', type='number', placeholder="Min")], width=6),
            dbc.Col([html.Label("Max Growth (%):"), dbc.Input(id='limit-growth-max', type='number', placeholder="Max")], width=6)
        ]),
        html.Hr(),
        html.H6("Axis Settings", className="text-primary"),
        dbc.Checklist(
            id='axis-options',
            options=[{'label': ' Swap Axes (X <-> Y)', 'value': 'swap'}],
            value=[],
            switch=True
        )
    ]),
    dbc.ModalFooter(
        dbc.Button("Close", id="close-settings", className="ms-auto", n_clicks=0)
    ),
], id="settings-modal", is_open=False, size="lg")

# --- LAYOUT ---
app.layout = dbc.Container([
    dcc.Store(id='removed-points-store', data=[]), 
    dcc.Store(id='right-click-signal', data=0),
    dcc.Store(id='dummy-store'),                    
    settings_modal,
    handbook_modal,
    dcc.Download(id="download-dataframe-xlsx"),

    dbc.Row([dbc.Col(html.H2("MRR Growth Analytical Plane", className="text-center text-dark mb-4"), width=12)]),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Control Panel", className="font-weight-bold bg-light"),
                dbc.CardBody([
                    html.Label("View Mode:"),
                    dcc.Dropdown(
                        id='sector-dropdown',
                        options=[
                            {'label': '📍 Sector Averages (Summary)', 'value': 'Sector Avg'},
                            {'label': '--- All Customers ---', 'value': 'All'}
                        ] + [{'label': i, 'value': i} for i in sorted(global_df['Company Sector'].dropna().unique())],
                        value='Sector Avg',
                        clearable=False
                    ),
                    html.Hr(),
                    
                    # DELETE MODE SWITCH & UNDO
                    html.Div([
                        html.Label("Interaction Mode:", className="fw-bold"),
                        dbc.Checklist(
                            id='delete-mode-switch',
                            options=[{'label': ' 🗑️ Delete Mode (Click to Remove)', 'value': 'active'}],
                            value=[],
                            switch=True,
                            className="text-danger mb-2"
                        ),
                        dbc.Button("↩️ Undo Last", id="undo-btn", color="warning", size="sm", outline=True, className="w-100 mb-3", disabled=True),
                    ], className="p-2 bg-light border rounded mb-3"),

                    dbc.Button("⚙️ Open Settings", id="open-settings", color="secondary", outline=True, className="w-100 mb-2"),
                    dbc.Button("📘 Handbook", id="open-handbook", color="info", outline=True, className="w-100 mb-2"),
                    dbc.Button("📗 Export Excel", id="btn-export", color="success", outline=True, className="w-100 mb-3"),

                    html.Label("Quick Filters:"),
                    dbc.Checklist(
                        id='analysis-tools',
                        options=[
                            {'label': ' Show Regression Line', 'value': 'show_reg'},
                            {'label': ' Include Churned Customers', 'value': 'show_churn'}
                        ],
                        value=['show_churn'],
                        switch=True
                    ),
                    html.Hr(),
                    html.Div(id='stats-card', className="p-3 bg-white border rounded", children=[
                        html.H5(id='total-cust-lbl', children="..."),
                        html.P(id='total-mrr-lbl', children="...", className="text-success font-weight-bold"),
                        html.Small(id='age-info-lbl', className="text-muted")
                    ])
                ])
            ], className="h-100 shadow-sm border-0")
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(
                        id='main-graph', style={'height': '80vh'}, 
                        config={'displayModeBar': True, 'displaylogo': False, 'scrollZoom': True, 'toImageButtonOptions': {'format': 'png', 'scale': 2}}
                    )
                ], className="p-1")
            ], className="shadow-sm border-0")
        ], width=9)
    ])
], fluid=True, className="py-3", style={'backgroundColor': '#eaeaea', 'minHeight': '100vh'})

# --- JAVASCRIPT HOOKS (SAĞ TIK ENGELLEME & CTRL+Z) ---
app.clientside_callback(
    """
    function(id) {
        // 1 saniye bekle ki grafik yüklensin
        setTimeout(function() {
            var graphDiv = document.getElementById('main-graph');
            if (graphDiv) {
                // Sağ Tıkı Yakala
                graphDiv.oncontextmenu = function(e) {
                    e.preventDefault(); // Tarayıcı menüsünü engelle
                    // Python'a sinyal gönder (Timestamp ile benzersiz yapıyoruz)
                    window.dash_clientside.set_props('right-click-signal', {data: Date.now()});
                    return false;
                };
            }
        }, 1000);

        // Klavye Dinleyicisi (Ctrl + Z)
        document.addEventListener('keydown', function(event) {
            if ((event.ctrlKey || event.metaKey) && event.key === 'z') {
                // Undo sinyali gönder
                window.dash_clientside.set_props('right-click-signal', {data: 'UNDO_' + Date.now()});
            }
        });

        return window.dash_clientside.no_update;
    }
    """,
    Output('dummy-store', 'data'), 
    Input('main-graph', 'id')
)

# --- CALLBACKS ---

@app.callback(
    Output("settings-modal", "is_open"),
    [Input("open-settings", "n_clicks"), Input("close-settings", "n_clicks")],
    [State("settings-modal", "is_open")],
)
def toggle_settings(n1, n2, is_open):
    if n1 or n2: return not is_open
    return is_open

@app.callback(
    Output("handbook-modal", "is_open"),
    [Input("open-handbook", "n_clicks"), Input("close-handbook", "n_clicks")],
    [State("handbook-modal", "is_open")],
)
def toggle_handbook(n1, n2, is_open):
    if n1 or n2: return not is_open
    return is_open

# --- HANDBOOK IMAGE COLLAPSE CALLBACK (PATTERN MATCHING) ---
@app.callback(
    Output({'type': 'hb-img', 'index': MATCH}, 'is_open'),
    Input({'type': 'hb-btn', 'index': MATCH}, 'n_clicks'),
    State({'type': 'hb-img', 'index': MATCH}, 'is_open'),
)
def toggle_handbook_images(n, is_open):
    if n: return not is_open
    return is_open

@app.callback(
    [Output('removed-points-store', 'data'),
     Output('undo-btn', 'disabled')],
    [Input('right-click-signal', 'data'),  # JS Sinyali (Sağ tık veya Ctrl+Z)
     Input('undo-btn', 'n_clicks')],       # Fiziksel Undo butonu
    [State('main-graph', 'hoverData'),     # Fare şu an neyin üzerinde?
     State('removed-points-store', 'data')]
)
def global_interaction_handler(signal, btn_clicks, hoverData, removed_list):
    ctx_trigger = ctx.triggered_id
    removed_list = removed_list or []

    # 1. Undo İşlemi (Buton veya Ctrl+Z)
    is_undo_signal = isinstance(signal, str) and signal.startswith("UNDO_")
    
    if ctx_trigger == 'undo-btn' or (ctx_trigger == 'right-click-signal' and is_undo_signal):
        if removed_list:
            removed_list.pop() # Son silineni listeden çıkar
        return removed_list, (len(removed_list) == 0)

    # 2. Silme İşlemi (Sağ Tık)
    # Sinyal sayıysa (Timestamp) sağ tık yapılmıştır.
    is_right_click = isinstance(signal, (int, float)) and signal > 0
    
    if is_right_click and hoverData:
        point = hoverData['points'][0]
        # 'text' içinde müşteri veya sektör adı var
        target_name = point.get('text') 
        
        if target_name and target_name not in removed_list:
            removed_list.append(target_name)
            
    return removed_list, (len(removed_list) == 0)

# --- MAIN GRAPH UPDATE ---
@app.callback(
    [Output('main-graph', 'figure'),
     Output('total-cust-lbl', 'children'),
     Output('total-mrr-lbl', 'children'),
     Output('age-info-lbl', 'children')],
    [Input('sector-dropdown', 'value'),
     Input('analysis-tools', 'value'),
     Input('age-filter-mode', 'value'), 
     Input('limit-mrr-min', 'value'),
     Input('limit-mrr-max', 'value'),
     Input('limit-growth-min', 'value'),
     Input('limit-growth-max', 'value'),
     Input('axis-options', 'value'),
     Input('removed-points-store', 'data')] # <--- 1. YENİ INPUT EKLENDİ
)
def update_dashboard(selected_mode, tools_list, age_mode, min_mrr, max_mrr, min_growth, max_growth, axis_opts, removed_list): # <--- 2. PARAMETRE EKLENDİ
    swap_axes = 'swap' in axis_opts
    show_churn = 'show_churn' in tools_list
    
    # 3. filter_data ÇAĞRISI GÜNCELLENDİ (removed_list eklendi)
    dff, x_title, y_title = filter_data(
        global_df, age_mode, min_mrr, max_mrr, min_growth, max_growth, show_churn, swap_axes, removed_list
    )

    total_count = len(dff)
    total_mrr_sum = dff['Plot_X'].sum() if not swap_axes else dff['Plot_Y'].sum()

    fig = go.Figure()
    unique_sectors = sorted(dff['Company Sector'].dropna().unique())
    color_map = {sec: MATTE_COLORS[i % len(MATTE_COLORS)] for i, sec in enumerate(unique_sectors)}

    # --- SCENARIO 1: SECTOR AVG ---
    if selected_mode == 'Sector Avg':
        avg_df = dff.groupby('Company Sector').agg({
            'Plot_X': 'mean', 'Plot_Y': 'mean', 'Customer': 'count'
        }).reset_index()
        
        smart_positions = calculate_smart_positions(avg_df, 'Plot_X', 'Plot_Y')
        avg_df['TextPos'] = smart_positions

        for _, row in avg_df.iterrows():
            sec_name = row['Company Sector']
            fig.add_trace(go.Scatter(
                x=[row['Plot_X']], y=[row['Plot_Y']],
                mode='markers+text', name=sec_name, text=[sec_name],
                textposition=row['TextPos'], 
                textfont=dict(color='#333333', size=11, family="Arial"), 
                marker=dict(
                    size=[row['Customer']], sizemode='area',
                    sizeref=2.*max(avg_df['Customer'])/(60.**2), sizemin=8,
                    color=color_map.get(sec_name, '#333'),
                    line=dict(width=1, color='#333333'), opacity=0.9
                ),
                customdata=[row['Customer']],
                hovertemplate="<b>%{text}</b><br>Count: %{customdata}<br>X: %{x:,.0f}<br>Y: %{y:.2f}<extra></extra>",
                legendgroup="group_sectors", legendgrouptitle_text="🏢 SECTORS"
            ))
        title_text = f"Sector Averages ({age_mode})"

    # --- SCENARIO 2: CUSTOMERS ---
    else:
        if selected_mode != 'All': dff = dff[dff['Company Sector'] == selected_mode]
        fig.add_trace(go.Scatter(
            x=dff['Plot_X'], y=dff['Plot_Y'], mode='markers', name='Customers',
            marker=dict(
                size=12, color=dff['Plot_Y'], colorscale='Twilight',
                showscale=True, opacity=0.8, line=dict(width=1, color='#555555')
            ),
            text=dff['Customer'], customdata=dff['Company Sector'],
            hovertemplate="<b>%{text}</b><br>Sector: %{customdata}<br>X: %{x:,.0f}<br>Y: %{y:.2f}<extra></extra>"
        ))
        title_text = f"{selected_mode} Analysis ({age_mode})"

    # --- REGRESSION ---
    if 'show_reg' in tools_list and len(dff) > 1:
        calc_df = avg_df if selected_mode == 'Sector Avg' else dff
        reg_result = calculate_regression_line(calc_df, 'Plot_X')
        m = reg_result.get('m')
        b = reg_result.get('b')
        if m is not None:
            x_range = np.linspace(calc_df['Plot_X'].min(), calc_df['Plot_X'].max(), 100)
            y_range = m * x_range + b
            fig.add_trace(go.Scatter(
                x=x_range, y=y_range, mode='lines', name=f'Trend ({m:.4f})',
                line=dict(color='#d62728', width=2.5, dash='dash'),
                legendgroup="group_indicators", legendgrouptitle_text="📊 INDICATORS"
            ))

    # --- LAYOUT ---
    mean_x = dff['Plot_X'].mean()
    mean_y = dff['Plot_Y'].mean()
    
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='lines', name=f'Avg MRR (${mean_x:,.0f})',
        line=dict(color='#1f77b4', width=2), 
        legendgroup="group_indicators", legendgrouptitle_text="📊 INDICATORS"
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='lines', name=f'Avg Growth (%{mean_y:.2f})',
        line=dict(color='#ff7f0e', width=2),
        legendgroup="group_indicators", legendgrouptitle_text="📊 INDICATORS"
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='lines', name='Zero Growth',
        line=dict(color='#d62728', width=2, dash='dot'),
        legendgroup="group_indicators", legendgrouptitle_text="📊 INDICATORS"
    ))

    fig.update_layout(
        title=dict(text=title_text, x=0.5, font=dict(size=20, color='#333')),
        plot_bgcolor='white', paper_bgcolor='white',
        hovermode="closest", 
        # EĞER SİLME MODU AÇIKSA DRAG YAPMA (Sadece Tıklamaya İzin Ver)
        dragmode='pan', 
        xaxis=dict(title=x_title, showgrid=True, gridcolor='#e5e5e5', zeroline=False, showline=True, linecolor='#444', mirror=True),
        yaxis=dict(title=y_title, showgrid=True, gridcolor='#e5e5e5', zeroline=False, showline=True, linecolor='#444', mirror=True),
        legend=dict(
            yanchor="top", y=1, xanchor="left", x=1.02,
            bgcolor="rgba(250,250,250,0.95)", bordercolor="#d1d1d1", borderwidth=1,
            itemsizing='constant', itemclick="toggleothers", itemdoubleclick="toggle",
            font=dict(family="Segoe UI", size=12, color="#333"), groupclick="toggleitem"
        ),
        shapes=[
            dict(type="line", x0=mean_x, x1=mean_x, y0=0, y1=1, yref="paper", line=dict(color="#1f77b4", width=1.5)),
            dict(type="line", y0=mean_y, y1=mean_y, x0=0, x1=1, xref="paper", line=dict(color="#ff7f0e", width=1.5)),
            dict(type="line", y0=0, y1=0, x0=0, x1=1, xref="paper", line=dict(color="#d62728", width=1.5, dash="dot"))
        ]
    )

    return fig, f"Total Customers: {total_count}", f"Total Val: ${total_mrr_sum:,.0f}", f"Current Filter: {age_mode}"

@app.callback(
    Output("download-dataframe-xlsx", "data"),
    Input("btn-export", "n_clicks"),
    [State('sector-dropdown', 'value'), State('analysis-tools', 'value'), State('age-filter-mode', 'value'), State('limit-mrr-min', 'value'), State('limit-mrr-max', 'value'), State('limit-growth-min', 'value'), State('limit-growth-max', 'value'), State('axis-options', 'value'), State('removed-points-store', 'data')],
    prevent_initial_call=True,
)
def export_data(n_clicks, selected_mode, tools_list, age_mode, min_mrr, max_mrr, min_growth, max_growth, axis_opts, removed_list):
    if not n_clicks: return dash.no_update
    swap_axes = 'swap' in axis_opts
    show_churn = 'show_churn' in tools_list
    dff, _, _ = filter_data(global_df, age_mode, min_mrr, max_mrr, min_growth, max_growth, show_churn, swap_axes, removed_list)
    if selected_mode != 'Sector Avg' and selected_mode != 'All':
        dff = dff[dff['Company Sector'] == selected_mode]
    return dcc.send_data_frame(dff.to_excel, "Analytics_Export.xlsx", sheet_name="Data")

if __name__ == '__main__':
    app.run(debug=False, port=8052)