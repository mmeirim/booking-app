import pandas as pd
import streamlit as st

@st.cache_data
def prepare_resources(df_expandido):
    resources = []
    for _, row in df_expandido.iterrows():
        resource = {
            "id": row['Sala'],
            "building": row['Sala'],
            "title": f"{row['Sala']}"
        }
        resources.append(resource)
    return resources

@st.cache_data
def prepare_events(df_expandido, group_colors):
    events = []
    for _, row in df_expandido.iterrows():
        # Combine date and time for start and end
        data_ocorrencia = convert_date_format(row['Data Ocorrência'])
        start_datetime = f"{data_ocorrencia}T{row['Hora Início']}:00-03:00"
        end_datetime = f"{data_ocorrencia}T{row['Hora fim']}:00-03:00"
        
        # Create title combining Grupo and Atividade
        title = f"({row['Sala']}) {row['Grupo']}"
        
        # Get color for this group
        color = group_colors.get(row['Grupo'], '#3788D8')
        
        event = {
            "title": title,
            "start": start_datetime,
            "end": end_datetime,
            "backgroundColor": color,
            "borderColor": color,
            "resourceId": row['Sala'],
            "extendedProps": {
                "responsavel": row['Responsável'],
                "status": row['Status'],
                "grupo": row['Grupo'],
                "atividade": row['Atividade'],
                "id_reserva": row['id_reserva']
            }
        }
        
        events.append(event)
    return events

@st.cache_data
def generate_color_palette(groups):
    """Generate a color palette for rooms"""
    colors = [
        # --- Madeiras e Metais Escuros (Poder e Solidez) ---
        '#5D4037', # Jacarandá (Marrom profundo)
        '#3E2723', # Ébano Litúrgico (Quase preto)
        '#795548', # Nogueira Clássica
        '#B7950B', # Ouro Nobre (Destaque metálico)
        '#9A7D0A', # Bronze Sacro

        # --- Cores Litúrgicas Profundas (Identidade Forte) ---
        '#4A148C', # Roxo Real (Quaresma/Bispo)
        '#311B92', # Índigo Catedral (Azul profundo)
        '#1B5E20', # Verde Floresta (Tempo Comum/Crescimento)
        '#B71C1C', # Vermelho Carmesim (Mártires/Paixão)
        '#880E4F', # Vinho Bordô (Sacrifício)

        # --- Pedras e Arquitetura (Estrutural) ---
        '#263238', # Ardósia Escura
        '#37474F', # Cinza Chumbo
        '#455A64', # Pedra de Castelo
        '#546E7A', # Cinza Oceano Sóbrio
        '#212121', # Antracite (Preto neutro)

        # --- Tons de Transição e Detalhes ---
        '#512E5F', # Ameixa Sóbria
        '#154360', # Azul Petróleo Profundo
        '#145A32', # Verde Oliva Escuro
        '#78281F', # Sangue de Boi (Terracota escura)
        '#1B2631'  # Azul Noite Abissal
    ]
    group_colors = {}
    for idx, group in enumerate(groups):
        group_colors[group] = colors[idx % len(colors)]
    return group_colors

def generate_calendar_options(resources, mode):
    
    calendar_options = {
        "editable": False,
        "selectable": True,
        "dayMaxEvents": True,
        "resourceGroupField": "building",
        "resources": resources,
        "slotMinTime": "07:00:00",
        "slotMaxTime": "22:00:00",
        "locale": "pt-br",
        "timeZone": "America/Sao_Paulo",
        "buttonText": {
            "today": "Hoje",
            "month": "Mês",
            "week": "Semana",
            "day": "Dia"
        }
    }
    
    if "resource" in mode:
        if mode == "Por Sala (Dia)":
            calendar_options = {
                **calendar_options,
                "initialView": "resourceDayGridDay",
                "resourceGroupField": "building",
            }
        elif mode == "resource-timeline":
            calendar_options = {
                **calendar_options,
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "resourceTimelineDay,resourceTimelineWeek,resourceTimelineMonth",
                },
                "initialView": "resourceTimelineDay",
                "resourceGroupField": "building",
            }
        elif mode == "resource-timegrid":
            calendar_options = {
                **calendar_options,
                "initialView": "resourceTimeGridDay",
                "resourceGroupField": "building",
            }
    else:
        if mode == "Calendário":
            calendar_options = {
                **calendar_options,
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "dayGridDay,dayGridWeek,dayGridMonth",
                },
                "initialView": "dayGridMonth",
            }
            calendar_options['dayGridWeek'] = {
                "dayMaxEvents": 15,
            }
        elif mode == "Agenda":
            calendar_options = {
                **calendar_options,
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "timeGridDay,timeGridWeek",
                },
                "initialView": "timeGridWeek",
            }
        elif mode == "timeline":
            calendar_options = {
                **calendar_options,
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "timelineDay,timelineWeek,timelineMonth",
                },
                "initialView": "timelineMonth",
            }
        elif mode == "Lista":
            calendar_options = {
                **calendar_options,
                "initialView": "listMonth",
            }
        elif mode == "multimonth":
            calendar_options = {
                **calendar_options,
                "initialView": "multiMonthYear",
            }
    return calendar_options

def get_calendar_modes():
    return (
            "Calendário",
            "Agenda",
        )

def convert_date_format(date_str):
    """Convert dd/mm/yyyy to yyyy-mm-dd format"""
    try:
        if pd.isna(date_str):
            return None
        date_str = str(date_str).strip()
        # Check if already in yyyy-mm-dd format
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            return date_str
        # Convert from dd/mm/yyyy
        if '/' in date_str:
            day, month, year = date_str.split('/')
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return date_str
    except Exception as e:
        st.sidebar.error(f"Error converting date {date_str}: {e}")
        return None