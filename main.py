import sys
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
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

class GPSExtractor:
    """Enhanced GPS coordinate extractor with improved accuracy and reduced false positives"""
    
    def __init__(self):
        # More precise GPS coordinate patterns with validation
        self.gps_patterns = [
            # GPS with explicit labels - highest confidence
            {
                'pattern': r'(?:GPS|COORDINATES?)[:\s]*\(?([+-]?\d{1,2}\.?\d{0,8})[°\s]*,?\s*([+-]?\d{1,3}\.?\d{0,8})[°\s]*\)?',
                'priority': 10,
                'type': 'labeled'
            },
            {
                'pattern': r'(?:LAT|LATITUDE)[:\s]*([+-]?\d{1,2}\.?\d{0,8})[°\s]*([NS])?\s*,?\s*(?:LON|LONGITUDE)[:\s]*([+-]?\d{1,3}\.?\d{0,8})[°\s]*([EW])?',
                'priority': 9,
                'type': 'lat_lon'
            },
            
            # Degree-minute-second format with direction indicators
            {
                'pattern': r'([NS])\s*(\d{1,2})[°\s]+(\d{1,2})[\'′\s]+(\d{1,2}(?:\.\d+)?)[\"″\s]*,?\s*([EW])\s*(\d{1,3})[°\s]+(\d{1,2})[\'′\s]+(\d{1,2}(?:\.\d+)?)[\"″\s]*',
                'priority': 8,
                'type': 'dms_dir_first'
            },
            {
                'pattern': r'(\d{1,2})[°\s]+(\d{1,2})[\'′\s]+(\d{1,2}(?:\.\d+)?)[\"″\s]*([NS])\s*,?\s*(\d{1,3})[°\s]+(\d{1,2})[\'′\s]+(\d{1,2}(?:\.\d+)?)[\"″\s]*([EW])',
                'priority': 8,
                'type': 'dms_dir_last'
            },
            
            # Degree-decimal minute format
            {
                'pattern': r'([NS])\s*(\d{1,2})[°\s]+(\d{1,2}\.?\d*)[\'′\s]*,?\s*([EW])\s*(\d{1,3})[°\s]+(\d{1,2}\.?\d*)[\'′\s]*',
                'priority': 7,
                'type': 'dm_dir_first'
            },
            {
                'pattern': r'(\d{1,2})[°\s]+(\d{1,2}\.?\d*)[\'′\s]*([NS])\s*,?\s*(\d{1,3})[°\s]+(\d{1,2}\.?\d*)[\'′\s]*([EW])',
                'priority': 7,
                'type': 'dm_dir_last'
            },
            
            # Decimal degrees with direction indicators
            {
                'pattern': r'([NS])\s*([+-]?\d{1,2}\.?\d{0,8})[°\s]*,?\s*([EW])\s*([+-]?\d{1,3}\.?\d{0,8})[°\s]*',
                'priority': 6,
                'type': 'decimal_dir_separate'
            },
            {
                'pattern': r'([+-]?\d{1,2}\.?\d{0,8})[°\s]*([NS])\s*,?\s*([+-]?\d{1,3}\.?\d{0,8})[°\s]*([EW])',
                'priority': 6,
                'type': 'decimal_dir_attached'
            },
            
            # Pure decimal degrees (lowest priority, needs validation)
            {
                'pattern': r'([+-]?\d{1,2}\.\d{4,8})[°\s]*,?\s*([+-]?\d{1,3}\.\d{4,8})[°\s]*',
                'priority': 3,
                'type': 'pure_decimal'
            }
        ]
        
        # Exclusion patterns to avoid false positives
        self.exclusion_patterns = [
            r'\d{1,2}:\d{2}:\d{2}',  # Time format (HH:MM:SS)
            r'\d{1,2}:\d{2}\s*(?:AM|PM)',  # 12-hour time
            r'\d{2,4}-\d{1,2}-\d{1,2}',  # Date format
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # Date format
            r'[\d.]+\s*(?:KB|MB|GB|TB)',  # File sizes
            r'\$[\d.]+',  # Currency
            r'[\d.]+\s*(?:MM|CM|M|KM|IN|FT)',  # Measurements
            r'[\d.]+\s*(?:%|PERCENT)',  # Percentages
            r'[\d.]+\s*(?:V|VOLT|A|AMP)',  # Electrical measurements
            r'ISO\s*\d+',  # ISO values
            r'F/\d+',  # F-stop values
            r'\d+\s*(?:MP|MEGAPIXEL)',  # Camera specs
            r'[\d.]+\s*(?:°C|°F|CELSIUS|FAHRENHEIT)',  # Temperature
            r'SERIAL\s*[:#]?\s*[\w\d]+',  # Serial numbers
            r'MODEL\s*[:#]?\s*[\w\d]+',  # Model numbers
        ]
    
    def is_false_positive(self, text: str) -> bool:
        """Check if text matches exclusion patterns"""
        text_upper = text.upper().strip()
        
        for pattern in self.exclusion_patterns:
            if re.search(pattern, text_upper):
                return True
        
        return False
    
    def validate_gps_coordinates(self, lat: float, lon: float, source_text: str) -> bool:
        """Validate GPS coordinates for reasonableness"""
        # Basic range check
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return False
        
        # Check for obvious false positives
        if self.is_false_positive(source_text):
            return False
        
        # Reject coordinates that are too simple (like 1.0, 2.0)
        if abs(lat - round(lat)) == 0 and abs(lon - round(lon)) == 0 and abs(lat) < 10 and abs(lon) < 10:
            return False
        
        # Reject coordinates at exactly 0,0 (Gulf of Guinea - often a default value)
        if lat == 0 and lon == 0:
            return False
        
        # For pure decimal coordinates, require reasonable precision
        lat_str = str(abs(lat))
        lon_str = str(abs(lon))
        if '.' in lat_str and '.' in lon_str:
            lat_decimals = len(lat_str.split('.')[1])
            lon_decimals = len(lon_str.split('.')[1])
            # Require at least 3 decimal places for high confidence
            if lat_decimals < 3 or lon_decimals < 3:
                if not any(indicator in source_text.upper() for indicator in ['N', 'S', 'E', 'W', 'GPS', 'LAT', 'LON']):
                    return False
        
        return True
    
    def extract_gps_coordinates(self, text_list: List[str]) -> Optional[Dict[str, Any]]:
        """Extract GPS coordinates from a list of text strings with improved accuracy"""
        # Combine all text and clean it
        combined_text = ' '.join(text_list)
        
        # Remove common noise patterns that might interfere
        cleaned_text = re.sub(r'\b(?:EXIF|CAMERA|PHOTO|IMAGE)\b', '', combined_text, flags=re.IGNORECASE)
        
        candidates = []
        
        # Try each pattern in priority order
        for pattern_info in sorted(self.gps_patterns, key=lambda x: x['priority'], reverse=True):
            pattern = pattern_info['pattern']
            matches = re.finditer(pattern, combined_text, re.IGNORECASE)
            
            for match in matches:
                result = self._parse_match(match, pattern_info)
                if result and self.validate_gps_coordinates(
                    result['latitude'], 
                    result['longitude'], 
                    result['source_text']
                ):
                    candidates.append({
                        **result,
                        'priority': pattern_info['priority'],
                        'type': pattern_info['type']
                    })
        
        # Return the highest priority valid match
        if candidates:
            best_candidate = max(candidates, key=lambda x: x['priority'])
            # Remove priority and type from final result
            return {
                'latitude': best_candidate['latitude'],
                'longitude': best_candidate['longitude'],
                'source_text': best_candidate['source_text'],
                'extraction_confidence': self._calculate_confidence(best_candidate)
            }
        
        return None
    
    def _calculate_confidence(self, candidate: Dict[str, Any]) -> str:
        """Calculate confidence level based on pattern type and validation"""
        priority = candidate['priority']
        pattern_type = candidate['type']
        
        if priority >= 9:
            return "HIGH"
        elif priority >= 7:
            return "MEDIUM-HIGH"
        elif priority >= 5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _parse_match(self, match, pattern_info) -> Optional[Dict[str, Any]]:
        """Parse a regex match into GPS coordinates based on pattern type"""
        groups = match.groups()
        pattern_type = pattern_info['type']
        
        try:
            if pattern_type == 'labeled':
                # GPS: lat, lon or similar
                lat, lon = float(groups[0]), float(groups[1])
                
            elif pattern_type == 'lat_lon':
                # LAT: lat N, LON: lon E
                lat = float(groups[0])
                lat_dir = groups[1] if len(groups) > 1 and groups[1] else None
                lon = float(groups[2])
                lon_dir = groups[3] if len(groups) > 3 and groups[3] else None
                
                if lat_dir == 'S' or (lat_dir is None and lat > 0 and 'S' in match.group().upper()):
                    lat = -lat
                if lon_dir == 'W' or (lon_dir is None and lon > 0 and 'W' in match.group().upper()):
                    lon = -lon
                    
            elif pattern_type == 'dms_dir_first':
                # N DD MM SS.ss, E DDD MM SS.ss
                lat = self._dms_to_decimal(float(groups[1]), float(groups[2]), float(groups[3]))
                if groups[0] == 'S': lat = -lat
                lon = self._dms_to_decimal(float(groups[5]), float(groups[6]), float(groups[7]))
                if groups[4] == 'W': lon = -lon
                
            elif pattern_type == 'dms_dir_last':
                # DD MM SS.ss N, DDD MM SS.ss E
                lat = self._dms_to_decimal(float(groups[0]), float(groups[1]), float(groups[2]))
                if groups[3] == 'S': lat = -lat
                lon = self._dms_to_decimal(float(groups[4]), float(groups[5]), float(groups[6]))
                if groups[7] == 'W': lon = -lon
                
            elif pattern_type in ['dm_dir_first', 'dm_dir_last']:
                # Degree-decimal minute formats
                if pattern_type == 'dm_dir_first':
                    lat = self._dm_to_decimal(float(groups[1]), float(groups[2]))
                    if groups[0] == 'S': lat = -lat
                    lon = self._dm_to_decimal(float(groups[4]), float(groups[5]))
                    if groups[3] == 'W': lon = -lon
                else:
                    lat = self._dm_to_decimal(float(groups[0]), float(groups[1]))
                    if groups[2] == 'S': lat = -lat
                    lon = self._dm_to_decimal(float(groups[3]), float(groups[4]))
                    if groups[5] == 'W': lon = -lon
                    
            elif pattern_type in ['decimal_dir_separate', 'decimal_dir_attached']:
                # Decimal degrees with direction
                if pattern_type == 'decimal_dir_separate':
                    lat = float(groups[1])
                    if groups[0] == 'S': lat = -lat
                    lon = float(groups[3])
                    if groups[2] == 'W': lon = -lon
                else:
                    lat = float(groups[0])
                    if groups[1] == 'S': lat = -lat
                    lon = float(groups[2])
                    if groups[3] == 'W': lon = -lon
                    
            elif pattern_type == 'pure_decimal':
                # Pure decimal coordinates - requires extra validation
                lat, lon = float(groups[0]), float(groups[1])
                
            else:
                return None
            
            return {
                'latitude': lat,
                'longitude': lon,
                'source_text': match.group(0).strip()
            }
                
        except (ValueError, IndexError):
            return None
    
    def _dms_to_decimal(self, degrees: float, minutes: float, seconds: float) -> float:
        """Convert degrees, minutes, seconds to decimal degrees"""
        return degrees + minutes/60 + seconds/3600
    
    def _dm_to_decimal(self, degrees: float, minutes: float) -> float:
        """Convert degrees, decimal minutes to decimal degrees"""
        return degrees + minutes/60
    
    def decimal_to_exif_gps(self, lat: float, lon: float) -> Dict[str, Any]:
        """Convert decimal GPS coordinates to EXIF GPS format"""
        
        def decimal_to_dms(decimal_deg: float) -> Tuple[int, int, float]:
            """Convert decimal degrees to degrees, minutes, seconds"""
            decimal_deg = abs(decimal_deg)
            degrees = int(decimal_deg)
            minutes_float = (decimal_deg - degrees) * 60
            minutes = int(minutes_float)
            seconds = (minutes_float - minutes) * 60
            return degrees, minutes, seconds
        
        def float_to_rational(f: float) -> Tuple[int, int]:
            """Convert float to rational number (numerator, denominator)"""
            if f == int(f):
                return int(f), 1
            else:
                # Use high precision for seconds
                precision = 1000000
                return int(f * precision), precision
        
        lat_deg, lat_min, lat_sec = decimal_to_dms(lat)
        lon_deg, lon_min, lon_sec = decimal_to_dms(lon)
        
        gps_data = {
            piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
            piexif.GPSIFD.GPSLatitude: [
                (lat_deg, 1),
                (lat_min, 1),
                float_to_rational(lat_sec)
            ],
            piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
            piexif.GPSIFD.GPSLongitude: [
                (lon_deg, 1),
                (lon_min, 1),
                float_to_rational(lon_sec)
            ],
            piexif.GPSIFD.GPSMapDatum: 'WGS-84',
            piexif.GPSIFD.GPSVersionID: (2, 2, 0, 0)
        }
        
        return gps_data

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
        self.gps_extractor = GPSExtractor()
        
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
                        'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'gps_coordinates': None,
                        'all_detected_text': []
                    }
                    
                    extracted_texts = []
                    
                    if result:
                        for detection in result:
                            box = detection[0]  # Coordinates (4 points)
                            text = detection[1]  # Text
                            confidence = detection[2]  # Confidence
                            
                            extracted_texts.append(text)
                            formatted_result['all_detected_text'].append(text)
                            
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
                    
                    # Extract GPS coordinates from all detected text
                    if extracted_texts:
                        gps_coords = self.gps_extractor.extract_gps_coordinates(extracted_texts)
                        if gps_coords:
                            formatted_result['gps_coordinates'] = gps_coords
                    
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
        self.gps_extractor = GPSExtractor()
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("LIGER - Layer-based Image GPS Extraction and Recognition (Enhanced)")
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
        self.statusBar().showMessage("Ready - Enhanced GPS extraction with reduced false positives")
        
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
        
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        export_layout.addWidget(self.export_btn)
        
        # Save Images with GPS
        self.save_images_btn = QPushButton("Save Images with GPS Data")
        self.save_images_btn.clicked.connect(self.save_images_with_gps)
        self.save_images_btn.setEnabled(False)
        export_layout.addWidget(self.save_images_btn)
        
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
        self.save_images_btn.setEnabled(True)
        
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
            text_output += "❌ No GPS coordinates detected in text\n\n"
        
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
                exif_dict['0th'][piexif.ImageIFD.Software] = "GPS OCR Extractor"
                
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
                    exif_dict['0th'][piexif.ImageIFD.Software] = "GPS OCR Extractor"
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