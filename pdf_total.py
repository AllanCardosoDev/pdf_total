import streamlit as st
import re
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import os
import pypdf
import tempfile
from pathlib import Path
from PIL import Image
import textwrap
import zipfile

# Funções auxiliares
def format_cpf(cpf):
    cpf_numerico = re.sub(r'\D', '', cpf)
    return cpf_numerico

def obter_primeiro_nome(nome_completo):
    if not nome_completo:
        return "documento"
    partes = nome_completo.strip().split()
    return partes[0].lower() if partes else "documento"

def formatar_nome_arquivo(nome_original, primeiro_nome):
    nome, extensao = os.path.splitext(nome_original)
    return f"{nome}_{primeiro_nome}{extensao}"

def pegar_dados_pdf(escritor):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_pdf_file = Path(temp_dir) / 'temp.pdf'
        escritor.write(temp_pdf_file)
        with open(temp_pdf_file, 'rb') as output_pdf:
            pdf_data = output_pdf.read()
    return pdf_data

# Funções principais
def add_watermark(input_pdf, name, cpf):
    cpf_formatado = format_cpf(cpf)
    cpf_exibicao = f"{cpf_formatado[:3]}.{cpf_formatado[3:6]}.{cpf_formatado[6:9]}-{cpf_formatado[9:]}"

    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont("Helvetica", 10)
    can.setFillColorRGB(1, 0, 0)  # Cor vermelha
    can.drawString(0, 10, f" {name} - {cpf_exibicao}")
    can.save()
    packet.seek(0)
    watermark = PdfReader(packet)

    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in range(len(reader.pages)):
        page_obj = reader.pages[page]
        page_obj.merge_page(watermark.pages[0])
        writer.add_page(page_obj)

    output_packet = BytesIO()
    writer.write(output_packet)
    output_packet.seek(0)
    return output_packet

def encrypt_pdf(input_pdf, password):
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.encrypt(password, owner_password=None, use_128bit=False)

    output_packet = BytesIO()
    writer.write(output_packet)
    output_packet.seek(0)
    return output_packet

def combinar_arquivos_pdf(arquivos_pdf, paginas_selecionadas=None):
    escritor = pypdf.PdfWriter()
    for i, arquivo_pdf in enumerate(arquivos_pdf):
        leitor = pypdf.PdfReader(arquivo_pdf)
        if paginas_selecionadas and i in paginas_selecionadas:
            for num_pagina in paginas_selecionadas[i]:
                if 0 <= num_pagina < len(leitor.pages):
                    escritor.add_page(leitor.pages[num_pagina])
        else:
            for pagina in leitor.pages:
                escritor.add_page(pagina)
    dados_pdf = pegar_dados_pdf(escritor=escritor)
    return dados_pdf

def extrair_paginas_pdf(arquivo_pdf, paginas):
    leitor = pypdf.PdfReader(arquivo_pdf)
    escritor = pypdf.PdfWriter()
    for num_pagina in paginas:
        if 1 <= num_pagina <= len(leitor.pages):
            escritor.add_page(leitor.pages[num_pagina - 1])
    dados_pdf = pegar_dados_pdf(escritor=escritor)
    return dados_pdf

def gerar_arquivo_pdf_com_imagens(imagens, opcoes):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    width, height = A4

    for imagem in imagens:
        img = Image.open(imagem)
        img_width, img_height = img.size

        if opcoes['tipo_insercao'] == 'Página inteira':
            can.setPageSize((img_width, img_height))
            can.drawImage(imagem, 0, 0, width=img_width, height=img_height)
        elif opcoes['tipo_insercao'] == 'Ajustar à página':
            aspect = img_width / float(img_height)
            if aspect > 1:
                img_width = width
                img_height = width / aspect
            else:
                img_height = height
                img_width = height * aspect
            can.drawImage(imagem, 0, 0, width=img_width, height=img_height)
        elif opcoes['tipo_insercao'] == 'Personalizado':
            x = opcoes['posicao_x']
            y = height - opcoes['posicao_y'] - opcoes['altura']
            can.drawImage(imagem, x, y, width=opcoes['largura'], height=opcoes['altura'])

        if opcoes['adicionar_texto']:
            can.setFont("Helvetica", opcoes['tamanho_fonte'])
            can.setFillColor(opcoes['cor_texto'])
            text_object = can.beginText(opcoes['posicao_texto_x'], height - opcoes['posicao_texto_y'])
            wrapped_text = textwrap.wrap(opcoes['texto'], width=40)
            for line in wrapped_text:
                text_object.textLine(line)
            can.drawText(text_object)

        can.showPage()

    can.save()
    packet.seek(0)
    novo_pdf = PdfReader(packet)
    escritor = PdfWriter()
    for pagina in novo_pdf.pages:
        escritor.add_page(pagina)

    dados_pdf = pegar_dados_pdf(escritor=escritor)
    return dados_pdf

