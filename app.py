from flask import Flask, render_template, request, redirect, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3


# =========================================================
# CONFIGURAÇÃO
# =========================================================

app = Flask(__name__)

app.secret_key = "chave_secreta_do_davi"
app.permanent_session_lifetime = timedelta(days=36500)

socketio = SocketIO(
    app,
    async_mode="eventlet"
)


# =========================================================
# ADMIN PRINCIPAL
# =========================================================

ADMIN_USUARIO = "adm_master_47"
ADMIN_SENHA = "R7!mQ2#vL9@xK4"


# =========================================================
# BANCO DE DADOS
# =========================================================

def conectar_banco():
    return sqlite3.connect("banco.db")


def init_db():

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            tipo TEXT DEFAULT 'usuario',
            banido INTEGER DEFAULT 0,
            ban_expira TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            titulo TEXT,
            texto TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mural (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            texto TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def configurar_admin():

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM usuarios
        WHERE tipo = 'admin'
        LIMIT 1
    """)

    admin = cursor.fetchone()

    senha_hash = generate_password_hash(ADMIN_SENHA)

    if admin:

        cursor.execute("""
            UPDATE usuarios
            SET nome = ?,
                usuario = ?,
                senha = ?,
                tipo = 'admin',
                banido = 0,
                ban_expira = NULL
            WHERE id = ?
        """, (
            "Administrador",
            ADMIN_USUARIO,
            senha_hash,
            admin[0]
        ))

    else:

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
            VALUES (?, ?, ?, 'admin', 0, NULL, ?)
        """, (
            "Administrador",
            ADMIN_USUARIO,
            senha_hash,
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

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

    dados = cursor.fetchone()

    conn.close()

    return dados


def verificar_banimento(usuario):

    dados = buscar_usuario(usuario)

    if not dados:
        return False, None

    banido = dados[5]
    ban_expira = dados[6]

    if not banido:
        return False, None

    # Banimento permanente
    if not ban_expira:
        return True, "permanente"

    try:
        expiracao = datetime.fromisoformat(ban_expira)

        if datetime.now() >= expiracao:

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

            return False, None

        return True, expiracao.strftime("%d/%m/%Y %H:%M")

    except ValueError:

        return True, "permanente"


def exigir_login():

    if "usuario" not in session:
        return False

    banido, _ = verificar_banimento(
        session["usuario"]
    )

    if banido:
        session.clear()
        return False

    return True


def exigir_admin():

    if "usuario" not in session:
        return False

    dados = buscar_usuario(
        session["usuario"]
    )

    if not dados:
        return False

    if dados[4] != "admin":
        return False

    banido, _ = verificar_banimento(
        session["usuario"]
    )

    if banido:
        session.clear()
        return False

    return True


# =========================================================
# INICIALIZAÇÃO DO BANCO
# =========================================================

init_db()
configurar_admin()


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route("/")
def index():

    if not exigir_login():
        return redirect("/login")

    dados = buscar_usuario(
        session["usuario"]
    )

    eh_admin = (
        dados
        and dados[4] == "admin"
    )

    return render_template(
        "index.html",
        usuario=session["usuario"],
        nome=dados[1] if dados else "",
        eh_admin=eh_admin
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login")
def login():

    if "usuario" in session:

        if exigir_login():
            return redirect("/")

    return render_template("login.html")


@app.route("/cadastrar", methods=["POST"])
def cadastrar():

    nome = request.form.get(
        "nome",
        ""
    ).strip()

    usuario = request.form.get(
        "usuario",
        ""
    ).strip()

    senha = request.form.get(
        "senha",
        ""
    )

    if not nome or not usuario or not senha:
        return "Preencha todos os campos.", 400

    if len(usuario) < 3:
        return "O nome de usuário precisa ter pelo menos 3 caracteres.", 400

    if len(senha) < 4:
        return "A senha precisa ter pelo menos 4 caracteres.", 400

    existente = buscar_usuario(usuario)

    if existente:
        return "Esse nome de usuário já está sendo usado.", 400

    senha_hash = generate_password_hash(senha)

    conn = conectar_banco()
    cursor = conn.cursor()

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
        VALUES (?, ?, ?, 'usuario', 0, NULL, ?)
    """, (
        nome,
        usuario,
        senha_hash,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    session.permanent = True
    session["usuario"] = usuario

    return redirect("/")


@app.route("/entrar", methods=["POST"])
def entrar():

    usuario = request.form.get(
        "usuario",
        ""
    ).strip()

    senha = request.form.get(
        "senha",
        ""
    )

    dados = buscar_usuario(usuario)

    if not dados:
        return "Usuário ou senha incorretos.", 401

    senha_correta = check_password_hash(
        dados[3],
        senha
    )

    if not senha_correta:
        return "Usuário ou senha incorretos.", 401

    banido, motivo = verificar_banimento(usuario)

    if banido:

        if motivo == "permanente":
            return "Sua conta está banida permanentemente.", 403

        return (
            f"Sua conta está banida até {motivo}."
        ), 403

    session.permanent = True
    session["usuario"] = usuario

    return redirect("/")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================================================
# BLOCO / NOTAS
# =========================================================

@app.route("/bloco")
def bloco():

    if not exigir_login():
        return redirect("/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            titulo,
            texto,
            criado_em
        FROM notas
        WHERE usuario = ?
        ORDER BY id DESC
    """, (
        session["usuario"],
    ))

    notas = cursor.fetchall()

    conn.close()

    return render_template(
        "bloco.html",
        notas=notas
    )


@app.route("/bloco/salvar", methods=["POST"])
def salvar_bloco():

    if not exigir_login():
        return redirect("/login")

    titulo = request.form.get(
        "titulo",
        ""
    ).strip()

    texto = request.form.get(
        "texto",
        ""
    ).strip()

    if not texto:
        return redirect("/bloco")

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO notas
        (
            usuario,
            titulo,
            texto,
            criado_em
        )
        VALUES (?, ?, ?, ?)
    """, (
        session["usuario"],
        titulo,
        texto,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    return redirect("/bloco")


@app.route("/bloco/excluir/<int:id>", methods=["POST"])
def excluir_bloco(id):

    if not exigir_login():
        return redirect("/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM notas
        WHERE id = ?
        AND usuario = ?
    """, (
        id,
        session["usuario"]
    ))

    conn.commit()
    conn.close()

    return redirect("/bloco")


# =========================================================
# MURAL
# =========================================================

@app.route("/mural")
def mural():

    if not exigir_login():
        return redirect("/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            usuario,
            texto,
            criado_em
        FROM mural
        ORDER BY id DESC
    """)

    mensagens = cursor.fetchall()

    conn.close()

    return render_template(
        "mural.html",
        mensagens=mensagens
    )


@app.route("/mural/postar", methods=["POST"])
def postar_mural():

    if not exigir_login():
        return redirect("/login")

    texto = request.form.get(
        "texto",
        ""
    ).strip()

    if not texto:
        return redirect("/mural")

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO mural
        (
            usuario,
            texto,
            criado_em
        )
        VALUES (?, ?, ?)
    """, (
        session["usuario"],
        texto,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    return redirect("/mural")


@app.route("/mural/excluir/<int:id>", methods=["POST"])
def excluir_mural(id):

    if not exigir_login():
        return redirect("/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM mural
        WHERE id = ?
        AND usuario = ?
    """, (
        id,
        session["usuario"]
    ))

    conn.commit()
    conn.close()

    return redirect("/mural")


# =========================================================
# CHAT
# =========================================================

@app.route("/chat")
def chat():

    if not exigir_login():
        return redirect("/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            usuario,
            mensagem,
            criado_em
        FROM chat
        ORDER BY id ASC
    """)

    historico = cursor.fetchall()

    conn.close()

    return render_template(
        "chat.html",
        historico=historico
    )


@socketio.on("enviar_mensagem")
def enviar_mensagem(data):

    if "usuario" not in session:
        return

    mensagem = ""

    if isinstance(data, dict):
        mensagem = str(
            data.get("mensagem", "")
        ).strip()

    if not mensagem:
        return

    if len(mensagem) > 2000:
        mensagem = mensagem[:2000]

    usuario = session["usuario"]

    banido, _ = verificar_banimento(usuario)

    if banido:
        return

    criado_em = datetime.now().isoformat()

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO chat
        (
            usuario,
            mensagem,
            criado_em
        )
        VALUES (?, ?, ?)
    """, (
        usuario,
        mensagem,
        criado_em
    ))

    mensagem_id = cursor.lastrowid

    conn.commit()
    conn.close()

    emit(
        "receber_mensagem",
        {
            "id": mensagem_id,
            "usuario": usuario,
            "mensagem": mensagem,
            "criado_em": criado_em
        },
        broadcast=True
    )


# =========================================================
# ADMIN
# =========================================================

@app.route("/admin")
def admin():

    if not exigir_admin():
        return "Acesso negado.", 403

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
        ORDER BY id DESC
    """)

    usuarios = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*)
        FROM usuarios
        WHERE tipo = 'usuario'
    """)

    total_usuarios = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM usuarios
        WHERE tipo = 'usuario'
        AND banido = 1
    """)

    total_banidos = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM chat
    """)

    total_mensagens = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "admin.html",
        usuarios=usuarios,
        total_usuarios=total_usuarios,
        total_banidos=total_banidos,
        total_mensagens=total_mensagens
    )


# =========================================================
# ADMIN - BANIR
# =========================================================

@app.route("/admin/banir", methods=["POST"])
def admin_banir():

    if not exigir_admin():
        return "Acesso negado.", 403

    usuario = request.form.get(
        "usuario",
        ""
    ).strip()

    duracao = request.form.get(
        "duracao",
        ""
    ).strip().lower()

    if not usuario:
        return "Usuário inválido.", 400

    dados = buscar_usuario(usuario)

    if not dados:
        return "Usuário não encontrado.", 404

    # Não permite banir administradores
    if dados[4] == "admin":
        return "Não é possível banir um administrador.", 403

    # Banimento permanente
    if duracao == "p":

        conn = conectar_banco()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE usuarios
            SET banido = 1,
                ban_expira = NULL
            WHERE usuario = ?
        """, (
            usuario,
        ))

        conn.commit()
        conn.close()

        return redirect("/admin")

    # Banimento temporário
    try:

        minutos = int(duracao)

        if minutos <= 0:
            return "A duração precisa ser maior que zero.", 400

        expiracao = (
            datetime.now()
            + timedelta(minutes=minutos)
        ).isoformat()

    except ValueError:

        return (
            "Duração inválida. Use P ou um número de minutos."
        ), 400

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET banido = 1,
            ban_expira = ?
        WHERE usuario = ?
    """, (
        expiracao,
        usuario
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


# =========================================================
# ADMIN - DESBANIR
# =========================================================

@app.route("/admin/desbanir", methods=["POST"])
def admin_desbanir():

    if not exigir_admin():
        return "Acesso negado.", 403

    usuario = request.form.get(
        "usuario",
        ""
    ).strip()

    if not usuario:
        return "Usuário inválido.", 400

    dados = buscar_usuario(usuario)

    if not dados:
        return "Usuário não encontrado.", 404

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET banido = 0,
            ban_expira = NULL
        WHERE usuario = ?
    """, (
        usuario,
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


# =========================================================
# ADMIN - EDITAR USUÁRIO
# =========================================================

@app.route("/admin/editar", methods=["POST"])
def admin_editar():

    if not exigir_admin():
        return "Acesso negado.", 403

    usuario_atual = request.form.get(
        "usuario_atual",
        ""
    ).strip()

    novo_nome = request.form.get(
        "nome",
        ""
    ).strip()

    novo_usuario = request.form.get(
        "usuario",
        ""
    ).strip()

    if (
        not usuario_atual
        or not novo_nome
        or not novo_usuario
    ):
        return "Preencha todos os campos.", 400

    dados = buscar_usuario(
        usuario_atual
    )

    if not dados:
        return "Usuário não encontrado.", 404

    # Não permite editar administrador
    if dados[4] == "admin":
        return (
            "O administrador principal não pode "
            "ser editado por aqui."
        ), 403

    outro_usuario = buscar_usuario(
        novo_usuario
    )

    if (
        outro_usuario
        and outro_usuario[0] != dados[0]
    ):
        return (
            "Esse nome de usuário já está sendo usado."
        ), 400

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET nome = ?,
            usuario = ?
        WHERE id = ?
    """, (
        novo_nome,
        novo_usuario,
        dados[0]
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


# =========================================================
# ADMIN - EXCLUIR USUÁRIO
# =========================================================

@app.route("/admin/excluir", methods=["POST"])
def admin_excluir():

    if not exigir_admin():
        return "Acesso negado.", 403

    usuario = request.form.get(
        "usuario",
        ""
    ).strip()

    if not usuario:
        return "Usuário inválido.", 400

    dados = buscar_usuario(usuario)

    if not dados:
        return "Usuário não encontrado.", 404

    # Proteção do ADM
    if dados[4] == "admin":
        return "Não é possível excluir um administrador.", 403

    conn = conectar_banco()
    cursor = conn.cursor()

    # Apaga notas
    cursor.execute("""
        DELETE FROM notas
        WHERE usuario = ?
    """, (
        usuario,
    ))

    # Apaga posts do mural
    cursor.execute("""
        DELETE FROM mural
        WHERE usuario = ?
    """, (
        usuario,
    ))

    # Apaga mensagens do chat
    cursor.execute("""
        DELETE FROM chat
        WHERE usuario = ?
    """, (
        usuario,
    ))

    # Apaga conta
    cursor.execute("""
        DELETE FROM usuarios
        WHERE usuario = ?
    """, (
        usuario,
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


# =========================================================
# EXECUTAR
# =========================================================

if __name__ == "__main__":

    socketio.run(
        app,
        host="0.0.0.0",
        port=5000
    )
