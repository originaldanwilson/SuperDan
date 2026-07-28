#!/usr/bin/env python3
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from html.parser import HTMLParser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QDialog, QLineEdit, QDialogButtonBox, QInputDialog, QMenu, QSplitter,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QMimeData, QUrl, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor, QDrag


class BookmarkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.bookmarks = []
        self.folder_stack = []
        self.current_bookmark = None
        self.in_anchor = False
        self.current_data = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == 'a':
            self.in_anchor = True
            self.current_bookmark = {
                'title': '',
                'url': attrs_dict.get('href', ''),
                'folder': '/'.join(self.folder_stack) if self.folder_stack else 'Unsorted'
            }
        elif tag == 'h3':
            self.current_data = ""

    def handle_data(self, data):
        if self.in_anchor or (hasattr(self, 'h3_open') and self.h3_open):
            self.current_data += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.in_anchor:
            self.in_anchor = False
            if self.current_bookmark and self.current_bookmark['url']:
                self.current_bookmark['title'] = self.current_data.strip()
                self.bookmarks.append(self.current_bookmark)
            self.current_data = ""
        elif tag == 'h3':
            folder_name = self.current_data.strip()
            if folder_name:
                self.folder_stack.append(folder_name)
            self.current_data = ""
        elif tag == 'dl':
            if self.folder_stack:
                self.folder_stack.pop()


