SISTEMA FINANCEIRO - PELADA DO KATITO

Como rodar no Windows:

1) Extraia o ZIP em uma pasta.
2) Abra o CMD dentro da pasta.
3) Rode:
   py -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python app.py

4) Abra no navegador:
   http://127.0.0.1:5000

O sistema cria o banco katito.db automaticamente.

Funções:
- Cadastro de jogadores
- Configuração da mensalidade e dia de vencimento
- Controle mensal: pago, pendente e em atraso
- Alertas de mensalidade atrasada
- Lançamento de gastos: churrasco, cerveja, coca/refrigerante e outros
- Churrasco entra como gasto do mês
- Cerveja e coca são calculadas no rateio separado entre jogadores ativos
- Relatório mensal com saldo, recebidos, gastos e rateio
