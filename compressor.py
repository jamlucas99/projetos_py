

"""
Sistema Local de Divisão de PDFs para Faturamento Hospitalar

Objetivo:
- Monitorar pastas de convênios hospitalares.
- Cada convênio possui um limite máximo próprio em MB definido diretamente no código.
- O sistema cria automaticamente uma pasta para cada convênio.
- Quando um PDF é jogado na pasta do convênio, o sistema verifica o tamanho.
- Se o PDF estiver acima do limite, ele divide automaticamente em partes menores.

"""

from __future__ import annotations

import logging
import shutil
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# Pasta fixa para uso em máquinas Windows.
# Ao gerar um .exe, o sistema criará automaticamente essa estrutura no disco C:.
BASE_DIR = Path.home() / "Documents" / "DivisorPDFHospitalar"
PASTA_ENTRADA = BASE_DIR / "entrada"
PASTA_PROCESSADOS = BASE_DIR / "processados"
PASTA_DIVIDIDOS = BASE_DIR / "divididos"
PASTA_LOGS = BASE_DIR / "logs"
ARQUIVO_LOG = PASTA_LOGS / "divisor_pdfs.log"

# Regras fixas por convênio.
# Altere aqui quando precisar adicionar/remover convênios ou mudar limites.
# O valor representa o limite máximo em MB para cada PDF.
REGRAS_CONVENIOS_MB = {
    "Unimed": 10,
    "Bradesco": 15,
    "Hapvida": 8,
    "Amil": 10,
    "SulAmerica": 12,
}

INTERVALO_ESTABILIZACAO_SEGUNDOS = 2


@dataclass
class Convenio:
    nome: str
    limite_mb: float

    @property
    def limite_bytes(self) -> int:
        return int(self.limite_mb * 1024 * 1024)


