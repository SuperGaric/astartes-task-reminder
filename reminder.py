#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌面任务提醒 — 半透明玻璃风格 · 日期关联 · 定时弹窗提醒
"""

import sys, json, os, traceback
from datetime import datetime, date, time as dtime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QScrollArea, QSizePolicy,
    QCalendarWidget, QMessageBox, QSystemTrayIcon, QMenu,
    QTimeEdit, QDateEdit, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QDate, QTime, QRect
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QLinearGradient, QIcon
)

# ===================== 配置 =====================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "tasks.json")
LOG_FILE = os.path.join(APP_DIR, "reminder.log")

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")

# ===================== 数据 =====================
def load_tasks():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return []

def save_tasks(tasks):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except: pass

# ===================== 颜色 =====================
C = {
    "bg": "#1e1e2e",
    "surface": "rgba(255,255,255,15)",
    "surface_hover": "rgba(255,255,255,40)",
    "primary": "rgba(130,160,255,180)",
    "danger": "#ff7878",
    "success": "#78dc8c",
    "text": "#e0e0f5",
    "text_secondary": "#b4b4c8",
    "text_muted": "#787890",
}

# ===================== 自定义任务项 =====================
class TaskItem(QFrame):
    def __init__(self, task, on_toggle, on_delete, parent=None):
        super().__init__(parent)
        self.task = task
        self._on_toggle = on_toggle
        self._on_delete = on_delete
        self._hover = False
        self.setFixedHeight(54)
        self.setMouseTracking(True)

    def enterEvent(self, e): self._hover = True; self.update()
    def leaveEvent(self, e): self._hover = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if e.pos().x() > self.width() - 45:
                self._on_delete(self.task["id"])
            else:
                self._on_toggle(self.task["id"])

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(5, 3, -5, -3)
        rd = 8

        # 背景
        alpha = 50 if self._hover else 20
        p.setBrush(QBrush(QColor(255, 255, 255, alpha)))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawRoundedRect(r, rd, rd)

        # 复选框
        cx, cy = r.left() + 16, r.center().y()
        if self.task.get("completed"):
            p.setBrush(QBrush(QColor(C["success"])))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPoint(cx, cy), 7, 7)
            p.setPen(QPen(Qt.white, 2))
            p.drawLine(cx - 3, cy, cx - 1, cy + 3)
            p.drawLine(cx - 1, cy + 3, cx + 4, cy - 3)
        else:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(150, 150, 170), 2))
            p.drawEllipse(QPoint(cx, cy), 7, 7)

        # 任务文字（第一行）
        text_color = QColor(150, 150, 170) if self.task.get("completed") else QColor(C["text"])
        p.setPen(text_color)
        font = QFont("Microsoft YaHei", 10)
        if self.task.get("completed"): font.setStrikeOut(True)
        p.setFont(font)
        text = self.task.get("text", "")
        elided = p.fontMetrics().elidedText(text, Qt.ElideRight, r.width() - 80)
        p.drawText(r.adjusted(32, 2, -44, -10), Qt.AlignVCenter | Qt.AlignLeft, elided)

        # 日期时间（第二行）
        task_date = self.task.get("date", "")
        task_time = self.task.get("time", "")
        if task_date:
            p.setPen(QColor(130, 130, 160))
            p.setFont(QFont("Microsoft YaHei", 8))
            dt_text = task_date
            if task_time: dt_text += f"  {task_time}"
            if self.task.get("completed"):
                dt_text += "  ✓"
            elif self._is_overdue():
                dt_text += "  ⚠ overdue"
                p.setPen(QColor(C["danger"]))
            p.drawText(r.adjusted(32, 8, -44, 0), Qt.AlignVCenter | Qt.AlignLeft, dt_text)

        # 删除按钮
        dr = r.adjusted(r.width() - 40, 0, 0, 0)
        p.setPen(QColor(C["danger"]) if self._hover else QColor(100, 100, 130))
        p.setFont(QFont("Microsoft YaHei", 11))
        p.drawText(dr, Qt.AlignCenter, "✕")
        p.end()

    def _is_overdue(self):
        """检查是否过期"""
        task_date = self.task.get("date", "")
        task_time = self.task.get("time", "")
        if not task_date: return False
        try:
            now = datetime.now()
            dt_str = task_date
            if task_time: dt_str += f" {task_time}"
            due = datetime.strptime(dt_str, "%Y-%m-%d %H:%M" if task_time else "%Y-%m-%d")
            return now > due and not self.task.get("completed")
        except: return False


# ===================== 弹窗提醒 =====================
class ReminderPopup(QWidget):
    """提醒弹窗 - 玻璃风格"""
    def __init__(self, task, parent=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题
        title = QLabel("⏰ Time's Up!")
        title.setStyleSheet("color:#ffcc80;font-size:16px;font-weight:bold;background:transparent;")
        layout.addWidget(title)

        # 任务内容
        task_text = task.get("text", "")
        task_time = task.get("time", "")
        content = QLabel(f"{task_text}\nScheduled: {task_time}")
        content.setWordWrap(True)
        content.setStyleSheet("color:#e0e0f5;font-size:13px;background:transparent;padding:4px 0;")
        layout.addWidget(content)

        layout.addStretch()

        # 按钮
        bl = QHBoxLayout(); bl.setSpacing(8)
        snooze_btn = QPushButton("Snooze 5 min")
        snooze_btn.setCursor(Qt.PointingHandCursor)
        snooze_btn.clicked.connect(self.close)
        snooze_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,15);color:#b4b4c8;border:1px solid rgba(255,255,255,20);"
            "border-radius:6px;padding:6px 14px;font-size:11px;}"
            "QPushButton:hover{background:rgba(255,255,255,30);color:#e0e0f5;}")
        bl.addWidget(snooze_btn)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.clicked.connect(self.close)
        dismiss_btn.setStyleSheet(
            "QPushButton{background:rgba(130,160,255,100);color:#fff;border:none;"
            "border-radius:6px;padding:6px 18px;font-size:11px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(130,160,255,180);}")
        bl.addWidget(dismiss_btn)
        layout.addLayout(bl)

        # 定位：屏幕右下角
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 370, screen.height() - 190)

        # 自动关闭
        QTimer.singleShot(30000, self.close)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        p.fillRect(r, QColor(30, 30, 50, 235))
        # 边框
        p.setPen(QPen(QColor(255, 200, 130, 80), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1,1,-1,-1), 12, 12)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dpos = e.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and hasattr(self, '_dpos'):
            self.move(e.globalPos() - self._dpos)
class ReminderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.tasks = load_tasks()
        self._drag_pos = None
        self._cal_popup = None
        self._task_widgets = {}
        self._tray = None
        self._popups = []  # 弹窗引用
        self._filter_date = None  # 当前日历筛选日期，None=显示全部
        self._init_ui()
        self._init_tray()
        self._refresh()

        # 提醒检查定时器（每30秒）
        self._check_timer = QTimer()
        self._check_timer.timeout.connect(self._check_reminders)
        self._check_timer.start(30000)
        # 启动后立即检查一次
        QTimer.singleShot(2000, self._check_reminders)

    # ========== UI 构建 ==========
    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(400, 560)
        self.setWindowOpacity(0.93)
        self.setStyleSheet(f"background: {C['bg']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # ---- 标题栏 ----
        tl = QHBoxLayout(); tl.setContentsMargins(6, 2, 6, 2)
        title = QLabel("✦ Task Reminder")
        title.setStyleSheet(f"color:{C['text']};font-size:15px;font-weight:bold;background:transparent;")
        tl.addWidget(title)
        tl.addStretch()
        # 日期按钮
        self.date_btn = QPushButton()
        self.date_btn.setFixedHeight(30); self.date_btn.setMinimumWidth(110)
        self.date_btn.setCursor(Qt.PointingHandCursor)
        self.date_btn.clicked.connect(self._toggle_calendar)
        self._update_date_btn()
        tl.addWidget(self.date_btn)
        # 关闭
        cb = QPushButton("✕"); cb.setFixedSize(26,26); cb.setCursor(Qt.PointingHandCursor)
        cb.clicked.connect(self._hide_to_tray)
        cb.setStyleSheet("QPushButton{background:rgba(255,100,100,40);color:#e0e0f5;border-radius:13px;font-size:12px;font-weight:bold;}QPushButton:hover{background:rgba(255,100,100,160);}")
        tl.addWidget(cb)
        layout.addLayout(tl)

        # 分隔线
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,12);max-height:1px;")
        layout.addWidget(sep)

        # ---- 输入区 ----
        il = QHBoxLayout(); il.setContentsMargins(4,2,4,2); il.setSpacing(4)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Add a task...")
        self.input.setFixedHeight(34)
        self.input.returnPressed.connect(self._add)
        self.input.setStyleSheet(
            "QLineEdit{background:rgba(255,255,255,15);color:#e0e0f5;"
            "border:1px solid rgba(255,255,255,20);border-radius:7px;"
            "padding:4px 10px;font-size:13px;}"
            "QLineEdit:focus{border-color:rgba(130,160,255,160);background:rgba(255,255,255,22);}")
        il.addWidget(self.input, 1)
        # 添加按钮
        add_btn = QPushButton("+ Add"); add_btn.setFixedSize(55,34)
        add_btn.setCursor(Qt.PointingHandCursor); add_btn.clicked.connect(self._add)
        add_btn.setStyleSheet(
            "QPushButton{background:rgba(130,160,255,100);color:#fff;"
            "border:none;border-radius:7px;font-size:12px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(130,160,255,180);}"
            "QPushButton:pressed{background:rgba(100,130,220,200);}")
        il.addWidget(add_btn)
        layout.addLayout(il)

        # ---- 日期时间选择行 ----
        dtl = QHBoxLayout(); dtl.setContentsMargins(4,0,4,0); dtl.setSpacing(6)
        dt_label = QLabel("Remind at:")
        dt_label.setStyleSheet(f"color:{C['text_secondary']};font-size:11px;background:transparent;")
        dtl.addWidget(dt_label)
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setFixedHeight(28)
        self.date_edit.setStyleSheet(
            "QDateEdit{background:rgba(255,255,255,12);color:#d0d0f0;"
            "border:1px solid rgba(255,255,255,18);border-radius:5px;padding:2px 6px;font-size:11px;}"
            "QDateEdit:hover{background:rgba(255,255,255,20);}"
            "QDateEdit::drop-down{width:20px;border:none;}"
            "QCalendarWidget{background:#28283a;color:#d0d0f0;}")
        dtl.addWidget(self.date_edit)
        self.time_edit = QTimeEdit(QTime.currentTime())
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setFixedHeight(28); self.time_edit.setFixedWidth(65)
        self.time_edit.setStyleSheet(
            "QTimeEdit{background:rgba(255,255,255,12);color:#d0d0f0;"
            "border:1px solid rgba(255,255,255,18);border-radius:5px;padding:2px 6px;font-size:11px;}"
            "QTimeEdit:hover{background:rgba(255,255,255,20);}"
            "QTimeEdit::up-button,QTimeEdit::down-button{width:12px;}")
        dtl.addWidget(self.time_edit)
        dtl.addStretch()
        layout.addLayout(dtl)

        # ---- 任务列表 ----
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:rgba(0,0,0,20);width:4px;border-radius:2px;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,25);border-radius:2px;min-height:30px;}"
            "QScrollBar::handle:vertical:hover{background:rgba(255,255,255,50);}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self.task_list = QWidget()
        self.task_list.setStyleSheet("background:transparent;")
        self.task_layout = QVBoxLayout(self.task_list)
        self.task_layout.setContentsMargins(0,0,0,0); self.task_layout.setSpacing(2)
        self.task_layout.addStretch()
        scroll.setWidget(self.task_list)
        layout.addWidget(scroll)

        # ---- 底部栏 ----
        fl = QHBoxLayout(); fl.setContentsMargins(6,2,6,2)
        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color:{C['text_muted']};font-size:11px;background:transparent;")
        fl.addWidget(self.status_label)
        # 清除筛选按钮（有筛选时显示）
        self.clear_filter_btn = QPushButton("✕ filter")
        self.clear_filter_btn.setCursor(Qt.PointingHandCursor)
        self.clear_filter_btn.clicked.connect(self._clear_filter)
        self.clear_filter_btn.setStyleSheet(
            "QPushButton{background:rgba(130,160,255,50);color:#a0c0ff;"
            "border:1px solid rgba(130,160,255,80);border-radius:4px;padding:2px 6px;font-size:9px;}"
            "QPushButton:hover{background:rgba(130,160,255,120);color:#fff;}")
        self.clear_filter_btn.hide()
        fl.addWidget(self.clear_filter_btn)
        fl.addStretch()
        clear_btn = QPushButton("Clear done"); clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_done)
        clear_btn.setStyleSheet(
            "QPushButton{background:transparent;color:rgba(180,180,200,130);"
            "border:1px solid rgba(255,255,255,12);border-radius:5px;padding:3px 8px;font-size:10px;}"
            "QPushButton:hover{background:rgba(255,100,100,30);color:#ff7878;border-color:rgba(255,100,100,80);}")
        fl.addWidget(clear_btn)
        layout.addLayout(fl)

    def _init_tray(self):
        """系统托盘图标"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self)
        # 绘制一个简单的托盘图标
        pixmap = self._make_tray_icon()
        self._tray.setIcon(QIcon(pixmap))
        self._tray.setToolTip("Task Reminder")
        menu = QMenu()
        menu.addAction("Show", self._show_from_tray)
        self._autostart_action = menu.addAction("Auto-start on boot")
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(self._is_autostart())
        self._autostart_action.triggered.connect(self._toggle_autostart)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

    def _make_tray_icon(self):
        from PyQt5.QtGui import QPixmap
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(41, 82, 163)))
        p.setPen(QPen(QColor(20, 40, 80), 1.5))
        p.drawEllipse(2, 2, 28, 28)
        p.setPen(QPen(Qt.white, 2.5))
        p.drawArc(10, 12, 12, 12, 0*16, 180*16)
        p.drawLine(10, 15, 10, 22)
        p.drawLine(22, 15, 22, 22)
        p.end()
        return pm

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _hide_to_tray(self):
        if self._tray:
            self.hide()
        else:
            self.close()

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit(self):
        self._tray.hide() if self._tray else None
        QApplication.quit()

    def _startup_path(self):
        import os as _os
        return _os.path.join(_os.getenv("APPDATA",""),
            r"Microsoft\Windows\Start Menu\Programs\Startup",
            "TaskReminder.lnk")

    def _is_autostart(self):
        return os.path.exists(self._startup_path())

    def _toggle_autostart(self, checked):
        from win32com.client import Dispatch
        startup = self._startup_path()
        if checked:
            try:
                shell = Dispatch("WScript.Shell")
                shortcut = shell.CreateShortcut(startup)
                shortcut.TargetPath = "D:\\python\\pythonw.exe"
                shortcut.Arguments = os.path.join(APP_DIR, "reminder.py")
                shortcut.WorkingDirectory = APP_DIR
                shortcut.Description = "Task Reminder"
                shortcut.Save()
            except:
                self._autostart_action.setChecked(False)
        else:
            if os.path.exists(startup):
                try: os.remove(startup)
                except: pass

    # ========== 绘制 ==========
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        p.fillRect(r, QColor(30, 30, 42, 245))
        # 顶部渐变线
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0.0, QColor(130, 160, 255, 0))
        g.setColorAt(0.3, QColor(130, 160, 255, 70))
        g.setColorAt(0.7, QColor(180, 130, 255, 70))
        g.setColorAt(1.0, QColor(180, 130, 255, 0))
        p.setPen(QPen(g, 2))
        p.drawLine(16, 2, self.width() - 16, 2)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)
    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    # ========== 日历 ==========
    def _update_date_btn(self):
        today = date.today()
        wd = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][today.weekday()]
        self.date_btn.setText(f"📅 {today.month}/{today.day} {wd}")
        self.date_btn.setStyleSheet(
            f"QPushButton{{background:rgba(255,255,255,12);color:{C['text_secondary']};"
            f"border:1px solid rgba(255,255,255,18);border-radius:7px;padding:3px 10px;font-size:11px;}}"
            f"QPushButton:hover{{background:rgba(255,255,255,30);color:{C['text']};}}")

    def _toggle_calendar(self):
        if self._cal_popup and self._cal_popup.isVisible():
            self._cal_popup.close(); return
        self._cal_popup = QWidget(None, Qt.Popup | Qt.FramelessWindowHint)
        self._cal_popup.setFixedSize(300, 330)
        self._cal_popup.setStyleSheet("background:#28283a;border-radius:10px;")
        cl = QVBoxLayout(self._cal_popup); cl.setContentsMargins(6,6,6,6)
        cal = QCalendarWidget()
        cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setStyleSheet(
            "QCalendarWidget{background:#28283a;border-radius:8px;padding:4px;color:#d0d0f0;}"
            "QCalendarWidget QToolButton{color:#d0d0f0;background:rgba(255,255,255,15);"
            "border-radius:5px;padding:4px 10px;font-weight:bold;}"
            "QCalendarWidget QToolButton:hover{background:rgba(255,255,255,30);}"
            "QCalendarWidget QAbstractItemView:enabled{color:#d0d0f0;"
            "selection-background-color:rgba(130,160,255,80);selection-color:#fff;}"
            "QCalendarWidget QAbstractItemView:disabled{color:rgba(120,120,150,80);}")
        cal.clicked.connect(lambda d: (
            self.date_edit.setDate(d),
            setattr(self, '_filter_date', d.toString("yyyy-MM-dd")),
            QTimer.singleShot(100, self._cal_popup.close),
            self._refresh()
        ))
        cl.addWidget(cal)
        btn = QPushButton("Today")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: cal.setSelectedDate(QDate.currentDate()))
        btn.setStyleSheet(
            "QPushButton{background:rgba(130,160,255,50);color:#d0d0f0;border:none;"
            "border-radius:6px;padding:6px;}QPushButton:hover{background:rgba(130,160,255,120);}")
        cl.addWidget(btn)
        pos = self.date_btn.mapToGlobal(self.date_btn.rect().bottomLeft())
        self._cal_popup.move(pos.x() - 80, pos.y() + 4)
        self._cal_popup.show()

    # ========== 业务逻辑 ==========
    def _add(self):
        txt = self.input.text().strip()
        if not txt: return
        task = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "text": txt,
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "time": self.time_edit.time().toString("HH:mm"),
            "reminded": False,
        }
        self.tasks.append(task)
        save_tasks(self.tasks)
        self.input.clear()
        self._refresh()
        log(f"Task added: {txt} @ {task['date']} {task['time']}")

    def _toggle(self, tid):
        for t in self.tasks:
            if t["id"] == tid:
                t["completed"] = not t.get("completed", False)
                break
        save_tasks(self.tasks)
        self._refresh()

    def _delete(self, tid):
        self.tasks = [t for t in self.tasks if t["id"] != tid]
        save_tasks(self.tasks)
        self._refresh()

    def _clear_done(self):
        self.tasks = [t for t in self.tasks if not t.get("completed")]
        save_tasks(self.tasks)
        self._refresh()

    def _refresh(self):
        # 清除旧控件
        for w in self._task_widgets.values():
            self.task_layout.removeWidget(w)
            w.deleteLater()
        self._task_widgets.clear()

        # 按日期排序
        self.tasks.sort(key=lambda t: (t.get("date",""), t.get("time",""), t.get("id","")))

        # 日期筛选：显示选中日期及之后的任务
        if self._filter_date:
            visible = [t for t in self.tasks if t.get("date","") >= self._filter_date]
        else:
            visible = self.tasks

        # 重建
        for t in visible:
            item = TaskItem(t, self._toggle, self._delete)
            self.task_layout.insertWidget(self.task_layout.count() - 1, item)
            self._task_widgets[t["id"]] = item

        # 状态栏
        total = len(self.tasks)
        shown = len(visible)
        done = sum(1 for t in visible if t.get("completed"))
        overdue = sum(1 for t in visible if self._is_task_overdue(t))

        parts = []
        if self._filter_date:
            parts.append(f"📅 {self._filter_date}")
        parts += [f"{shown}/{total} tasks", f"{shown-done} active", f"{done} done"]
        if overdue: parts.append(f"{overdue} overdue")
        # 清除筛选按钮显隐
        self.clear_filter_btn.setVisible(bool(self._filter_date))
        self.status_label.setText("  |  ".join(parts))

    def _clear_filter(self):
        """清除日期筛选"""
        self._filter_date = None
        self._refresh()

    def _is_task_overdue(self, task):
        if task.get("completed"): return False
        d = task.get("date","")
        if not d: return False
        try:
            tm = task.get("time","")
            dt_str = d + (" " + tm if tm else "")
            fmt = "%Y-%m-%d %H:%M" if tm else "%Y-%m-%d"
            return datetime.now() > datetime.strptime(dt_str, fmt)
        except: return False

    # ========== 提醒系统 ==========
    def _check_reminders(self):
        """检查是否有任务需要提醒"""
        now = datetime.now()
        for task in self.tasks:
            if task.get("completed"): continue
            if task.get("reminded"): continue
            d = task.get("date", "")
            t = task.get("time", "")
            if not d: continue
            try:
                dt_str = d + (" " + t if t else "")
                fmt = "%Y-%m-%d %H:%M" if t else "%Y-%m-%d"
                due = datetime.strptime(dt_str, fmt)
                # 在提醒时间前后 1 分钟内触发
                diff = abs((now - due).total_seconds())
                if diff <= 60:
                    self._fire_reminder(task)
                    task["reminded"] = True
                    save_tasks(self.tasks)
            except: pass

    def _fire_reminder(self, task):
        """弹出提醒窗口"""
        text = task.get("text", "")
        task_time = task.get("time", "")
        # 托盘通知
        if self._tray and QSystemTrayIcon.supportsMessages():
            self._tray.showMessage("⏰ Task Reminder", f"[{task_time}] {text}", QSystemTrayIcon.Information, 5000)
        # 弹窗
        popup = ReminderPopup(task)
        popup.show()
        self._popups.append(popup)
        # 清理已关闭的弹窗
        self._popups = [p for p in self._popups if p.isVisible()]
        log(f"REMINDER POPUP: {text}")

    # ========== 关闭事件 ==========
    def closeEvent(self, e):
        if self._tray and self._tray.isVisible():
            self.hide()
            e.ignore()
        else:
            QApplication.quit()


# ===================== 入口 =====================
def main():
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，由托盘控制
        app.setFont(QFont("Microsoft YaHei", 10))

        w = ReminderApp()
        screen = app.primaryScreen().geometry()
        w.move(screen.width() - 430, 60)
        w.show()

        sys.exit(app.exec_())
    except Exception:
        with open(os.path.join(APP_DIR, "error.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        try:
            QMessageBox.critical(None, "Error", traceback.format_exc())
        except: pass
        sys.exit(1)

if __name__ == "__main__":
    main()
