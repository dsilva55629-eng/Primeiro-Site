from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

# =========================================================
# CONFIGURAÇÕES
# =========================================================

app.secret_key = "chave_secreta_do_davi"

app.config['PERMANENT_SESSION_LIFETIME'] = (
    60 * 60 * 24 * 365 * 100
)

socketio = SocketIO(
    app,
    async_mode='eventlet'
)


# =========================================================
# BANCO DE DADOS
# =========================================================

def conectar_banco():

    return sqlite3.connect("banco.db")


def init_db():

    conn = conectar_banco()
    cursor = conn.cursor()

    # =====================================================
    # USUÁRIOS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nome TEXT NOT NULL,

            usuario TEXT UNIQUE NOT NULL,

            senha TEXT NOT NULL,

            tipo TEXT NOT NULL DEFAULT 'usuario',

            banido INTEGER NOT NULL DEFAULT 0,

            ban_expira TEXT,

            criado_em TEXT NOT NULL
        )
    """)

    # =====================================================
    # BLOCO DE NOTAS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            usuario TEXT,

            conteudo TEXT
        )
    """)

    # =====================================================
    # MURAL
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mural (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            usuario TEXT,

            texto TEXT,

            hora TEXT
        )
    """)

    # =====================================================
    # CHAT
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            usuario TEXT,

            mensagem TEXT,

            hora TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# CRIAR ADM PRINCIPAL
# =========================================================

def criar_admin():

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM usuarios
        WHERE tipo = 'admin'
        LIMIT 1
    """)

    admin_existente = cursor.fetchone()

    if not admin_existente:

        admin_usuario = "admin"
        admin_senha = "admin123"

        senha_hash = generate_password_hash(
            admin_senha
        )

        criado_em = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO usuarios
            (
                nome,
                usuario,
                senha,
                tipo,
                banido,
                ban_expira,
                criado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "Administrador",
            admin_usuario,
            senha_hash,
            "admin",
            0,
            None,
            criado_em
        ))

        conn.commit()

    conn.close()


criar_admin()


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def usuario_logado():

    return session.get('usuario')


def buscar_usuario(usuario):

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            nome,
            usuario,
            senha,
            tipo,
            banido,
            ban_expira,
            criado_em
        FROM usuarios
        WHERE usuario = ?
    """, (usuario,))

    resultado = cursor.fetchone()

    conn.close()

    return resultado


def verificar_banimento(usuario):

    dados = buscar_usuario(usuario)

    if not dados:
        return False

    banido = dados[5]
    ban_expira = dados[6]

    # Não está banido
    if not banido:
        return False

    # Banimento permanente
    if not ban_expira:
        return True

    # Banimento temporário
    try:

        data_expiracao = datetime.fromisoformat(
            ban_expira
        )

        if datetime.now() < data_expiracao:
            return True

        # Banimento acabou
        conn = conectar_banco()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE usuarios
            SET banido = 0,
                ban_expira = NULL
            WHERE usuario = ?
        """, (usuario,))

        conn.commit()
        conn.close()

        return False

    except ValueError:

        return True


def exigir_login():

    if 'usuario' not in session:
        return False

    usuario = session['usuario']

    if verificar_banimento(usuario):

        session.clear()
        return False

    return True


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route('/')
def menu_principal():

    if not exigir_login():
        return redirect('/login')

    return render_template(
        'index.html',
        usuario=session['usuario']
    )


# =========================================================
# LOGIN
# =========================================================

@app.route('/login')
def pagina_login():

    if 'usuario' in session:

        if not verificar_banimento(session['usuario']):
            return redirect('/')

        session.clear()

    return render_template('login.html')


# =========================================================
# CADASTRO
# =========================================================

@app.route('/cadastrar', methods=['POST'])
def cadastrar():

    nome = request.form.get(
        'nome',
        ''
    ).strip()

    usuario = request.form.get(
        'usuario',
        ''
    ).strip()

    senha = request.form.get(
        'senha',
        ''
    )

    # -----------------------------------------
    # VALIDAÇÕES
    # -----------------------------------------

    if not nome or not usuario or not senha:

        return "Preencha nome, usuário e senha."

    if len(nome) < 2:

        return "Digite um nome válido."

    if len(usuario) < 3:

        return "O usuário precisa ter pelo menos 3 caracteres."

    if len(senha) < 4:

        return "A senha precisa ter pelo menos 4 caracteres."

    # -----------------------------------------
    # VERIFICA SE USUÁRIO JÁ EXISTE
    # -----------------------------------------

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM usuarios
        WHERE usuario = ?
    """, (usuario,))

    if cursor.fetchone():

        conn.close()

        return "Esse usuário já existe."

    # -----------------------------------------
    # CRIA CONTA NORMAL
    # -----------------------------------------

    senha_hash = generate_password_hash(senha)

    criado_em = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO usuarios
        (
            nome,
            usuario,
            senha,
            tipo,
            banido,
            ban_expira,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        nome,
        usuario,
        senha_hash,
        'usuario',
        0,
        None,
        criado_em
    ))

    conn.commit()
    conn.close()

    # -----------------------------------------
    # LOGIN AUTOMÁTICO
    # -----------------------------------------

    session.permanent = True

    session['usuario'] = usuario

    return redirect('/')


# =========================================================
# ENTRAR
# =========================================================

@app.route('/entrar', methods=['POST'])
def entrar():

    usuario = request.form.get(
        'usuario',
        ''
    ).strip()

    senha = request.form.get(
        'senha',
        ''
    )

    resultado = buscar_usuario(usuario)

    if not resultado:

        return "Usuário ou senha incorretos."

    senha_banco = resultado[3]

    if not check_password_hash(
        senha_banco,
        senha
    ):

        return "Usuário ou senha incorretos."

    # -----------------------------------------
    # VERIFICAR BANIMENTO
    # -----------------------------------------

    if verificar_banimento(usuario):

        dados = buscar_usuario(usuario)

        ban_expira = dados[6]

        if ban_expira:

            try:

                data = datetime.fromisoformat(
                    ban_expira
                )

                restante = data - datetime.now()

                minutos = int(
                    restante.total_seconds() / 60
                )

                return (
                    "Sua conta está temporariamente banida. "
                    f"Tempo restante aproximado: {minutos} minutos."
                )

            except ValueError:

                return "Sua conta está banida."

        return "Sua conta foi banida permanentemente."

    # -----------------------------------------
    # LOGIN
    # -----------------------------------------

    if request.form.get('lembrar'):

        session.permanent = True

    else:

        session.permanent = False

    session['usuario'] = resultado[2]

    return redirect('/')


# =========================================================
# SAIR
# =========================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')


# =========================================================
# BLOCO DE NOTAS
# =========================================================

@app.route('/bloco')
def pagina_bloco():

    if not exigir_login():
        return redirect('/login')

    usuario = session['usuario']

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT conteudo
        FROM notas
        WHERE usuario = ?
    """, (usuario,))

    resultado = cursor.fetchone()

    conn.close()

    texto_nota = (
        resultado[0]
        if resultado
        else ""
    )

    return render_template(
        'bloco.html',
        texto_nota=texto_nota,
        usuario=usuario
    )


