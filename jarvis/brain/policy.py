"""
jarvis/brain/policy.py — o que exige CONFIRM por clique antes de rodar.

Regra do CLAUDE.md: nada que envie mensagem, altere agenda, mude prioridade ou
execute comando/arquivo/navegador no PC roda sem confirmação do usuário.

O Mark só confirma desligar, reiniciar e Wi-Fi (auditoria, achado 2). Esta
lista cobre as outras ações do Mark e as do JARVIS. Ela é lida pelo portão em
jarvis/brain/gate.py, chamado no despacho de ações do main.py e pelo serviço
de tarefas.

Três níveis (`nivel()`):
    DIRETO  — ferramenta fora das tabelas, ou sub-ação em _SAFE.
    VOZ     — sub-ação em _VOZ: espera um "sim" falado.
    CLIQUE  — ferramenta em _ALWAYS, ou qualquer outra sub-ação: banner.

Sub-ação ausente ou desconhecida numa ferramenta parcial vai para o CLIQUE.
O modelo pode omitir ou inventar o nome da ação, e na dúvida o portão pergunta.
"""

from __future__ import annotations

ALL = "ALL"

# Sub-ações que só leem ou que o Mark já sabe desfazer. Usadas para que uma
# ação ausente/desconhecida caia no lado seguro (confirmar).
_SAFE: dict[str, frozenset[str]] = {
    "computer_control": frozenset({
        "scroll", "move", "copy", "screenshot", "wait", "focus_window",
        "screen_find", "random_data", "user_data",
    }),
    "computer_settings": frozenset({
        "volume_up", "volume_down", "volume_set", "mute",
        "brightness_up", "brightness_down", "sleep_display", "pause_video",
        "full_screen", "minimize", "maximize", "snap_left", "snap_right",
        "switch_window", "show_desktop", "focus_search", "next_tab", "prev_tab",
        "new_tab",   # Ctrl+T não estraga nada; pedir clique só atrapalhava

        "zoom_in", "zoom_out", "zoom_reset", "find_on_page",
        "scroll_up", "scroll_down", "scroll_top", "scroll_bottom",
        "page_up", "page_down", "copy", "screenshot", "lock_screen",
        "dark_mode",
        # O Mark já põe estas três atrás de core/confirm.py. Confirmar aqui de
        # novo mostraria dois banners para a mesma coisa.
        "restart", "shutdown", "toggle_wifi",
    }),
    "browser_control": frozenset({
        "get_text", "get_url", "screenshot", "list_browsers", "scroll",
    }),
    "desktop_control": frozenset({"current_wallpaper", "list", "stats"}),
    "file_controller": frozenset({
        # create/move/copy/rename registram desfazer em core/undo.py.
        "list", "read", "find", "largest", "disk_usage", "info",
        "create_file", "create_folder", "move", "copy", "rename",
    }),
    "code_helper": frozenset({"explain"}),
    "game_updater": frozenset({"list", "download_status", "schedule_status"}),
    # Ações do JARVIS. Criar e concluir são reversíveis (core/undo.py), e
    # criar ainda pede o "sim" por voz antes de salvar (jarvis/tasks/service.py).
    # Uma ação nova que não estiver aqui pede CONFIRM até ser classificada.
    "jarvis_tarefas": frozenset({"criar", "listar_hoje", "concluir", "desfazer"}),
    # Perfil de comunicação: ler, esquecer e rejeitar não criam preferência.
    "jarvis_perfil": frozenset({"sugestoes", "listar", "esquecer", "rejeitar"}),
    # Agenda: consulta roda direto (documento-mestre §11). Criar e alterar
    # compromisso entram na tarefa 3 da Meta 2, com confirmação.
    "jarvis_agenda": frozenset({"ver"}),
}

# Sub-ações que pedem só um "sim" falado em vez do clique (escolha do usuário
# em 23/10/2026: digitar, teclar e clicar sem tocar no mouse). O portão
# confere a transcrição da fala; o modelo não consegue forjar esse "sim".
# Mensagem, apagar arquivo, navegador e código continuam no clique.
_VOZ: dict[str, frozenset[str]] = {
    "computer_control": frozenset({
        "type", "smart_type", "click", "double_click", "right_click",
        "hotkey", "press", "paste", "clear_field", "screen_click", "close_app",
    }),
    "computer_settings": frozenset({
        "type_text", "enter", "escape", "press_key", "paste", "cut", "save",
        "undo", "redo", "select_all", "close_window", "close_tab",
        "refresh_page", "go_back", "go_forward", "task_manager", "file_explorer",
    }),
    # Preferência permanente só depois de um "sim" (CLAUDE.md).
    "jarvis_perfil": frozenset({"lembrar"}),
}