class EditBookmarkDialog(QDialog):
    def __init__(self, parent=None, bookmark=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Bookmark")
        self.setGeometry(100, 100, 400, 200)
        
        layout = QVBoxLayout()
        
        # Title
        layout.addWidget(QLabel("Title:"))
        self.title_input = QLineEdit()
        if bookmark:
            self.title_input.setText(bookmark.get('title', ''))
        layout.addWidget(self.title_input)
        
        # URL
        layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        if bookmark:
            self.url_input.setText(bookmark.get('url', ''))
        layout.addWidget(self.url_input)
        
        # Folder
        layout.addWidget(QLabel("Folder:"))
        self.folder_input = QLineEdit()
        if bookmark:
            self.folder_input.setText(bookmark.get('folder', 'Unsorted'))
        layout.addWidget(self.folder_input)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_data(self):
        return {
            'title': self.title_input.text(),
            'url': self.url_input.text(),
            'folder': self.folder_input.text() or 'Unsorted'
        }


class BookmarkManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bookmark Manager")
        self.setGeometry(100, 100, 1000, 600)
        
        self.bookmarks: List[Dict] = []
        self.original_bookmarks: List[Dict] = []
        self._populating = False
        
        # Setup UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        
        self.load_btn = QPushButton("Load Bookmarks")
        self.load_btn.clicked.connect(self.load_file)
        toolbar_layout.addWidget(self.load_btn)
        
        self.save_btn = QPushButton("Save Bookmarks")
        self.save_btn.clicked.connect(self.save_file)
        self.save_btn.setEnabled(False)
        toolbar_layout.addWidget(self.save_btn)
        
        self.dedupe_btn = QPushButton("Remove Duplicates")
        self.dedupe_btn.clicked.connect(self.remove_duplicates)
        self.dedupe_btn.setEnabled(False)
        toolbar_layout.addWidget(self.dedupe_btn)
        
        self.sort_btn = QPushButton("Sort by Title")
        self.sort_btn.clicked.connect(self.sort_bookmarks)
        self.sort_btn.setEnabled(False)
        toolbar_layout.addWidget(self.sort_btn)
        
        self.add_btn = QPushButton("Add Bookmark")
        self.add_btn.clicked.connect(self.add_bookmark)
        self.add_btn.setEnabled(False)
        toolbar_layout.addWidget(self.add_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Splitter for tree and details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Tree widget for folders and bookmarks
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Bookmarks")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        # Enable drag-and-drop to move bookmarks between folders
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.model().rowsInserted.connect(self.on_rows_moved)
        splitter.addWidget(self.tree)
        
        # Details panel
        details_layout = QVBoxLayout()
        self.details_label = QLabel("Select a bookmark to view details")
        details_layout.addWidget(self.details_label)
        
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self.edit_selected)
        self.edit_btn.setEnabled(False)
        details_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setEnabled(False)
        details_layout.addWidget(self.delete_btn)
        
        details_layout.addStretch()
        
        details_widget = QWidget()
        details_widget.setLayout(details_layout)
        splitter.addWidget(details_widget)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        # Status bar
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        central_widget.setLayout(layout)
    
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Bookmarks File", "", "HTML Files (*.html);;JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.bookmarks = json.load(f)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    parser = BookmarkParser()
                    parser.feed(f.read())
                    self.bookmarks = parser.bookmarks
            
            # Add position tracking if not present
            for i, bm in enumerate(self.bookmarks):
                if 'position' not in bm:
                    bm['position'] = i
            
            self.original_bookmarks = [bm.copy() for bm in self.bookmarks]
            self.current_file = file_path
            
            self.save_btn.setEnabled(True)
            self.dedupe_btn.setEnabled(True)
            self.sort_btn.setEnabled(True)
            self.add_btn.setEnabled(True)
            
            self.refresh_tree()
            self.status_label.setText(f"Loaded {len(self.bookmarks)} bookmarks from {Path(file_path).name}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
    
    def refresh_tree(self):
        self._populating = True
        self.tree.clear()
        
        # Group bookmarks by folder
        folders: Dict[str, List[Dict]] = {}
        for bm in self.bookmarks:
            folder = bm.get('folder', 'Unsorted')
            if folder not in folders:
                folders[folder] = []
            folders[folder].append(bm)
        
        # Build tree, preserving folder order (first appearance) and the
        # manual order of bookmarks within each folder.
        for folder in folders.keys():
            folder_item = QTreeWidgetItem(self.tree)
            folder_item.setText(0, f"📁 {folder}")
            folder_item.setData(0, Qt.ItemDataRole.UserRole, ('folder', folder))
            
            for bm in folders[folder]:
                bm_item = QTreeWidgetItem(folder_item)
                bm_item.setText(0, f"🔗 {bm['title']}")
                bm_item.setData(0, Qt.ItemDataRole.UserRole, ('bookmark', bm))
                folder_item.addChild(bm_item)
            
            self.tree.addTopLevelItem(folder_item)
        
        self._populating = False
    
    def on_rows_moved(self, parent, first, last):
        # Called after a drag-and-drop move; rebuild bookmark data from the tree
        # so each bookmark's folder and order reflect the new tree layout.
        # Ignore signals fired while we programmatically populate the tree.
        if self._populating:
            return
        # Defer until after the internal move fully completes (insert + remove),
        # otherwise the moved item briefly exists twice and would be duplicated.
        QTimer.singleShot(0, self.rebuild_from_tree)
    
    def rebuild_from_tree(self):
        new_bookmarks: List[Dict] = []
        for i in range(self.tree.topLevelItemCount()):
            folder_item = self.tree.topLevelItem(i)
            folder_data = folder_item.data(0, Qt.ItemDataRole.UserRole)
            if not folder_data or folder_data[0] != 'folder':
                continue
            folder_name = folder_data[1]
            for j in range(folder_item.childCount()):
                child = folder_item.child(j)
                child_data = child.data(0, Qt.ItemDataRole.UserRole)
                if child_data and child_data[0] == 'bookmark':
                    bm = dict(child_data[1])
                    bm['folder'] = folder_name
                    child.setData(0, Qt.ItemDataRole.UserRole, ('bookmark', bm))
                    new_bookmarks.append(bm)
        if new_bookmarks:
            self.bookmarks = new_bookmarks
            self.status_label.setText("Bookmark moved")
    
    def on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self.details_label.setText("Select a bookmark to view details")
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data[0] == 'bookmark':
            bm = data[1]
            details_text = f"Title: {bm['title']}\n\nURL: {bm['url']}\n\nFolder: {bm['folder']}"
            self.details_label.setText(details_text)
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.details_label.setText("Select a bookmark to view details")
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
    
    def edit_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data[0] == 'bookmark':
            bm = data[1]
            dialog = EditBookmarkDialog(self, bm)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_data = dialog.get_data()
                
                # Find and update the bookmark
                for i, b in enumerate(self.bookmarks):
                    if b['url'] == bm['url'] and b['title'] == bm['title']:
                        self.bookmarks[i] = new_data
                        break
                
                self.refresh_tree()
                self.status_label.setText("Bookmark updated")
    
    def delete_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data[0] == 'bookmark':
            bm = data[1]
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete bookmark: {bm['title']}?"
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.bookmarks = [b for b in self.bookmarks 
                                 if not (b['url'] == bm['url'] and b['title'] == bm['title'])]
                self.refresh_tree()
                self.status_label.setText("Bookmark deleted")
    
    def add_bookmark(self):
        dialog = EditBookmarkDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.bookmarks.append(dialog.get_data())
            self.refresh_tree()
            self.status_label.setText("Bookmark added")
    
    def remove_duplicates(self):
        original_count = len(self.bookmarks)
        seen: Set[str] = set()
        unique = []
        
        for bm in self.bookmarks:
            url = bm['url']
            if url not in seen:
                seen.add(url)
                unique.append(bm)
        
        self.bookmarks = unique
        removed = original_count - len(self.bookmarks)
        
        self.refresh_tree()
        self.status_label.setText(f"Removed {removed} duplicate bookmarks")
        QMessageBox.information(self, "Duplicates Removed", f"Removed {removed} duplicate bookmarks")
    
    def sort_bookmarks(self):
        self.bookmarks.sort(key=lambda x: x['title'].lower())
        self.refresh_tree()
        self.status_label.setText("Bookmarks sorted by title")
    
    def show_context_menu(self, position):
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data[0] == 'bookmark':
            menu.addAction("Edit", self.edit_selected)
            menu.addAction("Delete", self.delete_selected)
            menu.addSeparator()
            menu.addAction("Copy URL", lambda: self.copy_url(data[1]))
        
        menu.exec(self.tree.mapToGlobal(position))
    
    def copy_url(self, bm):
        clipboard = QApplication.clipboard()
        clipboard.setText(bm['url'])
        self.status_label.setText("URL copied to clipboard")
    
    def save_file(self):
        if not hasattr(self, 'current_file'):
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Bookmarks", "", "HTML Files (*.html);;JSON Files (*.json)"
            )
            if not file_path:
                return
        else:
            file_path = self.current_file
        
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.bookmarks, f, indent=2, ensure_ascii=False)
            else:
                html_content = self.generate_html()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
            
            self.status_label.setText(f"Saved to {Path(file_path).name}")
            QMessageBox.information(self, "Success", "Bookmarks saved successfully!")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
    
    def generate_html(self) -> str:
        html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
"""
        
        # Group by folder
        folders: Dict[str, List[Dict]] = {}
        for bm in self.bookmarks:
            folder = bm.get('folder', 'Unsorted')
            if folder not in folders:
                folders[folder] = []
            folders[folder].append(bm)
        
        for folder in folders.keys():
            html += f'    <DT><H3>{folder}</H3>\n    <DL><p>\n'
            
            for bm in folders[folder]:
                title = bm['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                url = bm['url'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html += f'        <DT><A HREF="{url}">{title}</A>\n'
            
            html += "    </DL><p>\n"
        
        html += """</DL><p>
</BODY></HTML>
"""
        return html


def main():
    app = QApplication(sys.argv)
    manager = BookmarkManager()
    manager.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