@app.route('/salvar_nota', methods=['POST'])
def salvar_nota():

    if not exigir_login():
        return redirect('/login')

    usuario = session['usuario']

    texto_nota = request.form.get(
        'conteudo_nota',
        ''
    )

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM notas
        WHERE usuario = ?
    """, (usuario,))

    if cursor.fetchone():

        cursor.execute("""
            UPDATE notas
            SET conteudo = ?
            WHERE usuario = ?
        """, (
            texto_nota,
            usuario
        ))

    else:

        cursor.execute("""
            INSERT INTO notas
            (
                usuario,
                conteudo
            )
            VALUES (?, ?)
        """, (
            usuario,
            texto_nota
        ))

    conn.commit()
    conn.close()

    return redirect('/bloco')


# =========================================================
# MURAL
# =========================================================

@app.route('/mural')
def pagina_mural():

    if not exigir_login():
        return redirect('/login')

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            usuario,
            texto,
            hora
        FROM mural
        ORDER BY id DESC
    """)

    recados_banco = cursor.fetchall()

    conn.close()

    lista_de_tarefas = [

        {
            "id": r[0],
            "usuario": r[1],
            "texto": r[2],
            "hora": r[3]
        }

        for r in recados_banco

    ]

    return render_template(
        'mural.html',
        tarefas=lista_de_tarefas,
        usuario=session['usuario']
    )


@app.route('/adicionar_mural', methods=['POST'])
def adicionar_mural():

    if not exigir_login():
        return redirect('/login')

    usuario = session['usuario']

    texto_tarefa = request.form.get(
        'tarefa',
        ''
    ).strip()

    if texto_tarefa:

        hora_atual = datetime.now().strftime(
            "%d/%m %H:%M"
        )

        conn = conectar_banco()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO mural
            (
                usuario,
                texto,
                hora
            )
            VALUES (?, ?, ?)
        """, (
            usuario,
            texto_tarefa,
            hora_atual
        ))

        conn.commit()
        conn.close()

    return redirect('/mural')


@app.route('/deletar_mural/<int:tarefa_id>')
def deletar_mural(tarefa_id):

    if not exigir_login():
        return redirect('/login')

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM mural
        WHERE id = ?
    """, (tarefa_id,))

    conn.commit()
    conn.close()

    return redirect('/mural')


# =========================================================
# CHAT
# =========================================================

@app.route('/chat')
def pagina_chat():

    if not exigir_login():
        return redirect('/login')

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            usuario,
            mensagem,
            hora
        FROM chat
        ORDER BY id ASC
    """)

    historico = cursor.fetchall()

    conn.close()

    mensagens = [

        {
            "usuario": h[0],
            "mensagem": h[1],
            "hora": h[2]
        }

        for h in historico

    ]

    return render_template(
        'chat.html',
        historico=mensagens,
        usuario=session['usuario']
    )


@socketio.on('enviar_mensagem')
def gerenciar_mensagem(data):

    if not exigir_login():
        return

    usuario = session['usuario']

    mensagem = data.get(
        'mensagem',
        ''
    ).strip()

    if not mensagem:
        return

    hora_atual = datetime.now().strftime(
        "%H:%M"
    )

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO chat
        (
            usuario,
            mensagem,
            hora
        )
        VALUES (?, ?, ?)
    """, (
        usuario,
        mensagem,
        hora_atual
    ))

    conn.commit()
    conn.close()

    emit(
        'receber_mensagem',
        {
            'usuario': usuario,
            'mensagem': mensagem,
            'hora': hora_atual
        },
        broadcast=True
    )


# =========================================================
# INICIAR
# =========================================================

if __name__ == '__main__':

    socketio.run(
        app,
        debug=True
    )
