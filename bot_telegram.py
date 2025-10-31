import gspread
from google.oauth2.service_account import Credentials
import speech_recognition as sr
from pydub import AudioSegment
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import datetime
import re
import os
# NOVA IMPORTAÇÃO
from fuzzywuzzy import process as fuzzy_process

# --- CONFIGURAÇÕES - VERIFIQUE SEUS DADOS AQUI ---
TOKEN_TELEGRAM = "seu token"
ID_PLANILHA = "id da sua planilha"
ARQUIVO_CREDENCIAL = "credentials.json"

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# ---------------------------------------------------

# NOVO: Limite de confiança para a aproximação (em %)
# Se a similaridade for maior que 85%, ele "corrige" o nome.
# Se for menor, ele cria um cliente novo.
LIMITE_CONFIANCA_FUZZY = 85
# ---------------------------------------------------

# 1. FUNÇÃO DE ARMAZENAMENTO (GOOGLE SHEETS) - ATUALIZADA
def get_planilha_obj():
    """ Se conecta ao Google e retorna o OBJETO da planilha inteira. """
    try:
        creds = Credentials.from_service_account_file(ARQUIVO_CREDENCIAL, scopes=SCOPES)
        client = gspread.authorize(creds)
        planilha_obj = client.open_by_key(ID_PLANILHA)
        return planilha_obj
    except Exception as e:
        print(f"Erro ao conectar na Planilha: {e}")
        return None

def salvar_na_planilha(cliente_nome_extraido, info, tipo_midia):
    """
    Salva a informação na aba específica do cliente, usando
    FUZZY MATCHING e aplicando formatação de fonte.
    """
    print(f"Salvando na planilha: Cliente (extraído)='{cliente_nome_extraido}'...")
    
    planilha_obj = get_planilha_obj()
    if not planilha_obj:
        print("Não foi possível conectar ao objeto da planilha.")
        return False
        
    try:
        # 1. Pega o nome de TODAS as abas que já existem na planilha
        lista_abas_existentes = [aba.title for aba in planilha_obj.worksheets()]
        
        if "Página1" in lista_abas_existentes:
            lista_abas_existentes.remove("Página1")

        nome_final_cliente = cliente_nome_extraido
        aba_cliente = None

        # 2. LÓGICA FUZZY MATCHING
        if lista_abas_existentes: 
            melhor_match = fuzzy_process.extractOne(cliente_nome_extraido, lista_abas_existentes)
            nome_encontrado, pontuacao = melhor_match
            print(f"Melhor correspondência: '{nome_encontrado}' (Pontuação: {pontuacao}%)")

            # 3. DECISÃO
            if pontuacao >= LIMITE_CONFIANCA_FUZZY:
                print(f"Confiança alta. Usando a aba existente: '{nome_encontrado}'.")
                nome_final_cliente = nome_encontrado
                aba_cliente = planilha_obj.worksheet(nome_final_cliente)
            else:
                print(f"Confiança baixa. Criando nova aba para: '{cliente_nome_extraido}'.")
        else:
            print("Nenhum cliente anterior encontrado. Criando primeira aba.")
            
        # 4. CRIA A ABA SE NECESSÁRIO
        if aba_cliente is None:
            try:
                # Tenta criar a nova aba
                aba_cliente = planilha_obj.add_worksheet(title=nome_final_cliente, rows=100, cols=10)
                
                # --- INÍCIO DA NOVA FORMATAÇÃO DE FONTE ---
                
                # 4a. Define a formatação do CONTEÚDO (resto da planilha)
                # Define as colunas A, B, C para terem tamanho 18
                formato_conteudo = {
                    "textFormat": {"fontSize": 18}
                }
                aba_cliente.format("A:C", formato_conteudo)
                print("Fonte do conteúdo definida para tamanho 18.")
                
                # 4b. Adiciona o Cabeçalho
                headers = ["Data", "Informação", "Tipo de Mídia"]
                aba_cliente.append_row(headers)
                
                # 4c. Define a formatação do CABEÇALHO (sobrescreve o passo 4a)
                formato_cabecalho = {
                    "textFormat": {
                        "bold": True,
                        "fontSize": 25
                    },
                    "backgroundColor": {
                         "blue": 0.5
                    }
                }
                # Aplica o formato à primeira linha (A1 até C1)
                aba_cliente.format("A1:C1", formato_cabecalho)
                print("Cabeçalho formatado com tamanho 25, negrito e cor.")
                # --- FIM DA NOVA FORMATAÇÃO DE FONTE ---
                
            except gspread.exceptions.APIError as e:
                print(f"Erro ao criar aba (provavelmente já existe): {e}. Tentando abrir...")
                aba_cliente = planilha_obj.worksheet(nome_final_cliente)
        
        # 5. Adiciona a nova linha de dados na aba correta
        # (Esta linha já vai pegar a formatação de tamanho 18)
        agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = [agora, info, tipo_midia]
        aba_cliente.append_row(linha)
        
        print("Salvo com sucesso!")
        return True

    except Exception as e:
        print(f"Erro ao salvar/criar aba: {e}")
        return False
        
