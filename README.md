# Bot de Anotações de Clientes (Telegram para Google Sheets)

### 1. Visão Geral do Projeto

Este projeto é um bot de automação pessoal que monitora um chat do Telegram, captura anotações (enviadas como texto ou áudio) e as organiza automaticamente em uma Planilha Google.

O bot é programado para transcrever áudios, identificar o cliente por aproximação (para evitar duplicatas) e formatar a planilha, criando uma aba separada para cada cliente.

### 2. Funcionalidades Principais

* **Monitoramento de Múltiplos Formatos:** Ouve e processa mensagens de texto, mensagens de voz e arquivos de áudio.
* **Transcrição Gratuita de Áudio:** Utiliza a API Google Speech Recognition para converter áudio (.ogg) em texto (.wav > .txt) sem custo.
* **Organização por Abas:** Cria uma nova aba (guia) na Planilha Google para cada cliente novo.
* **Lógica de "Fuzzy Matching":** Corrige erros de digitação ou transcrição. Se você enviar "Cliente: João Silva" e já existir a aba "João da Silva", o bot salva na aba correta.
* **Formatação Automática:** Aplica estilos automaticamente a novas abas de cliente:
    * **Cabeçalho (Linha 1):** Negrito, Fonte Tamanho 25, Fundo Cinza.
    * **Conteúdo (Linhas 2+):** Fonte Tamanho 18.
* **Feedback ao Usuário:** O bot responde no Telegram confirmando o sucesso ou informando o erro.

### 3. Tecnologias Utilizadas

O bot funciona conectando três serviços de API principais, todos gerenciados por um único script Python.

#### APIs Externas

1.  **Telegram Bot API:**
    * **Propósito:** É o "ouvido" do bot. Usada para ler as mensagens (texto/áudio) enviadas no chat.
    * **Configuração:** Através do `@BotFather` no Telegram para obter o `TOKEN_TELEGRAM`.

2.  **Google Sheets API:**
    * **Propósito:** É a "mão" do bot. Usada para ler, escrever, criar e formatar as abas na planilha.
    * **Configuração:** Através do Google Cloud Console para obter o `credentials.json` e o `ID_PLANILHA`.

3.  **Google Speech Recognition API:**
    * **Propósito:** É o "tradutor" gratuito. Usada para transcrever os áudios.
    * **Configuração:** Nenhuma chave de API é necessária; o acesso é feito pela biblioteca `SpeechRecognition`.

#### Dependências de Sistema

1.  **FFmpeg:**
    * **Propósito:** Um programa de linha de comando essencial para conversão de mídia. É usado pela biblioteca `pydub` para converter o formato de áudio `.ogg` (do Telegram) para `.wav` (que o Google consegue ler).

#### Bibliotecas Python (`pip install ...`)

1.  **`python-telegram-bot` (v20+)**
2.  **`gspread`**
3.  **`google-auth`**
4.  **`SpeechRecognition`**
5.  **`pydub`**
6.  **`fuzzywuzzy`**
7.  **`apscheduler` (v3.10.4)**

### 4. Fluxo de Execução (Como Funciona)

1.  O script `bot_telegram.py` é iniciado.
2.  O bot se conecta ao Telegram e entra em modo "polling" (ouvindo).
3.  Um usuário envia uma mensagem (texto ou áudio).
4.  A função `handle_message` é ativada.
5.  **Se for Áudio:**
    * O áudio `.ogg` é baixado.
    * `pydub` (usando `ffmpeg`) converte o `.ogg` para `.wav`.
    * `SpeechRecognition` envia o `.wav` para a API do Google e recebe o texto transcrito.
6.  **Se for Texto:** O texto original é usado.
7.  O texto (original ou transcrito) é enviado para a função `extrair_dados`.
8.  A função usa Regex (`re.search`) para encontrar as palavras-chave `Cliente:` e `Info:`.
9.  O nome extraído (ex: "João Silva") é enviado para a função `salvar_na_planilha`.
10. `gspread` lista *todas* as abas existentes.
11. `fuzzywuzzy` compara "João Silva" com a lista de abas (ex: `["João da Silva"]`).
12. O bot decide usar a aba "João da Silva" (similaridade > 85%).
13. **Se nenhuma aba similar for encontrada:** O bot cria uma nova aba e aplica a formatação de fonte e cabeçalho (Tamanho 25/Negrito/Fundo).
14. A nova linha de dados é adicionada à aba correta.
15. O bot envia a mensagem `Dados... salvos!` no Telegram.

### 5. Formato de Uso (O "Contrato")

Para o bot entender a mensagem, ela **deve** seguir este formato:

`Cliente: [Nome do Cliente], Info: [Sua anotação aqui]`

* O formato funciona para **texto** e **áudio**.
* O bot ignora maiúsculas/minúsculas e espaços extras.
* Qualquer mensagem que não siga este formato receberá a resposta de erro `Formato não reconhecido...`.