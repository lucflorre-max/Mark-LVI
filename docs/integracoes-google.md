# Ligar o Google Calendar ao JARVIS

Feito uma vez, pelo dono da conta Google. Leva uns 10 minutos. Nenhum arquivo daqui vai para o Git.

## 1. Criar o projeto e ligar a API

1. Abra <https://console.cloud.google.com/> com a conta Google da agenda.
2. Crie um projeto (ex.: `jarvis-pessoal`).
3. Em **APIs e serviços → Biblioteca**, procure **Google Calendar API** e clique em **Ativar**.

## 2. Tela de consentimento (Google Auth Platform)

1. **Branding:** nome do app `JARVIS`, seu e-mail de suporte e de contato.
2. **Público-alvo (Audience):** tipo **Externo**. Em **Usuários de teste**, adicione o seu e-mail.
3. **Acesso a dados (Data access):** adicione o escopo
   `https://www.googleapis.com/auth/calendar.events.owned`
   ("ver, criar, alterar e excluir eventos nas agendas que você possui"). Nenhum outro.
4. **Importante:** em modo **Teste**, o Google expira a autorização a cada 7 dias. Para não precisar reautorizar toda semana, em **Público-alvo** clique em **Publicar app** (fica "Em produção"). Para uso só seu, o Google mostra o aviso "app não verificado" na autorização; é esperado: clique em **Avançado → Acessar JARVIS**.

## 3. Credencial

1. **Clientes (Clients) → Criar cliente**, tipo **App para computador** (Desktop app), nome `JARVIS PC`.
2. Baixe o JSON e salve exatamente como:
   `C:\Users\55519\projetos\jarvis\config\google\client_secret.json`
   (crie a pasta `google` se não existir).

## 4. Autorizar

No terminal do projeto, com o `.venv` ativo:

```powershell
python -m jarvis.integrations.google_auth autorizar
```

O navegador abre, você escolhe a conta e permite. O token fica em `config/google/token_calendar.json`.

Para conferir:

```powershell
python -m jarvis.integrations.google_auth status
```

## Revogar o acesso

<https://myaccount.google.com/permissions> → JARVIS → **Remover acesso**. Depois apague `config/google/token_calendar.json`.
