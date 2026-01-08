import streamlit as st
import pandas as pd
from streamlit_calendar import calendar
from typing import List, Dict
from src.services.calendar_service import prepare_events, prepare_resources, generate_calendar_options, generate_color_palette, get_calendar_modes
from src.services.conflicts_service import calculate_end_hour

@st.cache_data
def get_cached_calendar_data(df_expandido, df_salas, groups, ids_em_conflito):
    colors = generate_color_palette(groups)
    events = prepare_events(df_expandido, colors, ids_em_conflito)
    resources = prepare_resources(df_salas)
    df_expandido["Data Ocorrência View"] = pd.to_datetime(df_expandido["Data Ocorrência"], dayfirst=True).dt.tz_localize(None)
    return events, resources, df_expandido

def generate_calendar_page(df_expandido: pd.DataFrame, df_salas: pd.DataFrame, conflitos:List[Dict], sugestoes: List[Dict]):
    # IDs em conflito (Set é O(1) - busca instantânea)
    ids_em_conflito = set([c['id_reserva1'] for c in conflitos]).union(set([c['id_reserva2'] for c in conflitos]))
    if "last_df_view" not in st.session_state:
        st.session_state["last_df_view"] = pd.DataFrame()  # Inicializa vazio

    # col1, col2, col3 = st.columns(3)
    # with col1:
    #     mode = st.selectbox("Visualização:", get_calendar_modes(), key="calendar_view_mode")
    # with col2:
    #     weekday_map = {
    #         "Segunda": 1, "Terça": 2, "Quarta": 3, 
    #         "Quinta": 4, "Sexta": 5, "Sábado": 6, "Domingo": 0
    #     }
    #     weekday_filter = st.selectbox("Dias da Semana:", ["Todos"] + list(weekday_map.keys()),
    #                                     index=0, key="calendar_start_weekday")
    # with col3:
    #     st.space(20)
    
    with st.container(horizontal_alignment="right"):
        with st.popover("Filtros"):
            mode = st.selectbox("Visualização:", get_calendar_modes(), key="calendar_view_mode")
            
            weekday_map = {
                "Segunda": 1, "Terça": 2, "Quarta": 3, 
                "Quinta": 4, "Sexta": 5, "Sábado": 6, "Domingo": 0
            }
            weekday_filter = st.selectbox("Dias da Semana:", ["Todos"] + list(weekday_map.keys()),
                                            index=0, key="calendar_start_weekday")
            
            group_filter = st.selectbox("Grupos:", 
                                        options=['Todas'] + sorted(df_expandido['Grupo'].unique()))
            
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
        
        print(f"Filtrando grupo: {group_filter}")
        if group_filter != "Todas":
            print(f"Filtrando grupo: {group_filter}")
            events_base = [e for e in events_base if e['extendedProps']['grupo'] == group_filter]
            st.session_state["events"] = events_base
            
        state = calendar(
            events=st.session_state.get("events", events_base),
            options=calendar_options,
            custom_css= full_custom_css,
            key=f"full_calendar_{mode}_{weekday_filter}_{apenas_conflitos}_{group_filter}",
        )
        
        # st.write(state)

    with col_lista:            
        if state and "eventsSet" in state and "view" in state["eventsSet"]:
            v_start = pd.to_datetime(state["eventsSet"]["view"]["activeStart"]).tz_localize(None)
            v_end = pd.to_datetime(state["eventsSet"]["view"]["activeEnd"]).tz_localize(None)
            
            mask = (df_expandido['Data Ocorrência View'] >= v_start) & (df_expandido['Data Ocorrência View'] < v_end)
            df_filtrado = df_expandido.loc[mask].copy()
            
            if hidden_days:
                shown_days = set(range(7)) - set(hidden_days)
                shown_days_pd = [(d - 1) % 7 for d in shown_days]
                df_filtrado = df_filtrado[df_filtrado['Data Ocorrência View'].dt.weekday.isin(shown_days_pd)]
            
            if apenas_conflitos:
                df_filtrado = df_filtrado[df_filtrado['id_reserva'].isin(ids_em_conflito)]
                
            if group_filter != "Todas":
                df_filtrado = df_filtrado[df_filtrado['Grupo'] == group_filter]
            
            st.session_state["last_df_view"] = df_filtrado.sort_values(['Data Ocorrência View', 'Hora Início'])

        df_view = st.session_state.get("last_df_view", pd.DataFrame())

        # --- OTIMIZAÇÃO DE PERFORMANCE (Lookup Tables) ---
        # 1. Transformar Series em Set para busca instantânea O(1)
        set_view_ids = set(df_view['id_reserva'].astype(str))

        # 2. Pré-filtrar conflitos e criar um dicionário de busca por ID de reserva
        # Isso elimina o loop aninhado dentro da renderização
        dict_conflitos = {}
        for c in conflitos:
            id1, id2 = str(c['id_reserva1']), str(c['id_reserva2'])
            if id1 in set_view_ids or id2 in set_view_ids:
                dict_conflitos[id1] = c
                dict_conflitos[id2] = c

        # 3. Criar dicionário de sugestões mapeado pelo ID do conflito
        dict_sugestoes = {str(s['id_conflito']): s for s in sugestoes}

        st.markdown(f"##### 📋 Lista de Eventos ({len(df_view)})")
        st.space(1)
        with st.container(height=900):
            if df_view.empty:
                st.info("Nenhum evento visível.")
            else:
                # Iteração eficiente
                for idx, row in df_view.head(50).iterrows():
                    id_atual = str(row.get('id_reserva') or row.get('id'))
                    
                    # Busca instantânea nos dicionários (O(1))
                    conflito_data = dict_conflitos.get(id_atual)
                    conf_pres = id_atual in ids_em_conflito
                    
                    emoji = "🔴" if conf_pres else "🟢"
                    h_fim = calculate_end_hour(row['Hora Início'], row['Hora fim'])
                    data_str = row['Data Ocorrência View'].strftime('%d/%m')
                    
                    st.markdown(f"""
                    **{emoji} {row['Sala']}** | ⏰ {data_str} • {row['Hora Início']}-{h_fim}  
                    👥 {row['Grupo']} | {row['Atividade']}
                    """)
                    
                    if conf_pres and conflito_data:
                        st.error("⚠️ Conflito!")
                        # Busca a sugestão usando o ID do conflito encontrado
                        sug = dict_sugestoes.get(str(conflito_data['id']))
                        if sug:
                            if id_atual == conflito_data['id_reserva1']:
                                salas_recomendadas = sug['salas_recomendadas_g1']
                                salas_livres = sug['outras_salas_livres_g1']
                            else:
                                salas_recomendadas = sug['salas_recomendadas_g2']
                                salas_livres = sug['outras_salas_livres_g2']
                                
                            salas_recomendadas = [s for s in salas_recomendadas if s and str(s).strip()]
                            salas_livres = [s for s in salas_livres if s and str(s).strip()]
                            
                            if salas_recomendadas or salas_livres:
                                salas_recomendadas_f = " ".join([f":green-badge[{s}]" for s in sorted(salas_recomendadas)])
                                salas_livres_f = " ".join([f":orange-badge[{s}]" for s in sorted(salas_livres)])
                                st.markdown(f"{salas_recomendadas_f} {salas_livres_f}")
                            else:
                                st.caption("⚠️ **Atenção:** Não há outras salas disponíveis para este horário.")
                                                    
                    st.divider()


    # Sincroniza o estado global
    if state.get("eventsSet") is not None:
        st.session_state["events"] = state["eventsSet"]
                        