def adicionar_marca_dagua(arquivo_pdf, marca_dagua, opcoes):
    leitor = PdfReader(arquivo_pdf)
    escritor = PdfWriter()

    for pagina in leitor.pages:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(pagina.mediabox.width, pagina.mediabox.height))
        
        if opcoes['tipo'] == 'Texto':
            can.setFont("Helvetica", opcoes['tamanho'])
            can.setFillColor(opcoes['cor'])
            can.rotate(opcoes['rotacao'])
            can.drawString(opcoes['posicao_x'], opcoes['posicao_y'], marca_dagua)
        elif opcoes['tipo'] == 'Imagem':
            can.drawImage(marca_dagua, opcoes['posicao_x'], opcoes['posicao_y'], 
                          width=opcoes['largura'], height=opcoes['altura'], mask='auto')

        can.save()
        packet.seek(0)
        marca = PdfReader(packet)
        pagina.merge_page(marca.pages[0])
        escritor.add_page(pagina)

    dados_pdf = pegar_dados_pdf(escritor=escritor)
    return dados_pdf

def rotacionar_paginas(arquivo_pdf, paginas_rotacao):
    leitor = pypdf.PdfReader(arquivo_pdf)
    escritor = pypdf.PdfWriter()

    for i, pagina in enumerate(leitor.pages):
        if i in paginas_rotacao:
            pagina.rotate(paginas_rotacao[i])
        escritor.add_page(pagina)

    return pegar_dados_pdf(escritor)

def comprimir_pdf(arquivo_pdf):
    leitor = pypdf.PdfReader(arquivo_pdf)
    escritor = pypdf.PdfWriter()

    for pagina in leitor.pages:
        pagina.compress_content_streams()  # Isso faz uma compressão básica
        escritor.add_page(pagina)

    return pegar_dados_pdf(escritor)

def adicionar_numeracao(arquivo_pdf, posicao, inicio):
    leitor = pypdf.PdfReader(arquivo_pdf)
    escritor = pypdf.PdfWriter()

    for i, pagina in enumerate(leitor.pages):
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(pagina.mediabox.width, pagina.mediabox.height))
        can.setFont("Helvetica", 10)
        if posicao == "Inferior Direito":
            can.drawString(pagina.mediabox.width - 50, 30, str(i + inicio))
        elif posicao == "Inferior Esquerdo":
            can.drawString(30, 30, str(i + inicio))
        elif posicao == "Superior Direito":
            can.drawString(pagina.mediabox.width - 50, pagina.mediabox.height - 30, str(i + inicio))
        else:  # Superior Esquerdo
            can.drawString(30, pagina.mediabox.height - 30, str(i + inicio))
        can.save()
        packet.seek(0)
        nova_pagina = pypdf.PdfReader(packet).pages[0]
        pagina.merge_page(nova_pagina)
        escritor.add_page(pagina)

    return pegar_dados_pdf(escritor)

def remover_paginas(arquivo_pdf, paginas_remover):
    leitor = pypdf.PdfReader(arquivo_pdf)
    escritor = pypdf.PdfWriter()

    for i, pagina in enumerate(leitor.pages):
        if i + 1 not in paginas_remover:
            escritor.add_page(pagina)

    return pegar_dados_pdf(escritor)

def comparar_pdfs(arquivo_pdf1, arquivo_pdf2):
    leitor1 = pypdf.PdfReader(arquivo_pdf1)
    leitor2 = pypdf.PdfReader(arquivo_pdf2)

    if len(leitor1.pages) != len(leitor2.pages):
        return "Os PDFs têm números diferentes de páginas."

    diferencas = []
    for i in range(len(leitor1.pages)):
        if leitor1.pages[i].extract_text() != leitor2.pages[i].extract_text():
            diferencas.append(f"Diferença encontrada na página {i+1}")

    return "\n".join(diferencas) if diferencas else "Nenhuma diferença encontrada."

