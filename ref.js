import React, { useState, useMemo, useEffect } from 'react';
import { Calendar, AlertTriangle, CheckCircle, Clock, Users, Filter, FileText, TrendingUp } from 'lucide-react';
import Papa from 'papaparse';

const AnaliseSalasReal = () => {
  const [activeTab, setActiveTab] = useState('estatisticas');
  const [filtroSala, setFiltroSala] = useState('todas');
  const [filtroGrupo, setFiltroGrupo] = useState('todos');
  const [dados, setDados] = useState([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    const carregarDados = async () => {
      try {
        const csvData = await window.fs.readFile('Reservas de Sala  SA 2026  Página1.csv', { encoding: 'utf8' });
        
        Papa.parse(csvData, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            setDados(results.data);
            setCarregando(false);
          }
        });
      } catch (error) {
        console.error('Erro ao carregar CSV:', error);
        setCarregando(false);
      }
    };

    carregarDados();
  }, []);

  // Função para calcular hora fim
  const calcularHoraFim = (horaInicio, horaFim) => {
    if (horaFim && horaFim.trim()) return horaFim;
    
    const [h, m] = horaInicio.split(':').map(Number);
    const novaHora = (h + 3) % 24;
    return `${String(novaHora).padStart(2, '0')}:${String(m || 0).padStart(2, '0')}`;
  };

  // Função para expandir recorrências
  const expandirRecorrencias = (reserva) => {
    const ocorrencias = [];
    const dataInicio = new Date(reserva['Data Início']);
    const dataFim = new Date('2026-12-31');
    const recorrencia = reserva['Recorrência'];
    
    if (!recorrencia || !recorrencia.trim()) {
      return [{...reserva, dataOcorrencia: reserva['Data Início']}];
    }

    const partes = recorrencia.split('-');
    const tipo = partes[0];
    
    if (tipo === 'Semanal') {
      let data = new Date(dataInicio);
      while (data <= dataFim) {
        ocorrencias.push({
          ...reserva,
          dataOcorrencia: data.toISOString().split('T')[0]
        });
        data.setDate(data.getDate() + 7);
      }
    } else if (tipo === 'Quinzenal') {
      let data = new Date(dataInicio);
      while (data <= dataFim) {
        ocorrencias.push({
          ...reserva,
          dataOcorrencia: data.toISOString().split('T')[0]
        });
        data.setDate(data.getDate() + 14);
      }
    } else if (tipo === 'Mensal' && partes.length >= 3) {
      const ordem = partes[1].replace('º', '');
      const diaSemana = partes[2];
      const diasSemana = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
      const diaAlvo = diasSemana.indexOf(diaSemana);
      
      for (let mes = 0; mes < 12; mes++) {
        let contador = 0;
        let diaAtual = 1;
        
        while (diaAtual <= 31) {
          const dataTemp = new Date(2026, mes, diaAtual);
          if (dataTemp.getMonth() !== mes) break;
          
          if (dataTemp.getDay() === diaAlvo) {
            contador++;
            if (contador === parseInt(ordem)) {
              ocorrencias.push({
                ...reserva,
                dataOcorrencia: dataTemp.toISOString().split('T')[0]
              });
              break;
            }
          }
          diaAtual++;
        }
      }
    }
    
    return ocorrencias.length > 0 ? ocorrencias : [{...reserva, dataOcorrencia: reserva['Data Início']}];
  };

  // Expandir todas as reservas
  const reservasExpandidas = useMemo(() => {
    if (!dados.length) return [];
    return dados.flatMap(expandirRecorrencias);
  }, [dados]);

  // Função para verificar sobreposição de horários
  const verificarSobreposicao = (h1Inicio, h1Fim, h2Inicio, h2Fim) => {
    const converter = (hora) => {
      const [h, m] = hora.split(':').map(Number);
      return h * 60 + (m || 0);
    };
    
    const inicio1 = converter(h1Inicio);
    const fim1 = converter(h1Fim);
    const inicio2 = converter(h2Inicio);
    const fim2 = converter(h2Fim);
    
    return !(fim1 <= inicio2 || fim2 <= inicio1);
  };

  // Detectar conflitos
  const conflitos = useMemo(() => {
    const conf = [];
    
    for (let i = 0; i < reservasExpandidas.length; i++) {
      for (let j = i + 1; j < reservasExpandidas.length; j++) {
        const r1 = reservasExpandidas[i];
        const r2 = reservasExpandidas[j];
        
        if (r1.Sala === r2.Sala && r1.dataOcorrencia === r2.dataOcorrencia) {
          const h1Inicio = r1['Hora Início'];
          const h1Fim = calcularHoraFim(r1['Hora Início'], r1['Hora fim']);
          const h2Inicio = r2['Hora Início'];
          const h2Fim = calcularHoraFim(r2['Hora Início'], r2['Hora fim']);
          
          if (verificarSobreposicao(h1Inicio, h1Fim, h2Inicio, h2Fim)) {
            conf.push({
              sala: r1.Sala,
              data: r1.dataOcorrencia,
              reserva1: r1,
              reserva2: r2,
              horario1: `${h1Inicio}-${h1Fim}`,
              horario2: `${h2Inicio}-${h2Fim}`
            });
          }
        }
      }
    }
    
    return conf;
  }, [reservasExpandidas]);

  // Agrupar atividades por grupo, atividade e data
  const atividadesAgrupadas = useMemo(() => {
    const grupos = {};
    
    dados.forEach(reserva => {
      const chave = `${reserva.Grupo}|||${reserva.Atividade}|||${reserva['Data Início']}`;
      if (!grupos[chave]) {
        grupos[chave] = [];
      }
      grupos[chave].push(reserva);
    });
    
    return grupos;
  }, [dados]);

  // Sugestões de melhor opção
  const sugestoes = useMemo(() => {
    return Object.entries(atividadesAgrupadas)
      .filter(([_, opcoes]) => opcoes.length > 1)
      .map(([chave, opcoes]) => {
        const [grupo, atividade, data] = chave.split('|||');
        
        const opcao1 = opcoes.find(o => o.Status === 'Opção 1');
        const opcao2 = opcoes.find(o => o.Status === 'Opção 2');
        
        if (!opcao1 && !opcao2) return null;
        
        const conflitosOpcao1 = opcao1 ? conflitos.filter(c => 
          c.sala === opcao1.Sala && 
          c.data === opcao1['Data Início']
        ).length : 999;
        
        const conflitosOpcao2 = opcao2 ? conflitos.filter(c => 
          c.sala === opcao2.Sala && 
          c.data === opcao2['Data Início']
        ).length : 999;
        
        let opcaoRecomendada, justificativa;
        
        if (opcoes.length === 1) {
          opcaoRecomendada = opcoes[0].Sala;
          justificativa = 'Única opção disponível';
        } else if (conflitosOpcao1 === 0 && conflitosOpcao2 === 0) {
          opcaoRecomendada = opcao1 ? opcao1.Sala : opcao2.Sala;
          justificativa = 'Ambas livres - Opção 1 como padrão';
        } else if (conflitosOpcao1 === 0) {
          opcaoRecomendada = opcao1.Sala;
          justificativa = 'Opção 1 sem conflitos';
        } else if (conflitosOpcao2 === 0) {
          opcaoRecomendada = opcao2.Sala;
          justificativa = 'Opção 2 sem conflitos';
        } else if (conflitosOpcao1 < conflitosOpcao2) {
          opcaoRecomendada = opcao1.Sala;
          justificativa = `Menos conflitos (${conflitosOpcao1} vs ${conflitosOpcao2})`;
        } else {
          opcaoRecomendada = opcao2.Sala;
          justificativa = `Menos conflitos (${conflitosOpcao2} vs ${conflitosOpcao1})`;
        }
        
        return {
          grupo,
          atividade,
          data,
          opcoes: opcoes.map(o => `${o.Sala} (${o.Status})`).join(', '),
          opcaoRecomendada,
          justificativa,
          conflitosTotal: Math.min(conflitosOpcao1, conflitosOpcao2),
          responsavel: opcoes[0].Responsável
        };
      })
      .filter(s => s !== null);
  }, [atividadesAgrupadas, conflitos]);

  // Estatísticas
  const stats = useMemo(() => {
    const salas = [...new Set(dados.map(r => r.Sala))];
    const grupos = [...new Set(dados.map(r => r.Grupo))];
    
    const conflitoPorSala = {};
    conflitos.forEach(c => {
      conflitoPorSala[c.sala] = (conflitoPorSala[c.sala] || 0) + 1;
    });
    
    const salaMaisConflitos = Object.entries(conflitoPorSala).sort((a, b) => b[1] - a[1])[0];
    
    return {
      totalReservasOriginais: dados.length,
      totalReservas: reservasExpandidas.length,
      totalConflitos: conflitos.length,
      totalSalas: salas.length,
      totalGrupos: grupos.length,
      atividadesComOpcoes: sugestoes.length,
      salaMaisConflitos: salaMaisConflitos ? salaMaisConflitos : ['Nenhuma', 0],
      percentualSemConflito: sugestoes.length > 0 
        ? ((sugestoes.filter(s => s.conflitosTotal === 0).length / sugestoes.length) * 100).toFixed(1)
        : '100.0'
    };
  }, [dados, reservasExpandidas, conflitos, sugestoes]);

  // Filtros
  const salas = [...new Set(dados.map(r => r.Sala))].sort();
  const grupos = [...new Set(dados.map(r => r.Grupo))].sort();

  const dadosFiltrados = useMemo(() => {
    return reservasExpandidas.filter(r => {
      const passaSala = filtroSala === 'todas' || r.Sala === filtroSala;
      const passaGrupo = filtroGrupo === 'todos' || r.Grupo === filtroGrupo;
      return passaSala && passaGrupo;
    });
  }, [reservasExpandidas, filtroSala, filtroGrupo]);

  if (carregando) {
    return (
      <div className="w-full max-w-7xl mx-auto p-6 bg-gray-50 min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando dados...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-7xl mx-auto p-6 bg-gray-50 min-h-screen">
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 rounded-lg shadow-lg p-6 mb-6 text-white">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
          <Calendar size={32} />
          Análise de Reservas de Salas 2026
        </h1>
        <p className="text-blue-100">Sistema Avançado - {dados.length} reservas cadastradas</p>
      </div>

      {/* Estatísticas Dashboard */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded-lg shadow hover:shadow-lg transition-shadow">
          <div className="text-2xl font-bold text-blue-600">{stats.totalReservas}</div>
          <div className="text-xs text-gray-600">Ocorrências em 2026</div>
          <div className="text-xs text-gray-400 mt-1">({stats.totalReservasOriginais} reservas base)</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow hover:shadow-lg transition-shadow">
          <div className="text-2xl font-bold text-red-600">{stats.totalConflitos}</div>
          <div className="text-xs text-gray-600">Conflitos Detectados</div>
          <div className="text-xs text-gray-400 mt-1">Requerem atenção</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow hover:shadow-lg transition-shadow">
          <div className="text-2xl font-bold text-green-600">{stats.atividadesComOpcoes}</div>
          <div className="text-xs text-gray-600">Atividades c/ Múltiplas Opções</div>
          <div className="text-xs text-gray-400 mt-1">{stats.percentualSemConflito}% sem conflito</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow hover:shadow-lg transition-shadow">
          <div className="text-2xl font-bold text-purple-600">{stats.totalSalas}</div>
          <div className="text-xs text-gray-600">Salas Cadastradas</div>
          <div className="text-xs text-gray-400 mt-1">{stats.totalGrupos} grupos ativos</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow-lg mb-6">
        <div className="flex border-b overflow-x-auto">
          {[
            { id: 'estatisticas', icon: TrendingUp, label: 'Estatísticas' },
            { id: 'conflitos', icon: AlertTriangle, label: 'Conflitos', badge: stats.totalConflitos },
            { id: 'sugestoes', icon: CheckCircle, label: 'Sugestões', badge: sugestoes.length },
            { id: 'calendario', icon: Calendar, label: 'Calendário' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-3 px-4 font-semibold flex items-center justify-center gap-2 whitespace-nowrap ${
                activeTab === tab.id ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50' : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <tab.icon size={20} />
              {tab.label}
              {tab.badge !== undefined && (
                <span className={`ml-1 px-2 py-0.5 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                }`}>
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeTab === 'estatisticas' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold mb-4 text-gray-800">Resumo Geral</h2>
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-600">
                    <div className="font-semibold text-gray-800 mb-2">Sala com Mais Conflitos</div>
                    <div className="text-2xl font-bold text-blue-600">{stats.salaMaisConflitos[0]}</div>
                    <div className="text-sm text-gray-600">{stats.salaMaisConflitos[1]} conflitos</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg border-l-4 border-green-600">
                    <div className="font-semibold text-gray-800 mb-2">Taxa de Sucesso</div>
                    <div className="text-2xl font-bold text-green-600">{stats.percentualSemConflito}%</div>
                    <div className="text-sm text-gray-600">Opções sem conflito</div>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold mb-3 text-gray-800">Distribuição por Sala</h3>
                <div className="space-y-2">
                  {salas.map(sala => {
                    const total = reservasExpandidas.filter(r => r.Sala === sala).length;
                    const conf = conflitos.filter(c => c.sala === sala).length;
                    return (
                      <div key={sala} className="flex items-center gap-3 bg-gray-50 p-3 rounded">
                        <div className="font-semibold text-gray-700 w-24">{sala}</div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-blue-600 h-2 rounded-full" 
                                style={{width: `${(total / stats.totalReservas) * 100}%`}}
                              ></div>
                            </div>
                            <span className="text-sm text-gray-600 w-16 text-right">{total} usos</span>
                          </div>
                          {conf > 0 && (
                            <div className="text-xs text-red-600 mt-1">{conf} conflitos</div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'conflitos' && (
            <div>
              <h2 className="text-xl font-bold mb-4 text-gray-800 flex items-center gap-2">
                <AlertTriangle className="text-red-600" />
                Conflitos Identificados ({conflitos.length})
              </h2>
              {conflitos.length === 0 ? (
                <div className="text-center py-12 bg-green-50 rounded-lg">
                  <CheckCircle size={64} className="mx-auto mb-3 text-green-500" />
                  <p className="text-lg font-semibold text-green-800">Parabéns!</p>
                  <p className="text-gray-600">Nenhum conflito encontrado</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {conflitos.map((conflito, idx) => (
                    <div key={idx} className="border-l-4 border-red-500 bg-red-50 p-4 rounded-lg hover:shadow-md transition-shadow">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <div className="font-bold text-red-800 text-lg">{conflito.sala}</div>
                          <div className="text-sm text-gray-600">{new Date(conflito.data).toLocaleDateString('pt-BR')}</div>
                        </div>
                        <div className="bg-red-600 text-white px-3 py-1 rounded-full text-xs font-semibold">
                          Conflito #{idx + 1}
                        </div>
                      </div>
                      <div className="grid md:grid-cols-2 gap-3">
                        <div className="bg-white p-3 rounded border-l-2 border-orange-400">
                          <div className="font-semibold text-gray-800">{conflito.reserva1.Grupo}</div>
                          <div className="text-sm text-gray-600 mb-1">{conflito.reserva1.Atividade}</div>
                          <div className="text-xs text-gray-500">
                            <Clock className="inline mr-1" size={12} />
                            {conflito.horario1}
                          </div>
                          <div className="text-xs text-gray-500">
                            <Users className="inline mr-1" size={12} />
                            {conflito.reserva1.Responsável}
                          </div>
                        </div>
                        <div className="bg-white p-3 rounded border-l-2 border-orange-400">
                          <div className="font-semibold text-gray-800">{conflito.reserva2.Grupo}</div>
                          <div className="text-sm text-gray-600 mb-1">{conflito.reserva2.Atividade}</div>
                          <div className="text-xs text-gray-500">
                            <Clock className="inline mr-1" size={12} />
                            {conflito.horario2}
                          </div>
                          <div className="text-xs text-gray-500">
                            <Users className="inline mr-1" size={12} />
                            {conflito.reserva2.Responsável}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'sugestoes' && (
            <div>
              <h2 className="text-xl font-bold mb-4 text-gray-800 flex items-center gap-2">
                <CheckCircle className="text-green-600" />
                Recomendações de Salas ({sugestoes.length})
              </h2>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {sugestoes.map((sug, idx) => (
                  <div key={idx} className={`border-l-4 p-4 rounded-lg hover:shadow-md transition-shadow ${
                    sug.conflitosTotal === 0 ? 'border-green-500 bg-green-50' : 'border-yellow-500 bg-yellow-50'
                  }`}>
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex-1">
                        <div className="font-bold text-gray-800 text-lg">{sug.atividade}</div>
                        <div className="text-sm text-gray-600">{sug.grupo} • {sug.responsavel}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-blue-600">{sug.opcaoRecomendada}</div>
                        <div className="text-xs text-gray-500">{new Date(sug.data).toLocaleDateString('pt-BR')}</div>
                      </div>
                    </div>
                    <div className="bg-white p-3 rounded">
                      <div className="text-sm text-gray-600 mb-1">
                        <strong>Opções disponíveis:</strong> {sug.opcoes}
                      </div>
                      <div className={`text-sm font-semibold mt-2 flex items-center gap-2 ${
                        sug.conflitosTotal === 0 ? 'text-green-700' : 'text-yellow-700'
                      }`}>
                        {sug.conflitosTotal === 0 ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
                        {sug.justificativa}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'calendario' && (
            <div>
              <div className="flex flex-wrap gap-3 mb-4">
                <select
                  value={filtroSala}
                  onChange={(e) => setFiltroSala(e.target.value)}
                  className="border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="todas">📍 Todas as Salas</option>
                  {salas.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <select
                  value={filtroGrupo}
                  onChange={(e) => setFiltroGrupo(e.target.value)}
                  className="border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="todos">👥 Todos os Grupos</option>
                  {grupos.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
                <div className="flex-1"></div>
                <div className="text-sm text-gray-600 flex items-center gap-2 bg-gray-100 px-4 py-2 rounded-lg">
                  <FileText size={16} />
                  {dadosFiltrados.length} reservas
                </div>
              </div>
              
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {dadosFiltrados.slice(0, 100).map((reserva, idx) => {
                  const temConflito = conflitos.some(c => 
                    c.sala === reserva.Sala && c.data === reserva.dataOcorrencia
                  );
                  
                  return (
                    <div key={idx} className={`border rounded-lg p-3 hover:shadow-md transition-all ${
                      temConflito ? 'bg-red-50 border-red-300' : 'bg-white border-gray-200'
                    }`}>
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-semibold text-gray-800">{reserva.Atividade}</div>
                          <div className="text-sm text-gray-600 mt-1">
                            <span className="font-medium">{reserva.Grupo}</span> • {reserva.Responsável}
                          </div>
                        </div>
                        <div className="text-right ml-4">
                          <div className="font-bold text-blue-600 text-lg">{reserva.Sala}</div>
                          <div className="text-sm text-gray-600">{new Date(reserva.dataOcorrencia).toLocaleDateString('pt-BR')}</div>
                          <div className="text-xs text-gray-500 mt-1 flex items-center justify-end gap-1">
                            <Clock size={12} />
                            {reserva['Hora Início']} - {calcularHoraFim(reserva['Hora Início'], reserva['Hora fim'])}
                          </div>
                          {temConflito && (
                            <div className="text-xs text-red-600 font-semibold mt-1 flex items-center justify-end gap-1">
                              <AlertTriangle size={12} />
                              Conflito
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
                {dadosFiltrados.length > 100 && (
                  <div className="text-center py-4 text-gray-500 text-sm bg-gray-50 rounded-lg">
                    Mostrando 100 de {dadosFiltrados.length} reservas. Use os filtros para refinar.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AnaliseSalasReal;