class DivisorPDFHospitalar:
    def __init__(self) -> None:
        self.criar_estrutura_base()
        self.configurar_logs()
        self.convenios = self.carregar_convenios()
        self.criar_pastas_convenios()

    def criar_estrutura_base(self) -> None:
        for pasta in [PASTA_ENTRADA, PASTA_PROCESSADOS, PASTA_DIVIDIDOS, PASTA_LOGS]:
            pasta.mkdir(parents=True, exist_ok=True)


    def configurar_logs(self) -> None:
        logging.basicConfig(
            filename=ARQUIVO_LOG,
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            encoding="utf-8",
        )

    def carregar_convenios(self) -> dict[str, Convenio]:
        convenios: dict[str, Convenio] = {}

        for nome, limite_mb in REGRAS_CONVENIOS_MB.items():
            convenios[nome] = Convenio(nome=nome, limite_mb=float(limite_mb))

        return convenios

    def criar_pastas_convenios(self) -> None:
        for convenio in self.convenios.values():
            (PASTA_ENTRADA / convenio.nome).mkdir(parents=True, exist_ok=True)
            (PASTA_PROCESSADOS / convenio.nome).mkdir(parents=True, exist_ok=True)
            (PASTA_DIVIDIDOS / convenio.nome).mkdir(parents=True, exist_ok=True)

    def processar_pdfs_existentes(self) -> None:
        for convenio in self.convenios.values():
            pasta = PASTA_ENTRADA / convenio.nome
            for caminho_pdf in pasta.glob("*.pdf"):
                self.processar_pdf(caminho_pdf, convenio)

    def processar_pdf(self, caminho_pdf: Path, convenio: Convenio) -> None:
        if not caminho_pdf.exists() or caminho_pdf.suffix.lower() != ".pdf":
            return

        self.aguardar_arquivo_estabilizar(caminho_pdf)

        tamanho_bytes = caminho_pdf.stat().st_size
        tamanho_mb = self.bytes_para_mb(tamanho_bytes)

        logging.info(
            "PDF recebido | convenio=%s | arquivo=%s | tamanho=%.2fMB | limite=%.2fMB",
            convenio.nome,
            caminho_pdf.name,
            tamanho_mb,
            convenio.limite_mb,
        )

        if tamanho_bytes <= convenio.limite_bytes:
            destino = self.gerar_destino_unico(PASTA_PROCESSADOS / convenio.nome, caminho_pdf.name)
            shutil.move(str(caminho_pdf), str(destino))
            logging.info("PDF dentro do limite. Movido para processados: %s", destino)
            print(f"OK: {caminho_pdf.name} está dentro do limite de {convenio.limite_mb} MB.")
            return

        print(
            f"Dividindo {caminho_pdf.name}: {tamanho_mb:.2f} MB acima do limite "
            f"de {convenio.limite_mb} MB para {convenio.nome}."
        )

        partes = self.dividir_pdf_por_tamanho(caminho_pdf, convenio)

        destino_original = self.gerar_destino_unico(PASTA_PROCESSADOS / convenio.nome, caminho_pdf.name)
        shutil.move(str(caminho_pdf), str(destino_original))

        logging.info(
            "PDF dividido | convenio=%s | arquivo=%s | partes=%s | original_movido=%s",
            convenio.nome,
            caminho_pdf.name,
            len(partes),
            destino_original,
        )

        print(f"Concluído: {caminho_pdf.name} dividido em {len(partes)} parte(s).")

    def dividir_pdf_por_tamanho(self, caminho_pdf: Path, convenio: Convenio) -> list[Path]:
        reader = PdfReader(str(caminho_pdf))
        total_paginas = len(reader.pages)

        if total_paginas == 0:
            raise ValueError("PDF sem páginas.")

        pasta_saida = PASTA_DIVIDIDOS / convenio.nome / caminho_pdf.stem
        pasta_saida.mkdir(parents=True, exist_ok=True)

        partes_geradas: list[Path] = []
        paginas_parte: list[int] = []
        numero_parte = 1

        for indice_pagina in range(total_paginas):
            tentativa_paginas = paginas_parte + [indice_pagina]
            arquivo_teste = self.salvar_parte_temporaria(reader, tentativa_paginas, pasta_saida)
            tamanho_teste = arquivo_teste.stat().st_size
            arquivo_teste.unlink(missing_ok=True)

            if tamanho_teste <= convenio.limite_bytes:
                paginas_parte = tentativa_paginas
                continue

            if not paginas_parte:
                # Uma única página já ultrapassa o limite. Não é possível dividir por página.
                caminho_saida = self.salvar_parte_final(
                    reader=reader,
                    paginas=[indice_pagina],
                    pasta_saida=pasta_saida,
                    nome_base=caminho_pdf.stem,
                    numero_parte=numero_parte,
                )
                partes_geradas.append(caminho_saida)
                logging.warning(
                    "Página individual acima do limite | arquivo=%s | pagina=%s | tamanho=%.2fMB | limite=%.2fMB",
                    caminho_pdf.name,
                    indice_pagina + 1,
                    self.bytes_para_mb(caminho_saida.stat().st_size),
                    convenio.limite_mb,
                )
                numero_parte += 1
                paginas_parte = []
                continue

            caminho_saida = self.salvar_parte_final(
                reader=reader,
                paginas=paginas_parte,
                pasta_saida=pasta_saida,
                nome_base=caminho_pdf.stem,
                numero_parte=numero_parte,
            )
            partes_geradas.append(caminho_saida)
            numero_parte += 1
            paginas_parte = [indice_pagina]

        if paginas_parte:
            caminho_saida = self.salvar_parte_final(
                reader=reader,
                paginas=paginas_parte,
                pasta_saida=pasta_saida,
                nome_base=caminho_pdf.stem,
                numero_parte=numero_parte,
            )
            partes_geradas.append(caminho_saida)

        return partes_geradas

    def salvar_parte_temporaria(self, reader: PdfReader, paginas: list[int], pasta_saida: Path) -> Path:
        caminho_temp = pasta_saida / "__temp__.pdf"
        writer = PdfWriter()
        for pagina in paginas:
            writer.add_page(reader.pages[pagina])
        with caminho_temp.open("wb") as arquivo:
            writer.write(arquivo)
        return caminho_temp

    def salvar_parte_final(
        self,
        reader: PdfReader,
        paginas: list[int],
        pasta_saida: Path,
        nome_base: str,
        numero_parte: int,
    ) -> Path:
        writer = PdfWriter()
        for pagina in paginas:
            writer.add_page(reader.pages[pagina])

        caminho_saida = pasta_saida / f"{nome_base}_parte_{numero_parte:03d}.pdf"
        caminho_saida = self.gerar_destino_unico(pasta_saida, caminho_saida.name)

        with caminho_saida.open("wb") as arquivo:
            writer.write(arquivo)

        logging.info(
            "Parte gerada | arquivo=%s | paginas=%s-%s | tamanho=%.2fMB",
            caminho_saida.name,
            paginas[0] + 1,
            paginas[-1] + 1,
            self.bytes_para_mb(caminho_saida.stat().st_size),
        )

        return caminho_saida

    def identificar_convenio_por_caminho(self, caminho_pdf: Path) -> Convenio | None:
        try:
            relativo = caminho_pdf.relative_to(PASTA_ENTRADA)
        except ValueError:
            return None

        if not relativo.parts:
            return None

        nome_pasta_convenio = relativo.parts[0]
        return self.convenios.get(nome_pasta_convenio)

    def aguardar_arquivo_estabilizar(self, caminho: Path) -> None:
        tamanho_anterior = -1

        while True:
            if not caminho.exists():
                return

            tamanho_atual = caminho.stat().st_size
            if tamanho_atual == tamanho_anterior:
                time.sleep(INTERVALO_ESTABILIZACAO_SEGUNDOS)
                if caminho.exists() and caminho.stat().st_size == tamanho_atual:
                    return

            tamanho_anterior = tamanho_atual
            time.sleep(1)

    @staticmethod
    def gerar_destino_unico(pasta: Path, nome_arquivo: str) -> Path:
        destino = pasta / nome_arquivo
        if not destino.exists():
            return destino

        stem = destino.stem
        suffix = destino.suffix
        contador = 1

        while True:
            novo_destino = pasta / f"{stem}_{contador}{suffix}"
            if not novo_destino.exists():
                return novo_destino
            contador += 1

    @staticmethod
    def bytes_para_mb(valor_bytes: int) -> float:
        return valor_bytes / (1024 * 1024)