def adicionar_marca_dagua_imagem(arquivo_pdf, imagem_marca, opcoes):
    leitor = pypdf.PdfReader(arquivo_pdf)
    escritor = pypdf.PdfWriter()

    marca_dagua = Image.open(imagem_marca)

    for pagina in leitor.pages:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=(pagina.mediabox.width, pagina.mediabox.height))
        can.drawImage(imagem_marca, opcoes['posicao_x'], opcoes['posicao_y'], 
                      width=opcoes['largura'], height=opcoes['altura'], mask='auto')
        can.save()
        packet.seek(0)
        nova_pagina = pypdf.PdfReader(packet).pages[0]
        pagina.merge_page(nova_pagina)
        escritor.add_page(pagina)

    return pegar_dados_pdf(escritor)

def redact_pdf(arquivo_pdf, texto_redact):
    leitor = pypdf.PdfReader(arquivo_pdf)
    escritor = pypdf.PdfWriter()

    for pagina in leitor.pages:
        conteudo = pagina.extract_text()
        if texto_redact in conteudo:
            conteudo = conteudo.replace(texto_redact, "[REDACTED]")
            # Aqui, idealmente, desenharíamos um retângulo preto sobre o texto
            # Mas isso requer manipulação mais avançada do PDF
        escritor.add_page(pagina)

    return pegar_dados_pdf(escritor)

