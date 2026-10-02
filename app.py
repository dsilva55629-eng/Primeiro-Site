from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Chave usada para proteger as sessões
app.secret_key = "chave_secreta_do_davi"

# Sessão permanente por aproximadamente 100 anos
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 365 * 100

socketio = SocketIO(app, async_mode='eventlet')


# =========================================================
# BANCO DE DADOS
# =========================================================

def init_db():

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    # Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')

    # Bloco de notas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            conteudo TEXT
        )
    ''')

    # Mural
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mural (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            texto TEXT,
            hora TEXT
        )
    ''')

    # Chat
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            mensagem TEXT,
            hora TEXT
        )
    ''')

    conn.commit()
    conn.close()


init_db()


# =========================================================
# LOGIN / CADASTRO
# =========================================================

@app.route('/')
def menu_principal():

    if 'usuario' not in session:
        return redirect('/login')

    return render_template(
        'index.html',
        usuario=session['usuario']
    )


@app.route('/login')
def pagina_login():

    if 'usuario' in session:
        return redirect('/')

    return render_template('login.html')


@app.route('/cadastrar', methods=['POST'])
def cadastrar():

    usuario = request.form.get('usuario', '').strip()
    senha = request.form.get('senha', '')

    if not usuario or not senha:
        return "Preencha usuário e senha."

    if len(usuario) < 3:
        return "O usuário precisa ter pelo menos 3 caracteres."

    if len(senha) < 4:
        return "A senha precisa ter pelo menos 4 caracteres."

    senha_hash = generate_password_hash(senha)

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    try:

        cursor.execute(
            "INSERT INTO usuarios (usuario, senha) VALUES (?, ?)",
            (usuario, senha_hash)
        )

        conn.commit()

    except sqlite3.IntegrityError:

        conn.close()

        return "Esse usuário já existe."

    conn.close()

    # Ao criar a conta, mantém o usuário conectado
    session.permanent = True
    session['usuario'] = usuario

    return redirect('/')


@app.route('/entrar', methods=['POST'])
def entrar():

    usuario = request.form.get('usuario', '').strip()
    senha = request.form.get('senha', '')

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT usuario, senha FROM usuarios WHERE usuario = ?",
        (usuario,)
    )

    resultado = cursor.fetchone()

    conn.close()

    if not resultado:
        return "Usuário ou senha incorretos."

    usuario_banco = resultado[0]
    senha_banco = resultado[1]

    if not check_password_hash(senha_banco, senha):
        return "Usuário ou senha incorretos."

    # Se marcar "Lembrar de mim",
    # o login permanece por aproximadamente 100 anos.
    if request.form.get('lembrar'):
        session.permanent = True
    else:
        session.permanent = False

    session['usuario'] = usuario_banco

    return redirect('/')


@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')


# =========================================================
# BLOCO DE NOTAS
# =========================================================

@app.route('/bloco')
def pagina_bloco():

    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT conteudo FROM notas WHERE usuario = ?",
        (usuario,)
    )

    resultado = cursor.fetchone()

    conn.close()

    texto_nota = resultado[0] if resultado else ""

    return render_template(
        'bloco.html',
        texto_nota=texto_nota,
        usuario=usuario
    )


@app.route('/salvar_nota', methods=['POST'])
def salvar_nota():

    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']

    texto_nota = request.form.get(
        'conteudo_nota',
        ''
    )

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM notas WHERE usuario = ?",
        (usuario,)
    )

    if cursor.fetchone():

        cursor.execute(
            "UPDATE notas SET conteudo = ? WHERE usuario = ?",
            (texto_nota, usuario)
        )

    else:

        cursor.execute(
            "INSERT INTO notas (usuario, conteudo) VALUES (?, ?)",
            (usuario, texto_nota)
        )

    conn.commit()
    conn.close()

    return redirect('/bloco')


# =========================================================
# MURAL DE RECADOS
# =========================================================

@app.route('/mural')
def pagina_mural():

    if 'usuario' not in session:
        return redirect('/login')

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, usuario, texto, hora FROM mural ORDER BY id DESC"
    )

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

    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']

    texto_tarefa = request.form.get('tarefa')

    if texto_tarefa:

        hora_atual = datetime.now().strftime(
            "%d/%m %H:%M"
        )

        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO mural (usuario, texto, hora)
            VALUES (?, ?, ?)
            """,
            (
                usuario,
                texto_tarefa,
                hora_atual
            )
        )

        conn.commit()
        conn.close()

    return redirect('/mural')


@app.route('/deletar_mural/<int:tarefa_id>')
def deletar_mural(tarefa_id):

    if 'usuario' not in session:
        return redirect('/login')

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM mural WHERE id = ?",
        (tarefa_id,)
    )

    conn.commit()
    conn.close()

    return redirect('/mural')


# =========================================================
# CHAT
# =========================================================

@app.route('/chat')
def pagina_chat():

    if 'usuario' not in session:
        return redirect('/login')

    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT usuario, mensagem, hora FROM chat ORDER BY id ASC"
    )

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

    # Só permite enviar mensagens estando logado
    if 'usuario' not in session:
        return

    usuario = session['usuario']

    mensagem = data.get(
        'mensagem',
        ''
    ).strip()

    if mensagem:

        hora_atual = datetime.now().strftime(
            "%H:%M"
        )

        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO chat
            (usuario, mensagem, hora)
            VALUES (?, ?, ?)
            """,
            (
                usuario,
                mensagem,
                hora_atual
            )
        )

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
