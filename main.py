import sys
import json
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QSlider, QLineEdit, QComboBox,
    QCheckBox, QMessageBox, QGridLayout
)
from pynput import keyboard, mouse

APP_DIR = Path.home() / "AppData" / "Local" / "BLACK_MACRO_MENU"
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = APP_DIR / "config.json"

DEFAULTS = {
    "lite_steps": [
        {"key": "scroll_down", "ms": 30},
        {"key": "e", "ms": 30},
        {"key": "q", "ms": 30},
        {"key": "left_ctrl", "ms": 30},
    ],
    "lite_trigger": "mouse2",
    "lite_mode": "press",
    "run_interval": 321,
    "run_enabled": False,
    "lite_enabled": False,
}

def load_config():
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        merged = DEFAULTS.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULTS.copy()

def save_config(data):
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

class Bus(QObject):
    status = Signal(str, bool)
    info = Signal(str)

class MacroEngine:
    def __init__(self, bus, config):
        self.bus = bus
        self.config = config
        self.lock = threading.RLock()
        self.lite_active = False
        self.run_active = False
        self.run_keys = set()
        self.last_lite = 0.0
        self.last_scroll = 0.0
        self.stop_event = threading.Event()
        self.k_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.m_listener = mouse.Listener(on_click=self.on_click)
        self.k_listener.start()
        self.m_listener.start()
        self.worker = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker.start()

    def set_config(self, config):
        with self.lock:
            self.config = config

    def set_lite(self, enabled):
        with self.lock:
            self.lite_active = enabled
        self.bus.status.emit("lite", enabled)

    def set_run(self, enabled):
        with self.lock:
            self.run_active = enabled
        self.bus.status.emit("run", enabled)

    def on_press(self, key):
        name = self.key_name(key)
        with self.lock:
            if name in ("w", "a", "s", "d"):
                self.run_keys.add(name)
            if not self.lite_active:
                return
            trigger = self.config.get("lite_trigger", "mouse2")
            mode = self.config.get("lite_mode", "press")
            if trigger == "right_mouse" and key == keyboard.Key.ctrl_r:
                return
        # Lite Foot is triggered by right mouse button in press/release mode below.

    def on_release(self, key):
        name = self.key_name(key)
        with self.lock:
            self.run_keys.discard(name)

    def on_click(self, x, y, button, pressed):
        if button != mouse.Button.right:
            return
        with self.lock:
            if not self.lite_active:
                return
            mode = self.config.get("lite_mode", "press")
            if (mode == "press" and pressed) or (mode == "release" and not pressed):
                now = time.monotonic()
                if now - self.last_lite < 0.12:
                    return
                self.last_lite = now
        threading.Thread(target=self.run_lite_sequence, daemon=True).start()

    @staticmethod
    def key_name(key):
        try:
            if hasattr(key, "char") and key.char:
                return key.char.lower()
            mapping = {
                keyboard.Key.ctrl_l: "left_ctrl",
                keyboard.Key.ctrl_r: "right_ctrl",
                keyboard.Key.shift: "shift",
                keyboard.Key.alt: "alt",
                keyboard.Key.space: "space",
            }
            return mapping.get(key, str(key).replace("Key.", "").lower())
        except Exception:
            return ""

    def send_step(self, name):
        ctl = mouse.Controller()
        kb = keyboard.Controller()
        if name == "scroll_down":
            ctl.scroll(0, -1)
        elif name == "scroll_up":
            ctl.scroll(0, 1)
        elif name == "left_ctrl":
            kb.press(keyboard.Key.ctrl_l)
            kb.release(keyboard.Key.ctrl_l)
        elif name == "right_ctrl":
            kb.press(keyboard.Key.ctrl_r)
            kb.release(keyboard.Key.ctrl_r)
        elif len(name) == 1:
            kb.press(name)
            kb.release(name)

    def run_lite_sequence(self):
        with self.lock:
            steps = [dict(s) for s in self.config.get("lite_steps", [])]
        try:
            for step in steps:
                self.send_step(step.get("key", ""))
                time.sleep(max(1, min(1000, int(step.get("ms", 30)))) / 1000)
        except Exception as exc:
            self.bus.info.emit(f"Falha no Lite Foot: {exc}")

    def worker_loop(self):
        while not self.stop_event.is_set():
            with self.lock:
                should_run = self.run_active and bool(self.run_keys)
                interval = max(40, min(2000, int(self.config.get("run_interval", 321))))
                now = time.monotonic()
                fire = should_run and (now - self.last_scroll) * 1000 >= interval
                if fire:
                    self.last_scroll = now
            if fire:
                try:
                    mouse.Controller().scroll(0, 1)
                except Exception as exc:
                    self.bus.info.emit(f"Falha no Correr: {exc}")
            time.sleep(0.005)

    def close(self):
        self.stop_event.set()
        try:
            self.k_listener.stop()
            self.m_listener.stop()
        except Exception:
            pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.bus = Bus()
        self.engine = MacroEngine(self.bus, self.config)
        self.bus.status.connect(self.update_status)
        self.bus.info.connect(self.show_info)
        self.setWindowTitle("BLACK MACRO MENU")
        self.resize(1120, 720)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLE)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(250)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("BLACK MACRO MENU")
        brand.setObjectName("brand")
        side.addWidget(brand)
        side.addSpacing(28)
        side.addWidget(self.nav_button("⌂   Início", 0))
        side.addWidget(self.nav_button("▣   Lite Foot", 1))
        side.addWidget(self.nav_button("◎   Correr", 2))
        side.addStretch()
        foot = QLabel("By MTA FORGE\nSomente duas funções")
        foot.setObjectName("muted")
        side.addWidget(foot)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.home_page())
        self.pages.addWidget(self.lite_page())
        self.pages.addWidget(self.run_page())
        layout.addWidget(sidebar)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

    def nav_button(self, label, index):
        b = QPushButton(label)
        b.setObjectName("nav")
        b.clicked.connect(lambda: self.pages.setCurrentIndex(index))
        return b

    def make_card(self):
        f = QFrame()
        f.setObjectName("card")
        return f

    def home_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(36, 34, 36, 30)
        title = QLabel("Início")
        title.setObjectName("pageTitle")
        l.addWidget(title)
        sub = QLabel("Painel de macros para MTA")
        sub.setObjectName("muted")
        l.addWidget(sub)
        l.addSpacing(24)
        for name, desc, page in [
            ("LITE FOOT", "Q-Bug automático com sequência configurável.", 1),
            ("CORRER", "Scroll para cima enquanto W, A, S ou D estiver pressionada.", 2),
        ]:
            card = self.make_card()
            cl = QVBoxLayout(card)
            h = QLabel(name); h.setObjectName("cardTitle")
            d = QLabel(desc); d.setObjectName("muted")
            btn = QPushButton("ABRIR")
            btn.clicked.connect(lambda checked=False, p=page: self.pages.setCurrentIndex(p))
            cl.addWidget(h); cl.addWidget(d); cl.addWidget(btn, alignment=Qt.AlignLeft)
            l.addWidget(card)
            l.addSpacing(14)
        l.addStretch()
        return w

    def lite_page(self):
        w = QWidget()
        l = QVBoxLayout(w); l.setContentsMargins(36, 30, 36, 30)
        title = QLabel("Lite Foot"); title.setObjectName("pageTitle")
        l.addWidget(title)
        desc = QLabel("Configure a sequência do Q-Bug e o intervalo de cada etapa.")
        desc.setObjectName("muted"); l.addWidget(desc); l.addSpacing(18)
        card = self.make_card(); grid = QGridLayout(card); grid.setContentsMargins(22, 20, 22, 20)
        grid.addWidget(self.heading("TECLA"), 0, 0)
        grid.addWidget(self.heading("DELAY (MS)"), 0, 1)
        self.step_inputs = []
        labels = ["Etapa 1", "Etapa 2", "Etapa 3", "Etapa 4"]
        for i, label in enumerate(labels):
            step = self.config["lite_steps"][i]
            grid.addWidget(QLabel(label), i+1, 0)
            key = QLineEdit(step["key"]); key.setMaximumWidth(180)
            ms = QLineEdit(str(step["ms"])); ms.setMaximumWidth(100)
            grid.addWidget(key, i+1, 0, alignment=Qt.AlignRight)
            grid.addWidget(ms, i+1, 1)
            self.step_inputs.append((key, ms))
        l.addWidget(card)
        l.addSpacing(14)
        options = self.make_card(); ol = QVBoxLayout(options)
        row = QHBoxLayout()
        row.addWidget(QLabel("DISPARAR"))
        self.trigger = QComboBox(); self.trigger.addItem("Mouse 2 (botão direito)", "mouse2")
        row.addWidget(self.trigger); row.addStretch()
        ol.addLayout(row)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("QUANDO"))
        self.mode = QComboBox(); self.mode.addItem("Ao pressionar", "press"); self.mode.addItem("Ao soltar", "release")
        row2.addWidget(self.mode); row2.addStretch(); ol.addLayout(row2)
        l.addWidget(options); l.addSpacing(14)
        self.lite_status = self.status_label()
        l.addWidget(self.lite_status)
        row = QHBoxLayout()
        save = QPushButton("SALVAR CONFIGURAÇÃO"); save.clicked.connect(self.save_lite)
        self.lite_toggle = QPushButton("ATIVAR"); self.lite_toggle.setObjectName("primary")
        self.lite_toggle.clicked.connect(self.toggle_lite)
        row.addWidget(save); row.addWidget(self.lite_toggle); l.addLayout(row); l.addStretch()
        return w

    def run_page(self):
        w = QWidget()
        l = QVBoxLayout(w); l.setContentsMargins(36, 30, 36, 30)
        title = QLabel("Correr"); title.setObjectName("pageTitle")
        l.addWidget(title)
        desc = QLabel("Enquanto W, A, S ou D estiver pressionada, o macro envia Mouse Wheel Up.")
        desc.setObjectName("muted"); l.addWidget(desc); l.addSpacing(20)
        card = self.make_card(); cl = QVBoxLayout(card)
        row = QHBoxLayout()
        row.addWidget(QLabel("INTERVALO DA ROLAGEM"))
        self.interval_label = QLabel(f'{self.config["run_interval"]} ms'); self.interval_label.setObjectName("accent")
        row.addStretch(); row.addWidget(self.interval_label); cl.addLayout(row)
        self.interval = QSlider(Qt.Horizontal); self.interval.setRange(40, 1000)
        self.interval.setValue(int(self.config["run_interval"]))
        self.interval.valueChanged.connect(lambda v: self.interval_label.setText(f"{v} ms"))
        cl.addWidget(self.interval)
        l.addWidget(card); l.addSpacing(18)
        self.run_status = self.status_label()
        l.addWidget(self.run_status)
        self.run_toggle = QPushButton("ATIVAR"); self.run_toggle.setObjectName("primary")
        self.run_toggle.clicked.connect(self.toggle_run)
        l.addWidget(self.run_toggle, alignment=Qt.AlignLeft)
        note = QLabel("O macro só dispara a rolagem enquanto uma das teclas W, A, S ou D estiver pressionada.")
        note.setObjectName("muted"); note.setWordWrap(True); l.addWidget(note)
        l.addStretch()
        return w

    def heading(self, text):
        x = QLabel(text); x.setObjectName("muted"); return x

    def status_label(self):
        x = QLabel("STATUS: OFF"); x.setObjectName("status"); return x

    def save_lite(self):
        steps = []
        for key, ms in self.step_inputs:
            name = key.text().strip().lower()
            if name not in {"scroll_down", "scroll_up", "e", "q", "left_ctrl", "right_ctrl", "space"} and len(name) != 1:
                QMessageBox.warning(self, "Tecla inválida", f"Tecla não reconhecida: {name}")
                return
            try: delay = max(1, min(1000, int(ms.text())))
            except ValueError:
                QMessageBox.warning(self, "Delay inválido", "Use um número de milissegundos.")
                return
            steps.append({"key": name, "ms": delay})
        self.config["lite_steps"] = steps
        self.config["lite_trigger"] = self.trigger.currentData()
        self.config["lite_mode"] = self.mode.currentData()
        save_config(self.config); self.engine.set_config(self.config)
        self.bus.info.emit("Configuração do Lite Foot salva.")

    def toggle_lite(self):
        enabled = not self.engine.lite_active
        if enabled: self.save_lite()
        self.engine.set_lite(enabled)
        self.lite_toggle.setText("DESATIVAR" if enabled else "ATIVAR")

    def toggle_run(self):
        enabled = not self.engine.run_active
        self.config["run_interval"] = self.interval.value()
        save_config(self.config); self.engine.set_config(self.config)
        self.engine.set_run(enabled)
        self.run_toggle.setText("DESATIVAR" if enabled else "ATIVAR")

    def update_status(self, which, enabled):
        label = self.lite_status if which == "lite" else self.run_status
        label.setText("STATUS: ON" if enabled else "STATUS: OFF")

    def show_info(self, message):
        self.statusBar().showMessage(message, 4000)

    def closeEvent(self, event):
        self.engine.close()
        event.accept()

