COMO SUBIR NO COOLIFY

1) Envie esta pasta para um repositório no GitHub.
2) No Coolify, crie um novo recurso: Application > GitHub Repository.
3) Selecione o repositório.
4) Build Pack: Dockerfile.
5) Porta/Port: 5000.
6) Variáveis de ambiente:
   PORT=5000
   DATABASE_PATH=/data/katito.db
7) Crie um volume persistente:
   Source: katito_data
   Destination: /data
8) Faça o deploy.

IMPORTANTE:
Sem o volume em /data, o banco SQLite pode sumir quando redeployar.

CÁLCULO DO SALDO:
Saldo da mensalidade = mensalidades pagas - gastos de churrasco.
Cerveja e coca NÃO entram no saldo, porque são rateio separado por jogador ativo.
