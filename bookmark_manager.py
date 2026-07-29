#!/usr/bin/env python3
import sys
import json
from pathlib import Path
from typing import List, Dict, Set
from html.parser import HTMLParser

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QDialog, QLineEdit, QDialogButtonBox, QMenu, QSplitter, QTextEdit, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor


class BookmarkParser(HTMLParser):
    """Parse Netscape-format HTML bookmark files (Chrome / Edge export)."""

    def __init__(self):
        super().__init__()
        self.bookmarks: List[Dict] = []
        self.folder_stack: List[str] = []
        self.current_bookmark: Dict = {}
        self.current_data: str = ""
        self.in_anchor: bool = False
        self.in_h3: bool = False  # was 'h3_open' — never set in original, now fixed

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'a':
            self.in_anchor = True
            self.in_h3 = False
            self.current_data = ""
            self.current_bookmark = {
                'title': '',
                'url': attrs_dict.get('href', ''),
                'folder': '/'.join(self.folder_stack) if self.folder_stack else 'Unsorted',
            }
        elif tag == 'h3':
            self.in_h3 = True
            self.in_anchor = False
            self.current_data = ""

    def handle_data(self, data):
        if self.in_anchor or self.in_h3:
            self.current_data += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.in_anchor:
            self.in_anchor = False
            if self.current_bookmark.get('url'):
                self.current_bookmark['title'] = self.current_data.strip() or self.current_bookmark['url']
                self.bookmarks.append(self.current_bookmark)
            self.current_data = ""
        elif tag == 'h3' and self.in_h3:
            self.in_h3 = False
            name = self.current_data.strip()
            if name:
                self.folder_stack.append(name)
            self.current_data = ""
        elif tag == 'dl':
            if self.folder_stack:
                self.folder_stack.pop()


# ──────────────────────────────────────────────
#  Edit dialog
# ──────────────────────────────────────────────