STYLE = """
QMainWindow, QWidget { background: #080808; color: #eeeeee; font-family: Segoe UI; font-size: 14px; }
#sidebar { background: #0b0b0b; border-right: 1px solid #242424; }
#brand { color: #ffbd00; font-family: Georgia; font-size: 23px; font-weight: bold; }
#nav { text-align: left; padding: 13px 12px; border: 0; border-radius: 8px; color: #aaa; font-weight: 600; }
#nav:hover { background: #241d08; color: #ffbd00; }
#pageTitle { font-family: Georgia; font-size: 32px; font-weight: bold; color: #f4f0e7; }
#muted { color: #99958d; }
#card { background: #101010; border: 1px solid #303030; border-radius: 16px; padding: 12px; }
#cardTitle { color: #ffbd00; font-size: 18px; font-weight: bold; }
QPushButton { background: #181818; color: #eee; border: 1px solid #333; border-radius: 9px; padding: 11px 18px; font-weight: bold; }
QPushButton:hover { border-color: #ffbd00; }
QPushButton#primary { background: #ffbd00; color: #080808; border: 0; min-width: 160px; }
QPushButton#primary:hover { background: #ffd23f; }
QLineEdit, QComboBox { background: #080808; border: 1px solid #383838; border-radius: 7px; padding: 9px; color: #ffbd00; }
QSlider::groove:horizontal { height: 6px; background: #303030; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #ffbd00; border-radius: 3px; }
QSlider::handle:horizontal { background: #ffbd00; width: 18px; margin: -7px 0; border-radius: 9px; }
#status { background: #141414; border: 1px solid #333; border-radius: 9px; padding: 13px; color: #ffbd00; font-weight: bold; }
#accent { color: #ffbd00; font-weight: bold; }
QStatusBar { color: #ffbd00; }
"""

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
