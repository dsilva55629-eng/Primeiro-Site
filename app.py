from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = "chave_secreta_do_davi"

# Função para conectar ao banco de dados e criar as tabelas corretamente
def init_db():
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    # Tabela para o Bloco de Notas (CORRIGIDO AQUI)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            conteudo TEXT
        )
    ''')
    # Tabela para o Mural de Recados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mural (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            texto TEXT,
            hora TEXT
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
    nome = request.form.get('nome_usuario', 'Convidado')
    if nome.strip():
        session['usuario'] = nome.strip()
    return redirect('/')

# --- PÁGINA DO BLOCO DE NOTAS ---
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
    existe = cursor.fetchone()
    
    if existe:
        cursor.execute("UPDATE notas SET conteudo = ? WHERE usuario = ?", (texto_nota, usuario))
    else:
        cursor.execute("INSERT INTO notas (usuario, conteudo) VALUES (?, ?)", (usuario, texto_nota))
        
    conn.commit()
    conn.close()
    return redirect('/bloco')

# --- PÁGINA DO MURAL DE RECADOS ---
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

if __name__ == '__main__':
    app.run(debug=True)
