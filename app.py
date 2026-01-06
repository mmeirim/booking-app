import streamlit as st
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import plotly.express as px
import plotly.graph_objects as go
import src.services.gsheet_service as gsheet_service
import src.services.recommendation_service as recommendation_service
import src.services.reccuring_service as recurring_service
import src.services.conflicts_service as conflicts_service
import src.ui.pages.calendar as calendar_page

# ============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================================

st.set_page_config(
    page_title="Sistema de Reservas de Salas 2026",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def validar_estrutura_dados(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Valida se os dados do Google Sheets estão no formato correto"""
    erros = []
    
    if df.empty:
        erros.append("DataFrame vazio")
        return False, erros
    
    # Validar datas
    try:
        pd.to_datetime(df['Data Início'], dayfirst=True, errors='coerce')
    except:
        erros.append("Formato de data inválido em 'Data Início' (use YYYY-MM-DD)")
    
    # Validar horários
    for col in ['Hora Início', 'Hora fim']:
        if col in df.columns:
            valores_nao_vazios = df[df[col].notna()][col]
            for hora in valores_nao_vazios:
                if hora and not pd.isna(hora):
                    if ':' not in str(hora):
                        erros.append(f"Formato de horário inválido em '{col}' (use HH:MM)")
                        break
    
    return len(erros) == 0, erros
# ============================================================================
# ESTATÍSTICAS E ANÁLISES
# ============================================================================

def calcular_estatisticas(df_reservas: pd.DataFrame, df_expandido: pd.DataFrame, 
                         conflitos: List[Dict], sugestoes: List[Dict]) -> Dict:
    """Calcula estatísticas gerais do sistema"""
    
    salas = df_reservas['Sala'].unique()
    grupos = df_reservas['Grupo'].unique()
    total_ocorrencias = len(df_expandido)
    
    # Conflitos por sala
    conflitos_por_sala = {}
    for c in conflitos:
        sala = c['sala']
        conflitos_por_sala[sala] = conflitos_por_sala.get(sala, 0) + 1
    
    sala_mais_conflitos = max(conflitos_por_sala.items(), key=lambda x: x[1]) if conflitos_por_sala else ('Nenhuma', 0)
    
    # Percentual sem conflito
    reservas_com_conflito = set()
    for c in conflitos:
        reservas_com_conflito.add(c['id_reserva1']) # Assumindo que você tem um ID único
        reservas_com_conflito.add(c['id_reserva2'])

    total_com_conflito = len(reservas_com_conflito)
    total_sem_conflito = total_ocorrencias - total_com_conflito
    percentual_sem_conflito = (total_sem_conflito / total_ocorrencias * 100) if total_ocorrencias > 0 else 100
    
    return {
        'total_reservas_originais': len(df_reservas),
        'total_ocorrencias': total_ocorrencias,
        'total_conflitos': len(conflitos),
        'total_salas': len(salas),
        'total_grupos': len(grupos),
        'atividades_com_opcoes': len(sugestoes),
        'sala_mais_conflitos': sala_mais_conflitos,
        'percentual_sem_conflito': round(percentual_sem_conflito, 1),
        'conflitos_por_sala': conflitos_por_sala
    }


# ============================================================================
# VISUALIZAÇÕES (PROMPT 2)
# ============================================================================

def criar_grafico_ocupacao_salas(df_expandido: pd.DataFrame):
    """Gráfico de barras com ocupação por sala"""
    ocupacao = df_expandido['Sala'].value_counts().reset_index()
    ocupacao.columns = ['Sala', 'Ocorrências']
    
    fig = px.bar(
        ocupacao, 
        x='Sala', 
        y='Ocorrências',
        title='Ocupação por Sala (2026)',
        color='Ocorrências',
        color_continuous_scale='Blues'
    )
    fig.update_layout(showlegend=False)
    return fig


def criar_grafico_distribuicao_grupos(df_expandido: pd.DataFrame):
    """Gráfico de pizza com distribuição por grupo"""
    distribuicao = df_expandido['Grupo'].value_counts().head(10)
    
    fig = px.pie(
        values=distribuicao.values,
        names=distribuicao.index,
        title='Top 10 Grupos Mais Ativos'
    )
    return fig


def criar_timeline_ocupacao(df_expandido: pd.DataFrame):
    """Timeline de ocupação ao longo do ano"""
    df_expandido['Data Ocorrência'] = pd.to_datetime(df_expandido['Data Ocorrência'], dayfirst=True)
    df_expandido['Mês'] = df_expandido['Data Ocorrência'].dt.to_period('M').astype(str)
    
    ocupacao_mensal = df_expandido.groupby('Mês').size().reset_index(name='Reservas')
    
    fig = px.line(
        ocupacao_mensal,
        x='Mês',
        y='Reservas',
        title='Ocupação ao Longo de 2026',
        markers=True
    )
    fig.update_traces(line_color='#1f77b4', line_width=3)
    return fig




# ============================================================================
# INTERFACE PRINCIPAL
# ============================================================================

def main():
    # Input do Spreadsheet ID
    spreadsheet_id = st.secrets.get("spreadsheet_id", "")
    
    # # Header principal
    st.title("""🏛️ Sistema de Gestão de Reservas de Salas""")
    # st.markdown("**Análise Completa de Conflitos e Sugestões**")
    
    # Carregar dados
    with st.spinner("📥 Carregando dados do Google Sheets..."):
        dfs_original = gsheet_service.load_all_data_gsheets(spreadsheet_id)
    
    if not dfs_original:
        st.error("❌ Não foi possível carregar os dados. Verifique as configurações.")
        st.info("""
        **Como configurar:**
        1. Crie um Service Account no Google Cloud Console
        2. Compartilhe a planilha com o email do Service Account
        3. Adicione as credenciais no arquivo `.streamlit/secrets.toml`
        
        ```toml
        spreadsheet_id = "seu-spreadsheet-id"
        
        [gcp_service_account]
        type = "service_account"
        project_id = "seu-projeto"
        private_key_id = "..."
        private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
        client_email = "..."
        client_id = "..."
        ```
        """)
        return
    
    df_reservas = dfs_original.get('Reservas', pd.DataFrame())
    if df_reservas.empty:
        st.error("❌ A aba 'Reservas' não foi encontrada ou está vazia.")
        return
    
    df_salas = dfs_original.get('Salas', pd.DataFrame()) 
    df_grupos = dfs_original.get('Grupos', pd.DataFrame())
    
    # Validar estrutura
    valido, erros = validar_estrutura_dados(df_reservas)
    if not valido:
        st.error("❌ Erro na estrutura dos dados:")
        for erro in erros:
            st.write(f"- {erro}")
        return
    
    # Processar dados
    with st.spinner("⚙️ Processando recorrências..."):
        df_expandido = recurring_service.expand_recurring_events(df_reservas)
    
    with st.spinner("🔍 Detectando conflitos..."):
        conflitos = conflicts_service.find_conflicts(df_expandido)
    
    with st.spinner("💡 Gerando sugestões..."):
        sugestoes = recommendation_service.generate_recommendations(df_expandido, df_salas, df_grupos, conflitos)
      
    with st.sidebar:
        # st.image("https://via.placeholder.com/200x80/1f77b4/ffffff?text=Igreja", use_column_width=True)
        st.title("Paróquia Santo Afonso")
                
        st.markdown("### 📊 Estatísticas")
        st.metric("Total de Reservas", len(df_expandido))
        st.metric("Total de Salas", len(df_salas))
        st.metric("Total de Conflitos", len(conflitos), 
                  delta="Requer atenção" if len(conflitos) > 0 else "Tudo OK", delta_color="inverse")
        st.metric("Grupos Ativos", len(df_expandido['Grupo'].unique()))
        
        st.divider()
        
        # Botão de atualizar
        if st.button("🔄 Atualizar Dados", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Tabs principais
    tab1, tab2, tab5 = st.tabs([
        "📅 Calendário", 
        "⚠️ Conflitos", 
        # "✅ Sugestões", 
        # "📅 Calendário",
        "📋 Dados Brutos"
    ])
    
    # # TAB 1: DASHBOARD
    with tab1:
        calendar_page.generate_calendar_page(df_expandido, df_salas, pd.DataFrame(conflitos))
    # TAB 2: CONFLITOS
    with tab2:
        # Cabeçalho com ícone e contagem
        st.subheader(f"⚠️ Conflitos Identificados ({len(conflitos)})")
        
        if not conflitos:
            # Layout de Sucesso (CheckCircle do React)
            container_sucesso = st.container(border=True)
            with container_sucesso:
                st.markdown("<h1 style='text-align: center;'>✅</h1>", unsafe_allow_html=True)
                st.markdown("<h3 style='text-align: center; color: #166534;'>Parabéns!</h3>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: #666;'>Nenhum conflito encontrado</p>", unsafe_allow_html=True)
            return

        # --- ÁREA DE FILTROS ---
        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
        with col_f1:
            salas = sorted(list(set(c['sala'] for c in conflitos)))
            filtro_sala = st.selectbox("Filtrar por Sala", ["Todas"] + salas)
        with col_f2:
            grupos = sorted(list(set([c['grupo1'] for c in conflitos] + [c['grupo2'] for c in conflitos])))
            filtro_grupo = st.selectbox("Filtrar por Grupo", ["Todos"] + grupos)
        with col_f3:
            filtro_duracao = st.selectbox("Filtrar por Duração do conflito", ["Todos", "Menos de 30min"])
        with col_f4:
            filtro_dia_semana = st.selectbox("Filtrar por Dia da Semana", ["Todos", "Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
        with col_f5:
            filtro_data = st.date_input("Filtrar por Data", value=None, format="DD/MM/YYYY")

        # Filtros lógicos
        conflitos_filtrados = conflitos
        if filtro_sala != "Todas":
            conflitos_filtrados = [c for c in conflitos_filtrados if c['sala'] == filtro_sala]
        if filtro_grupo != "Todos":
            conflitos_filtrados = [c for c in conflitos_filtrados if c['grupo1'] == filtro_grupo or c['grupo2'] == filtro_grupo]
        if filtro_duracao != "Todos":
            ids_com_ajuste = {s['id_conflito'] for s in sugestoes if s.get('ajuste_tempo') != ""}
            conflitos_filtrados = [c for c in conflitos_filtrados if c['id'] in ids_com_ajuste]
        if filtro_dia_semana != "Todos":
            conflitos_filtrados = [c for c in conflitos_filtrados if filtro_dia_semana.lower() in c['dia_semana']]
        if filtro_data:
            data_str = filtro_data.strftime('%d/%m/%Y')
            conflitos_filtrados = [c for c in conflitos_filtrados if c['data'] == data_str]

        st.write(f"Mostrando **{len(conflitos_filtrados)}** conflitos")
        
        conflitos_filtrados = sorted(
            conflitos_filtrados, 
            key=lambda x: (datetime.strptime(x['data'], '%d/%m/%Y'))
        )
        
        # --- LISTAGEM DE CONFLITOS (CARD STYLE NATIVO) ---
        for idx, conf in enumerate(conflitos_filtrados, 1):
            sug = [s for s in sugestoes if s['id_conflito'] == conf['id']][0]
            cor = "🟢" if sug['resolvido'] else "🔴"
            # Usamos um container com borda para simular o "card"
            with st.expander(f"{cor} {sug['sala_original']} | {sug['grupo1']} & {sug['grupo2']} ({conf['data']})"):
                # Cabeçalho do Card
                header_col1, header_col2 = st.columns([3, 1])
                with header_col1:
                    st.markdown(f"### 📍 {conf['sala']} :violet-badge[{sug['ajuste_tempo']}]")
                    st.markdown(f"📅 Data: {conf['data']}")
                # with header_col2:
                #     st.error(f"Conflito #{idx}")                           

                # Corpo do Card (As duas reservas lado a lado)
                res1_col, res2_col = st.columns(2)
                
                with res1_col:
                    st.markdown("**Reserva 1**")
                    # Usando o help ou info para destacar a área da reserva
                    with st.container():
                        st.info(f"""
                        **{conf['grupo1']}** *{conf['atividade1']}* 🕒 {conf['horario1']}  
                        👤 {conf['responsavel1']}
                        """)
                        
                        salas_recomendadas = sug['salas_recomendadas_g1']
                        salas_livres = sug['outras_salas_livres_g1']
                        if salas_recomendadas:
                            with st.success("💡 **Sugestão de realocação:**"):
                                st.markdown(f"Salas recomendadas neste dia e horário:")
                                # Exibe as salas como "tags" usando st.write ou markdown
                                salas_formatadas = " ".join([f":green-badge[{s}]" for s in sorted(salas_recomendadas)])
                                st.markdown(f"**Salas Recomendadas:** {salas_formatadas}")
                        if salas_livres:    
                            salas_formatadas = " ".join([f":orange-badge[{s}]" for s in sorted(salas_livres)])
                            st.markdown(f"**Demais salas Livres:** {salas_formatadas}")
                        else:
                            with st.warning("⚠️ **Atenção:** Não há outras salas disponíveis para este horário."):
                                st.markdown("Considere ajustar o horário ou entrar em contato com a administração.")                      
                
                with res2_col:
                    st.markdown("**Reserva 2**")
                    with st.container():
                        # Usamos 'warning' para diferenciar a segunda reserva e criar o tom laranja
                        st.warning(f"""
                        **{conf['grupo2']}** *{conf['atividade2']}* 🕒 {conf['horario2']}  
                        👤 {conf['responsavel2']}
                        """)
                        
                        salas_recomendadas = sug['salas_recomendadas_g2']
                        salas_livres = sug['outras_salas_livres_g2']
                        if salas_recomendadas:
                            with st.success("💡 **Sugestão de realocação:**"):
                                st.markdown(f"Salas recomendadas neste dia e horário:")
                                # Exibe as salas como "tags" usando st.write ou markdown
                                salas_formatadas = " ".join([f":green-badge[{s}]" for s in sorted(salas_recomendadas)])
                                st.markdown(f"**Salas Recomendadas:** {salas_formatadas}")
                        if salas_livres:    
                            salas_formatadas = " ".join([f":orange-badge[{s}]" for s in sorted(salas_livres)])
                            st.markdown(f"**Demais salas Livres:** {salas_formatadas}")
                        else:
                            with st.warning("⚠️ **Atenção:** Não há outras salas disponíveis para este horário."):
                                st.markdown("Considere ajustar o horário ou entrar em contato com a administração.")
                
    # TAB 3: SUGESTÕES
    # with tab3:
    #     st.subheader(f"✅ Sugestões de Salas ({len(sugestoes)})")
        
    #     if not sugestoes:
    #         st.info("ℹ️ Nenhuma atividade com múltiplas opções encontrada.")
    #     else:
    #         # --- Área de Filtros Dinâmicos ---
    #         col_f1, col_f2 = st.columns(2)
            
    #         with col_f1:
    #             # Pega todos os nomes únicos de grupos (posições 1 e 2)
    #             todos_grupos = sorted(list(set([s['grupo1'] for s in sugestoes] + [s['grupo2'] for s in sugestoes])))
    #             filtro_grupo = st.selectbox("Filtrar por Grupo", ["Todos"] + todos_grupos)
                
    #         with col_f2:
    #             todas_salas = sorted(list(set([s['sala_original'] for s in sugestoes])))
    #             filtro_sala = st.selectbox("Filtrar por Sala do Conflito", ["Todas"] + todas_salas)

    #         # --- Lógica de Filtragem ---
    #         sugestoes_filtradas = sugestoes
            
    #         if filtro_grupo != "Todos":
    #             sugestoes_filtradas = [
    #                 s for s in sugestoes_filtradas 
    #                 if s['grupo1'] == filtro_grupo or s['grupo2'] == filtro_grupo
    #             ]
                
    #         if filtro_sala != "Todas":
    #             sugestoes_filtradas = [
    #                 s for s in sugestoes_filtradas if s['sala_original'] == filtro_sala
    #             ]

    #         st.write(f"**Mostrando {len(sugestoes_filtradas)} sugestões**")
            
    #         # --- Listagem (Seu loop original ajustado) ---
    #         for idx, sug in enumerate(sugestoes_filtradas, 1):
    #             # Lógica de cor baseada na resolução
    #             cor = "🟢" if sug['resolvido'] else "🔴"
                
    #             with st.expander(f"{cor} {sug['sala_original']} | {sug['grupo1']} & {sug['grupo2']}"):
    #                 col1, col2 = st.columns([2, 1])
                    
    #                 with col1:
    #                     st.markdown(f"""
    #                     📍 **Sala:** {sug['sala_original']}  
    #                     📅 **Data:** {sug['data']}  
    #                     👥 **Envolvidos:** {sug['grupo1']} e {sug['grupo2']}
    #                     """)
                        
    #                     if sug['ajuste_tempo']:
    #                         st.warning(sug['ajuste_tempo'])
                    
    #                 with col2:
    #                     # Exibe alerta de conflito curto se houver
    #                     if sug['ajuste_tempo']:
    #                         st.warning(sug['ajuste_tempo'])
    #                     st.markdown("**Recomendação de Sala:**")
    #                     if sug['salas_recomendadas']:
    #                         # Exibe a primeira (melhor) recomendação em destaque
    #                         st.success(f"🏠 **{sug['salas_recomendadas'][0]}**")
    #                         if len(sug['salas_recomendadas']) > 1:
    #                             st.caption(f"Outras opções: {', '.join(sug['salas_recomendadas'][1:])}")
    #                     else:
    #                         st.error("Nenhuma sala disponível")
                        
    #                     st.info(f"💡 {sug['justificativa']}")
    
    # TAB 4: CALENDÁRIO
    # with tab4:
    #     st.subheader("📅 Calendário de Reservas")
        
    #     # Filtros
    #     col1, col2, col3 = st.columns(3)
        
    #     with col1:
    #         salas_unicas = sorted(df_expandido['Sala'].unique())
    #         filtro_sala_cal = st.selectbox("Filtrar por Sala", ["Todas"] + list(salas_unicas))
        
    #     with col2:
    #         grupos_unicos = sorted(df_expandido['Grupo'].unique())
    #         filtro_grupo_cal = st.selectbox("Filtrar por Grupo", ["Todos"] + list(grupos_unicos))
        
    #     with col3:
    #         # Filtro de mês
    #         meses = sorted(df_expandido['Data Ocorrência'].unique())
    #         if meses:
    #             mes_padrao = meses[0][3:5]  # YYYY-MM
    #             filtro_mes = st.selectbox("Filtrar por Mês", ["Todos"] + sorted(list(set([m[3:5] for m in meses]))))
        
    #     # Aplicar filtros
    #     df_filtrado = df_expandido.copy()
        
    #     if filtro_sala_cal != "Todas":
    #         df_filtrado = df_filtrado[df_filtrado['Sala'] == filtro_sala_cal]
        
    #     if filtro_grupo_cal != "Todos":
    #         df_filtrado = df_filtrado[df_filtrado['Grupo'] == filtro_grupo_cal]
        
    #     if 'filtro_mes' in locals() and filtro_mes != "Todos":
    #         df_filtrado = df_filtrado[df_filtrado['Data Ocorrência'].str.contains(f"/{filtro_mes}/")]
        
    #     # Busca textual
    #     busca = st.text_input("🔍 Buscar por atividade ou responsável", "")
    #     if busca:
    #         df_filtrado = df_filtrado[
    #             df_filtrado['Atividade'].str.contains(busca, case=False, na=False) |
    #             df_filtrado['Responsável'].str.contains(busca, case=False, na=False)
    #         ]
        
    #     st.write(f"**Mostrando {len(df_filtrado)} de {len(df_expandido)} reservas**")
        
    #     # Verificar conflitos para cada reserva
    #     def tem_conflito(row):
    #         return any(
    #             c['sala'] == row['Sala'] and c['data'] == row['Data Ocorrência']
    #             for c in conflitos
    #         )
        
    #     df_filtrado = df_filtrado.sort_values(by=['Data Ocorrência','Hora Início'],
    #                                           key=lambda x: pd.to_datetime(x, dayfirst=True))
        
    #     # Exibir reservas
    #     for idx, row in df_filtrado.head(100).iterrows():
    #         conflito_presente = tem_conflito(row)
    #         cor_borda = "🔴" if conflito_presente else "🟢"
            
    #         with st.container():
    #             col1, col2 = st.columns([3, 1])
                
    #             with col1:
    #                 st.markdown(f"""
    #                 {cor_borda} **{row['Atividade']}**  
    #                 👥 {row['Grupo']} • 👤 {row['Responsável']}
    #                 """)
                
    #             with col2:
    #                 hora_fim_calc = conflicts_service.calculate_end_hour(row['Hora Início'], row['Hora fim'])
    #                 st.markdown(f"""
    #                 🏠 **{row['Sala']}**  
    #                 📅 {row['Data Ocorrência']}  
    #                 ⏰ {row['Hora Início']} - {hora_fim_calc}
    #                 """)
    #                 if conflito_presente:
    #                     st.error("⚠️ Conflito")
                
    #             st.divider()
        
    #     if len(df_filtrado) > 100:
    #         st.info(f"ℹ️ Mostrando apenas as primeiras 100 reservas. Use os filtros para refinar.")
    
    # TAB 5: DADOS BRUTOS
    with tab5:
        st.subheader("📋 Dados Brutos")
        
        tab_dados1, tab_dados2, tab_dados3 = st.tabs([
            "Reservas Originais",
            "Ocorrências Expandidas",
            "Exportar"
        ])
        
        with tab_dados1:
            st.write(f"**{len(df_reservas)} reservas cadastradas**")
            st.dataframe(df_reservas, use_container_width=True, height=400)
        
        with tab_dados2:
            st.write(f"**{len(df_expandido)} ocorrências em 2026**")
            st.dataframe(df_expandido, use_container_width=True, height=400)
        
        with tab_dados3:
            st.write("**Exportar Dados**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_original = df_reservas.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Reservas Originais (CSV)",
                    csv_original,
                    "reservas_originais.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col2:
                csv_expandido = df_expandido.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Ocorrências 2026 (CSV)",
                    csv_expandido,
                    "ocorrencias_2026.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col3:
                # Exportar conflitos
                if conflitos:
                    df_conflitos = pd.DataFrame(conflitos)
                    csv_conflitos = df_conflitos.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Conflitos (CSV)",
                        csv_conflitos,
                        "conflitos.csv",
                        "text/csv",
                        use_container_width=True
                    )
    
    # Footer
    st.divider()
    st.caption("💡 Sistema de Gestão de Reservas de Salas 2026 • Dados atualizados automaticamente")


if __name__ == "__main__":
    main()
            