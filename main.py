import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any
import threading
import time

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QTextEdit, 
                            QFileDialog, QProgressBar, QListWidget, QSplitter,
                            QGroupBox, QCheckBox, QComboBox, QMessageBox,
                            QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont, QPainter, QPen, QColor
from PIL import Image, ExifTags
import piexif
import easyocr

class OCRWorker(QThread):
    """Worker thread for OCR processing"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, image_paths: List[str], language: str = 'en'):
        super().__init__()
        self.image_paths = image_paths
        self.language = language
        self.results = []
        
    def run(self):
        try:
            # Initialize EasyOCR
            ocr = easyocr.Reader([self.language])
            
            total_files = len(self.image_paths)
            
            for i, image_path in enumerate(self.image_paths):
                try:
                    # Process image
                    result = ocr.readtext(image_path)
                    
                    # Format results
                    formatted_result = {
                        'image_path': image_path,
                        'text_data': [],
                        'processed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    if result:
                        for detection in result:
                            box = detection[0]  # Coordinates (4 points)
                            text = detection[1]  # Text
                            confidence = detection[2]  # Confidence
                            
                            formatted_result['text_data'].append({
                                'text': text,
                                'confidence': confidence,
                                'coordinates': {
                                    'top_left': [int(box[0][0]), int(box[0][1])],
                                    'top_right': [int(box[1][0]), int(box[1][1])],
                                    'bottom_right': [int(box[2][0]), int(box[2][1])],
                                    'bottom_left': [int(box[3][0]), int(box[3][1])]
                                }
                            })
                    
                    self.results.append(formatted_result)
                    
                    # Update progress
                    progress_percent = int((i + 1) / total_files * 100)
                    self.progress.emit(progress_percent)
                    
                except Exception as e:
                    self.error.emit(f"Error processing {image_path}: {str(e)}")
                    continue
            
            self.finished.emit(self.results)
            
        except Exception as e:
            self.error.emit(f"OCR initialization failed: {str(e)}")

class ImageDisplayWidget(QLabel):
    """Custom widget to display image with text boxes"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        self.setStyleSheet("border: 1px solid gray;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("No image selected")
        self.original_pixmap = None
        self.text_boxes = []
        
    def set_image(self, image_path: str):
        """Load and display image"""
        try:
            self.original_pixmap = QPixmap(image_path)
            self.display_image()
        except Exception as e:
            self.setText(f"Error loading image: {str(e)}")
            
    def set_text_boxes(self, text_data: List[Dict]):
        """Set text boxes to overlay on image"""
        self.text_boxes = text_data
        self.display_image()
        
    def display_image(self):
        """Display image with text boxes"""
        if not self.original_pixmap:
            return
            
        # Scale pixmap to fit widget
        scaled_pixmap = self.original_pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Draw text boxes if available
        if self.text_boxes:
            painter = QPainter(scaled_pixmap)
            pen = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen)
            
            # Calculate scaling factors
            scale_x = scaled_pixmap.width() / self.original_pixmap.width()
            scale_y = scaled_pixmap.height() / self.original_pixmap.height()
            
            for text_item in self.text_boxes:
                coords = text_item['coordinates']
                # Scale coordinates
                points = [
                    (int(coords['top_left'][0] * scale_x), 
                     int(coords['top_left'][1] * scale_y)),
                    (int(coords['top_right'][0] * scale_x), 
                     int(coords['top_right'][1] * scale_y)),
                    (int(coords['bottom_right'][0] * scale_x), 
                     int(coords['bottom_right'][1] * scale_y)),
                    (int(coords['bottom_left'][0] * scale_x), 
                     int(coords['bottom_left'][1] * scale_y))
                ]
                
                # Draw rectangle
                for i in range(4):
                    painter.drawLine(points[i][0], points[i][1], 
                                   points[(i+1)%4][0], points[(i+1)%4][1])
            
            painter.end()
        
        self.setPixmap(scaled_pixmap)

class OCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_results = []
        self.selected_files = []
        self.ocr_worker = None
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("OCR Text Coordinate Extractor")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel - Controls
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, 1)
        
        # Right panel - Image display and results
        right_panel = self.create_display_panel()
        main_layout.addWidget(right_panel, 2)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def create_control_panel(self):
        """Create the left control panel"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMaximumWidth(350)
        
        layout = QVBoxLayout(panel)
        
        # File selection
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)
        
        self.select_files_btn = QPushButton("Select Images")
        self.select_files_btn.clicked.connect(self.select_files)
        file_layout.addWidget(self.select_files_btn)
        
        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self.on_file_selected)
        file_layout.addWidget(self.file_list)
        
        layout.addWidget(file_group)
        
        # OCR Settings
        settings_group = QGroupBox("OCR Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['en', 'ch', 'fr', 'german', 'korean', 'japan'])
        lang_layout.addWidget(self.lang_combo)
        settings_layout.addLayout(lang_layout)
        
        layout.addWidget(settings_group)
        
        # Processing
        process_group = QGroupBox("Processing")
        process_layout = QVBoxLayout(process_group)
        
        self.process_btn = QPushButton("Process Images")
        self.process_btn.clicked.connect(self.process_images)
        process_layout.addWidget(self.process_btn)
        
        self.progress_bar = QProgressBar()
        process_layout.addWidget(self.progress_bar)
        
        layout.addWidget(process_group)
        
        # Export options
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout(export_group)
        
        self.embed_metadata_cb = QCheckBox("Embed in Image Metadata")
        self.embed_metadata_cb.setChecked(True)
        export_layout.addWidget(self.embed_metadata_cb)
        
        self.export_json_cb = QCheckBox("Export to JSON")
        self.export_json_cb.setChecked(True)
        export_layout.addWidget(self.export_json_cb)
        
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        export_layout.addWidget(self.export_btn)
        
        layout.addWidget(export_group)
        
        # Add stretch to push everything to top
        layout.addStretch()
        
        return panel
        
    def create_display_panel(self):
        """Create the right display panel"""
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Image display
        image_group = QGroupBox("Image Preview")
        image_layout = QVBoxLayout(image_group)
        
        self.image_display = ImageDisplayWidget()
        image_layout.addWidget(self.image_display)
        
        splitter.addWidget(image_group)
        
        # Results display
        results_group = QGroupBox("Extracted Text")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(QFont("Courier", 10))
        results_layout.addWidget(self.results_text)
        
        splitter.addWidget(results_group)
        
        # Set initial sizes
        splitter.setSizes([400, 300])
        
        return splitter
        
    def select_files(self):
        """Select image files"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"
        )
        
        if file_paths:
            self.selected_files = file_paths
            self.file_list.clear()
            
            for file_path in file_paths:
                self.file_list.addItem(os.path.basename(file_path))
            
            self.statusBar().showMessage(f"Selected {len(file_paths)} files")
            
    def on_file_selected(self, row):
        """Handle file selection in the list"""
        if row >= 0 and row < len(self.selected_files):
            file_path = self.selected_files[row]
            self.image_display.set_image(file_path)
            
            # Show results if available
            if self.current_results:
                for result in self.current_results:
                    if result['image_path'] == file_path:
                        self.display_text_results(result)
                        self.image_display.set_text_boxes(result['text_data'])
                        break
            
    def process_images(self):
        """Process selected images with OCR"""
        if not self.selected_files:
            QMessageBox.warning(self, "Warning", "Please select images first!")
            return
            
        # Disable UI during processing
        self.process_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Processing images...")
        
        # Start OCR worker
        self.ocr_worker = OCRWorker(self.selected_files, self.lang_combo.currentText())
        self.ocr_worker.progress.connect(self.progress_bar.setValue)
        self.ocr_worker.finished.connect(self.on_processing_finished)
        self.ocr_worker.error.connect(self.on_processing_error)
        self.ocr_worker.start()
        
    def on_processing_finished(self, results):
        """Handle OCR processing completion"""
        self.current_results = results
        self.process_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.statusBar().showMessage(f"Processing complete! Found text in {len(results)} images")
        
        # Display results for currently selected file
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            self.on_file_selected(current_row)
            
    def on_processing_error(self, error_msg):
        """Handle OCR processing errors"""
        QMessageBox.critical(self, "Error", error_msg)
        self.process_btn.setEnabled(True)
        self.statusBar().showMessage("Processing failed")
        
    def display_text_results(self, result):
        """Display text results in the text widget"""
        text_output = f"Image: {os.path.basename(result['image_path'])}\n"
        text_output += f"Processed: {result['processed_at']}\n"
        text_output += f"Found {len(result['text_data'])} text regions\n\n"
        
        for i, text_item in enumerate(result['text_data'], 1):
            text_output += f"Text {i}: {text_item['text']}\n"
            text_output += f"Confidence: {text_item['confidence']:.2f}\n"
            text_output += f"Coordinates: {text_item['coordinates']}\n\n"
            
        self.results_text.setPlainText(text_output)
        
    def export_results(self):
        """Export results to files"""
        if not self.current_results:
            QMessageBox.warning(self, "Warning", "No results to export!")
            return
            
        try:
            # Export to JSON
            if self.export_json_cb.isChecked():
                json_path, _ = QFileDialog.getSaveFileName(
                    self, "Save JSON Results", "ocr_results.json", 
                    "JSON Files (*.json)"
                )
                
                if json_path:
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(self.current_results, f, indent=2, ensure_ascii=False)
                    
            # Embed in image metadata
            if self.embed_metadata_cb.isChecked():
                self.embed_metadata_in_images()
                
            QMessageBox.information(self, "Success", "Results exported successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
            
    def embed_metadata_in_images(self):
        """Embed OCR results in image metadata"""
        for result in self.current_results:
            try:
                image_path = result['image_path']
                
                for item in result['text_data']:
                    print(item['text'])


                # Create metadata string
                metadata_str = json.dumps({
                    'ocr_data': result['text_data'],
                    'processed_at': result['processed_at']
                }, ensure_ascii=False)
                
                # Load existing EXIF data
                try:
                    exif_dict = piexif.load(image_path)
                except:
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
                
                # Add OCR data to user comment
                exif_dict['Exif'][piexif.ExifIFD.UserComment] = metadata_str.encode('utf-8')
                
                # Save back to image
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, image_path)
                
            except Exception as e:
                print(f"Failed to embed metadata in {image_path}: {str(e)}")

def main():
    print('app')
    app = QApplication(sys.argv)
    
    print('style')
    # Set application style
    app.setStyle('Fusion')
    
    print('window')
    window = OCRApp()
    print('show')
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()