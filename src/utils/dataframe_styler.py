import pandas as pd

def style_zebra(df):
    return df.style.set_table_styles([
        # Estilo para os cabeçalhos (Títulos em Negrito e fundo cinza claro)
        {'selector': 'th', 'props': [('font-weight', 'bold'), 
                                     ('background-color', '#f0f2f6'),
                                     ('color', 'black')]}
    ]).map(lambda x: 'background-color: #f9f9f9', 
           subset=pd.IndexSlice[df.index[1::2], :]) # Aplica nas linhas ímpares