DIRETO, VOZ, CLIQUE = "direto", "voz", "clique"

# Sub-ação usada quando o modelo não manda nenhuma.
_DEFAULT_ACTION = {
    "code_helper": "auto",       # padrão do code_helper, que pode executar código
    "jarvis_tarefas": "criar",
    "jarvis_perfil": "sugestoes",
    "jarvis_agenda": "ver",
}

# As categorias do CLAUDE.md e onde cada uma está coberta. Documentação viva:
# tests/test_policy.py confere que todo exemplo daqui pede CONFIRM.
CATEGORIAS_CONFIRM: dict[str, list[tuple[str, dict]]] = {
    "enviar mensagem": [("send_message", {})],
    "alterar agenda": [("reminder", {})],   # Google Calendar entra na Meta 2
    "apagar em lote": [("file_controller", {"action": "organize_desktop"}),
                       ("desktop_control", {"action": "clean"})],
    "comandos no PC": [("computer_control", {"action": "type"}),
                       ("computer_control", {"action": "close_app"}),
                       ("computer_settings", {"action": "press_key"}),
                       ("code_helper", {"action": "run"}),
                       ("dev_agent", {})],
    "navegador": [("browser_control", {"action": "go_to"})],
}

# Ferramentas que pedem confirmação sempre, seja qual for a sub-ação.
_ALWAYS = frozenset({
    "send_message",   # envia mensagem em nome do usuário
    "dev_agent",      # cria projeto, roda pip install e comandos
    "reminder",       # agenda tarefa no sistema operacional
})

# Rótulos em pt-BR para o banner.
LABELS: dict[str, str] = {
    "send_message":      "Enviar mensagem",
    "computer_control":  "Controlar o computador",
    "computer_settings": "Comando no computador",
    "browser_control":   "Controlar o navegador",
    "desktop_control":   "Alterar a área de trabalho",
    "file_controller":   "Alterar arquivos",
    "code_helper":       "Escrever ou executar código",
    "dev_agent":         "Criar e executar projeto",
    "reminder":          "Agendar lembrete",
    "game_updater":      "Atualizar ou instalar jogos",
    "jarvis_tarefas":    "Tarefas",
    "jarvis_perfil":     "Lembrar do seu jeito de falar",
    "jarvis_agenda":     "Agenda",
}

_ACTION_KEYS = ("action", "mode", "acao")


def sub_action(args: dict) -> str:
    """A sub-ação pedida, normalizada. '' quando não veio."""
    raw = next((args[k] for k in _ACTION_KEYS if args.get(k)), "")
    return str(raw).strip().lower()


def nivel(name: str, args: dict | None) -> str:
    """DIRETO (roda já), VOZ (espera um "sim" falado) ou CLIQUE (banner)."""
    if name in _ALWAYS:
        return CLIQUE
    safe = _SAFE.get(name)
    if safe is None:
        return DIRETO
    action = sub_action(args or {}) or _DEFAULT_ACTION.get(name, "")
    if action in safe:
        return DIRETO
    if action in _VOZ.get(name, ()):
        return VOZ
    return CLIQUE


def requires_confirm(name: str, args: dict | None) -> bool:
    """True quando a chamada `name(args)` precisa de alguma confirmação."""
    return nivel(name, args) != DIRETO


def describe(name: str, args: dict | None, limit: int = 160) -> tuple[str, str]:
    """(título, detalhe) para o banner, em pt-BR e sem textos enormes."""
    args = args or {}
    title = LABELS.get(name, name)
    action = sub_action(args)
    if action:
        title = f"{title}: {action}"
    parts = []
    for key, value in args.items():
        if key in _ACTION_KEYS or value in (None, "", [], {}):
            continue
        text = str(value).replace("\n", " ")
        parts.append(f"{key}: {text}")
    detail = " · ".join(parts)
    if len(detail) > limit:
        detail = detail[: limit - 1] + "…"
    return title, detail
