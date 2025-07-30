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
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PIL import Image
import piexif

# Import our custom modules
from gps_extractor import GPSExtractor
from ocr_worker import OCRWorker, OCRModelCache
from image_display import ImageDisplayWidget

class OCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_results = []
        self.selected_files = []
        self.ocr_worker = None
        self.gps_extractor = GPSExtractor()

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("LIGER - Layer-based Image GPS Extraction and Recovery")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon('app_logo.png'))

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
        self.statusBar().showMessage("Ready - Enhanced GPS extraction with reduced false positives")
        copyright_label = QLabel("© ICT4RM-CarSU & Martin, Amora")
        self.statusBar().addPermanentWidget(copyright_label, stretch=0)

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
        
        # Advanced OCR options
        self.multi_pass_cb = QCheckBox("Multi-pass OCR (Higher Accuracy)")
        self.multi_pass_cb.setChecked(False)
        settings_layout.addWidget(self.multi_pass_cb)
        
        self.roi_detection_cb = QCheckBox("Smart Region Detection")
        self.roi_detection_cb.setChecked(False)
        settings_layout.addWidget(self.roi_detection_cb)
        
        self.gpu_acceleration_cb = QCheckBox("GPU Acceleration (if available)")
        self.gpu_acceleration_cb.setChecked(False)
        settings_layout.addWidget(self.gpu_acceleration_cb)

        layout.addWidget(settings_group)

        # Processing
        process_group = QGroupBox("Processing")
        process_layout = QVBoxLayout(process_group)

        self.process_btn = QPushButton("Extract GPS from Images")
        self.process_btn.clicked.connect(self.process_images)
        process_layout.addWidget(self.process_btn)

        self.progress_bar = QProgressBar()
        process_layout.addWidget(self.progress_bar)

        layout.addWidget(process_group)

        # Export options
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout(export_group)

        self.embed_gps_cb = QCheckBox("Embed GPS in Image Metadata")
        self.embed_gps_cb.setChecked(True)
        export_layout.addWidget(self.embed_gps_cb)

        self.export_json_cb = QCheckBox("Export to JSON")
        self.export_json_cb.setChecked(True)
        export_layout.addWidget(self.export_json_cb)

        self.export_btn = QPushButton("Export JSON & Image")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        export_layout.addWidget(self.export_btn)

        # Save Images with GPS
        self.save_images_btn = QPushButton("Save Images with GPS Data Only")
        self.save_images_btn.clicked.connect(self.save_images_with_gps)
        self.save_images_btn.setEnabled(False)
        export_layout.addWidget(self.save_images_btn)

        layout.addWidget(export_group)

        # Model Cache Management
        cache_group = QGroupBox("Model Cache")
        cache_layout = QVBoxLayout(cache_group)
        
        self.cache_info_label = QLabel("No models cached")
        cache_layout.addWidget(self.cache_info_label)
        
        self.clear_cache_btn = QPushButton("Clear Model Cache")
        self.clear_cache_btn.clicked.connect(self.clear_model_cache)
        cache_layout.addWidget(self.clear_cache_btn)
        
        layout.addWidget(cache_group)

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
        results_group = QGroupBox("Extracted Text and GPS")
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
        self.statusBar().showMessage("Processing images and extracting GPS with enhanced accuracy...")

        # Start OCR worker with advanced settings
        self.ocr_worker = OCRWorker(
            self.selected_files, 
            self.lang_combo.currentText(),
            use_gpu=self.gpu_acceleration_cb.isChecked(),
            multi_pass=self.multi_pass_cb.isChecked(),
            roi_detection=self.roi_detection_cb.isChecked()
        )
        self.ocr_worker.progress.connect(self.progress_bar.setValue)
        self.ocr_worker.finished.connect(self.on_processing_finished)
        self.ocr_worker.error.connect(self.on_processing_error)
        self.ocr_worker.model_loading.connect(self.on_model_loading)
        self.ocr_worker.start()

    def on_processing_finished(self, results):
        """Handle OCR processing completion"""
        self.current_results = results
        self.process_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.save_images_btn.setEnabled(True)

        # Update cache info
        self.update_cache_info()

        # Count how many images have GPS data with confidence levels
        gps_results = [result for result in results if result.get('gps_coordinates')]
        gps_count = sum(1 for result in results if result.get('gps_coordinates'))

        self.statusBar().showMessage(f"Processing complete! Found GPS in {gps_count}/{len(results)} images")

        # Display results for currently selected file
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            self.on_file_selected(current_row)

    def on_processing_error(self, error_msg):
        """Handle OCR processing errors"""
        QMessageBox.critical(self, "Error", error_msg)
        self.process_btn.setEnabled(True)
        self.statusBar().showMessage("Processing failed")
    
    def on_model_loading(self, message):
        """Handle model loading status updates"""
        self.statusBar().showMessage(message)

    def display_text_results(self, result):
        """Display text results and GPS information in the text widget"""
        text_output = f"Image: {os.path.basename(result['image_path'])}\n"
        text_output += f"Processed: {result['processed_at']}\n"
        text_output += f"Found {len(result['text_data'])} text regions\n\n"

        # Display GPS information first if found
        if result.get('gps_coordinates'):
            gps = result['gps_coordinates']
            text_output += "🌍 GPS COORDINATES FOUND:\n"
            text_output += f"  Latitude: {gps['latitude']:.6f}\n"
            text_output += f"  Longitude: {gps['longitude']:.6f}\n"
            text_output += f"  Source Text: {gps['source_text']}\n\n"
        else:
            text_output += "❌ No GPS coordinates detected in text / Invalid GPS format\n\n"

        text_output += "📝 ALL DETECTED TEXT:\n"
        text_output += "=" * 40 + "\n"

        for i, text_item in enumerate(result['text_data'], 1):
            text_output += f"\nText {i}: {text_item['text']}\n"
            text_output += f"Confidence: {text_item['confidence']:.2f}\n"
            text_output += f"Coordinates: {text_item['coordinates']}\n"

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
                    self, "Save JSON Results", "gps_extraction_results.json", 
                    "JSON Files (*.json)"
                )

                if json_path:
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(self.current_results, f, indent=2, ensure_ascii=False)

            # Embed GPS in original image files
            if self.embed_gps_cb.isChecked():
                success_count, error_count = self.embed_gps_in_images()

                if success_count > 0:
                    QMessageBox.information(
                        self, "GPS Data Embedded", 
                        f"Successfully embedded GPS data in {success_count} images!"
                        + (f"\n{error_count} files had errors." if error_count > 0 else "")
                    )
                else:
                    QMessageBox.warning(self, "Warning", "No GPS data was embedded!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")

    def embed_gps_in_images(self):
        """Embed GPS coordinates in image metadata"""
        success_count = 0
        error_count = 0

        for result in self.current_results:
            try:
                gps_coords = result.get('gps_coordinates')
                if not gps_coords:
                    continue  # Skip images without GPS

                image_path = result['image_path']

                # Handle different image formats
                try:
                    # Try to load existing EXIF data
                    exif_dict = piexif.load(image_path)
                except:
                    # Create new EXIF structure if none exists
                    exif_dict = {
                        "0th": {},
                        "Exif": {},
                        "GPS": {},
                        "1st": {},
                        "thumbnail": None
                    }

                # Convert GPS coordinates to EXIF format
                gps_data = self.gps_extractor.decimal_to_exif_gps(
                    gps_coords['latitude'], 
                    gps_coords['longitude']
                )

                # Update GPS data in EXIF
                exif_dict['GPS'].update(gps_data)

                # Add processing info to main EXIF
                exif_dict['0th'][piexif.ImageIFD.ImageDescription] = f"GPS extracted: {gps_coords['latitude']:.6f}, {gps_coords['longitude']:.6f}"
                exif_dict['0th'][piexif.ImageIFD.Software] = "LIGER"

                # Save GPS data back to image
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, image_path)

                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"Failed to embed GPS in {image_path}: {str(e)}")

        return success_count, error_count

    def save_images_with_gps(self):
        """Save copies of images with embedded GPS metadata"""
        if not self.current_results:
            QMessageBox.warning(self, "Warning", "No results to save!")
            return

        # Select output directory
        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Directory for Images with GPS Data"
        )

        if not output_dir:
            return

        try:
            success_count = 0
            error_count = 0

            for result in self.current_results:
                try:
                    gps_coords = result.get('gps_coordinates')
                    if not gps_coords:
                        continue  # Skip images without GPS

                    original_path = result['image_path']
                    filename = os.path.basename(original_path)
                    name, ext = os.path.splitext(filename)

                    # Create new filename with GPS suffix
                    new_filename = f"{name}_with_gps{ext}"
                    new_path = os.path.join(output_dir, new_filename)

                    # Copy original image
                    img = Image.open(original_path)

                    # Prepare EXIF data
                    exif_dict = {
                        "0th": {},
                        "Exif": {},
                        "GPS": {},
                        "1st": {},
                        "thumbnail": None
                    }

                    # Convert GPS coordinates to EXIF format
                    gps_data = self.gps_extractor.decimal_to_exif_gps(
                        gps_coords['latitude'], 
                        gps_coords['longitude']
                    )

                    # Add GPS data
                    exif_dict['GPS'].update(gps_data)

                    # Add comprehensive metadata
                    exif_dict['0th'][piexif.ImageIFD.ImageDescription] = f"GPS: {gps_coords['latitude']:.6f}, {gps_coords['longitude']:.6f}"
                    exif_dict['0th'][piexif.ImageIFD.Software] = "LIGER"
                    exif_dict['0th'][piexif.ImageIFD.XPKeywords] = f"GPS {gps_coords['source_text']}".encode('utf-16le')

                    # Add processing info to EXIF
                    processing_info = {
                        'extracted_gps': gps_coords,
                        'processing_info': {
                            'processed_at': result['processed_at'],
                            'total_text_regions': len(result['text_data']),
                            'ocr_engine': 'EasyOCR',
                            'original_filename': filename
                        }
                    }

                    metadata_str = json.dumps(processing_info, ensure_ascii=False)
                    exif_dict['Exif'][piexif.ExifIFD.UserComment] = metadata_str.encode('utf-8')

                    # Save image with GPS metadata
                    exif_bytes = piexif.dump(exif_dict)

                    # Handle different image formats
                    if ext.lower() in ['.jpg', '.jpeg']:
                        img.save(new_path, "JPEG", exif=exif_bytes, quality=95)
                    elif ext.lower() in ['.tiff', '.tif']:
                        img.save(new_path, "TIFF", exif=exif_bytes)
                    else:
                        # For formats that don't support EXIF, save as JPEG
                        jpeg_path = os.path.join(output_dir, f"{name}_with_gps.jpg")
                        img.convert('RGB').save(jpeg_path, "JPEG", exif=exif_bytes, quality=95)
                        new_path = jpeg_path

                    success_count += 1

                except Exception as e:
                    error_count += 1
                    print(f"Failed to save {original_path}: {str(e)}")

            # Show completion message
            if success_count > 0:
                message = f"Successfully saved {success_count} images with GPS data"
                if error_count > 0:
                    message += f"\n{error_count} files had errors"
                message += f"\n\nFiles saved to: {output_dir}"
                QMessageBox.information(self, "Save Complete", message)
            else:
                QMessageBox.warning(self, "No GPS Data", "No images contained GPS coordinates to embed!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save images: {str(e)}")

    def clear_model_cache(self):
        """Clear the OCR model cache"""
        try:
            cache = OCRModelCache()
            cache.clear_cache()
            self.cache_info_label.setText("Model cache cleared")
            self.statusBar().showMessage("OCR model cache cleared")
            QMessageBox.information(self, "Cache Cleared", "OCR model cache has been cleared successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear cache: {str(e)}")
    
    def update_cache_info(self):
        """Update cache information display"""
        try:
            cache = OCRModelCache()
            cached_languages = list(cache._models.keys())
            if cached_languages:
                self.cache_info_label.setText(f"Cached: {', '.join(cached_languages)}")
            else:
                self.cache_info_label.setText("No models cached")
        except:
            self.cache_info_label.setText("Cache info unavailable")

    def view_gps_info(self):
        """Show information about GPS extraction and metadata embedding"""
        if not self.current_results:
            return

        gps_count = sum(1 for result in self.current_results if result.get('gps_coordinates'))

        info_text = "GPS EXTRACTION INFORMATION:\n\n"
        info_text += f"Images processed: {len(self.current_results)}\n"
        info_text += f"Images with GPS found: {gps_count}\n\n"
        info_text += "SUPPORTED GPS FORMATS:\n\n"
        info_text += "• Decimal Degrees: 40.7128, -74.0060\n"
        info_text += "• Degrees Minutes Seconds: 40°42'46\"N, 74°00'21\"W\n"
        info_text += "• Degrees Decimal Minutes: 40°42.767'N, 74°00.350'W\n"
        info_text += "• With Direction Indicators: N40.7128, W74.0060\n"
        info_text += "• Labeled Coordinates: LAT: 40.7128, LON: -74.0060\n"
        info_text += "• GPS Tags: GPS: (40.7128, -74.0060)\n\n"
        info_text += "METADATA EMBEDDED:\n\n"
        info_text += "The tool embeds GPS coordinates in standard EXIF GPS fields:\n"
        info_text += "• GPSLatitude & GPSLatitudeRef\n"
        info_text += "• GPSLongitude & GPSLongitudeRef\n"
        info_text += "• GPSMapDatum (WGS-84)\n\n"
        info_text += "Additional metadata includes:\n"
        info_text += "• Processing timestamp\n"
        info_text += "• Source text that contained GPS\n"
        info_text += "• OCR processing information\n\n"
        info_text += "GPS metadata can be read by most photo viewers,\n"
        info_text += "mapping applications, and photo management tools."

        QMessageBox.information(self, "GPS Extraction Information", info_text)

def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    window = OCRApp()
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()