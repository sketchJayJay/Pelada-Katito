from flask import Flask, render_template, request, redirect, url_for, flash
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime

APP_DIR = Path(__file__).resolve().parent
# No Coolify use DATABASE_PATH=/data/katito.db e crie um volume persistente em /data
DB_PATH = Path(os.environ.get('DATABASE_PATH', APP_DIR / 'katito.db'))

app = Flask(__name__)
app.secret_key = 'katito-financeiro-secreto'

MESES = [
    (1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'), (4, 'Abril'),
    (5, 'Maio'), (6, 'Junho'), (7, 'Julho'), (8, 'Agosto'),
    (9, 'Setembro'), (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro')
]

CATEGORIAS = [
    ('churrasco', 'Churrasco'),
    ('cerveja', 'Cerveja'),
    ('coca', 'Coca / Refrigerante'),
    ('outros', 'Outros')
]


def money(v):
    try:
        return float(str(v).replace(',', '.'))
    except Exception:
        return 0.0


def brl(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

app.jinja_env.filters['brl'] = brl


def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mensalidade REAL NOT NULL DEFAULT 50,
            dia_vencimento INTEGER NOT NULL DEFAULT 10
        );
        INSERT OR IGNORE INTO config (id, mensalidade, dia_vencimento) VALUES (1, 50, 10);

        CREATE TABLE IF NOT EXISTS jogadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS mensalidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador_id INTEGER NOT NULL,
            ano INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            pago INTEGER NOT NULL DEFAULT 0,
            data_pagamento TEXT,
            observacao TEXT,
            UNIQUE(jogador_id, ano, mes),
            FOREIGN KEY(jogador_id) REFERENCES jogadores(id)
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            valor REAL NOT NULL,
            observacao TEXT
        );
        ''')


def get_config():
    with conn() as db:
        return db.execute('SELECT * FROM config WHERE id = 1').fetchone()


def ensure_month(ano, mes):
    with conn() as db:
        jogadores = db.execute('SELECT id FROM jogadores WHERE ativo = 1').fetchall()
        for j in jogadores:
            db.execute('''INSERT OR IGNORE INTO mensalidades (jogador_id, ano, mes, pago)
                          VALUES (?, ?, ?, 0)''', (j['id'], ano, mes))


def status_atraso(row, cfg):
    hoje = date.today()
    venc = date(int(row['ano']), int(row['mes']), min(int(cfg['dia_vencimento']), 28))
    if row['pago']:
        return 'Pago'
    if hoje > venc:
        return 'Em atraso'
    return 'Pendente'


@app.route('/')
def index():
    hoje = date.today()
    ano = int(request.args.get('ano', hoje.year))
    mes = int(request.args.get('mes', hoje.month))
    ensure_month(ano, mes)
    cfg = get_config()
    with conn() as db:
        total_jogadores = db.execute('SELECT COUNT(*) AS n FROM jogadores WHERE ativo = 1').fetchone()['n']
        mensalidades = db.execute('''
            SELECT m.*, j.nome FROM mensalidades m
            JOIN jogadores j ON j.id = m.jogador_id
            WHERE m.ano = ? AND m.mes = ? AND j.ativo = 1
            ORDER BY j.nome
        ''', (ano, mes)).fetchall()
        pagos = sum(1 for m in mensalidades if m['pago'])
        atrasados = sum(1 for m in mensalidades if status_atraso(m, cfg) == 'Em atraso')
        recebido = pagos * float(cfg['mensalidade'])
        churrasco_mes = db.execute('''SELECT COALESCE(SUM(valor),0) AS total FROM gastos
                                      WHERE strftime('%Y', data)=? AND strftime('%m', data)=? AND categoria='churrasco' ''',
                                   (str(ano), f'{mes:02d}')).fetchone()['total']
        bebidas_mes = db.execute('''SELECT COALESCE(SUM(valor),0) AS total FROM gastos
                                    WHERE strftime('%Y', data)=? AND strftime('%m', data)=? AND categoria IN ('cerveja','coca') ''',
                                 (str(ano), f'{mes:02d}')).fetchone()['total']
    rateio_bebidas = (bebidas_mes / total_jogadores) if total_jogadores else 0
    # Saldo do mês considera SOMENTE o caixa da mensalidade:
    # mensalidades recebidas menos churrasco. Cerveja e coca ficam fora, pois são rateio separado.
    saldo_mes = recebido - churrasco_mes
    alertas = [m for m in mensalidades if status_atraso(m, cfg) == 'Em atraso']
    return render_template('index.html', ano=ano, mes=mes, meses=MESES, cfg=cfg,
                           total_jogadores=total_jogadores, pagos=pagos, atrasados=atrasados,
                           recebido=recebido, churrasco_mes=churrasco_mes,
                           bebidas_mes=bebidas_mes, rateio_bebidas=rateio_bebidas,
                           saldo_mes=saldo_mes, alertas=alertas)


@app.route('/config', methods=['POST'])
def salvar_config():
    mensalidade = money(request.form.get('mensalidade'))
    dia = int(request.form.get('dia_vencimento') or 10)
    dia = max(1, min(dia, 28))
    with conn() as db:
        db.execute('UPDATE config SET mensalidade=?, dia_vencimento=? WHERE id=1', (mensalidade, dia))
    flash('Configurações salvas.')
    return redirect(url_for('index'))


@app.route('/jogadores', methods=['GET', 'POST'])
def jogadores():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        telefone = request.form.get('telefone', '').strip()
        if nome:
            with conn() as db:
                db.execute('INSERT INTO jogadores (nome, telefone) VALUES (?, ?)', (nome, telefone))
            flash('Jogador cadastrado.')
        return redirect(url_for('jogadores'))
    with conn() as db:
        lista = db.execute('SELECT * FROM jogadores ORDER BY ativo DESC, nome').fetchall()
    return render_template('jogadores.html', jogadores=lista)


@app.route('/jogadores/<int:jogador_id>/toggle', methods=['POST'])
def toggle_jogador(jogador_id):
    with conn() as db:
        atual = db.execute('SELECT ativo FROM jogadores WHERE id=?', (jogador_id,)).fetchone()
        if atual:
            db.execute('UPDATE jogadores SET ativo=? WHERE id=?', (0 if atual['ativo'] else 1, jogador_id))
    return redirect(url_for('jogadores'))


@app.route('/jogadores/<int:jogador_id>/excluir', methods=['POST'])
def excluir_jogador(jogador_id):
    with conn() as db:
        db.execute('DELETE FROM mensalidades WHERE jogador_id=?', (jogador_id,))
        db.execute('DELETE FROM jogadores WHERE id=?', (jogador_id,))
    flash('Jogador excluído.')
    return redirect(url_for('jogadores'))


@app.route('/mensalidades')
def mensalidades():
    hoje = date.today()
    ano = int(request.args.get('ano', hoje.year))
    mes = int(request.args.get('mes', hoje.month))
    ensure_month(ano, mes)
    cfg = get_config()
    with conn() as db:
        lista = db.execute('''
            SELECT m.*, j.nome, j.telefone FROM mensalidades m
            JOIN jogadores j ON j.id = m.jogador_id
            WHERE m.ano = ? AND m.mes = ? AND j.ativo = 1
            ORDER BY j.nome
        ''', (ano, mes)).fetchall()
    linhas = []
    for item in lista:
        d = dict(item)
        d['status'] = status_atraso(item, cfg)
        linhas.append(d)
    return render_template('mensalidades.html', mensalidades=linhas, ano=ano, mes=mes, meses=MESES, cfg=cfg)


@app.route('/mensalidades/<int:mensalidade_id>/pagar', methods=['POST'])
def pagar(mensalidade_id):
    with conn() as db:
        db.execute('UPDATE mensalidades SET pago=1, data_pagamento=?, observacao=? WHERE id=?',
                   (date.today().isoformat(), request.form.get('observacao', ''), mensalidade_id))
    return redirect(request.referrer or url_for('mensalidades'))


@app.route('/mensalidades/<int:mensalidade_id>/desmarcar', methods=['POST'])
def desmarcar(mensalidade_id):
    with conn() as db:
        db.execute('UPDATE mensalidades SET pago=0, data_pagamento=NULL WHERE id=?', (mensalidade_id,))
    return redirect(request.referrer or url_for('mensalidades'))


@app.route('/gastos', methods=['GET', 'POST'])
def gastos():
    if request.method == 'POST':
        data = request.form.get('data') or date.today().isoformat()
        descricao = request.form.get('descricao', '').strip()
        categoria = request.form.get('categoria')
        valor = money(request.form.get('valor'))
        obs = request.form.get('observacao', '')
        if descricao and valor > 0:
            with conn() as db:
                db.execute('INSERT INTO gastos (data, descricao, categoria, valor, observacao) VALUES (?, ?, ?, ?, ?)',
                           (data, descricao, categoria, valor, obs))
            flash('Gasto lançado.')
        return redirect(url_for('gastos'))
    with conn() as db:
        lista = db.execute('SELECT * FROM gastos ORDER BY data DESC, id DESC').fetchall()
        jogadores_ativos = db.execute('SELECT COUNT(*) AS n FROM jogadores WHERE ativo=1').fetchone()['n']
    total_bebidas = sum(float(g['valor']) for g in lista if g['categoria'] in ('cerveja', 'coca'))
    return render_template('gastos.html', gastos=lista, categorias=CATEGORIAS,
                           hoje=date.today().isoformat(), jogadores_ativos=jogadores_ativos,
                           total_bebidas=total_bebidas, rateio=(total_bebidas / jogadores_ativos if jogadores_ativos else 0))


@app.route('/gastos/<int:gasto_id>/excluir', methods=['POST'])
def excluir_gasto(gasto_id):
    with conn() as db:
        db.execute('DELETE FROM gastos WHERE id=?', (gasto_id,))
    flash('Gasto excluído.')
    return redirect(url_for('gastos'))


@app.route('/relatorios')
def relatorios():
    hoje = date.today()
    ano = int(request.args.get('ano', hoje.year))
    mes = int(request.args.get('mes', hoje.month))
    ensure_month(ano, mes)
    cfg = get_config()
    with conn() as db:
        mensalidades = db.execute('''
            SELECT m.*, j.nome FROM mensalidades m JOIN jogadores j ON j.id=m.jogador_id
            WHERE m.ano=? AND m.mes=? AND j.ativo=1 ORDER BY j.nome
        ''', (ano, mes)).fetchall()
        gastos = db.execute('''SELECT * FROM gastos WHERE strftime('%Y', data)=? AND strftime('%m', data)=?
                               ORDER BY data DESC, id DESC''', (str(ano), f'{mes:02d}')).fetchall()
        jogadores_ativos = db.execute('SELECT COUNT(*) AS n FROM jogadores WHERE ativo=1').fetchone()['n']
    pagos = [m for m in mensalidades if m['pago']]
    atrasados = [m for m in mensalidades if status_atraso(m, cfg) == 'Em atraso']
    pendentes = [m for m in mensalidades if status_atraso(m, cfg) == 'Pendente']
    total_recebido = len(pagos) * float(cfg['mensalidade'])
    total_churrasco = sum(float(g['valor']) for g in gastos if g['categoria'] == 'churrasco')
    total_bebidas = sum(float(g['valor']) for g in gastos if g['categoria'] in ('cerveja', 'coca'))
    # Saldo do mês considera SOMENTE o caixa da mensalidade:
    # mensalidades recebidas menos churrasco. Cerveja e coca ficam fora, pois são rateio separado.
    saldo = total_recebido - total_churrasco
    rateio = total_bebidas / jogadores_ativos if jogadores_ativos else 0
    return render_template('relatorios.html', ano=ano, mes=mes, meses=MESES, cfg=cfg,
                           pagos=pagos, atrasados=atrasados, pendentes=pendentes,
                           gastos=gastos, total_recebido=total_recebido, total_churrasco=total_churrasco,
                           total_bebidas=total_bebidas, saldo=saldo, rateio=rateio,
                           jogadores_ativos=jogadores_ativos)


# Importante para rodar no Coolify/Gunicorn: inicializa o banco quando o app sobe.
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