class EditBookmarkDialog(QDialog):
    def __init__(self, parent=None, bookmark: Dict = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Bookmark" if bookmark else "Add Bookmark")
        self.setMinimumWidth(460)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        self.title_input  = QLineEdit(bookmark.get('title',  '') if bookmark else '')
        self.url_input    = QLineEdit(bookmark.get('url',    '') if bookmark else '')
        self.folder_input = QLineEdit(bookmark.get('folder', 'Unsorted') if bookmark else 'Unsorted')
        for lbl, widget in [("Title:", self.title_input), ("URL:", self.url_input), ("Folder:", self.folder_input)]:
            layout.addWidget(QLabel(lbl))
            layout.addWidget(widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> Dict:
        return {
            'title':  self.title_input.text().strip(),
            'url':    self.url_input.text().strip(),
            'folder': self.folder_input.text().strip() or 'Unsorted',
        }


# ──────────────────────────────────────────────
#  Main window
# ──────────────────────────────────────────────

class BookmarkManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bookmark Manager")
        self.setMinimumSize(900, 560)
        self.resize(1100, 660)
        self.bookmarks: List[Dict] = []
        self.current_file: str = ""
        self._populating: bool = False
        self._build_ui()
        self._apply_style()

    # ── UI construction ──────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(8, 8, 8, 8)

        # Toolbar
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.load_btn   = self._mkbtn("📂  Load",               self.load_file,   always_on=True)
        self.save_btn   = self._mkbtn("💾  Save",               self.save_file)
        self.saveas_btn = self._mkbtn("💾  Save As…",           self.save_file_as)
        self.dedupe_btn = self._mkbtn("🔁  Remove Duplicates",  self.remove_duplicates)
        self.sort_btn   = self._mkbtn("🔤  Sort by Title",      self.sort_bookmarks)
        self.add_btn    = self._mkbtn("➕  Add Bookmark",       self.add_bookmark)
        for btn in [self.load_btn, self.save_btn, self.saveas_btn,
                    self.dedupe_btn, self.sort_btn, self.add_btn]:
            bar.addWidget(btn)
        bar.addStretch()
        root.addLayout(bar)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("divider")
        root.addWidget(line)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Folders & Bookmarks")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.model().rowsInserted.connect(self._on_rows_moved)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        splitter.addWidget(self.tree)

        # Detail panel
        detail_panel = QWidget()
        detail_panel.setObjectName("detailPanel")
        dp = QVBoxLayout(detail_panel)
        dp.setContentsMargins(10, 10, 10, 10)
        dp.setSpacing(8)
        dp.addWidget(QLabel("Details", objectName="detailHeader"))
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setObjectName("detailText")
        self.detail_text.setPlaceholderText("Select a bookmark to see its details.")
        dp.addWidget(self.detail_text)
        self.edit_btn   = self._mkbtn("✏️  Edit",   self.edit_selected)
        self.delete_btn = self._mkbtn("🗑️  Delete", self.delete_selected)
        for btn in [self.edit_btn, self.delete_btn]:
            btn.setEnabled(False)
            dp.addWidget(btn)
        dp.addStretch()
        splitter.addWidget(detail_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        self.status_lbl = QLabel("Ready — load a Chrome or Edge HTML export to begin.")
        self.status_lbl.setObjectName("statusBar")
        root.addWidget(self.status_lbl)

    def _mkbtn(self, text: str, slot, always_on: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.clicked.connect(slot)
        if not always_on:
            b.setEnabled(False)
        return b

    def _apply_style(self):
        QApplication.setStyle("Fusion")
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#1e1e2e; color:#cdd6f4;
                font-family:'Segoe UI',sans-serif; font-size:13px; }
            QPushButton { background:#313244; color:#cdd6f4; border:1px solid #45475a;
                border-radius:5px; padding:5px 12px; min-width:110px; }
            QPushButton:hover   { background:#45475a; }
            QPushButton:pressed { background:#585b70; }
            QPushButton:disabled{ background:#1e1e2e; color:#585b70; border-color:#313244; }
            QTreeWidget { background:#181825; border:1px solid #313244;
                border-radius:6px; color:#cdd6f4; }
            QTreeWidget::item { padding:3px 4px; border-radius:3px; }
            QTreeWidget::item:selected { background:#313244; color:#cba6f7; }
            QTreeWidget::item:hover    { background:#252535; }
            QHeaderView::section { background:#181825; color:#6c7086; border:none; padding:4px; }
            QTextEdit#detailText { background:#181825; border:1px solid #313244;
                border-radius:6px; color:#cdd6f4; padding:6px; }
            QLabel#detailHeader { color:#89b4fa; font-weight:bold; font-size:14px; }
            QLabel#statusBar    { color:#6c7086; font-size:11px; padding:4px 2px 0 2px; }
            QFrame#divider      { color:#313244; margin:4px 0; }
            QScrollBar:vertical { background:#181825; width:8px; border-radius:4px; }
            QScrollBar::handle:vertical { background:#45475a; border-radius:4px; }
            QDialog  { background:#1e1e2e; color:#cdd6f4; }
            QLabel   { color:#cdd6f4; }
            QLineEdit{ background:#181825; border:1px solid #45475a;
                border-radius:4px; color:#cdd6f4; padding:4px 6px; }
            QLineEdit:focus { border-color:#89b4fa; }
            QMenu { background:#313244; color:#cdd6f4; border:1px solid #45475a; }
            QMenu::item:selected { background:#45475a; }
        """)

    # ── File operations ───────────────────────

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Bookmarks", "",
            "HTML Bookmark Files (*.html *.htm);;JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            if path.lower().endswith('.json'):
                with open(path, 'r', encoding='utf-8') as f:
                    self.bookmarks = json.load(f)
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    parser = BookmarkParser()
                    parser.feed(f.read())
                    self.bookmarks = parser.bookmarks
            if not self.bookmarks:
                QMessageBox.warning(self, "Empty File",
                    "No bookmarks found. Make sure this is a Chrome/Edge HTML export.")
                return
            self.current_file = path
            self._enable_buttons(True)
            self._refresh_tree()
            folders = len({bm['folder'] for bm in self.bookmarks})
            self._status(f"Loaded {len(self.bookmarks)} bookmarks in {folders} folders  ·  {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not read file:\n{e}")

    def save_file(self):
        if not self.current_file:
            self.save_file_as()
            return
        self._write_file(self.current_file)

    def save_file_as(self):
        default = self.current_file or "bookmarks_edited.html"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Bookmarks As", default,
            "HTML Bookmark Files (*.html);;JSON Files (*.json)"
        )
        if path:
            self._write_file(path)
            self.current_file = path

    def _write_file(self, path: str):
        try:
            if path.lower().endswith('.json'):
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.bookmarks, f, indent=2, ensure_ascii=False)
            else:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self._generate_html())
            self._status(f"Saved \u2192 {path}")
            QMessageBox.information(self, "Saved", f"Bookmarks saved to:\n{path}")
        except PermissionError:
            # Common on corporate Windows where the source file location is protected.
            # Offer to save to Desktop instead.
            desktop = Path.home() / 'Desktop' / 'bookmarks_edited.html'
            QMessageBox.warning(
                self, "Permission Denied",
                f"Cannot write to:\n{path}\n\n"
                "The location may be read-only or protected by your IT policy.\n"
                "Please choose a different save location (e.g. Desktop or Documents)."
            )
            new_path, _ = QFileDialog.getSaveFileName(
                self, "Save Bookmarks As", str(desktop),
                "HTML Bookmark Files (*.html);;JSON Files (*.json)"
            )
            if new_path:
                self.current_file = new_path
                self._write_file(new_path)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file:\n{e}")

    def _generate_html(self) -> str:
        folders: Dict[str, List[Dict]] = {}
        for bm in self.bookmarks:
            folders.setdefault(bm.get('folder', 'Unsorted'), []).append(bm)
        lines = [
            '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            '<TITLE>Bookmarks</TITLE>', '<H1>Bookmarks</H1>', '<DL><p>',
        ]
        for folder, bms in folders.items():
            ef = folder.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            lines += [f'    <DT><H3>{ef}</H3>', '    <DL><p>']
            for bm in bms:
                t = bm['title'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                u = bm['url'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                lines.append(f'        <DT><A HREF="{u}">{t}</A>')
            lines.append('    </DL><p>')
        lines.append('</DL><p>')
        return '\n'.join(lines) + '\n'

    # ── Tree ─────────────────────────────────

    def _refresh_tree(self):
        self._populating = True
        self.tree.clear()
        folders: Dict[str, List[Dict]] = {}
        for bm in self.bookmarks:
            folders.setdefault(bm.get('folder', 'Unsorted'), []).append(bm)
        for folder, bms in folders.items():
            fi = QTreeWidgetItem(self.tree)
            fi.setText(0, f"📁  {folder}  ({len(bms)})")
            fi.setData(0, Qt.ItemDataRole.UserRole, ('folder', folder))
            fi.setExpanded(True)
            for bm in bms:
                bi = QTreeWidgetItem(fi)
                bi.setText(0, f"🔗  {bm['title'] or bm['url']}")
                bi.setData(0, Qt.ItemDataRole.UserRole, ('bookmark', bm))
        self._populating = False

    def _on_rows_moved(self, parent, first, last):
        if self._populating:
            return
        QTimer.singleShot(0, self._rebuild_from_tree)

    def _rebuild_from_tree(self):
        new_bms: List[Dict] = []
        for i in range(self.tree.topLevelItemCount()):
            fi = self.tree.topLevelItem(i)
            fd = fi.data(0, Qt.ItemDataRole.UserRole)
            if not fd or fd[0] != 'folder':
                continue
            folder_name = fd[1]
            for j in range(fi.childCount()):
                child = fi.child(j)
                cd = child.data(0, Qt.ItemDataRole.UserRole)
                if cd and cd[0] == 'bookmark':
                    bm = dict(cd[1])
                    bm['folder'] = folder_name
                    child.setData(0, Qt.ItemDataRole.UserRole, ('bookmark', bm))
                    new_bms.append(bm)
        if new_bms:
            self.bookmarks = new_bms
            for i in range(self.tree.topLevelItemCount()):
                fi = self.tree.topLevelItem(i)
                fd = fi.data(0, Qt.ItemDataRole.UserRole)
                if fd and fd[0] == 'folder':
                    fi.setText(0, f"📁  {fd[1]}  ({fi.childCount()})")
            self._status("Order updated — remember to save.")

    # ── Selection & detail ────────────────────

    def _on_selection(self):
        items = self.tree.selectedItems()
        if not items:
            self.detail_text.clear()
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if data and data[0] == 'bookmark':
            bm = data[1]
            self.detail_text.setHtml(
                f"<b style='color:#89b4fa'>Title</b><br>{bm['title']}<br><br>"
                f"<b style='color:#89b4fa'>URL</b><br>"
                f"<a style='color:#a6e3a1' href='{bm['url']}'>{bm['url']}</a><br><br>"
                f"<b style='color:#89b4fa'>Folder</b><br>{bm['folder']}"
            )
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.detail_text.clear()
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)

    # ── CRUD ─────────────────────────────────

    def edit_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not (data and data[0] == 'bookmark'):
            return
        bm = data[1]
        dlg = EditBookmarkDialog(self, bm)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new = dlg.get_data()
            for i, b in enumerate(self.bookmarks):
                if b is bm or (b['url'] == bm['url'] and b['title'] == bm['title']):
                    self.bookmarks[i] = new
                    break
            self._refresh_tree()
            self._status("Bookmark updated — remember to save.")

    def delete_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not (data and data[0] == 'bookmark'):
            return
        bm = data[1]
        if QMessageBox.question(self, "Delete", f"Delete:\n{bm['title']}?") == QMessageBox.StandardButton.Yes:
            self.bookmarks = [b for b in self.bookmarks
                              if not (b['url'] == bm['url'] and b['title'] == bm['title'])]
            self._refresh_tree()
            self._status("Bookmark deleted — remember to save.")

    def add_bookmark(self):
        dlg = EditBookmarkDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.bookmarks.append(dlg.get_data())
            self._refresh_tree()
            self._status("Bookmark added — remember to save.")

    def remove_duplicates(self):
        seen: Set[str] = set()
        unique = []
        for bm in self.bookmarks:
            if bm['url'] not in seen:
                seen.add(bm['url'])
                unique.append(bm)
        removed = len(self.bookmarks) - len(unique)
        self.bookmarks = unique
        self._refresh_tree()
        self._status(f"Removed {removed} duplicate(s) — remember to save.")
        QMessageBox.information(self, "Duplicates Removed", f"Removed {removed} duplicate bookmark(s).")

    def sort_bookmarks(self):
        self.bookmarks.sort(key=lambda x: x['title'].lower())
        self._refresh_tree()
        self._status("Sorted by title — remember to save.")

    # ── Context menu ─────────────────────────

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        if data and data[0] == 'bookmark':
            menu.addAction("✏️  Edit",   self.edit_selected)
            menu.addAction("🗑️  Delete", self.delete_selected)
            menu.addSeparator()
            menu.addAction("📋  Copy URL", lambda: QApplication.clipboard().setText(data[1]['url']))
        elif data and data[0] == 'folder':
            menu.addAction("🔤  Sort this folder A→Z", lambda: self._sort_folder(data[1]))
        menu.exec(self.tree.mapToGlobal(pos))

    def _sort_folder(self, folder_name: str):
        order = list(dict.fromkeys(bm['folder'] for bm in self.bookmarks))
        grouped = {f: [b for b in self.bookmarks if b['folder'] == f] for f in order}
        grouped[folder_name].sort(key=lambda x: x['title'].lower())
        self.bookmarks = [bm for f in order for bm in grouped[f]]
        self._refresh_tree()
        self._status(f"Folder '{folder_name}' sorted — remember to save.")

    # ── Helpers ──────────────────────────────

    def _enable_buttons(self, on: bool):
        for btn in [self.save_btn, self.saveas_btn, self.dedupe_btn, self.sort_btn, self.add_btn]:
            btn.setEnabled(on)

    def _status(self, msg: str):
        self.status_lbl.setText(msg)


def main():
    app = QApplication(sys.argv)
    manager = BookmarkManager()
    manager.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