# Função principal
def main():
    st.set_page_config(page_title="PDFTools Avançado", page_icon="🔒", layout="wide")
    st.title("🔒 PDFTools Avançado")

    menu = [
        "Proteção de PDF", "Extrair Páginas", "Combinar PDFs", "Adicionar Marca d'água",
        "Imagens para PDF", "Rotação de Páginas", "Compressão de PDF", "Adicionar Numeração",
        "Remover Páginas", "Comparação de PDFs", "Marca d'água Personalizada", "Redação de Texto"
    ]
    choice = st.sidebar.selectbox("Escolha uma opção", menu)

    if choice == "Proteção de PDF":
        st.subheader("Proteção de Documentos PDF")
        st.write("Esta opção permite adicionar uma marca d'água com nome e CPF a múltiplos PDFs e criptografá-los.")

        uploaded_files = st.file_uploader("Escolha os arquivos PDF", type=['pdf'], accept_multiple_files=True)

        if uploaded_files:
            st.subheader("👤 Informações Pessoais")
            name = st.text_input("Nome Completo")
            cpf = st.text_input("CPF")

            primeiro_nome = obter_primeiro_nome(name)

            if st.button("Proteger PDFs"):
                if not name or not cpf:
                    st.error("Nome completo e CPF são obrigatórios!")
                else:
                    try:
                        senha = format_cpf(cpf)
                        processed_pdfs = []

                        progress_bar = st.progress(0)
                        for i, uploaded_file in enumerate(uploaded_files):
                            nome_arquivo_saida = formatar_nome_arquivo(uploaded_file.name, primeiro_nome)
                            processed_pdf = add_watermark(uploaded_file, name, cpf)
                            final_pdf = encrypt_pdf(processed_pdf, senha)
                            processed_pdfs.append((nome_arquivo_saida, final_pdf))
                            progress_bar.progress((i + 1) / len(uploaded_files))

                        st.success("PDFs processados com sucesso! 🎉")
                        st.warning(f"⚠️ Senha de acesso para todos os PDFs: {senha}")

                        # Opção para baixar todos os PDFs em um arquivo ZIP
                        if len(processed_pdfs) > 1:
                            zip_buffer = BytesIO()
                            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                                for file_name, file_data in processed_pdfs:
                                    zip_file.writestr(file_name, file_data.getvalue())
                            
                            st.download_button(
                                label="📥 Baixar todos os PDFs protegidos (ZIP)",
                                data=zip_buffer.getvalue(),
                                file_name="pdfs_protegidos.zip",
                                mime="application/zip"
                            )

                        # Opção para baixar PDFs individualmente
                        st.write("Ou baixe os PDFs individualmente:")
                        for file_name, file_data in processed_pdfs:
                            st.download_button(
                                label=f"📥 Baixar {file_name}",
                                data=file_data,
                                file_name=file_name,
                                mime="application/pdf",
                                key=file_name  # Necessário para criar botões únicos
                            )

                    except Exception as e:
                        st.error(f"Erro no processamento: {e}")

    elif choice == "Extrair Páginas":
        st.subheader("Extrair Páginas do PDF")
        st.write("Esta opção permite extrair páginas específicas de um PDF. Você pode selecionar páginas individuais, intervalos ou páginas alternadas.")
        
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF", type='pdf')
        if arquivo_pdf:
            reader = PdfReader(arquivo_pdf)
            num_paginas = len(reader.pages)
            st.write(f"O PDF tem {num_paginas} páginas.")
            
            opcao_extracao = st.radio(
                "Escolha como deseja extrair as páginas:",
                ("Páginas específicas", "Intervalo de páginas", "Páginas alternadas")
            )
            
            if opcao_extracao == "Páginas específicas":
                paginas = st.text_input("Digite os números das páginas separados por vírgula (ex: 1,3,5)")
                if paginas:
                    paginas_list = [int(p.strip()) for p in paginas.split(',') if p.strip().isdigit()]
            elif opcao_extracao == "Intervalo de páginas":
                inicio = st.number_input("Página inicial", min_value=1, max_value=num_paginas, value=1)
                fim = st.number_input("Página final", min_value=inicio, max_value=num_paginas, value=num_paginas)
                paginas_list = list(range(inicio, fim + 1))
            else:  # Páginas alternadas
                inicio = st.number_input("Página inicial", min_value=1, max_value=num_paginas, value=1)
                passo = st.number_input("Passo (ex: 2 para extrair uma página sim, outra não)", min_value=1, max_value=num_paginas, value=2)
                paginas_list = list(range(inicio, num_paginas + 1, passo))
            
            if st.button('Extrair Páginas'):
                dados_pdf = extrair_paginas_pdf(arquivo_pdf, paginas_list)
                nome_arquivo = f'{Path(arquivo_pdf.name).stem}_extraido.pdf'
                st.download_button(
                    'Baixar Páginas Extraídas',
                    data=dados_pdf,
                    file_name=nome_arquivo,
                    mime="application/pdf"
                )

    elif choice == "Combinar PDFs":
        st.subheader("Combinar PDFs")
        st.write("Esta opção permite combinar múltiplos arquivos PDF em um único documento.")
        arquivos_pdf = st.file_uploader("Selecione os arquivos PDF para combinar", type='pdf', accept_multiple_files=True)
        
        if arquivos_pdf:
            opcao_combinacao = st.radio(
                "Escolha como deseja combinar os PDFs:",
                ("Todos os arquivos completos", "Selecionar páginas específicas")
            )

            paginas_selecionadas = None
            if opcao_combinacao == "Selecionar páginas específicas":
                paginas_selecionadas = {}
                for i, arquivo in enumerate(arquivos_pdf):
                    st.write(f"Arquivo {i+1}: {arquivo.name}")
                    paginas = st.text_input(f"Páginas para o arquivo {i+1} (ex: 1,3,5)", key=f"paginas_{i}")
                    if paginas:
                        paginas_selecionadas[i] = [int(p.strip())-1 for p in paginas.split(',') if p.strip().isdigit()]

            if st.button('Combinar PDFs'):
                dados_pdf = combinar_arquivos_pdf(arquivos_pdf, paginas_selecionadas)
                nome_arquivo = "combinado.pdf"
                st.download_button(
                    'Baixar PDF Combinado',
                    data=dados_pdf,
                    file_name=nome_arquivo,
                    mime="application/pdf"
                )

    elif choice == "Adicionar Marca d'água":
        st.subheader("Adicionar Marca d'água")
        st.write("Esta opção permite adicionar uma marca d'água a todas as páginas de um PDF.")
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF", type='pdf')
        
        tipo_marca = st.radio("Tipo de marca d'água", ["Texto", "Imagem"])
        
        if tipo_marca == "Texto":
            marca_dagua = st.text_input("Digite o texto da marca d'água")
            tamanho = st.slider("Tamanho da fonte", 10, 100, 40)
            cor = st.color_picker("Cor do texto", "#888888")
            rotacao = st.slider("Rotação (graus)", 0, 360, 45)
        else:
            marca_dagua = st.file_uploader("Selecione a imagem para marca d'água", type=['png', 'jpg', 'jpeg'])
        
        posicao_x = st.slider("Posição X", 0, 500, 100)
        posicao_y = st.slider("Posição Y", 0, 700, 300)
        
        if tipo_marca == "Imagem":
            largura = st.slider("Largura da imagem", 50, 500, 200)
            altura = st.slider("Altura da imagem", 50, 500, 200)
        
        if arquivo_pdf and ((tipo_marca == "Texto" and marca_dagua) or (tipo_marca == "Imagem" and marca_dagua)):
            if st.button("Adicionar Marca d'água"):
                opcoes = {
                    'tipo': tipo_marca,
                    'tamanho': tamanho,
                    'cor': Color(*[int(cor.lstrip('#')[i:i+2], 16)/255 for i in (0, 2, 4)]),
                    'rotacao': rotacao,
                    'posicao_x': posicao_x,
                    'posicao_y': posicao_y,
                    'largura': largura if tipo_marca == "Imagem" else None,
                    'altura': altura if tipo_marca == "Imagem" else None
                }
                dados_pdf = adicionar_marca_dagua(arquivo_pdf, marca_dagua, opcoes)
                nome_arquivo = f'{Path(arquivo_pdf.name).stem}_marca.pdf'
                st.download_button(
                    'Baixar PDF com Marca d\'água',
                    data=dados_pdf,
                    file_name=nome_arquivo,
                    mime="application/pdf"
                )

    elif choice == "Imagens para PDF":
        st.subheader("Imagens para PDF")
        st.write("Esta opção permite converter múltiplas imagens em um único arquivo PDF.")
        imagens = st.file_uploader("Selecione as imagens", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        
        if imagens:
            tipo_insercao = st.radio("Tipo de inserção", ["Página inteira", "Ajustar à página", "Personalizado"])
            
            opcoes = {'tipo_insercao': tipo_insercao}
            
            if tipo_insercao == "Personalizado":
                opcoes['posicao_x'] = st.slider("Posição X", 0, 500, 0)
                opcoes['posicao_y'] = st.slider("Posição Y", 0, 700, 0)
                opcoes['largura'] = st.slider("Largura", 50, 500, 200)
                opcoes['altura'] = st.slider("Altura", 50, 500, 200)
            
            adicionar_texto = st.checkbox("Adicionar texto às imagens")
            if adicionar_texto:
                opcoes['adicionar_texto'] = True
                opcoes['texto'] = st.text_input("Digite o texto")
                opcoes['tamanho_fonte'] = st.slider("Tamanho da fonte", 8, 72, 12)
                opcoes['cor_texto'] = st.color_picker("Cor do texto", "#000000")
                opcoes['posicao_texto_x'] = st.slider("Posição X do texto", 0, 500, 10)
                opcoes['posicao_texto_y'] = st.slider("Posição Y do texto", 0, 700, 10)
            else:
                opcoes['adicionar_texto'] = False
            
            if st.button('Criar PDF'):
                dados_pdf = gerar_arquivo_pdf_com_imagens(imagens, opcoes)
                nome_arquivo = "imagens.pdf"
                st.download_button(
                    'Baixar PDF com Imagens',
                    data=dados_pdf,
                    file_name=nome_arquivo,
                    mime="application/pdf"
                )

    elif choice == "Rotação de Páginas":
        st.subheader("Rotação de Páginas")
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF", type='pdf')
        if arquivo_pdf:
            leitor = pypdf.PdfReader(arquivo_pdf)
            num_paginas = len(leitor.pages)
            st.write(f"O PDF tem {num_paginas} páginas.")
            
            paginas_rotacao = {}
            for i in range(num_paginas):
                col1, col2 = st.columns(2)
                with col1:
                    if st.checkbox(f"Rotacionar página {i+1}"):
                        with col2:
                            rotacao = st.selectbox(f"Rotação para página {i+1}", [0, 90, 180, 270], key=f"rot_{i}")
                            paginas_rotacao[i] = rotacao

            if st.button('Aplicar Rotação'):
                dados_pdf = rotacionar_paginas(arquivo_pdf, paginas_rotacao)
                st.download_button(
                    'Baixar PDF Rotacionado',
                    data=dados_pdf,
                    file_name="rotacionado.pdf",
                    mime="application/pdf"
                )

    elif choice == "Compressão de PDF":
        st.subheader("Compressão de PDF")
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF para comprimir", type='pdf')
        if arquivo_pdf:
            st.warning("Nota: Esta é uma compressão básica e pode não resultar em redução significativa do tamanho do arquivo.")
            if st.button('Comprimir PDF'):
                dados_pdf = comprimir_pdf(arquivo_pdf)
                st.download_button(
                    'Baixar PDF Comprimido',
                    data=dados_pdf,
                    file_name="comprimido.pdf",
                    mime="application/pdf"
                )

    elif choice == "Adicionar Numeração":
        st.subheader("Adicionar Numeração de Páginas")
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF", type='pdf')
        if arquivo_pdf:
            posicao = st.selectbox("Posição da Numeração", ["Inferior Direito", "Inferior Esquerdo", "Superior Direito", "Superior Esquerdo"])
            inicio = st.number_input("Número Inicial", value=1, min_value=1)
            if st.button('Adicionar Numeração'):
                dados_pdf = adicionar_numeracao(arquivo_pdf, posicao, inicio)
                st.download_button(
                    'Baixar PDF Numerado',
                    data=dados_pdf,
                    file_name="numerado.pdf",
                    mime="application/pdf"
                )

    elif choice == "Remover Páginas":
        st.subheader("Remover Páginas do PDF")
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF", type='pdf')
        if arquivo_pdf:
            leitor = pypdf.PdfReader(arquivo_pdf)
            num_paginas = len(leitor.pages)
            st.write(f"O PDF tem {num_paginas} páginas.")
            paginas_remover = st.multiselect("Selecione as páginas para remover", range(1, num_paginas + 1))
            if st.button('Remover Páginas'):
                dados_pdf = remover_paginas(arquivo_pdf, paginas_remover)
                st.download_button(
                    'Baixar PDF Modificado',
                    data=dados_pdf,
                    file_name="modificado.pdf",
                    mime="application/pdf"
                )

    elif choice == "Comparação de PDFs":
        st.subheader("Comparação de PDFs")
        arquivo_pdf1 = st.file_uploader("Selecione o primeiro PDF", type='pdf', key="pdf1")
        arquivo_pdf2 = st.file_uploader("Selecione o segundo PDF", type='pdf', key="pdf2")
        if arquivo_pdf1 and arquivo_pdf2:
            if st.button('Comparar PDFs'):
                resultado = comparar_pdfs(arquivo_pdf1, arquivo_pdf2)
                st.text_area("Resultado da Comparação", resultado, height=300)

    elif choice == "Marca d'água Personalizada":
        st.subheader("Adicionar Marca d'água Personalizada")
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF", type='pdf')
        imagem_marca = st.file_uploader("Selecione a imagem para marca d'água", type=['png', 'jpg', 'jpeg'])
        if arquivo_pdf and imagem_marca:
            opcoes = {
                'posicao_x': st.slider("Posição X", 0, 500, 100),
                'posicao_y': st.slider("Posição Y", 0, 700, 300),
                'largura': st.slider("Largura", 50, 500, 200),
                'altura': st.slider("Altura", 50, 500, 200)
            }
            if st.button("Adicionar Marca d'água"):
                dados_pdf = adicionar_marca_dagua_imagem(arquivo_pdf, imagem_marca, opcoes)
                st.download_button(
                    'Baixar PDF com Marca d\'água',
                    data=dados_pdf,
                    file_name="marca_dagua_personalizada.pdf",
                    mime="application/pdf"
                )

    elif choice == "Redação de Texto":
        st.subheader("Redação de Texto em PDF")
        arquivo_pdf = st.file_uploader("Selecione o arquivo PDF", type='pdf')
        if arquivo_pdf:
            texto_redact = st.text_input("Digite o texto a ser redatado")
            st.warning("Nota: Esta é uma implementação simplificada e não realiza redação real. O texto será substituído por '[REDACTED]'.")
            if st.button('Aplicar Redação'):
                dados_pdf = redact_pdf(arquivo_pdf, texto_redact)
                st.download_button(
                    'Baixar PDF Redatado',
                    data=dados_pdf,
                    file_name="redatado.pdf",
                    mime="application/pdf"
                )

if __name__ == "__main__":
    main()