# 2. FUNÇÃO DE TRADUÇÃO (VERSÃO GRATUITA - GOOGLE)
# (Esta função não muda)
async def transcrever_audio(caminho_arquivo_ogg):
    print("Iniciando transcrição gratuita...")
    caminho_arquivo_wav = "temp_audio.wav"
    try:
        audio = AudioSegment.from_ogg(caminho_arquivo_ogg)
        audio.export(caminho_arquivo_wav, format="wav")
        recognizer = sr.Recognizer()
        with sr.AudioFile(caminho_arquivo_wav) as source:
            audio_data = recognizer.record(source)
        texto = recognizer.recognize_google(audio_data, language="pt-BR")
        print("Transcrição concluída.")
        return texto
    except Exception as e:
        print(f"Erro na transcrição: {e}")
        return None
    finally:
        if os.path.exists(caminho_arquivo_ogg):
            os.remove(caminho_arquivo_ogg)
        if os.path.exists(caminho_arquivo_wav):
            os.remove(caminho_arquivo_wav)

# 3. FUNÇÃO DE PROCESSAMENTO (O CÉREBRO)
# (Esta função não muda)
def extrair_dados(texto):
    """
    Procura pelo "Contrato" no texto.
    Agora é flexível e aceita:
    - 'Cliente: [Nome], Info: [Dados]' (digitado)
    - 'cliente [Nome] info [Dados]' (falado)
    """
    # Regex (com \W+) aceita qualquer caractere não-alfanumérico
    # (espaços, vírgulas, dois-pontos, etc.) como separador.
    match = re.search(r"cliente\W+(.*?)\W+info\W+(.*)", texto, re.IGNORECASE | re.DOTALL)

    if match:
        cliente = match.group(1).strip()
        info = match.group(2).strip()

        # Checagem extra: garante que o nome não está vazio
        if not cliente or not info:
            print("Formato reconhecido, mas cliente ou info estão vazios.")
            return None, None

        print(f"Dados extraídos: Cliente={cliente}, Info={info}")
        return cliente, info
    else:
        print(f"Formato não reconhecido no texto: '{texto}'")
        return None, None
    
    
# 4. FUNÇÕES DO "OUVIDO" (TELEGRAM - v20+)
# (Esta função não muda)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_para_processar = None
    tipo_midia = None

    if update.message.voice or update.message.audio:
        await update.message.reply_text("Recebi seu áudio. Transcrevendo (grátis)...")
        file_obj = update.message.voice or update.message.audio
        file_id = file_obj.file_id
        arquivo_temp_path = f"{file_id}.ogg"
        arquivo_telegram = await context.bot.get_file(file_id)
        await arquivo_telegram.download_to_drive(arquivo_temp_path)
        texto_para_processar = await transcrever_audio(arquivo_temp_path)
        tipo_midia = "Áudio"
        
        if texto_para_processar:
            await update.message.reply_text(f"Texto transcrito:\n\n'{texto_para_processar}'")
        else:
            await update.message.reply_text("❌ Desculpe, não consegui entender o áudio.")
            return
            
    elif update.message.text:
        print("Recebi mensagem de texto.")
        texto_para_processar = update.message.text
        tipo_midia = "Texto"

    else:
        return

    if texto_para_processar:
        cliente, info = extrair_dados(texto_para_processar)
        
        if cliente and info:
            if salvar_na_planilha(cliente, info, tipo_midia):
                await update.message.reply_text(f"✅ Dados do cliente '{cliente}' salvos!")
            else:
                await update.message.reply_text("❌ Erro ao salvar na planilha. Verifique o console.")
        else:
            await update.message.reply_text("❌ Formato não reconhecido. Use:\n\n`Cliente: [Nome], Info: [Dados]`")

# --- EXECUÇÃO PRINCIPAL (v20+) ---
def main():
    print("Iniciando Bot (v20+ com Fuzzy Matching)...")
    application = Application.builder().token(TOKEN_TELEGRAM).build()
    handler = MessageHandler(filters.TEXT | filters.AUDIO | filters.VOICE, handle_message)
    application.add_handler(handler)
    print("Bot no ar. Ouvindo mensagens...")
    application.run_polling()

if __name__ == '__main__':
    main()