class MonitorPDFs(FileSystemEventHandler):
    def __init__(self, app: DivisorPDFHospitalar) -> None:
        self.app = app

    def on_created(self, event) -> None:
        if event.is_directory:
            return

        caminho = Path(event.src_path)
        if caminho.suffix.lower() != ".pdf":
            return

        convenio = self.app.identificar_convenio_por_caminho(caminho)
        if not convenio:
            logging.warning("PDF ignorado, convênio não identificado: %s", caminho)
            return

        try:
            self.app.processar_pdf(caminho, convenio)
        except Exception as erro:
            logging.exception("Erro ao processar PDF %s: %s", caminho, erro)
            print(f"Erro ao processar {caminho.name}: {erro}")


class JanelaMonitoramento:
    def __init__(self) -> None:
        self.app_pdf: DivisorPDFHospitalar | None = None
        self.observador: Observer | None = None
        self.monitorando = False

        self.janela = tk.Tk()
        self.janela.title("Divisor de PDFs - Faturamento Hospitalar")
        self.janela.geometry("720x460")
        self.janela.resizable(False, False)
        self.janela.protocol("WM_DELETE_WINDOW", self.fechar)

        self.criar_interface()
        self.iniciar_monitoramento_em_thread()

    def criar_interface(self) -> None:
        self.janela.configure(bg="#f4f6f8")

        titulo = tk.Label(
            self.janela,
            text="Divisor de PDFs para Faturamento Hospitalar",
            font=("Segoe UI", 17, "bold"),
            bg="#f4f6f8",
            fg="#1f2937",
        )
        titulo.pack(pady=(22, 6))

        subtitulo = tk.Label(
            self.janela,
            text="Monitoramento automático por convênio e limite de tamanho",
            font=("Segoe UI", 10),
            bg="#f4f6f8",
            fg="#4b5563",
        )
        subtitulo.pack(pady=(0, 18))

        card = tk.Frame(self.janela, bg="white", bd=0, highlightbackground="#d1d5db", highlightthickness=1)
        card.pack(padx=24, pady=8, fill="x")

        self.status_texto = tk.StringVar(value="Iniciando monitoramento...")
        self.status_label = tk.Label(
            card,
            textvariable=self.status_texto,
            font=("Segoe UI", 13, "bold"),
            bg="white",
            fg="#2563eb",
        )
        self.status_label.pack(anchor="w", padx=18, pady=(16, 6))

        self.pasta_texto = tk.StringVar(value=f"Pasta monitorada: {PASTA_ENTRADA}")
        pasta_label = tk.Label(
            card,
            textvariable=self.pasta_texto,
            font=("Segoe UI", 9),
            bg="white",
            fg="#374151",
            wraplength=660,
            justify="left",
        )
        pasta_label.pack(anchor="w", padx=18, pady=(0, 12))

        botoes = tk.Frame(card, bg="white")
        botoes.pack(anchor="w", padx=18, pady=(0, 16))

        self.botao_abrir_pasta = ttk.Button(
            botoes,
            text="Abrir pasta monitorada",
            command=self.abrir_pasta_monitorada,
        )
        self.botao_abrir_pasta.grid(row=0, column=0, padx=(0, 8))

        self.botao_parar = ttk.Button(
            botoes,
            text="Parar monitoramento",
            command=self.parar_monitoramento,
        )
        self.botao_parar.grid(row=0, column=1, padx=(0, 8))

        self.botao_iniciar = ttk.Button(
            botoes,
            text="Iniciar monitoramento",
            command=self.iniciar_monitoramento_em_thread,
        )
        self.botao_iniciar.grid(row=0, column=2)

        frame_convenios = tk.Frame(self.janela, bg="white", bd=0, highlightbackground="#d1d5db", highlightthickness=1)
        frame_convenios.pack(padx=24, pady=12, fill="both", expand=True)

        label_convenios = tk.Label(
            frame_convenios,
            text="Convênios configurados",
            font=("Segoe UI", 12, "bold"),
            bg="white",
            fg="#111827",
        )
        label_convenios.pack(anchor="w", padx=18, pady=(14, 8))

        colunas = ("convenio", "limite", "entrada")
        self.tabela = ttk.Treeview(frame_convenios, columns=colunas, show="headings", height=7)
        self.tabela.heading("convenio", text="Convênio")
        self.tabela.heading("limite", text="Limite")
        self.tabela.heading("entrada", text="Pasta")
        self.tabela.column("convenio", width=140)
        self.tabela.column("limite", width=100)
        self.tabela.column("entrada", width=430)
        self.tabela.pack(padx=18, pady=(0, 16), fill="x")

        for nome, limite in REGRAS_CONVENIOS_MB.items():
            self.tabela.insert("", "end", values=(nome, f"{limite} MB", str(PASTA_ENTRADA / nome)))

    def iniciar_monitoramento_em_thread(self) -> None:
        if self.monitorando:
            return

        thread = threading.Thread(target=self.iniciar_monitoramento, daemon=True)
        thread.start()

    def iniciar_monitoramento(self) -> None:
        try:
            self.app_pdf = DivisorPDFHospitalar()
            self.app_pdf.processar_pdfs_existentes()

            monitor = MonitorPDFs(self.app_pdf)
            self.observador = Observer()
            self.observador.schedule(monitor, str(PASTA_ENTRADA), recursive=True)
            self.observador.start()

            self.monitorando = True
            self.atualizar_status("Monitorando pastas normalmente", "#16a34a")

            while self.monitorando:
                time.sleep(1)

        except Exception as erro:
            self.monitorando = False
            self.atualizar_status("Erro no monitoramento", "#dc2626")
            messagebox.showerror("Erro", f"Erro ao iniciar o monitoramento:{erro}")

    def parar_monitoramento(self) -> None:
        if self.observador:
            self.observador.stop()
            self.observador.join(timeout=3)

        self.monitorando = False
        self.atualizar_status("Monitoramento parado", "#dc2626")

    def atualizar_status(self, texto: str, cor: str) -> None:
        self.janela.after(0, lambda: self.status_texto.set(texto))
        self.janela.after(0, lambda: self.status_label.configure(fg=cor))

    def abrir_pasta_monitorada(self) -> None:
        try:
            PASTA_ENTRADA.mkdir(parents=True, exist_ok=True)
            import os
            os.startfile(str(PASTA_ENTRADA))
        except Exception as erro:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta:{erro}")

    def fechar(self) -> None:
        self.parar_monitoramento()
        self.janela.destroy()

    def executar(self) -> None:
        self.janela.mainloop()


def iniciar_interface() -> None:
    JanelaMonitoramento().executar()


if __name__ == "__main__":
    iniciar_interface()
