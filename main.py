import json
import threading
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

try:
    import keyboard
except ImportError:
    keyboard = None

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "macros.json"

class MacroMenu:
    def __init__(self, root):
        self.root = root
        self.root.title("BLACK MACRO MENU")
        self.root.geometry("850x560")
        self.root.minsize(760, 500)
        self.root.configure(bg="#101010")
        self.macros = []
        self.hotkey_handles = []
        self.running = False

        self._style()
        self._build()
        self.load_macros()
        self.refresh_list()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#191919", foreground="#eeeeee",
                        fieldbackground="#191919", rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background="#252525", foreground="#ff4545",
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#5b1717")])
        style.configure("TCombobox", fieldbackground="#202020", background="#202020",
                        foreground="white")

    def _label(self, parent, text):
        return tk.Label(parent, text=text, bg="#101010", fg="#cfcfcf",
                        font=("Segoe UI", 10, "bold"))

    def _entry(self, parent, width=22):
        return tk.Entry(parent, width=width, bg="#202020", fg="white",
                        insertbackground="white", relief="flat",
                        font=("Segoe UI", 11))

    def _build(self):
        header = tk.Frame(self.root, bg="#101010")
        header.pack(fill="x", padx=22, pady=(18, 10))
        tk.Label(header, text="BLACK", bg="#101010", fg="#ff3434",
                 font=("Segoe UI", 25, "bold")).pack(side="left")
        tk.Label(header, text=" MACRO MENU", bg="#101010", fg="white",
                 font=("Segoe UI", 18, "bold")).pack(side="left", pady=(5, 0))
        self.status = tk.Label(header, text="● DESATIVADO", bg="#101010",
                               fg="#888888", font=("Segoe UI", 10, "bold"))
        self.status.pack(side="right", pady=10)

        body = tk.Frame(self.root, bg="#101010")
        body.pack(fill="both", expand=True, padx=22, pady=8)

        left = tk.Frame(body, bg="#151515", highlightbackground="#292929",
                        highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(left, text="MACROS CADASTRADAS", bg="#151515", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=12)

        self.tree = ttk.Treeview(left, columns=("trigger", "sequence", "delay"),
                                 show="headings", selectmode="browse")
        self.tree.heading("trigger", text="TECLA")
        self.tree.heading("sequence", text="SEQUÊNCIA")
        self.tree.heading("delay", text="DELAY")
        self.tree.column("trigger", width=90, anchor="center")
        self.tree.column("sequence", width=300)
        self.tree.column("delay", width=90, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree.bind("<<TreeviewSelect>>", self.select_macro)

        right = tk.Frame(body, bg="#151515", width=270,
                         highlightbackground="#292929", highlightthickness=1)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="EDITOR DE MACRO", bg="#151515", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=12)

        form = tk.Frame(right, bg="#151515")
        form.pack(fill="x", padx=14)
        self._label(form, "TECLA DE ATIVAÇÃO").pack(anchor="w")
        self.trigger_entry = self._entry(form)
        self.trigger_entry.pack(fill="x", pady=(5, 12))
        self._label(form, "SEQUÊNCIA DE TECLAS").pack(anchor="w")
        self.sequence_entry = self._entry(form)
        self.sequence_entry.pack(fill="x", pady=(5, 4))
        tk.Label(form, text="Ex.: w, w, space, e", bg="#151515", fg="#777777",
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 12))
        self._label(form, "INTERVALO ENTRE TECLAS (MS)").pack(anchor="w")
        self.delay_entry = self._entry(form)
        self.delay_entry.insert(0, "100")
        self.delay_entry.pack(fill="x", pady=(5, 14))

        self._button(right, "ADICIONAR / ATUALIZAR", self.save_macro).pack(fill="x", padx=14, pady=4)
        self._button(right, "LIMPAR CAMPOS", self.clear_fields, secondary=True).pack(fill="x", padx=14, pady=4)
        self._button(right, "EXCLUIR MACRO", self.delete_macro, secondary=True).pack(fill="x", padx=14, pady=4)

        footer = tk.Frame(self.root, bg="#101010")
        footer.pack(fill="x", padx=22, pady=(8, 18))
        self._button(footer, "ATIVAR MACROS", self.enable_macros).pack(side="left")
        self._button(footer, "DESATIVAR", self.disable_macros, secondary=True).pack(side="left", padx=8)
        tk.Label(footer, text="Modo PRESS: aperte a tecla uma vez para executar a sequência.",
                 bg="#101010", fg="#888888", font=("Segoe UI", 9)).pack(side="right", pady=10)

    def _button(self, parent, text, command, secondary=False):
        bg = "#292929" if secondary else "#a91f1f"
        active = "#3a3a3a" if secondary else "#d12a2a"
        return tk.Button(parent, text=text, command=command, bg=bg, fg="white",
                         activebackground=active, activeforeground="white",
                         relief="flat", bd=0, padx=12, pady=10,
                         font=("Segoe UI", 9, "bold"), cursor="hand2")

    def load_macros(self):
        if DATA_FILE.exists():
            try:
                self.macros = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            except Exception:
                messagebox.showwarning("BLACK MACRO MENU", "Não foi possível ler macros.json. Começando com uma lista vazia.")
                self.macros = []

    def persist(self):
        DATA_FILE.write_text(json.dumps(self.macros, ensure_ascii=False, indent=2), encoding="utf-8")

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, macro in enumerate(self.macros):
            self.tree.insert("", "end", iid=str(i), values=(
                macro["trigger"], ", ".join(macro["sequence"]), f'{macro["delay"]} ms'
            ))

    def select_macro(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        macro = self.macros[int(selected[0])]
        self.trigger_entry.delete(0, "end")
        self.trigger_entry.insert(0, macro["trigger"])
        self.sequence_entry.delete(0, "end")
        self.sequence_entry.insert(0, ", ".join(macro["sequence"]))
        self.delay_entry.delete(0, "end")
        self.delay_entry.insert(0, str(macro["delay"]))

    def clear_fields(self):
        self.trigger_entry.delete(0, "end")
        self.sequence_entry.delete(0, "end")
        self.delay_entry.delete(0, "end")
        self.delay_entry.insert(0, "100")
        self.tree.selection_remove(self.tree.selection())

    def save_macro(self):
        trigger = self.trigger_entry.get().strip().lower()
        sequence_text = self.sequence_entry.get().strip().lower()
        if not trigger or not sequence_text:
            messagebox.showerror("Campo obrigatório", "Preencha a tecla de ativação e a sequência.")
            return
        sequence = [key.strip() for key in sequence_text.split(",") if key.strip()]
        try:
            delay = int(self.delay_entry.get().strip())
            if delay < 0 or delay > 10000:
                raise ValueError
        except ValueError:
            messagebox.showerror("Delay inválido", "Use um número entre 0 e 10000 ms.")
            return
        selected = self.tree.selection()
        item = {"trigger": trigger, "sequence": sequence, "delay": delay}
        if selected:
            self.macros[int(selected[0])] = item
        else:
            if any(m["trigger"] == trigger for m in self.macros):
                messagebox.showerror("Tecla repetida", "Essa tecla já está sendo usada por outra macro.")
                return
            self.macros.append(item)
        self.persist()
        self.refresh_list()
        self.clear_fields()

    def delete_macro(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Excluir macro", "Selecione uma macro na lista.")
            return
        del self.macros[int(selected[0])]
        self.persist()
        self.refresh_list()
        self.clear_fields()

    def run_sequence(self, macro):
        if not keyboard:
            return
        try:
            for key in macro["sequence"]:
                if not self.running:
                    break
                keyboard.press_and_release(key)
                time.sleep(macro["delay"] / 1000)
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("Erro na macro", str(exc)))

    def enable_macros(self):
        if keyboard is None:
            messagebox.showerror("Dependência ausente", "Instale as dependências com: pip install -r requirements.txt")
            return
        self.disable_macros(silent=True)
        if not self.macros:
            messagebox.showinfo("Sem macros", "Adicione pelo menos uma macro antes de ativar.")
            return
        self.running = True
        try:
            for macro in self.macros:
                handle = keyboard.add_hotkey(
                    macro["trigger"],
                    lambda m=macro: threading.Thread(target=self.run_sequence, args=(m,), daemon=True).start(),
                    suppress=False
                )
                self.hotkey_handles.append(handle)
            self.status.config(text="● ATIVADO", fg="#35c46a")
        except Exception as exc:
            self.disable_macros(silent=True)
            messagebox.showerror("Não foi possível ativar", str(exc))

    def disable_macros(self, silent=False):
        self.running = False
        if keyboard:
            for handle in self.hotkey_handles:
                try:
                    keyboard.remove_hotkey(handle)
                except Exception:
                    pass
        self.hotkey_handles.clear()
        self.status.config(text="● DESATIVADO", fg="#888888")
        if not silent:
            pass

    def close(self):
        self.disable_macros(silent=True)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MacroMenu(root)
    root.mainloop()
