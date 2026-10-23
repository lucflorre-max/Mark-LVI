"""
jarvis/brain/policy.py — o que exige CONFIRM por clique antes de rodar.

Regra do CLAUDE.md: nada que envie mensagem, altere agenda, mude prioridade ou
execute comando/arquivo/navegador no PC roda sem confirmação do usuário.

O Mark só confirma desligar, reiniciar e Wi-Fi (auditoria, achado 2). Esta
lista cobre as outras ações do Mark. Ela é lida pelo portão em
jarvis/brain/gate.py, chamado no despacho de ações do main.py.

Como ler a tabela:
    ALL               — toda chamada da ferramenta pede confirmação.
    frozenset({...})  — só as sub-ações listadas (parâmetro `action`/`mode`).
Ferramenta fora da tabela: roda direto.

Sub-ação ausente ou desconhecida numa ferramenta parcial conta como perigosa.
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
}


def sub_action(args: dict) -> str:
    """A sub-ação pedida, normalizada. '' quando não veio."""
    raw = args.get("action") or args.get("mode") or ""
    return str(raw).strip().lower()


def requires_confirm(name: str, args: dict | None) -> bool:
    """True quando a chamada `name(args)` precisa do clique em CONFIRM."""
    if name in _ALWAYS:
        return True
    safe = _SAFE.get(name)
    if safe is None:
        return False
    action = sub_action(args or {})
    if name == "code_helper" and not action:
        action = "auto"   # padrão do code_helper, que pode executar código
    return action not in safe


def describe(name: str, args: dict | None, limit: int = 160) -> tuple[str, str]:
    """(título, detalhe) para o banner, em pt-BR e sem textos enormes."""
    args = args or {}
    title = LABELS.get(name, name)
    action = sub_action(args)
    if action:
        title = f"{title}: {action}"
    parts = []
    for key, value in args.items():
        if key in ("action", "mode") or value in (None, "", [], {}):
            continue
        text = str(value).replace("\n", " ")
        parts.append(f"{key}: {text}")
    detail = " · ".join(parts)
    if len(detail) > limit:
        detail = detail[: limit - 1] + "…"
    return title, detail
