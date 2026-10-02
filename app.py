from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = "chave_secreta_do_davi"
socketio = SocketIO(app, async_mode='eventlet')

def init_db():
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, conteudo TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mural (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, texto TEXT, hora TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, mensagem TEXT, hora TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def menu_principal():
    if 'usuario' not in session:
        session['usuario'] = "Convidado"
    return render_template('index.html', usuario=session['usuario'])

@app.route('/definir_usuario', methods=['POST'])
def definir_usuario():
    nome = request.form.get('nome_usuario', 'Convidado').strip()
    if nome:
        session['usuario'] = nome
    return redirect('/')

# --- BLOCO DE NOTAS ---
@app.route('/bloco')
def pagina_bloco():
    usuario = session.get('usuario', 'Convidado')
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT conteudo FROM notas WHERE usuario = ?", (usuario,))
    resultado = cursor.fetchone()
    conn.close()
    texto_nota = resultado[0] if resultado else ""
    return render_template('bloco.html', texto_nota=texto_nota, usuario=usuario)

@app.route('/salvar_nota', methods=['POST'])
def salvar_nota():
    usuario = session.get('usuario', 'Convidado')
    texto_nota = request.form.get('conteudo_nota', '')
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM notas WHERE usuario = ?", (usuario,))
    if cursor.fetchone():
        cursor.execute("UPDATE notas SET conteudo = ? WHERE usuario = ?", (texto_nota, usuario))
    else:
        cursor.execute("INSERT INTO notas (usuario, conteudo) VALUES (?, ?)", (usuario, texto_nota))
    conn.commit()
    conn.close()
    return redirect('/bloco')

# --- MURAL DE RECADOS ---
@app.route('/mural')
def pagina_mural():
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, usuario, texto, hora FROM mural ORDER BY id DESC")
    recados_banco = cursor.fetchall()
    conn.close()
    lista_de_tarefas = [{"id": r[0], "usuario": r[1], "texto": r[2], "hora": r[3]} for r in recados_banco]
    return render_template('mural.html', tarefas=lista_de_tarefas, usuario=session.get('usuario', 'Convidado'))

@app.route('/adicionar_mural', methods=['POST'])
def adicionar_mural():
    usuario = session.get('usuario', 'Convidado')
    texto_tarefa = request.form.get('tarefa')
    if texto_tarefa:
        hora_atual = datetime.now().strftime("%d/%m %H:%M")
        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO mural (usuario, texto, hora) VALUES (?, ?, ?)", (usuario, texto_tarefa, hora_atual))
        conn.commit()
        conn.close()
    return redirect('/mural')

@app.route('/deletar_mural/<int:tarefa_id>')
def deletar_mural(tarefa_id):
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mural WHERE id = ?", (tarefa_id,))
    conn.commit()
    conn.close()
    return redirect('/mural')

# --- CHAT EM TEMPO REAL ---
@app.route('/chat')
def pagina_chat():
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT usuario, mensagem, hora FROM chat ORDER BY id ASC")
    historico = cursor.fetchall()
    conn.close()
    mensagens = [{"usuario": h[0], "mensagem": h[1], "hora": h[2]} for h in historico]
    return render_template('chat.html', historico=mensagens, usuario=session.get('usuario', 'Convidado'))

@socketio.on('enviar_mensagem')
def gerenciar_mensagem(data):
    usuario = session.get('usuario', 'Convidado')
    mensagem = data.get('mensagem', '').strip()
    if mensagem:
        hora_atual = datetime.now().strftime("%H:%M")
        conn = sqlite3.connect("banco.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat (usuario, mensagem, hora) VALUES (?, ?, ?)", (usuario, mensagem, hora_atual))
        conn.commit()
        conn.close()
        emit('receber_mensagem', {'usuario': usuario, 'mensagem': mensagem, 'hora': hora_atual}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
