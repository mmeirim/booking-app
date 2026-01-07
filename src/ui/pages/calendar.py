import streamlit as st
import pandas as pd
from streamlit_calendar import calendar
from datetime import datetime
import time
from src.services.calendar_service import prepare_events, prepare_resources, generate_calendar_options, generate_color_palette, get_calendar_modes
from src.services.conflicts_service import calculate_end_hour

@st.cache_data
def get_cached_calendar_data(df_expandido, df_salas, groups, ids_em_conflito):
    colors = generate_color_palette(groups)
    events = prepare_events(df_expandido, colors, ids_em_conflito)
    resources = prepare_resources(df_salas)
    df_expandido["Data Ocorrência View"] = pd.to_datetime(df_expandido["Data Ocorrência"], dayfirst=True).dt.tz_localize(None)
    return events, resources, df_expandido

def generate_calendar_page(df_expandido: pd.DataFrame, df_salas: pd.DataFrame, conflitos: list):
    # IDs em conflito (Set é O(1) - busca instantânea)
    ids_em_conflito = set(conflitos['id_reserva1']).union(set(conflitos['id_reserva2']))
    if "last_df_view" not in st.session_state:
        st.session_state["last_df_view"] = pd.DataFrame()  # Inicializa vazio

    col1, col2, col3 = st.columns(3)
    with col1:
        mode = st.selectbox("Visualização:", get_calendar_modes(), key="calendar_view_mode")
    with col2:
        weekday_map = {
            "Segunda": 1, "Terça": 2, "Quarta": 3, 
            "Quinta": 4, "Sexta": 5, "Sábado": 6, "Domingo": 0
        }
        weekday_filter = st.selectbox("Dias da Semana:", ["Todos"] + list(weekday_map.keys()),
                                        index=0, key="calendar_start_weekday")
    with col3:
        st.space(20)
        apenas_conflitos = st.toggle("Apenas Conflitos", value=False, key="calendar_only_conflicts")
        
    col_calendario, col_lista = st.columns([0.8, 0.2])

    with col_calendario: 
        hidden_days = []   
        if weekday_filter != "Todos":
                hidden_days = [d for d in range(7) if d != weekday_map[weekday_filter]]
        
        # Cache dos eventos e recursos
        unique_groups = tuple(df_expandido['Grupo'].unique())
        events_base, resources, df_expandido = get_cached_calendar_data(df_expandido, df_salas, unique_groups, ids_em_conflito)
        calendar_options = generate_calendar_options(resources, mode)
        
        if hidden_days:
            mode = "Agenda"
            calendar_options["hiddenDays"] = hidden_days
            calendar_options["fixedWeekCount"] = False
            calendar_options["showNonCurrentDates"] = False
            calendar_options["initialView"] = "timeGrid"
            calendar_options["duration"] = {"months": 1}
            calendar_options["headerToolbar"] = {
                "left": "today prev,next",
                "center": "title",
                "right": "timeGrid,timeGridDay",}
            
        if apenas_conflitos:
            opacity_style = """
                .evento-limpo {
                    opacity: 0.15 !important;
                    filter: grayscale(80%);
                    pointer-events: none; /* Opcional: desabilita clique nos sem conflito */
                }
                .evento-conflito {
                    opacity: 1 !important;
                    z-index: 99999 !important; /* Traz os conflitos para frente */
                }
            """
        else:
            opacity_style = ""

        # Combine com seus outros estilos
        full_custom_css = f"""
            {opacity_style}
            # .fc-event-past {{
            #     opacity: 0.8;
            # }}
            .fc-event-time {{
                font-style: italic;
            }}
            .fc .fc-toolbar-title {{
                font-size: 1.1rem !important; /* Ajuste conforme necessário */
                font-weight: bold;
            }}
            .fc .fc-button {{
                font-size: 0.85rem !important; 
                padding: 4px 8px !important;
            }}
        """
            
        state = calendar(
            events=st.session_state.get("events", events_base),
            options=calendar_options,
            custom_css= full_custom_css,
            key=f"full_calendar_{mode}_{weekday_filter}_{apenas_conflitos}",
        )
        
        # st.write(state)

    with col_lista:
        # print(state["eventsSet"]["view"] if state else "No state")
              
        # --- FILTRO ULTRA-RÁPIDO ---
        if state and "eventsSet" in state and "view" in state["eventsSet"]:
            # print("ENTROU")
            # Pegamos as datas da visão atual do calendário
            v_start = pd.to_datetime(state["eventsSet"]["view"]["activeStart"]).tz_localize(None)
            v_end = pd.to_datetime(state["eventsSet"]["view"]["activeEnd"]).tz_localize(None)
            
            # print(f"VIEW RANGE: {v_start} to {v_end}, df_expandido dates from {df_expandido['Data Ocorrência View'].min()} to {df_expandido['Data Ocorrência View'].max()}")
            
            # Filtro vetorizado (muito rápido)
            # Certifique-se que 'Data Ocorrência' já foi convertida no início do script
            mask = (df_expandido['Data Ocorrência View'] >= v_start) & (df_expandido['Data Ocorrência View'] < v_end)
            df_filtrado = df_expandido.loc[mask].copy()
            
            if hidden_days:
                shown_days = set(range(7)) - set(hidden_days)
                shown_days_pd = [(d - 1) % 7 for d in shown_days]
                df_filtrado = df_filtrado[df_filtrado['Data Ocorrência View'].dt.weekday.isin(shown_days_pd)]
            
            if apenas_conflitos:
                # Filtra o dataframe mantendo apenas IDs que estão no set de conflitos
                df_filtrado = df_filtrado[df_filtrado['id_reserva'].isin(ids_em_conflito)]
            
            st.session_state["last_df_view"] = df_filtrado.sort_values(['Data Ocorrência View', 'Hora Início'])
            
        df_view = st.session_state["last_df_view"]

        # --- RENDERIZAÇÃO SEM TRAVAMENTO ---
        # Usamos um único container com scroll e limitamos a 50 itens
        # Para evitar lentidão, vamos compor o HTML/Markdown em uma lista e imprimir de uma vez
        st.space("medium")
        with st.container(height=900):
            if df_view.empty:
                st.info("Nenhum evento visível.")
            else:
                for idx, row in df_view.head(50).iterrows():
                    # Usamos o ID que você colocou no extendedProps (id_reserva)
                    id_atual = row.get('id_reserva') or row.get('id')
                    conf_pres = id_atual in ids_em_conflito
                    
                    emoji = "🔴" if conf_pres else "🟢"
                    h_fim = calculate_end_hour(row['Hora Início'], row['Hora fim'])
                    data_str = row['Data Ocorrência View'].strftime('%d/%m')
                    
                    # Markdown simplificado para evitar criar muitos objetos st.columns
                    # Isso é o que impede o navegador de travar
                    st.markdown(f"""
                    **{emoji} {row['Sala']}** | ⏰ {data_str} • {row['Hora Início']}-{h_fim}   
                    👥 {row['Grupo']} | {row['Atividade']}
                    """)
                    
                    if conf_pres:
                        st.error("⚠️ Conflito!", icon="🚨")
                    st.divider()

    # Sincroniza o estado global
    if state.get("eventsSet") is not None:
        st.session_state["events"] = state["eventsSet"]
                        